"""
Management command to create the Alphabet Delegation Test community.

This command creates a systematic test community with 12 users named after letters
(AAAAAAAAAAA through LLLLLLLLLLL) to validate complex delegation inheritance 
calculations and visualize multi-level delegation trees.

The community demonstrates realistic cross-level following relationships where
manual voters also follow others, creating complex inheritance networks that
mirror real-world influence patterns.

Usage:
    python manage.py create_alphabet_test_community --clear-existing
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from security.models import Following
from democracy.models import Community, Decision, Choice, Ballot, Vote, Membership
from decimal import Decimal
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create Alphabet Delegation Test community with systematic delegation relationships'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing alphabet test community before creating new one',
        )

    def handle(self, *args, **options):
        """Create the alphabet test community with complex delegation relationships."""
        
        if options['clear_existing']:
            self.clear_existing_data()
        
        with transaction.atomic():
            # Create community
            community = self.create_community()
            
            # Create 12 users A through L
            users = self.create_users()
            
            # Create memberships
            self.create_memberships(community, users)
            
            # Create complex following relationships
            self.create_following_relationships(users)
            
            # Create test decision with 3 choices
            decision = self.create_test_decision(community)
            
            # Have manual voters cast votes
            self.create_manual_votes(decision, users)
            
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully created Alphabet Delegation Test community with:'
                f'\n- 12 users (AAAAAAAAAAA through LLLLLLLLLLL)'
                f'\n- Complex cross-level following relationships'
                f'\n- Test decision "Test Delegation Inheritance" with 3 choices'
                f'\n- Manual votes from 4 users with different star ratings'
                f'\n\nNext steps:'
                f'\n1. Run: python manage.py stage_and_tally_ballots'
                f'\n2. Visit the community to see delegation trees'
                f'\n3. Run: pytest tests/test_services/test_alphabet_delegation_validation.py'
            )
        )

    def clear_existing_data(self):
        """Clear existing alphabet test community data."""
        try:
            community = Community.objects.get(name="Alphabet Delegation Test")
            self.stdout.write("Clearing existing Alphabet Delegation Test community...")
            
            # Get alphabet users
            alphabet_users = User.objects.filter(
                username__in=[f"{chr(65+i)}" * 11 for i in range(12)]
            )
            
            # Delete in correct order to avoid PROTECT constraint violations
            # 1. Delete ALL votes for community decisions (not just alphabet users)
            Vote.objects.filter(ballot__decision__community=community).delete()
            
            # 2. Delete ALL ballots for community decisions (not just alphabet users)
            Ballot.objects.filter(decision__community=community).delete()
            
            # 3. Delete choices (which reference decisions)
            Choice.objects.filter(decision__community=community).delete()
            
            # 4. Delete decisions
            Decision.objects.filter(community=community).delete()
            
            # 5. Delete following relationships
            Following.objects.filter(follower__in=alphabet_users).delete()
            Following.objects.filter(followee__in=alphabet_users).delete()
            
            # 6. Delete ALL memberships for this community
            Membership.objects.filter(community=community).delete()
            
            # 7. Delete community
            community.delete()
            
            # 8. Finally delete users
            alphabet_users.delete()
            
            self.stdout.write(self.style.SUCCESS("Existing data cleared."))
            
        except Community.DoesNotExist:
            self.stdout.write("No existing alphabet test community found.")

    def create_community(self):
        """Create the Alphabet Delegation Test community."""
        community = Community.objects.create(
            name="Alphabet Delegation Test",
            description=(
                "Systematic test community for validating complex delegation inheritance "
                "calculations. Features 12 users with realistic cross-level following "
                "relationships to demonstrate multi-level delegation trees and fractional "
                "star averaging in CrowdVote's democratic system."
            ),
            auto_approve_applications=True
        )
        
        self.stdout.write(f"Created community: {community.name}")
        return community

    def create_users(self):
        """Create 12 users with alphabet-based names."""
        users = {}
        
        for i in range(12):
            letter = chr(65 + i)  # A=65, B=66, etc.
            username = letter * 11  # AAAAAAAAAAA, BBBBBBBBBBB, etc.
            
            user = User.objects.create_user(
                username=username,
                email=f"{username.lower()}@alphabettest.com",
                first_name=username,
                last_name="Test"
            )
            
            users[letter] = user
            self.stdout.write(f"Created user: {username} Test")
        
        return users

    def create_memberships(self, community, users):
        """Create memberships for all users in the community."""
        for letter, user in users.items():
            Membership.objects.create(
                member=user,
                community=community,
                is_voting_community_member=True,
                is_community_manager=False  # All regular voters for simplicity
            )
        
        self.stdout.write(f"Created memberships for all 12 users")

    def create_following_relationships(self, users):
        """Create complex cross-level following relationships."""
        
        # Manual voters who also follow others
        following_data = [
            # AAAAAAAAAAA follows others on tags they don't vote on manually
            ('A', 'J', 'four,five', 1),
            ('A', 'L', 'six', 2),
            
            # BBBBBBBBBBB follows others on non-manual tags
            ('B', 'G', 'one,three', 1),
            ('B', 'K', 'six', 2),
            
            # CCCCCCCCCCC follows others on non-manual tags
            ('C', 'E', 'one,two', 1),
            ('C', 'I', 'four', 2),
            
            # DDDDDDDDDDD follows others on non-manual tags
            ('D', 'F', 'two,three', 1),
            ('D', 'H', 'five', 2),
            
            # Mixed delegation users with complex cross-level following
            ('E', 'A', 'one,two', 1),
            ('E', 'B', 'four', 2),
            ('E', 'K', 'three,five', 3),
            
            ('F', 'B', 'two,five', 1),
            ('F', 'C', 'three', 2),
            ('F', 'I', 'one,six', 3),
            
            ('G', 'C', 'five,six', 1),
            ('G', 'D', 'one', 2),
            ('G', 'L', 'two,four', 3),
            
            ('H', 'A', 'one,two,three', 1),
            ('H', 'D', 'six', 2),
            ('H', 'J', 'four,five', 3),
            
            ('I', 'E', 'one,two', 1),
            ('I', 'F', 'three,four', 2),
            ('I', 'A', 'five,six', 3),
            
            ('J', 'G', 'five,six', 1),
            ('J', 'H', 'one,two', 2),
            ('J', 'B', 'three,four', 3),
            
            ('K', 'E', 'one,three', 1),
            ('K', 'G', 'six', 2),
            ('K', 'C', 'two,four,five', 3),
            
            ('L', 'I', 'one,two,three', 1),
            ('L', 'J', 'four,five', 2),
            ('L', 'D', 'six', 3),
        ]
        
        for follower_letter, followee_letter, tags, order in following_data:
            Following.objects.create(
                follower=users[follower_letter],
                followee=users[followee_letter],
                tags=tags,
                order=order
            )
        
        self.stdout.write(f"Created {len(following_data)} following relationships")

    def create_test_decision(self, community):
        """Create test decision with 3 choices."""
        decision = Decision.objects.create(
            community=community,
            title="Test Delegation Inheritance",
            description=(
                "Test decision to validate complex delegation inheritance calculations. "
                "This decision demonstrates how votes and tags flow through multi-level "
                "delegation networks with fractional star averaging."
            ),
            dt_close=timezone.now() + timedelta(days=7),  # Close in 7 days
            results_need_updating=True
        )
        
        # Create 3 choices
        choices = []
        choice_titles = [
            "Choice Alpha - Test Fractional Inheritance",
            "Choice Beta - Validate Tag-Specific Delegation", 
            "Choice Gamma - Verify Priority Ordering"
        ]
        
        for i, title in enumerate(choice_titles):
            choice = Choice.objects.create(
                decision=decision,
                title=title,
                description=f"Test choice {i+1} for validating delegation calculations"
            )
            choices.append(choice)
        
        self.stdout.write(f"Created decision '{decision.title}' with 3 choices")
        return decision

    def create_manual_votes(self, decision, users):
        """Create manual votes for the 4 manual voters with different star ratings."""
        
        # Manual voter data: (letter, tags, [stars for choice 1, 2, 3])
        manual_votes = [
            ('A', 'one,two,three', [5, 3, 1]),
            ('B', 'two,four,five', [2, 4, 5]),
            ('C', 'three,five,six', [4, 1, 3]),
            ('D', 'one,four,six', [1, 5, 2]),
        ]
        
        choices = list(decision.choices.all())
        
        for letter, tags, star_ratings in manual_votes:
            user = users[letter]
            
            # Create ballot
            ballot = Ballot.objects.create(
                decision=decision,
                voter=user,
                is_calculated=False,
                is_anonymous=False,
                tags=tags
            )
            
            # Create votes for each choice
            for i, stars in enumerate(star_ratings):
                Vote.objects.create(
                    choice=choices[i],
                    ballot=ballot,
                    stars=Decimal(str(stars))
                )
            
            self.stdout.write(f"Created manual vote for {user.username}: {star_ratings} stars")
        
        self.stdout.write("All manual votes created successfully")
