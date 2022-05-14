import random

from django.db import transaction
from django.core.management.base import BaseCommand

from accounts.models import CustomUser, Following
from communities.models import Community, Election, Candidate, Membership, Ballot, Vote

from shared.utilities import get_random_madeup_tags


class Command(BaseCommand):
    help = (
        "Generates specific test data to make it a little easier to test everything..."
    )

    @transaction.atomic
    def handle(self, *args, **kwargs):

        self.stdout.write("Creating new specific data...")

        community = Community.objects.create(
            name="A Test Community", description="Description of this test community"
        )

        # Create some users
        users = []
        for user in ["a", "b", "c"]:
            users.append(
                CustomUser.objects.create(
                    first_name=user,
                    last_name=user,
                    email=f"{user}@{user}.com",
                    username=user,
                )
            )

        # Set their memberships
        for user in users:
            Membership.objects.create(
                member=user,
                community=community,
                is_public=True,
                is_voting_community_member=True,
            )

        #TODO: leaving off here this morning.  Need to do next:
        - Add non voting lobbyists
        - Add elections, candiates, etc...


        self.stdout.write("....and done!")
