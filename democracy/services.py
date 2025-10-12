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
    def __init__(self, snapshot_id=None):
        """
        Initialize Tally service.
        
        Args:
            snapshot_id: Optional UUID of DecisionSnapshot to tally from (Plan #9)
        """
        super().__init__()
        self.snapshot_id = snapshot_id
        self.logger = logging.getLogger(__name__)
    
    def process(self):
        """
        Calculate STAR voting results using Plan #7 STARVotingTally.
        
        If snapshot_id provided (Plan #9), tallies from frozen snapshot data.
        Otherwise, tallies all open decisions from live database.
        
        Returns:
            str: HTML-formatted tally report
        """
        # Plan #9: If snapshot provided, tally only that snapshot
        if self.snapshot_id:
            from democracy.models import DecisionSnapshot
            snapshot = DecisionSnapshot.objects.get(id=self.snapshot_id)
            return self._tally_snapshot(snapshot)
        
        # Original behavior: tally all open decisions
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
    
    def _tally_snapshot(self, snapshot):
        """
        Tally a specific snapshot using frozen data (Plan #9).
        
        Args:
            snapshot: DecisionSnapshot instance
            
        Returns:
            str: HTML-formatted tally report
        """
        from decimal import Decimal
        
        decision = snapshot.decision
        snapshot_data = snapshot.snapshot_data
        
        self.logger.info(f"Tallying snapshot {snapshot.id} for decision '{decision.title}'")
        
        # Extract ballot data from snapshot
        delegation_tree = snapshot_data.get('delegation_tree', {})
        nodes = delegation_tree.get('nodes', [])
        
        # Convert nodes to ballot format for STARVotingTally
        ballot_list = []
        choice_id_to_obj = {}
        
        for node in nodes:
            if node.get('vote_type') in ['manual', 'calculated'] and node.get('votes'):
                ballot_dict = {}
                for choice_id, vote_data in node['votes'].items():
                    # Convert stars back to Decimal
                    ballot_dict[str(choice_id)] = Decimal(str(vote_data.get('stars', 0)))
                    # Keep track of choice for display
                    if choice_id not in choice_id_to_obj:
                        try:
                            from democracy.models import Choice
                            choice_id_to_obj[str(choice_id)] = Choice.objects.get(id=choice_id)
                        except Choice.DoesNotExist:
                            pass
                
                if ballot_dict:
                    ballot_list.append(ballot_dict)
        
        self.logger.info(f"Extracted {len(ballot_list)} ballots from snapshot for tallying")
        
        # Run STAR voting tally
        try:
            star_tally = STARVotingTally()
            result = star_tally.run(ballot_list)
            
            # Update snapshot with results
            if result.get('winner'):
                winner_choice = choice_id_to_obj.get(result['winner'])
                snapshot.winner = winner_choice
            
            snapshot.tally_log = result.get('tally_log', [])
            
            # Only mark as final if decision is closed (model validation prevents final=True for open decisions)
            if not decision.is_open:
                snapshot.is_final = True
            
            snapshot.calculation_status = 'completed'
            snapshot.save()
            
            self.logger.info(f"Snapshot {snapshot.id} tally complete - winner: {snapshot.winner}, is_final: {snapshot.is_final}")
            
            return f"Tally complete for snapshot {snapshot.id}"
            
        except UnresolvedTieError as e:
            self.logger.warning(f"Unresolved tie in snapshot {snapshot.id}: {e.tied_candidates}")
            snapshot.tally_log = [f"Unresolved tie: {', '.join(e.tied_candidates)}"] + e.tiebreaker_log
            
            # Only mark as final if decision is closed
            if not decision.is_open:
                snapshot.is_final = True
            
            snapshot.calculation_status = 'completed'
            snapshot.save()
            return f"Tie detected in snapshot {snapshot.id}"
            
        except ValueError as e:
            self.logger.error(f"Tally error in snapshot {snapshot.id}: {str(e)}")
            snapshot.tally_log = [f"Error: {str(e)}"]
            snapshot.calculation_status = 'error'
            snapshot.save()
            return f"Error tallying snapshot {snapshot.id}: {str(e)}"


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
            
            # Process using snapshot data only
            results = self._process_snapshot_ballots(snapshot)
            
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
        
        This is the COMPLETE IMPLEMENTATION that calculates ballots recursively
        WITHOUT querying the live database, using only the data captured in the snapshot.
        
        Args:
            snapshot: DecisionSnapshot with captured system state
            
        Returns:
            dict: Processing results including delegation tree data
        """
        snapshot_data = snapshot.snapshot_data
        
        self.logger.info(f"Processing snapshot {snapshot.id} for decision {snapshot.decision.title}")
        
        # Track statistics
        self.stats = {
            'total_members': len(snapshot_data['community_memberships']),
            'manual_ballots': 0,
            'calculated_ballots': 0,
            'no_ballot': 0,
            'circular_prevented': 0,
            'max_delegation_depth': 0
        }
        
        # Build delegation tree
        self.delegation_tree = {
            'nodes': [],
            'edges': [],
            'inheritance_chains': [],
            'circular_prevented': []
        }
        
        # Cache for calculated ballots (voter_id -> ballot_dict)
        self.calculated_ballots_cache = {}
        
        # Get user lookup for display names
        from security.models import CustomUser
        user_ids = [member_id for member_id in snapshot_data['community_memberships']]
        users = CustomUser.objects.filter(id__in=user_ids)
        self.user_lookup = {str(user.id): user.username for user in users}
        
        # Process each member to calculate their ballot
        for member_id in snapshot_data['community_memberships']:
            member_id_str = str(member_id)
            
            # Calculate or retrieve ballot for this member
            ballot_result = self._calculate_ballot_from_snapshot(
                member_id_str, 
                snapshot_data, 
                follow_path=[], 
                delegation_depth=0
            )
            
            # ballot_result is dict with 'ballot', 'tags', 'type' keys or None
            if ballot_result is not None:
                if ballot_result['type'] == 'manual':
                    self.stats['manual_ballots'] += 1
                elif ballot_result['type'] == 'calculated':
                    self.stats['calculated_ballots'] += 1
            else:
                self.stats['no_ballot'] += 1
        
        # Store delegation tree in snapshot for visualization
        snapshot.snapshot_data['delegation_tree'] = self.delegation_tree
        snapshot.snapshot_data['statistics'] = self.stats
        snapshot.save()
        
        self.logger.info(f"Snapshot processing complete: {self.stats}")
        
        return self.stats
    
    def _calculate_ballot_from_snapshot(self, voter_id, snapshot_data, follow_path, delegation_depth):
        """
        Recursively calculate ballot for a voter using only snapshot data.
        
        This is the core recursive calculation engine that:
        - Works entirely from frozen snapshot data (no DB queries)
        - Builds delegation tree as it goes
        - Handles circular reference prevention
        - Performs tag matching and inheritance
        - Averages ballots from multiple sources
        
        Args:
            voter_id (str): UUID string of voter
            snapshot_data (dict): Frozen system state
            follow_path (list): List of voter IDs in current chain (circular prevention)
            delegation_depth (int): Current depth in delegation tree
            
        Returns:
            dict: {'ballot': {choice_id: stars}, 'tags': [str], 'type': 'manual|calculated'} or None
        """
        # Update max delegation depth
        self.stats['max_delegation_depth'] = max(self.stats['max_delegation_depth'], delegation_depth)
        
        # 1. CIRCULAR REFERENCE DETECTION
        if voter_id in follow_path:
            self.stats['circular_prevented'] += 1
            path_str = ' → '.join([self.user_lookup.get(vid, vid) for vid in follow_path + [voter_id]])
            self.delegation_tree['circular_prevented'].append({
                'voter': self.user_lookup.get(voter_id, voter_id),
                'voter_id': voter_id,
                'attempted_path': path_str
            })
            self.logger.info(f"Circular reference prevented: {path_str}")
            return None
        
        # 2. CHECK CACHE
        if voter_id in self.calculated_ballots_cache:
            return self.calculated_ballots_cache[voter_id]
        
        # 3. CHECK FOR EXISTING MANUAL BALLOT
        if voter_id in snapshot_data['existing_ballots']:
            ballot_data = snapshot_data['existing_ballots'][voter_id]
            if not ballot_data['is_calculated']:
                # Manual ballot found
                ballot_result = {
                    'ballot': {choice_id: Decimal(stars_str) for choice_id, stars_str in ballot_data['votes'].items()},
                    'tags': ballot_data['tags'].split(',') if ballot_data['tags'] else [],
                    'type': 'manual',
                    'is_anonymous': ballot_data['is_anonymous']
                }
                
                # Add to delegation tree nodes
                self._add_node_to_tree(voter_id, ballot_result, delegation_depth, sources=[])
                
                # Cache and return
                self.calculated_ballots_cache[voter_id] = ballot_result
                return ballot_result
        
        # 4. GET FOLLOWING RELATIONSHIPS
        followings = snapshot_data['followings'].get(voter_id, [])
        if not followings:
            # Can't calculate - not following anyone
            self._add_node_to_tree(voter_id, None, delegation_depth, sources=[], reason="Not following anyone")
            return None
        
        # 5. COLLECT BALLOTS TO AVERAGE
        ballots_to_average = []
        inherited_tags = set()
        sources_info = []
        
        for following in followings:
            followee_id = following['followee_id']
            follow_tags = following['tags'].split(',') if following['tags'] else []
            follow_order = following['order']
            
            # RECURSE to get followee's ballot
            followee_result = self._calculate_ballot_from_snapshot(
                followee_id,
                snapshot_data,
                follow_path + [voter_id],
                delegation_depth + 1
            )
            
            if followee_result is None:
                # Followee has no ballot
                continue
            
            followee_ballot = followee_result['ballot']
            followee_tags = followee_result['tags']
            
            # 6. TAG MATCHING
            should_inherit = False
            matching_tags = []
            
            if not follow_tags or (len(follow_tags) == 1 and not follow_tags[0]):
                # Following on ALL tags
                should_inherit = True
                matching_tags = followee_tags
            else:
                # Check intersection
                followee_tag_set = set(followee_tags)
                follow_tag_set = set(follow_tags)
                matching_tag_set = followee_tag_set.intersection(follow_tag_set)
                if matching_tag_set:
                    should_inherit = True
                    matching_tags = list(matching_tag_set)
            
            # Add edge to delegation tree
            self._add_edge_to_tree(voter_id, followee_id, follow_tags, follow_order, should_inherit)
            
            if should_inherit:
                # Add ballot to averaging list
                ballots_to_average.append(followee_ballot)
                inherited_tags.update(matching_tags)
                
                # Track source info
                sources_info.append({
                    'from_voter': self.user_lookup.get(followee_id, followee_id),
                    'from_voter_id': followee_id,
                    'tags': matching_tags,
                    'order': follow_order,
                    'is_anonymous': followee_result.get('is_anonymous', False)
                })
        
        # 7. AVERAGE BALLOTS (simple averaging, not STAR voting)
        if not ballots_to_average:
            # Following others but no tag matches
            self._add_node_to_tree(voter_id, None, delegation_depth, sources=[], 
                                  reason="Following others but no tag matches")
            return None
        
        # Average all inherited ballots
        calculated_ballot = {}
        all_choice_ids = set()
        for ballot in ballots_to_average:
            all_choice_ids.update(ballot.keys())
        
        for choice_id in all_choice_ids:
            total_stars = sum(ballot.get(choice_id, Decimal('0')) for ballot in ballots_to_average)
            avg_stars = total_stars / Decimal(len(ballots_to_average))
            calculated_ballot[choice_id] = avg_stars
        
        # 8. BUILD RESULT
        ballot_result = {
            'ballot': calculated_ballot,
            'tags': list(inherited_tags),
            'type': 'calculated',
            'is_anonymous': snapshot_data['existing_ballots'].get(voter_id, {}).get('is_anonymous', False)
        }
        
        # Add to delegation tree nodes
        self._add_node_to_tree(voter_id, ballot_result, delegation_depth, sources=sources_info)
        
        # Add inheritance chains for each choice
        for choice_id, final_stars in calculated_ballot.items():
            choice_title = next(
                (c['title'] for c in snapshot_data['choices_data'] if c['id'] == choice_id),
                choice_id
            )
            calculation_path = []
            for source_ballot, source_info in zip(ballots_to_average, sources_info):
                calculation_path.append({
                    'voter': source_info['from_voter'],
                    'voter_id': source_info['from_voter_id'],
                    'stars': float(source_ballot.get(choice_id, Decimal('0'))),
                    'weight': 1.0 / len(ballots_to_average),
                    'tags': source_info['tags'],
                    'is_anonymous': source_info['is_anonymous']
                })
            
            self.delegation_tree['inheritance_chains'].append({
                'final_voter': self.user_lookup.get(voter_id, voter_id),
                'final_voter_id': voter_id,
                'choice': choice_id,
                'choice_title': choice_title,
                'final_stars': float(final_stars),
                'calculation_path': calculation_path
            })
        
        # Cache and return
        self.calculated_ballots_cache[voter_id] = ballot_result
        return ballot_result
    
    def _add_node_to_tree(self, voter_id, ballot_result, delegation_depth, sources, reason=None):
        """Add a node to the delegation tree structure."""
        if ballot_result is None:
            # No ballot
            self.delegation_tree['nodes'].append({
                'voter_id': voter_id,
                'username': self.user_lookup.get(voter_id, voter_id),
                'vote_type': 'no_ballot',
                'reason': reason or "Unknown",
                'delegation_depth': delegation_depth
            })
        else:
            # Has ballot (manual or calculated)
            node = {
                'voter_id': voter_id,
                'username': self.user_lookup.get(voter_id, voter_id),
                'is_anonymous': ballot_result.get('is_anonymous', False),
                'vote_type': ballot_result['type'],
                'votes': {cid: {'stars': float(stars), 'choice_name': 'Choice'} for cid, stars in ballot_result['ballot'].items()},
                'tags': ballot_result['tags'],
                'delegation_depth': delegation_depth
            }
            
            if ballot_result['type'] == 'calculated':
                node['sources'] = sources
                node['inherited_tags'] = ballot_result['tags']
            
            self.delegation_tree['nodes'].append(node)
    
    def _add_edge_to_tree(self, follower_id, followee_id, tags, order, active_for_decision):
        """Add an edge to the delegation tree structure."""
        # Check if edge already exists
        existing_edge = next(
            (e for e in self.delegation_tree['edges'] 
             if e['follower'] == follower_id and e['followee'] == followee_id),
            None
        )
        
        if not existing_edge:
            self.delegation_tree['edges'].append({
                'follower': follower_id,
                'followee': followee_id,
                'tags': tags,
                'order': order,
                'active_for_decision': active_for_decision
            })
