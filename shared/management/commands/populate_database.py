import random

from django.db import transaction
from django.core.management.base import BaseCommand

from accounts.models import CustomUser
from accounts.factories import CustomUserFactory, FollowingFactory
from communities.factories import (
    CommunityFactory,
    MembershipFactory,
    ElectionFactory,
    CandidateFactory,
    BallotFactory,
    VoteFactory,
)

NUM_USERS = 100
NUM_ELECTIONS = 2
PERCENTAGE_OF_USERS_WHO_ARE_MEMBERS = 80
PERCENTAGE_OF_USERS_WHO_FOLLOWING_SOMEONE = 80
RANGE_MAX_OF_FOLLOWEES = 8
PERCENTAGE_OF_MEMBERS_VOTING = 60
PERCENTAGE_OF_ELECTIONS_SOLICITING_BALLOTS = 90


def get_random_tags():
    abcs = "abcdefghijklmnopqrstuvwxyz"
    tags = []
    for i in range(random.randint(0, 4)):
        tags.append(random.choice(abcs) * 5)
    return list(set(tags))


class Command(BaseCommand):
    help = "Generates test data"

    @transaction.atomic
    def handle(self, *args, **kwargs):

        self.stdout.write("Creating new data...")

        # Creating a community
        community = CommunityFactory()

        # Create all the users
        users = CustomUserFactory.create_batch(NUM_USERS)
        self.stdout.write(f"> {NUM_USERS} users created.")

        # Create memberships
        for i, user in enumerate(
            users[: round((len(users) * PERCENTAGE_OF_USERS_WHO_ARE_MEMBERS) / 100)]
        ):
            MembershipFactory(member=user, community=community)
        self.stdout.write(f"> {i} memberships created.")

        # Create followings
        i = 0
        for user in users[
            : round((len(users) * PERCENTAGE_OF_USERS_WHO_FOLLOWING_SOMEONE) / 100)
        ]:
            # Make sure this user can't follow itself:
            users.remove(user)
            for _ in range(2, random.randrange(1, RANGE_MAX_OF_FOLLOWEES)):
                FollowingFactory(
                    user=user, followee=random.choice(users), tags=get_random_tags()
                )
                i += 1

        self.stdout.write(f"> {i} followings created.")

        # Create elections
        elections = ElectionFactory.create_batch(NUM_ELECTIONS, community=community)
        self.stdout.write(f"> {NUM_ELECTIONS} elections created.")

        # Create Candidates on Elections
        i = 0
        for election in elections:
            for _ in range(2, random.randrange(2, 10)):
                CandidateFactory(election=election)
                i += 1
        self.stdout.write(f"> {i} candidates created on elections")

        # Create Votes for above % of folks voting and for some % of ballots
        random.shuffle(users)
        random.shuffle(elections)
        i = 0
        for user in users[: round((len(users) * PERCENTAGE_OF_MEMBERS_VOTING) / 100)]:
            for election in elections[
                : round(
                    (len(elections) * PERCENTAGE_OF_ELECTIONS_SOLICITING_BALLOTS) / 100
                )
            ]:
                ballot = BallotFactory(
                    election=election, voter=user, tags=get_random_tags()
                )
                for candidate in election.candidates.all():
                    VoteFactory(candidate=candidate, ballot=ballot)
                    i += 1
        self.stdout.write(f"> {i} Votes cast!")

        self.stdout.write("....and done!")
