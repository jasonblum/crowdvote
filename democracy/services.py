from collections import defaultdict
from weakref import ref

from django.utils import timezone

from service_objects.services import Service

from .models import Ballot, Community

from shared.utilities import get_object_or_None, normal_round


class StageBallots(Service):
    def score(self, ballots):
        """
        Calculate average star scores for each choice (the S in STAR).
        
        Args:
            ballots: QuerySet or list of Ballot objects to score
            
        Returns:
            OrderedDict: Choices ordered by score (highest first) with their average scores
        """
        from collections import defaultdict, OrderedDict
        from django.db.models import Avg
        
        if not ballots:
            return OrderedDict()
        
        # Get the decision from the first ballot
        decision = ballots[0].decision if ballots else None
        if not decision:
            return OrderedDict()
        
        choice_scores = {}
        
        # Calculate average score for each choice
        for choice in decision.choices.all():
            # Get all votes for this choice from the provided ballots
            votes = []
            ballot_ids = [b.id for b in ballots]
            
            for vote in choice.votes.filter(ballot__id__in=ballot_ids):
                votes.append(vote.stars)
            
            if votes:
                avg_score = sum(votes) / len(votes)
                choice_scores[choice] = {
                    'score': round(avg_score, 4),
                    'vote_count': len(votes),
                    'total_stars': sum(votes)
                }
            else:
                choice_scores[choice] = {
                    'score': 0.0,
                    'vote_count': 0,
                    'total_stars': 0
                }
        
        # Sort by score (highest first)
        sorted_choices = sorted(
            choice_scores.items(), 
            key=lambda x: x[1]['score'], 
            reverse=True
        )
        
        return OrderedDict(sorted_choices)

    def automatic_runoff(self, ballots):
        """
        Conduct automatic runoff between top 2 choices (the AR in STAR).
        
        Args:
            ballots: QuerySet or list of Ballot objects for the runoff
            
        Returns:
            dict: Runoff results with winner, vote counts, and detailed statistics
        """
        from collections import OrderedDict
        
        scores = self.score(ballots)
        
        if len(scores) < 2:
            # Need at least 2 choices for a runoff
            if len(scores) == 1:
                choice, data = list(scores.items())[0]
                return {
                    'winner': choice,
                    'winner_votes': data['vote_count'],
                    'runner_up': None,
                    'runner_up_votes': 0,
                    'total_ballots': len(ballots),
                    'margin': data['vote_count'],
                    'score_phase_results': scores,
                    'runoff_needed': False
                }
            else:
                return {
                    'winner': None,
                    'winner_votes': 0,
                    'runner_up': None,
                    'runner_up_votes': 0,
                    'total_ballots': len(ballots),
                    'margin': 0,
                    'score_phase_results': scores,
                    'runoff_needed': False
                }
        
        # Get top 2 choices from scoring phase
        top_choices = list(scores.items())[:2]
        choice_1, choice_1_data = top_choices[0]
        choice_2, choice_2_data = top_choices[1]
        
        # Count preferences in head-to-head runoff
        choice_1_preferences = 0
        choice_2_preferences = 0
        ties = 0
        
        ballot_ids = [b.id for b in ballots]
        
        for ballot_id in ballot_ids:
            # Get this voter's ratings for the top 2 choices
            vote_1 = choice_1.votes.filter(ballot__id=ballot_id).first()
            vote_2 = choice_2.votes.filter(ballot__id=ballot_id).first()
            
            stars_1 = vote_1.stars if vote_1 else 0
            stars_2 = vote_2.stars if vote_2 else 0
            
            # Determine preference
            if stars_1 > stars_2:
                choice_1_preferences += 1
            elif stars_2 > stars_1:
                choice_2_preferences += 1
            else:
                ties += 1
        
        # Determine winner
        if choice_1_preferences > choice_2_preferences:
            winner = choice_1
            winner_votes = choice_1_preferences
            runner_up = choice_2
            runner_up_votes = choice_2_preferences
        elif choice_2_preferences > choice_1_preferences:
            winner = choice_2
            winner_votes = choice_2_preferences
            runner_up = choice_1
            runner_up_votes = choice_1_preferences
        else:
            # Tie in runoff - winner determined by higher score phase average
            winner = choice_1  # Already ordered by score
            winner_votes = choice_1_preferences
            runner_up = choice_2
            runner_up_votes = choice_2_preferences
        
        return {
            'winner': winner,
            'winner_votes': winner_votes,
            'runner_up': runner_up,
            'runner_up_votes': runner_up_votes,
            'ties': ties,
            'total_ballots': len(ballots),
            'margin': abs(winner_votes - runner_up_votes),
            'score_phase_results': scores,
            'runoff_needed': True,
            'runoff_details': {
                choice_1.title: {
                    'score_phase_score': choice_1_data['score'],
                    'runoff_preferences': choice_1_preferences
                },
                choice_2.title: {
                    'score_phase_score': choice_2_data['score'],
                    'runoff_preferences': choice_2_preferences
                }
            }
        }

    def get_or_calculate_ballot(self, decision, voter, follow_path=[]):
        """
        This is where the magic happens: this recursive function gets a voter's ballot,
        or calculates one on their behalf IF they are following other users on zero or more tags (issues) and so
        can inherit votes from them.

        Note the follow_path prevents potential circular followings -- with each recursive call, 
        we add the voter to the follow_path, and if the voter is in the follow_path, we stop the recursion.
        """
        decision.ballot_tree_log_indent += 1
        decision.ballot_tree_log.append(
            {
                "indent": decision.ballot_tree_log_indent,
                "log": f"Getting or Creating ballot for voter {voter}",
            }
        )

        # this is the recursive function
        ballot, created = Ballot.objects.get_or_create(
            decision=decision, voter=voter
        )

        # If ballot had to be created or was already calculated, continue calculating
        # b/c If they manually cast their own ballot, calculated will be set to False
        if created or ballot.is_calculated:

            decision.ballot_tree_log.append(
                {
                    "indent": decision.ballot_tree_log_indent + 1,
                    "log": f"Ballot {'Created' if created else 'Retrieved and already set to calculated'} for {ballot.voter}",
                }
            )

            if not ballot.voter.followings.exists():
                decision.ballot_tree_log.append(
                    {
                        "indent": decision.ballot_tree_log_indent + 1,
                        "log": f"{ballot.voter} is not following anyone.",
                    }
                )

            ballots_to_compete = []

            # Get followings ordered by priority (lower order = higher priority)
            for following in ballot.voter.followings.select_related("followee").order_by("order"):

                if following.followee not in follow_path:
                    follow_path.append(ballot.voter)

                    decision.ballot_tree_log.append(
                        {
                            "indent": decision.ballot_tree_log_indent + 1,
                            "log": f"{ballot.voter} is following {following.followee} (order: {following.order})",
                        }
                    )

                    # Get or calculate the followee's ballot first
                    followee_ballot = self.get_or_calculate_ballot(
                        decision, following.followee, follow_path
                    )
                    
                    # Check if we should inherit from this ballot based on tag matching
                    should_inherit, matching_tags = self.should_inherit_ballot(
                        following, followee_ballot
                    )
                    
                    if should_inherit:
                        decision.ballot_tree_log.append(
                            {
                                "indent": decision.ballot_tree_log_indent + 2,
                                "log": f"✓ Tag match found: {matching_tags} - inheriting from {following.followee}",
                            }
                        )
                        ballots_to_compete.append({
                            'ballot': followee_ballot,
                            'following': following,
                            'inherited_tags': matching_tags
                        })
                    else:
                        decision.ballot_tree_log.append(
                            {
                                "indent": decision.ballot_tree_log_indent + 2,
                                "log": f"✗ No tag match - following {following.followee} on '{following.tags}' but ballot tagged '{followee_ballot.tags}'",
                            }
                        )

            # Now compete ballots to calculate this one
            ballot.votes.all().delete()
            
            # Collect inherited tags for this ballot
            inherited_tags = set()
            
            # Calculate votes with enhanced logging and tag inheritance
            for choice in ballot.decision.choices.all():
                stars_with_sources = []

                for ballot_data in ballots_to_compete:
                    source_ballot = ballot_data['ballot']
                    following = ballot_data['following']
                    choice_to_inherit = get_object_or_None(
                        source_ballot.votes.filter(choice=choice)
                    )
                    if choice_to_inherit:
                        stars_with_sources.append({
                            'stars': choice_to_inherit.stars,
                            'source': following.followee,
                            'order': following.order
                        })
                        # Collect inherited tags
                        inherited_tags.update(ballot_data['inherited_tags'])

                if stars_with_sources:
                    # Calculate average with tie-breaking by order
                    star_score = self.calculate_star_score_with_tiebreaking(
                        stars_with_sources, choice, decision
                    )
                    
                    decision.ballot_tree_log.append(
                        {
                            "indent": decision.ballot_tree_log_indent + 1,
                            "log": f"Creating vote for {ballot.voter} on {choice}: {star_score * '☆'} (avg from {len(stars_with_sources)} sources)",
                        }
                    )
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
            
            ballot.is_calculated = True
            ballot.save()

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
        if not following.tags.strip():
            followee_tags = [tag.strip() for tag in followee_ballot.tags.split(',') if tag.strip()]
            return True, followee_tags
        
        # Get tags we're following this person on
        following_tags = set(tag.strip() for tag in following.tags.split(',') if tag.strip())
        
        # Get tags the followee applied to their ballot
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
            int: Final star rating (0-5)
        """
        if not stars_with_sources:
            return 0
        
        # Simple average for now
        total_stars = sum(item['stars'] for item in stars_with_sources)
        average = total_stars / len(stars_with_sources)
        star_score = normal_round(average)
        
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
        """
        for community in Community.objects.all():
            for decision in community.decisions.filter(dt_close__gt=timezone.now()):

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

                return ballot_tree


