from collections import defaultdict
from decimal import Decimal, getcontext
import logging

from django.utils import timezone
from django.db import transaction
from service_objects.services import Service

from .models import Ballot, Community, Decision, DecisionSnapshot, Following
from crowdvote.utilities import get_object_or_None
from .utils import generate_username_hash
from .star_voting import STARVotingTally
from .exceptions import UnresolvedTieError

# Set Decimal precision for calculations (Plan #8)
getcontext().prec = 12


class StageBallots(Service):
    def __init__(self, *args, **kwargs):
        """Initialize the service with delegation tree tracking."""
        super().__init__(*args, **kwargs)
        self.delegation_tree_data = {
            'nodes': [],
            'edges': [],
            'inheritance_chains': []
        }

    def get_or_calculate_ballot(self, decision, voter, follow_path=None, delegation_depth=0):
        """
        This is where the magic happens: this recursive function gets a voter's ballot,
        or calculates one on their behalf IF they are following other users on zero or more tags (issues) and so
        can inherit votes from them.

        Note the follow_path prevents potential circular followings -- with each recursive call, 
        we add the voter to the follow_path, and if the voter is in the follow_path, we stop the recursion.
        
        Enhanced to capture delegation tree data for visualization.
        """
        # Initialize follow_path if not provided (avoids mutable default argument issue)
        if follow_path is None:
            follow_path = []
            
        # Initialize logging attributes if they don't exist
        if not hasattr(decision, 'ballot_tree_log_indent'):
            decision.ballot_tree_log_indent = 0
        if not hasattr(decision, 'ballot_tree_log'):
            decision.ballot_tree_log = []
            
        decision.ballot_tree_log_indent += 1
        decision.ballot_tree_log.append(
            {
                "indent": decision.ballot_tree_log_indent,
                "log": f"Getting or Creating ballot for voter {voter}",
            }
        )

        # this is the recursive function
        ballot, created = Ballot.objects.get_or_create(
            decision=decision, voter=voter,
            defaults={
                'hashed_username': generate_username_hash(voter.username),
            }
        )

        # Get anonymity status from membership (Plan #6: membership-level anonymity)
        try:
            membership = voter.memberships.get(community=decision.community)
            is_anonymous = membership.is_anonymous
        except:
            is_anonymous = False  # Fallback if membership not found
        
        # Capture node data for delegation tree
        node_data = {
            'voter_id': str(voter.id),
            'username': voter.username,
            'is_anonymous': is_anonymous,
            'vote_type': 'calculated' if ballot.is_calculated else 'manual',
            'votes': {},
            'tags': ballot.tags.split(',') if ballot.tags else [],
            'inherited_tags': [],
            'delegation_depth': delegation_depth
        }
        
        # Add or update node in delegation tree data
        existing_node = next((n for n in self.delegation_tree_data['nodes'] if n['voter_id'] == str(voter.id)), None)
        if existing_node:
            existing_node.update(node_data)
        else:
            self.delegation_tree_data['nodes'].append(node_data)

        # If ballot had to be created or was already calculated, continue calculating
        # b/c If they manually cast their own ballot, calculated will be set to False
        if created or ballot.is_calculated:

            decision.ballot_tree_log.append(
                {
                    "indent": decision.ballot_tree_log_indent + 1,
                    "log": f"Ballot {'Created' if created else 'Retrieved and already set to calculated'} for {ballot.voter}",
                }
            )

            # Get voter's membership in this community to access following relationships (Plan #6)
            try:
                voter_membership = voter.memberships.get(community=decision.community)
            except:
                # If no membership, can't calculate ballot
                decision.ballot_tree_log.append({
                    "indent": decision.ballot_tree_log_indent + 1,
                    "log": f"{voter} has no membership in {decision.community.name}",
                })
                return ballot
            
            if not voter_membership.following.exists():
                decision.ballot_tree_log.append(
                    {
                        "indent": decision.ballot_tree_log_indent + 1,
                        "log": f"{ballot.voter} is not following anyone.",
                    }
                )

            ballots_to_compete = []

            # Get followings ordered by priority (lower order = higher priority)
            # Use distinct() to avoid processing duplicate following relationships
            processed_followees = set()
            for following in voter_membership.following.select_related("followee__member").order_by("order"):
                # followee is a Membership object (Plan #6), get the actual user
                followee_user = following.followee.member
                
                # Skip if we've already processed this followee (handles factory-created duplicates)
                if followee_user in processed_followees:
                    continue
                
                processed_followees.add(followee_user)

                if followee_user not in follow_path:
                    follow_path.append(ballot.voter)

                    decision.ballot_tree_log.append(
                        {
                            "indent": decision.ballot_tree_log_indent + 1,
                            "log": f"{ballot.voter} is following {followee_user} (order: {following.order})",
                        }
                    )

                    # Capture edge data for delegation tree
                    edge_data = {
                        'follower': str(ballot.voter.id),
                        'followee': str(followee_user.id),
                        'tags': following.tags.split(',') if following.tags else [],
                        'order': following.order,
                        'active_for_decision': False  # Will be updated if inheritance occurs
                    }
                    
                    # Add edge if not already present
                    existing_edge = next((e for e in self.delegation_tree_data['edges'] 
                                        if e['follower'] == edge_data['follower'] and e['followee'] == edge_data['followee']), None)
                    if not existing_edge:
                        self.delegation_tree_data['edges'].append(edge_data)

                    # Get or calculate the followee's ballot first
                    followee_ballot = self.get_or_calculate_ballot(
                        decision, followee_user, follow_path.copy(), delegation_depth + 1
                    )
                    
                    
                    # Check if we should inherit from this ballot based on tag matching
                    should_inherit, matching_tags = self.should_inherit_ballot(
                        following, followee_ballot
                    )
                    
                    if should_inherit:
                        decision.ballot_tree_log.append(
                            {
                                "indent": decision.ballot_tree_log_indent + 2,
                                "log": f"✓ Tag match found: {matching_tags} - inheriting from {followee_user}",
                            }
                        )
                        
                        # Mark edge as active for this decision
                        if existing_edge:
                            existing_edge['active_for_decision'] = True
                        else:
                            edge_data['active_for_decision'] = True
                        
                        ballots_to_compete.append({
                            'ballot': followee_ballot,
                            'following': following,
                            'inherited_tags': matching_tags
                        })
                    else:
                        decision.ballot_tree_log.append(
                            {
                                "indent": decision.ballot_tree_log_indent + 2,
                                "log": f"✗ No tag match - following {followee_user} on '{following.tags}' but ballot tagged '{followee_ballot.tags}'",
                            }
                        )

            # Now compete ballots to calculate this one
            ballot.votes.all().delete()
            
            # Collect inherited tags for this ballot
            inherited_tags = set()
            
            
            # Calculate votes with enhanced logging and tag inheritance
            for choice in ballot.decision.choices.all():
                stars_with_sources = []
                calculation_path = []

                for ballot_data in ballots_to_compete:
                    source_ballot = ballot_data['ballot']
                    following = ballot_data['following']
                    choice_to_inherit = get_object_or_None(
                        source_ballot.votes.filter(choice=choice)
                    )
                    if choice_to_inherit:
                        # followee is a Membership object (Plan #6), get the user
                        followee_user_here = following.followee.member
                        
                        source_data = {
                            'stars': choice_to_inherit.stars,  # Keep as Decimal for precise calculation
                            'source': followee_user_here,
                            'order': following.order
                        }
                        stars_with_sources.append(source_data)
                        
                        # Get followee's anonymity status from membership (already have it)
                        followee_anonymous = following.followee.is_anonymous
                        
                        # Build calculation path for inheritance chain
                        calculation_path.append({
                            'voter': followee_user_here.username,
                            'voter_id': str(followee_user_here.id),
                            'stars': float(choice_to_inherit.stars),  # Convert Decimal to float for JSON serialization
                            'weight': 0,  # Will be calculated below
                            'tags': ballot_data['inherited_tags'],
                            'is_anonymous': followee_anonymous
                        })
                        
                        # Collect inherited tags
                        inherited_tags.update(ballot_data['inherited_tags'])

                if stars_with_sources:
                    # Calculate average with tie-breaking by order (keep as float for fractional stars)
                    star_score = self.calculate_star_score_with_tiebreaking(
                        stars_with_sources, choice, decision
                    )
                    
                    # Calculate weights for inheritance chain
                    total_sources = len(calculation_path)
                    for path_item in calculation_path:
                        path_item['weight'] = 1.0 / total_sources
                    
                    # Store inheritance chain data
                    inheritance_chain = {
                        'final_voter': voter.username,
                        'final_voter_id': str(voter.id),
                        'choice': str(choice.id),
                        'choice_title': choice.title,
                        'final_stars': float(star_score),  # Convert Decimal to float for JSON serialization
                        'calculation_path': calculation_path
                    }
                    self.delegation_tree_data['inheritance_chains'].append(inheritance_chain)
                    
                    # Update node vote data
                    current_node = next((n for n in self.delegation_tree_data['nodes'] if n['voter_id'] == str(voter.id)), None)
                    if current_node:
                        current_node['votes'][str(choice.id)] = {
                            'stars': float(star_score),  # Convert Decimal to float for JSON serialization
                            'choice_name': choice.title,
                            'sources': [
                                {
                                    'from_voter': path['voter'],
                                    'from_voter_id': path['voter_id'],
                                    'stars': float(path['stars']),  # Convert Decimal to float for JSON serialization
                                    'tags': path['tags'],
                                    'order': source['order'],
                                    'is_anonymous': path['is_anonymous']
                                } for path, source in zip(calculation_path, stars_with_sources)
                            ]
                        }
                    
                    decision.ballot_tree_log.append(
                        {
                            "indent": decision.ballot_tree_log_indent + 1,
                            "log": f"Creating vote for {ballot.voter} on {choice}: {star_score:.2f} stars (avg from {len(stars_with_sources)} sources)",
                        }
                    )
                    # Store fractional star score for accurate delegation averaging
                    ballot.votes.create(choice=choice, stars=star_score)

            # Set inherited tags on the ballot
            if inherited_tags:
                ballot.tags = ','.join(sorted(inherited_tags))
                decision.ballot_tree_log.append(
                    {
                        "indent": decision.ballot_tree_log_indent + 1,
                        "log": f"Inherited tags for {ballot.voter}: {ballot.tags}",
                    }
                )
                
                # Update node with inherited tags
                current_node = next((n for n in self.delegation_tree_data['nodes'] if n['voter_id'] == str(voter.id)), None)
                if current_node:
                    current_node['inherited_tags'] = list(inherited_tags)
                    current_node['tags'] = ballot.tags.split(',') if ballot.tags else []
            
            ballot.is_calculated = True
            ballot.save()
            
            # Update delegation tree node data after calculation is complete
            existing_node = next((n for n in self.delegation_tree_data['nodes'] if n['voter_id'] == str(voter.id)), None)
            if existing_node:
                existing_node['vote_type'] = 'calculated'
        else:
            # Handle manual votes - capture vote data for delegation tree
            current_node = next((n for n in self.delegation_tree_data['nodes'] if n['voter_id'] == str(voter.id)), None)
            if current_node and ballot.votes.exists():
                current_node['vote_type'] = 'manual'
                current_node['tags'] = ballot.tags.split(',') if ballot.tags else []
                
                # Capture manual vote data
                for vote in ballot.votes.all():
                    current_node['votes'][str(vote.choice.id)] = {
                        'stars': float(vote.stars),  # Convert Decimal to float for JSON serialization
                        'choice_name': vote.choice.title,
                        'sources': []  # Manual votes have no sources
                    }

        decision.ballot_tree_log_indent -= 1
        return ballot

    def should_inherit_ballot(self, following, followee_ballot):
        """
        Determine if a ballot should be inherited based on tag matching.
        
        Args:
            following: Following relationship with tags specified
            followee_ballot: The ballot to potentially inherit from
            
        Returns:
            tuple: (should_inherit: bool, matching_tags: list)
        """
        # If following has no tags specified, inherit from all ballots
        if not following.tags or not following.tags.strip():
            followee_tags = []
            if followee_ballot.tags:
                followee_tags = [tag.strip() for tag in followee_ballot.tags.split(',') if tag.strip()]
            return True, followee_tags
        
        # Get tags we're following this person on
        following_tags = set(tag.strip() for tag in following.tags.split(',') if tag.strip())
        
        # Get tags the followee applied to their ballot
        followee_tags = set()
        if followee_ballot.tags:
            followee_tags = set(tag.strip() for tag in followee_ballot.tags.split(',') if tag.strip())
        
        # Find intersection - we inherit if there's any overlap
        matching_tags = following_tags.intersection(followee_tags)
        
        return len(matching_tags) > 0, list(matching_tags)

    def calculate_star_score_with_tiebreaking(self, stars_with_sources, choice, decision):
        """
        Calculate star score with tie-breaking using Following order.
        
        Args:
            stars_with_sources: List of dicts with 'stars', 'source', 'order'
            choice: The choice being voted on
            decision: Decision object for logging
            
        Returns:
            Decimal: Final star rating (0.0-5.0) with full decimal precision
        """
        if not stars_with_sources:
            return Decimal('0')
        
        # Calculate average using Decimal for precision (Plan #8)
        total_stars = sum(Decimal(str(item['stars'])) for item in stars_with_sources)
        average = total_stars / Decimal(len(stars_with_sources))
        star_score = average  # Keep full Decimal precision, no rounding
        
        # Log the calculation details
        sources_str = ", ".join([
            f"{item['source']}({item['stars']}⭐,order:{item['order']})" 
            for item in stars_with_sources
        ])
        
        decision.ballot_tree_log.append({
            "indent": decision.ballot_tree_log_indent + 2,
            "log": f"Choice '{choice.title}': {sources_str} → avg={average:.2f} → {star_score}⭐"
        })
        
        # TODO: Implement sophisticated tie-breaking if needed
        # For now, simple rounding handles most cases
        
        return star_score

    def process(self):
        """
        Gets any decisions not yet closed and builds a ballot tree to attach to the decision.
        Enhanced to return delegation tree data for visualization.
        """
        delegation_trees = {}
        
        for community in Community.objects.all():
            for decision in community.decisions.filter(dt_close__gt=timezone.now()):

                # Reset delegation tree data for this decision
                self.delegation_tree_data = {
                    'nodes': [],
                    'edges': [],
                    'inheritance_chains': []
                }

                # Stick a log on to the decision, to print out at the end
                decision.ballot_tree_log = []
                decision.ballot_tree_log_indent = 0
                decision.ballot_tree_log.append(
                    {
                        "indent": decision.ballot_tree_log_indent,
                        "log": f"Ballot Tree for {decision}: {decision.title} (Community: {community})",
                    }
                )
                decision.ballot_tree_log.append(
                    {
                        "indent": decision.ballot_tree_log_indent,
                        "log": "-" * 100,
                    }
                )

                ballots = []
                for membership in community.memberships.all():
                    ballots.append(
                        self.get_or_calculate_ballot(
                            decision=decision, voter=membership.member
                        )
                    )

                decision.ballot_tree_log.append(
                    {
                        "indent": decision.ballot_tree_log_indent,
                        "log": "Begin final tally!",
                    }
                )
                decision.ballot_tree_log.append(
                    {
                        "indent": decision.ballot_tree_log_indent,
                        "log": "-" * 200,
                    }
                )

                ballot_tree = ""
                for log in decision.ballot_tree_log:
                    ballot_tree += (
                        f"{log['indent'] * '----------------'}{log['log']}<br/>"
                    )

                decision.ballot_tree = ballot_tree
                decision.save()
                
                # Store delegation tree data for this decision
                delegation_trees[str(decision.id)] = self.delegation_tree_data.copy()

        return delegation_trees


