from collections import defaultdict

from django.utils import timezone

from service_objects.services import Service

from .models import Ballot, Community

from shared.utilities import get_object_or_None, normal_round


class CalculateBallots(Service):
    def get_or_calculate_ballot(self, election, voter, follow_path=[]):
        """
        This is where the magic happens: this recursive function gets a voter's ballot,
        or calculates one on their behalf IF they are following other users from whom
        votes can be inherited.

        Note the follow_path prevents potential circular followings.
        """
        election.ballot_tree_log_indent += 1
        election.ballot_tree_log.append(
            {
                "indent": election.ballot_tree_log_indent,
                "log": f"Getting or Creating ballot for member {voter}",
            }
        )

        # this is the recursive function
        ballot, created = Ballot.objects.get_or_create(election=election, voter=voter)

        # If ballot had to be created or was already calculated, continue calculating
        # b/c If they manually cast their own ballot, calculated will be set to False
        if created or ballot.is_calculated:

            election.ballot_tree_log.append(
                {
                    "indent": election.ballot_tree_log_indent + 1,
                    "log": f"Ballot {'Created' if created else 'Retrieved and already set to calculated'} for {ballot.voter}",
                }
            )

            if not ballot.voter.followings.exists():
                election.ballot_tree_log.append(
                    {
                        "indent": election.ballot_tree_log_indent + 1,
                        "log": f"{ballot.voter} is not following anyone.",
                    }
                )

            ballots_to_compete = []

            for following in ballot.voter.followings.select_related("followee"):

                if following.followee not in follow_path:
                    follow_path.append(ballot.voter)

                    election.ballot_tree_log.append(
                        {
                            "indent": election.ballot_tree_log_indent + 1,
                            "log": f"{ballot.voter} is following {following.followee}",
                        }
                    )

                    # TODO: I think this goes here: only append, if the followee's ballot's tags are in my following.tags

                    ballots_to_compete.append(
                        self.get_or_calculate_ballot(
                            election, following.followee, follow_path
                        )
                    )

            # Now compete ballots to calculate this one
            ballot.votes.all().delete()

            for candidate in ballot.election.candidates.all():
                stars = []

                for ballot_to_compete in ballots_to_compete:
                    candidate_to_inherit = get_object_or_None(
                        ballot_to_compete.votes.filter(candidate=candidate)
                    )
                    if candidate_to_inherit:
                        stars.append(candidate_to_inherit.stars)

                if stars:
                    star_score = normal_round(sum(stars) / len(stars))
                    election.ballot_tree_log.append(
                        {
                            "indent": election.ballot_tree_log_indent + 1,
                            "log": f"Creating vote for {ballot.voter} on {candidate}: {star_score * '☆ '}",
                        }
                    )
                    ballot.votes.create(candidate=candidate, stars=star_score)

            ballot.is_calculated = True
            ballot.save()

        election.ballot_tree_log_indent -= 1
        return ballot

    def process(self):

        for community in Community.objects.all():
            for election in community.elections.filter(
                datetime_close__gt=timezone.now()
            ):

                # Stick a log on to the election, to print out at the end
                election.ballot_tree_log = []
                election.ballot_tree_log_indent = 0
                election.ballot_tree_log.append(
                    {
                        "indent": election.ballot_tree_log_indent,
                        "log": f"Ballot Tree for {election}: {election.title} (Community: {community})",
                    }
                )
                election.ballot_tree_log.append(
                    {
                        "indent": election.ballot_tree_log_indent,
                        "log": "-" * 100,
                    }
                )

                ballots = []
                for member in community.members.all():
                    ballots.append(
                        self.get_or_calculate_ballot(election=election, voter=member)
                    )

                election.ballot_tree_log.append(
                    {
                        "indent": election.ballot_tree_log_indent,
                        "log": "Begin final tally!",
                    }
                )
                election.ballot_tree_log.append(
                    {
                        "indent": election.ballot_tree_log_indent,
                        "log": "-" * 200,
                    }
                )

                ballot_tree = ""
                for log in election.ballot_tree_log:
                    ballot_tree += (
                        f"{log['indent'] * '----------------'}{log['log']}<br/>"
                    )

                election.ballot_tree = ballot_tree
                election.save()

                return ballot_tree


class Tally(Service):
    def process(self):

        for community in Community.objects.all():
            for election in community.elections.filter(
                datetime_close__gt=timezone.now()
            ):

                # Stick a log on to the election, to print out at the end
                election.tally_log = []
                election.tally_log_indent = 0
                election.tally_log.append(
                    {
                        "indent": election.tally_log_indent,
                        "log": f"Tallying balots for {election}: {election.title} (Community: {community})",
                    }
                )
                election.tally_log.append(
                    {
                        "indent": election.tally_log_indent,
                        "log": "-" * 100,
                    }
                )

                # (S)TAR: Score the candidates on each voting member's ballot:
                scores = defaultdict(list)
                for ballot in election.ballots.all():
                    if ballot.voter.memberships.filter(
                        community=community, is_voting_community_member=True
                    ).exists():
                        election.tally_log.append(
                            {
                                "indent": election.tally_log_indent + 1,
                                "log": f"{ballot.voter} is a voting member of {election}'s community ({community}",
                            }
                        )
                        for vote in ballot.votes.all():
                            scores[vote.candidate].append(vote.stars)
                        election.tally_log.append(
                            {
                                "indent": election.tally_log_indent + 2,
                                "log": "Scores added...",
                            }
                        )
                    else:
                        election.tally_log.append(
                            {
                                "indent": election.tally_log_indent + 1,
                                "log": f"{ballot.voter} is NOT a voting member of {election}'s community ({community}",
                            }
                        )

                # S(TAR): Then Automaticaly Run off: determine winner from ballot's preferred candidate

            tally_report = ""
            for log in election.tally_log:
                tally_report += f"{log['indent'] * '----------------'}{log['log']}<br/>"

            election.tally_report = tally_report + str(scores)
            election.save()

        return tally_report