class Tally(Service):
    def process(self):
        """
        Calculate STAR voting results for all open decisions.
        
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
                    "log": f"PARTICIPATION SUMMARY:",
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

                # Use StageBallots service for STAR voting
                stage_service = StageBallots()
                
                # SCORE PHASE (S in STAR)
                decision.tally_log.append({
                    "indent": decision.tally_log_indent,
                    "log": "SCORE PHASE (S in STAR):",
                })
                
                scores = stage_service.score(voting_ballots)
                for i, (choice, data) in enumerate(scores.items(), 1):
                    decision.tally_log.append({
                        "indent": decision.tally_log_indent + 1,
                        "log": f"{i}. {choice.title}: {data['score']:.3f} avg stars ({data['vote_count']} votes)",
                    })
                
                decision.tally_log.append({
                    "indent": decision.tally_log_indent,
                    "log": "",
                })

                # AUTOMATIC RUNOFF (AR in STAR)
                decision.tally_log.append({
                    "indent": decision.tally_log_indent,
                    "log": "AUTOMATIC RUNOFF (AR in STAR):",
                })
                
                runoff_results = stage_service.automatic_runoff(voting_ballots)
                
                if runoff_results['runoff_needed']:
                    decision.tally_log.append({
                        "indent": decision.tally_log_indent + 1,
                        "log": "Top 2 choices advance to head-to-head runoff:",
                    })
                    
                    for choice_title, details in runoff_results['runoff_details'].items():
                        decision.tally_log.append({
                            "indent": decision.tally_log_indent + 2,
                            "log": f"{choice_title}: {details['score_phase_score']:.3f} stars → {details['runoff_preferences']} preferences",
                        })
                    
                    if runoff_results['ties'] > 0:
                        decision.tally_log.append({
                            "indent": decision.tally_log_indent + 2,
                            "log": f"Tied preferences: {runoff_results['ties']}",
                        })
                else:
                    decision.tally_log.append({
                        "indent": decision.tally_log_indent + 1,
                        "log": "No runoff needed (fewer than 2 choices)",
                    })
                
                decision.tally_log.append({
                    "indent": decision.tally_log_indent,
                    "log": "",
                })

                # FINAL RESULT
                decision.tally_log.append({
                    "indent": decision.tally_log_indent,
                    "log": "🏆 FINAL RESULT:",
                })
                
                if runoff_results['winner']:
                    margin_pct = (runoff_results['margin'] / runoff_results['total_ballots']) * 100
                    decision.tally_log.append({
                        "indent": decision.tally_log_indent + 1,
                        "log": f"WINNER: {runoff_results['winner'].title}",
                    })
                    decision.tally_log.append({
                        "indent": decision.tally_log_indent + 1,
                        "log": f"Margin: {runoff_results['margin']} votes ({margin_pct:.1f}%)",
                    })
                    
                    if runoff_results['runner_up']:
                        decision.tally_log.append({
                            "indent": decision.tally_log_indent + 1,
                            "log": f"Runner-up: {runoff_results['runner_up'].title}",
                        })
                else:
                    decision.tally_log.append({
                        "indent": decision.tally_log_indent + 1,
                        "log": "No winner determined (no valid choices)",
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
                        percentage = (count / voting_ballots.count()) * 100
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
