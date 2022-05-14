from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


from communities.models import Community, Membership, Election, Ballot, Choice, Vote


def get_or_calculate_ballot(question, voter, follow_path=[]):

    question.tally_report_log_level += 1
    question.tally_report_log.append(
        {
            "level": question.tally_report_log_level,
            "log": f"Getting or Creating ballot for member {voter}",
        }
    )

    # this is the recursive function
    ballot, created = Ballot.objects.get_or_create(question=question, voter=voter)

    # If ballot had to be created or was already calculated, continue calculating
    # b/c If they manually cast their own ballot, calculated will be set to False
    if created or ballot.calculated:

        ballots_to_compete = []

        for following in ballot.voter.followings.all():

            if following.followee not in follow_path:
                follow_path.append(ballot.voter)
                ballots_to_compete.append(
                    get_or_calculate_ballot(question, following.followee, follow_path)
                )

        # Now compete ballots to calculate this one
        ballot.votes.all().delete()

        for choice in ballot.question.choices.all():
            stars = []

            for ballot_to_compete in ballots_to_compete:
                stars.append(ballot_to_compete.votes.get(choice=choice).stars)

            if stars:
                ballot.votes.create(choice=choice, stars=(sum(stars) / len(stars)))

        ballot.calculated = True
        ballot.save()

    question.tally_report_log_level += 1
    return ballot


class Command(BaseCommand):
    help = "Gets or Creates everyone's ballots and tallys them up!"

    @transaction.atomic
    def handle(self, *args, **kwargs):

        for community in Community.objects.all():
            for question in community.questions.filter(
                datetime_close__gt=timezone.now()
            ):

                # Stick a log on to the question, to print out at the end
                question.tally_report_log = []
                question.tally_report_log_level = 0
                question.tally_report_log.append(
                    {
                        "level": question.tally_report_log_level,
                        "log": f"Tally Report for {question}: {question.title} (Community: {community})",
                    }
                )

                ballots = []
                for member in community.members.all():
                    ballots.append(
                        get_or_calculate_ballot(question=question, voter=member)
                    )

                for ballot in ballots:
                    """TODO: STAR votes of each vote
                    Then set the winning vote on this question
                    """
                question.winning_choice = (
                    "whatever is the winning choice after the runoff above"
                )

                tally_report = ""
                for log in question.tally_report_log:
                    tally_report += f"{log[0] * '/t'}{log[1]}/n"

                question.tally_report = tally_report
                question.save()
                print(question.tally_report)
