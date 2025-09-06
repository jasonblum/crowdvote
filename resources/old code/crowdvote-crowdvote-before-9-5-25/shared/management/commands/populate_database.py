import random

from django.db import transaction
from django.core.management.base import BaseCommand

from accounts.models import CustomUser
from accounts.factories import CustomUserFactory, FollowingFactory
from communities.factories import (
    CommunityFactory,
    MembershipFactory,
    ReferendumFactory,
    ChoiceFactory,
    BallotFactory,
    VoteFactory,
)

from shared.utilities import get_random_madeup_tags


NUM_USERS = 100
NUM_REFERENDUMS = 2
PERCENTAGE_OF_USERS_WHO_ARE_MEMBERS = 80
PERCENTAGE_OF_USERS_WHO_FOLLOWING_SOMEONE = 80
MAX_NUM_OF_FOLLOWEES = 8
PERCENTAGE_OF_MEMBERS_VOTING = 60
PERCENTAGE_OF_REFERENDUMS_ATTRACTING_BALLOTS = 90


class Command(BaseCommand):
    help = "Generates test data"

    @transaction.atomic
    def handle(self, *args, **kwargs):

        self.stdout.write("> Creating new data...")

        # CREATE A COMMUNITY
        community = CommunityFactory()
        self.stdout.write(f"> Community created: {community}.")

        # CREATE USERS
        users = CustomUserFactory.create_batch(NUM_USERS)
        self.stdout.write(f"> {NUM_USERS} users created.")

        # CREATE MEMBERSHIPS
        memberships = []
        for i, user in enumerate(
            users[: round((len(users) * PERCENTAGE_OF_USERS_WHO_ARE_MEMBERS) / 100)]
        ):
            memberships.append(MembershipFactory(member=user, community=community))
        self.stdout.write(f"> {i} memberships created.")

        # CREATE FOLLOWINGS BETWEEN THOSE USERS
        i = 0
        for user in users[
            : round((len(users) * PERCENTAGE_OF_USERS_WHO_FOLLOWING_SOMEONE) / 100)
        ]:

            for _ in range(2, random.randrange(1, MAX_NUM_OF_FOLLOWEES)):
                FollowingFactory(
                    follower=user,
                    followee=random.choice(
                        [followee for followee in users if followee != user]
                    ),
                    tags=get_random_madeup_tags(),
                )
                i += 1
        self.stdout.write(f"> {i} followings created.")

        # CREATE REFERENDUMS
        referendums = ReferendumFactory.create_batch(
            NUM_REFERENDUMS, community=community
        )
        self.stdout.write(f"> {NUM_REFERENDUMS} referendums created.")

        # CREATE CANDIDATES
        i = 0
        for referendum in referendums:
            for _ in range(2, random.randrange(2, 10)):
                ChoiceFactory(referendum=referendum)
                i += 1
        self.stdout.write(f"> {i} choices created on referendums")

        # CREATE VOTES FOR PERCENTAGE_OF_MEMBERS_VOTING AND FOR SOME PERCENTAGE_OF_REFERENDUMS_ATTRACTING_BALLOTS
        random.shuffle(memberships)
        random.shuffle(referendums)
        i = 0
        for membership in memberships[
            : round((len(memberships) * PERCENTAGE_OF_MEMBERS_VOTING) / 100)
        ]:
            for referendum in referendums[
                : round(
                    (len(referendums) * PERCENTAGE_OF_REFERENDUMS_ATTRACTING_BALLOTS)
                    / 100
                )
            ]:
                ballot = BallotFactory(
                    referendum=referendum,
                    voter=membership.member,
                    #    Not sure why next line breaks, but manually running again below
                    #    tags=get_random_madeup_tags(),
                )
                ballot.tags = get_random_madeup_tags()
                ballot.save()

                for choice in referendum.choices.all():
                    VoteFactory(choice=choice, ballot=ballot)
                    i += 1
                print(i)
        self.stdout.write(f"> {i} Votes cast!")

        self.stdout.write("....and done!")
