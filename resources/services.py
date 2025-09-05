from collections import defaultdict
from weakref import ref

from django.utils import timezone

from service_objects.services import Service

from .models import Ballot, Community

from shared.utilities import get_object_or_None, normal_round


class CalculateBallots(Service):
    def score(self, ballots=[]):
        """
        Returns orderedDict of choices with their scores from all ballots (the S in STAR)
        """
        pass

    def automatic_runoff(self, ballots=[]):
        scores = self.score(ballots)
        """
        Returns orderedDict of choices with their scores and preferred count from all ballots (the AR in STAR)
        """
        pass

    def get_or_calculate_ballot(self, referendum, voter, follow_path=[]):
        """
        This is where the magic happens: this recursive function gets a voter's ballot,
        or calculates one on their behalf IF they are following other users from whom
        votes can be inherited.

        Note the follow_path prevents potential circular followings.
        """
        referendum.ballot_tree_log_indent += 1
        referendum.ballot_tree_log.append(
            {
                "indent": referendum.ballot_tree_log_indent,
                "log": f"Getting or Creating ballot for voter {voter}",
            }
        )

        # this is the recursive function
        ballot, created = Ballot.objects.get_or_create(
            referendum=referendum, voter=voter
        )

        # If ballot had to be created or was already calculated, continue calculating
        # b/c If they manually cast their own ballot, calculated will be set to False
        if created or ballot.is_calculated:

            referendum.ballot_tree_log.append(
                {
                    "indent": referendum.ballot_tree_log_indent + 1,
                    "log": f"Ballot {'Created' if created else 'Retrieved and already set to calculated'} for {ballot.voter}",
                }
            )

            if not ballot.voter.followings.exists():
                referendum.ballot_tree_log.append(
                    {
                        "indent": referendum.ballot_tree_log_indent + 1,
                        "log": f"{ballot.voter} is not following anyone.",
                    }
                )

            ballots_to_compete = []

            for following in ballot.voter.followings.select_related("followee"):

                if following.followee not in follow_path:
                    follow_path.append(ballot.voter)

                    referendum.ballot_tree_log.append(
                        {
                            "indent": referendum.ballot_tree_log_indent + 1,
                            "log": f"{ballot.voter} is following {following.followee}",
                        }
                    )

                    # TODO: I think this goes here: only append, if the followee's ballot's tags are in my following.tags

                    ballots_to_compete.append(
                        self.get_or_calculate_ballot(
                            referendum, following.followee, follow_path
                        )
                    )

            # Now compete ballots to calculate this one
            ballot.votes.all().delete()

            for choice in ballot.referendum.choices.all():
                stars = []

                for ballot_to_compete in ballots_to_compete:
                    choice_to_inherit = get_object_or_None(
                        ballot_to_compete.votes.filter(choice=choice)
                    )
                    if choice_to_inherit:
                        stars.append(choice_to_inherit.stars)

                if stars:
                    star_score = normal_round(sum(stars) / len(stars))
                    referendum.ballot_tree_log.append(
                        {
                            "indent": referendum.ballot_tree_log_indent + 1,
                            "log": f"Creating vote for {ballot.voter} on {choice}: {star_score * '☆ '}",
                        }
                    )
                    ballot.votes.create(choice=choice, stars=star_score)

            ballot.is_calculated = True
            ballot.save()

        referendum.ballot_tree_log_indent -= 1
        return ballot

    def process(self):

        for community in Community.objects.all():
            for referendum in community.referendums.filter(dt_close__gt=timezone.now()):

                # Stick a log on to the referendum, to print out at the end
                referendum.ballot_tree_log = []
                referendum.ballot_tree_log_indent = 0
                referendum.ballot_tree_log.append(
                    {
                        "indent": referendum.ballot_tree_log_indent,
                        "log": f"Ballot Tree for {referendum}: {referendum.title} (Community: {community})",
                    }
                )
                referendum.ballot_tree_log.append(
                    {
                        "indent": referendum.ballot_tree_log_indent,
                        "log": "-" * 100,
                    }
                )

                ballots = []
                for membership in community.memberships.all():
                    ballots.append(
                        self.get_or_calculate_ballot(
                            referendum=referendum, voter=membership.member
                        )
                    )

                referendum.ballot_tree_log.append(
                    {
                        "indent": referendum.ballot_tree_log_indent,
                        "log": "Begin final tally!",
                    }
                )
                referendum.ballot_tree_log.append(
                    {
                        "indent": referendum.ballot_tree_log_indent,
                        "log": "-" * 200,
                    }
                )

                ballot_tree = ""
                for log in referendum.ballot_tree_log:
                    ballot_tree += (
                        f"{log['indent'] * '----------------'}{log['log']}<br/>"
                    )

                referendum.ballot_tree = ballot_tree
                referendum.save()

                return ballot_tree


class Tally(Service):
    def process(self):

        for community in Community.objects.all():
            for referendum in community.referendums.filter(dt_close__gt=timezone.now()):

                # Stick a log on to the referendum, to print out at the end
                referendum.tally_log = []
                referendum.tally_log_indent = 0
                referendum.tally_log.append(
                    {
                        "indent": referendum.tally_log_indent,
                        "log": f"Tallying balots for {referendum}: {referendum.title} (Community: {community})",
                    }
                )
                referendum.tally_log.append(
                    {
                        "indent": referendum.tally_log_indent,
                        "log": "-" * 100,
                    }
                )

                # (S)TAR: Score the choices on each voting member's ballot:
                scores = defaultdict(list)
                for ballot in referendum.ballots.all():
                    if ballot.voter.memberships.filter(
                        community=community, is_voting_community_member=True
                    ).exists():
                        referendum.tally_log.append(
                            {
                                "indent": referendum.tally_log_indent + 1,
                                "log": f"{ballot.voter} is a voting member of {referendum}'s community ({community}",
                            }
                        )
                        for vote in ballot.votes.all():
                            scores[vote.choice].append(vote.stars)
                        referendum.tally_log.append(
                            {
                                "indent": referendum.tally_log_indent + 2,
                                "log": "Scores added...",
                            }
                        )
                    else:
                        referendum.tally_log.append(
                            {
                                "indent": referendum.tally_log_indent + 1,
                                "log": f"{ballot.voter} is NOT a voting member of {referendum}'s community ({community}",
                            }
                        )

                # S(TAR): Then Automaticaly Run off: determine winner from ballot's preferred choice

            tally_report = ""
            for log in referendum.tally_log:
                tally_report += f"{log['indent'] * '----------------'}{log['log']}<br/>"

            referendum.tally_report = tally_report + str(scores)
            referendum.save()

        return tally_report