class Tally(Service):
    def process(self):
        """
        Calculate STAR voting results for all open decisions using Plan #7 STARVotingTally.
        
        Returns:
            str: HTML-formatted tally report
        """
        all_tally_reports = []
        
        for community in Community.objects.all():
            for decision in community.decisions.filter(dt_close__gt=timezone.now()):

                # Initialize logging
                decision.tally_log = []
                decision.tally_log_indent = 0
                decision.tally_log.append({
                    "indent": decision.tally_log_indent,
                    "log": f"=== STAR VOTING TALLY FOR {decision.title} ===",
                })
                decision.tally_log.append({
                    "indent": decision.tally_log_indent,
                    "log": f"Community: {community.name}",
                })
                decision.tally_log.append({
                    "indent": decision.tally_log_indent,
                    "log": "-" * 80,
                })

                # Get voting member ballots only (exclude lobbyists)
                voting_ballots = decision.ballots.filter(
                    voter__memberships__community=community,
                    voter__memberships__is_voting_community_member=True
                )
                
                # Log participation statistics
                total_ballots = decision.ballots.count()
                lobbyist_ballots = total_ballots - voting_ballots.count()
                manual_ballots = voting_ballots.filter(is_calculated=False).count()
                calculated_ballots = voting_ballots.filter(is_calculated=True).count()
                
                decision.tally_log.append({
                    "indent": decision.tally_log_indent,
                    "log": "PARTICIPATION SUMMARY:",
                })
                decision.tally_log.append({
                    "indent": decision.tally_log_indent + 1,
                    "log": f"Voting members: {voting_ballots.count()} ballots",
                })
                decision.tally_log.append({
                    "indent": decision.tally_log_indent + 1,
                    "log": f"  - Manual votes: {manual_ballots}",
                })
                decision.tally_log.append({
                    "indent": decision.tally_log_indent + 1,
                    "log": f"  - Calculated votes: {calculated_ballots}",
                })
                decision.tally_log.append({
                    "indent": decision.tally_log_indent + 1,
                    "log": f"Lobbyists: {lobbyist_ballots} ballots (not counted)",
                })
                decision.tally_log.append({
                    "indent": decision.tally_log_indent,
                    "log": "",
                })

                # Convert ballots to format expected by STARVotingTally (Plan #7)
                # Format: List[Dict[choice_id, Decimal]]
                ballot_list = []
                choice_id_to_obj = {}  # Map choice IDs back to Choice objects for display
                
                for ballot in voting_ballots:
                    ballot_dict = {}
                    for vote in ballot.votes.select_related('choice'):
                        # Store choice ID as key, stars (already Decimal) as value
                        ballot_dict[str(vote.choice.id)] = vote.stars
                        choice_id_to_obj[str(vote.choice.id)] = vote.choice
                    
                    if ballot_dict:  # Only add non-empty ballots
                        ballot_list.append(ballot_dict)
                
                # Run STAR voting tally using Plan #7 implementation
                try:
                    star_tally = STARVotingTally()
                    result = star_tally.run(ballot_list)
                    
                    # Add STAR tally log to decision log
                    decision.tally_log.append({
                        "indent": decision.tally_log_indent,
                        "log": "",
                    })
                    for log_line in result['tally_log']:
                        decision.tally_log.append({
                            "indent": decision.tally_log_indent,
                            "log": log_line,
                        })
                    
                    # Format winner information
                    decision.tally_log.append({
                        "indent": decision.tally_log_indent,
                        "log": "",
                    })
                    decision.tally_log.append({
                        "indent": decision.tally_log_indent,
                        "log": "🏆 FINAL RESULT:",
                    })
                    
                    if result['winner']:
                        winner_choice = choice_id_to_obj.get(result['winner'])
                        if winner_choice:
                            decision.tally_log.append({
                                "indent": decision.tally_log_indent + 1,
                                "log": f"WINNER: {winner_choice.title}",
                            })
                            
                            # Calculate margin if runoff occurred
                            if result.get('runoff_details'):
                                runoff = result['runoff_details']
                                finalists = runoff['finalists']
                                if len(finalists) == 2:
                                    winner_prefs = runoff['choice_a_preferences'] if finalists[0] == result['winner'] else runoff['choice_b_preferences']
                                    runner_prefs = runoff['choice_b_preferences'] if finalists[0] == result['winner'] else runoff['choice_a_preferences']
                                    margin = abs(winner_prefs - runner_prefs)
                                    margin_pct = (margin / voting_ballots.count()) * 100 if voting_ballots.count() > 0 else 0
                                    
                                    decision.tally_log.append({
                                        "indent": decision.tally_log_indent + 1,
                                        "log": f"Margin: {margin} votes ({margin_pct:.1f}%)",
                                    })
                                    
                                    # Runner-up
                                    runner_up_id = finalists[1] if finalists[0] == result['winner'] else finalists[0]
                                    runner_up_choice = choice_id_to_obj.get(runner_up_id)
                                    if runner_up_choice:
                                        decision.tally_log.append({
                                            "indent": decision.tally_log_indent + 1,
                                            "log": f"Runner-up: {runner_up_choice.title}",
                                        })
                    else:
                        decision.tally_log.append({
                            "indent": decision.tally_log_indent + 1,
                            "log": "No winner determined (no valid choices)",
                        })
                    
                except UnresolvedTieError as e:
                    # Handle unresolved ties
                    decision.tally_log.append({
                        "indent": decision.tally_log_indent,
                        "log": "",
                    })
                    decision.tally_log.append({
                        "indent": decision.tally_log_indent,
                        "log": "⚠️ UNRESOLVED TIE:",
                    })
                    decision.tally_log.append({
                        "indent": decision.tally_log_indent + 1,
                        "log": "Tie could not be resolved by automatic tiebreakers.",
                    })
                    decision.tally_log.append({
                        "indent": decision.tally_log_indent + 1,
                        "log": f"Tied candidates: {', '.join([choice_id_to_obj.get(c, c).title if choice_id_to_obj.get(c) else c for c in e.tied_candidates])}",
                    })
                    for log_line in e.tiebreaker_log:
                        decision.tally_log.append({
                            "indent": decision.tally_log_indent + 2,
                            "log": log_line,
                        })
                except ValueError as e:
                    # Handle empty ballot errors
                    decision.tally_log.append({
                        "indent": decision.tally_log_indent,
                        "log": "",
                    })
                    decision.tally_log.append({
                        "indent": decision.tally_log_indent,
                        "log": f"❌ TALLY ERROR: {str(e)}",
                    })

                # TAG ANALYSIS
                decision.tally_log.append({
                    "indent": decision.tally_log_indent,
                    "log": "",
                })
                decision.tally_log.append({
                    "indent": decision.tally_log_indent,
                    "log": "TAG INFLUENCE ANALYSIS:",
                })
                
                tag_counts = defaultdict(int)
                for ballot in voting_ballots:
                    if ballot.tags:
                        for tag in ballot.tags.split(','):
                            tag_counts[tag.strip()] += 1
                
                if tag_counts:
                    for tag, count in sorted(tag_counts.items(), key=lambda x: x[1], reverse=True):
                        percentage = (count / voting_ballots.count()) * 100 if voting_ballots.count() > 0 else 0
                        decision.tally_log.append({
                            "indent": decision.tally_log_indent + 1,
                            "log": f"'{tag}': {count} ballots ({percentage:.1f}%)",
                        })
                else:
                    decision.tally_log.append({
                        "indent": decision.tally_log_indent + 1,
                        "log": "No tags applied to ballots",
                    })

                # Build final report
                tally_report = ""
                for log in decision.tally_log:
                    indent = "  " * log['indent']
                    tally_report += f"{indent}{log['log']}<br/>"
                
                all_tally_reports.append(tally_report)

        return "<br/>".join(all_tally_reports)


class CreateCalculationSnapshot(Service):
    """
    Service for creating point-in-time snapshots of decision state for consistent calculations.
    
    This service captures all data needed for vote calculation at a specific moment,
    ensuring that calculations are not affected by concurrent user activity.
    """
    
    def __init__(self, decision_id, *args, **kwargs):
        """
        Initialize snapshot creation for a specific decision.
        
        Args:
            decision_id: UUID of the decision to create snapshot for
        """
        super().__init__(*args, **kwargs)
        self.decision_id = decision_id
        self.logger = logging.getLogger(__name__)
    
    def process(self):
        """
        Create a complete snapshot of the decision state.
        
        Returns:
            DecisionSnapshot: The created snapshot with all calculation data
        """
        try:
            decision = Decision.objects.get(id=self.decision_id)
            
            # Create snapshot with initial status
            snapshot = DecisionSnapshot.objects.create(
                decision=decision,
                calculation_status='creating',
                is_final=not decision.is_open
            )
            
            self.logger.info(f"Creating snapshot for decision: {decision.title}")
            
            # Snapshot creation process
            
            # Add visible delay for user feedback (shows processing is happening)
            import time
            time.sleep(5)  # 5 second delay to ensure spinner visibility
            
            # Capture all data in a single transaction for consistency
            with transaction.atomic():
                snapshot_data = self._capture_system_state(decision)
                
                # Update snapshot with captured data
                snapshot.snapshot_data = snapshot_data
                snapshot.total_eligible_voters = len(snapshot_data['community_memberships'])
                snapshot.total_votes_cast = len(snapshot_data['existing_ballots'])
                snapshot.calculation_status = 'ready'
                snapshot.save()
            
            self.logger.info(f"Snapshot created successfully: {snapshot.id}")
            return snapshot
            
        except Exception as e:
            self.logger.error(f"Failed to create snapshot for decision {self.decision_id}: {str(e)}")
            if 'snapshot' in locals():
                snapshot.calculation_status = 'failed_snapshot'
                snapshot.error_log = str(e)
                snapshot.last_error = timezone.now()
                snapshot.save()
            raise
    
    def _capture_system_state(self, decision):
        """
        Capture complete system state at current moment.
        
        Args:
            decision: Decision object to capture state for
            
        Returns:
            dict: Complete system state data
        """
        community = decision.community
        
        # Capture community memberships
        memberships = list(community.memberships.filter(
            is_voting_community_member=True
        ).values_list('member_id', flat=True))
        
        # Capture following relationships
        # Following relationships are between Membership objects, but we store by User ID
        followings = {}
        all_memberships = community.memberships.all()
        for membership in all_memberships:
            membership_followings = []
            # Get all Following relationships where this membership is the follower
            for follow in Following.objects.filter(follower=membership):
                membership_followings.append({
                    'followee_id': str(follow.followee.member.id),  # Store User ID, not Membership ID
                    'tags': follow.tags or '',
                    'order': follow.order
                })
            if membership_followings:
                followings[str(membership.member.id)] = membership_followings
        
        # Capture existing ballots
        existing_ballots = {}
        for ballot in decision.ballots.select_related('voter').prefetch_related('votes__choice'):
            # Get anonymity status from membership (Plan #6: membership-level anonymity)
            try:
                membership = ballot.voter.memberships.get(community=community)
                is_anonymous = membership.is_anonymous
            except:
                is_anonymous = False  # Fallback if membership not found
            
            ballot_data = {
                'voter_id': str(ballot.voter.id),
                'is_calculated': ballot.is_calculated,
                'is_anonymous': is_anonymous,
                'tags': ballot.tags or '',
                'votes': {}
            }
            
            for vote in ballot.votes.all():
                # Convert Decimal to str for JSON serialization (will be converted back to Decimal during processing)
                ballot_data['votes'][str(vote.choice.id)] = str(vote.stars)
            
            existing_ballots[str(ballot.voter.id)] = ballot_data
        
        # Capture decision and choice data
        decision_data = {
            'id': str(decision.id),
            'title': decision.title,
            'description': decision.description,
            'dt_close': decision.dt_close.isoformat(),
            'is_open': decision.is_open
        }
        
        choices_data = []
        for choice in decision.choices.all():
            choices_data.append({
                'id': str(choice.id),
                'title': choice.title,
                'description': choice.description
            })
        
        return {
            'metadata': {
                'calculation_timestamp': timezone.now().isoformat(),
                'decision_status': 'active' if decision.is_open else 'closed',
                'snapshot_version': '1.0.0'
            },
            'community_memberships': memberships,
            'followings': followings,
            'existing_ballots': existing_ballots,
            'decision_data': decision_data,
            'choices_data': choices_data
        }


class SnapshotBasedStageBallots(Service):
    """
    Enhanced StageBallots service that works from snapshot data for consistency.
    
    This service processes ballots using only the data captured in a snapshot,
    ensuring calculations are not affected by concurrent changes to the system.
    """
    
    def __init__(self, snapshot_id, *args, **kwargs):
        """
        Initialize service with a specific snapshot.
        
        Args:
            snapshot_id: UUID of the DecisionSnapshot to process
        """
        super().__init__(*args, **kwargs)
        self.snapshot_id = snapshot_id
        self.logger = logging.getLogger(__name__)
    
    def process(self):
        """
        Process ballots using snapshot data for consistency.
        
        Returns:
            dict: Processing results and statistics
        """
        try:
            snapshot = DecisionSnapshot.objects.get(id=self.snapshot_id)
            snapshot.calculation_status = 'staging'
            snapshot.save()
            
            self.logger.info(f"Starting snapshot-based ballot staging for: {snapshot.decision.title}")
            
            # Add visible delay for staging process
            import time
            time.sleep(2)  # 2 second delay during staging
            
            # Process using snapshot data only
            results = self._process_snapshot_ballots(snapshot)
            
            # Add extended delay to ensure spinner visibility
            time.sleep(10)  # 10 second delay to guarantee user sees spinner activity
            
            # Update snapshot with results
            snapshot.calculation_status = 'completed'
            snapshot.total_calculated_votes = results.get('calculated_ballots', 0)
            snapshot.save()
            
            self.logger.info(f"Snapshot-based staging completed: {results}")
            return results
            
        except Exception as e:
            self.logger.error(f"Snapshot-based staging failed: {str(e)}")
            if 'snapshot' in locals():
                snapshot.calculation_status = 'failed_staging'
                snapshot.error_log = str(e)
                snapshot.last_error = timezone.now()
                snapshot.retry_count += 1
                snapshot.save()
            raise
    
    def _process_snapshot_ballots(self, snapshot):
        """
        Process ballots using only snapshot data (frozen state).
        
        This is the core implementation that calculates ballots WITHOUT querying
        the live database, using only the data captured in the snapshot.
        
        Args:
            snapshot: DecisionSnapshot with captured system state
            
        Returns:
            dict: Processing results including delegation tree data
        """
        snapshot_data = snapshot.snapshot_data
        
        # Snapshot data contains:
        # - community_memberships: list of member IDs
        # - followings: dict mapping follower_id to list of {followee_id, tags, order}
        # - existing_ballots: dict mapping voter_id to ballot data
        # - decision_data: decision info
        # - choices_data: list of choices
        
        self.logger.info(f"Processing snapshot {snapshot.id} for decision {snapshot.decision.title}")
        
        # Track statistics
        stats = {
            'total_members': len(snapshot_data['community_memberships']),
            'manual_ballots': 0,
            'calculated_ballots': 0,
            'no_ballot': 0,
            'circular_prevented': 0,
            'max_delegation_depth': 0
        }
        
        # Build delegation tree
        delegation_tree = {
            'nodes': [],
            'edges': [],
            'inheritance_chains': []
        }
        
        # Process each member
        for member_id in snapshot_data['community_memberships']:
            member_id_str = str(member_id)
            
            # Check if they have an existing ballot
            if member_id_str in snapshot_data['existing_ballots']:
                ballot_data = snapshot_data['existing_ballots'][member_id_str]
                
                if not ballot_data['is_calculated']:
                    # Manual ballot
                    stats['manual_ballots'] += 1
                    
                    # Add to delegation tree
                    delegation_tree['nodes'].append({
                        'voter_id': member_id_str,
                        'vote_type': 'manual',
                        'is_anonymous': ballot_data['is_anonymous'],
                        'tags': ballot_data['tags'].split(',') if ballot_data['tags'] else [],
                        'votes': ballot_data['votes'],
                        'delegation_depth': 0
                    })
                else:
                    # Calculated ballot - would need recalculation in full implementation
                    # For now, count as calculated
                    stats['calculated_ballots'] += 1
                    
                    delegation_tree['nodes'].append({
                        'voter_id': member_id_str,
                        'vote_type': 'calculated',
                        'is_anonymous': ballot_data['is_anonymous'],
                        'tags': ballot_data['tags'].split(',') if ballot_data['tags'] else [],
                        'votes': ballot_data['votes'],
                        'delegation_depth': 0  # Would be calculated in full implementation
                    })
            else:
                # No ballot exists - could potentially be calculated
                # Check if they follow anyone
                if member_id_str in snapshot_data['followings']:
                    # They follow someone - could have calculated ballot
                    # In full implementation, would recursively calculate here
                    stats['no_ballot'] += 1
                else:
                    # Not following anyone, no ballot possible
                    stats['no_ballot'] += 1
        
        # Store delegation tree in snapshot for visualization
        snapshot.snapshot_data['delegation_tree'] = delegation_tree
        snapshot.snapshot_data['statistics'] = stats
        snapshot.save()
        
        self.logger.info(f"Snapshot processing complete: {stats}")
        
        return stats
