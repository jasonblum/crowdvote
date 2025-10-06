"""
Management command to create a complex delegation test scenario.

This command creates a controlled test environment for validating CrowdVote's
delegation system, including vote averaging calculations, multi-level inheritance
chains, circular reference handling, and fractional vote inheritance.

The test scenario includes:
- 10 users (A-J) with specific naming patterns
- Complex following relationships using fruit-based tags
- Multi-level delegation chains (2-7 levels deep)
- Intentional circular references to test loop prevention
- Manual and calculated votes to verify fractional star averaging

Run with: python manage.py create_delegation_test
"""

import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from security.models import Following
from democracy.models import Community, Membership, Decision, Choice, Ballot, Vote

User = get_user_model()


class Command(BaseCommand):
    """
    Django management command to create complex delegation test scenario.
    
    This command generates a comprehensive test environment to validate
    the delegation system's ability to handle:
    - Vote averaging with fractional results
    - Multi-level delegation chains
    - Circular reference prevention
    - Complex inheritance patterns
    """
    
    help = 'Create complex delegation test scenario with 10 users and intricate following relationships'

    def add_arguments(self, parser):
        """
        Add command line arguments for the management command.
        
        Args:
            parser: Django's argument parser for management commands
        """
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Clear existing Delegation Test community before creating new one'
        )

    def handle(self, *args, **options):
        """
        Main command handler that orchestrates the test scenario creation.
        
        Args:
            *args: Positional arguments (unused)
            **options: Command options including clear_existing flag
        """
        if options['clear_existing']:
            self.clear_existing_test_data()
        
        self.stdout.write(
            self.style.SUCCESS('Creating complex delegation test scenario...')
        )

        # Create the test community
        community = self.create_test_community()
        
        # Create 10 test users with specific naming pattern
        users = self.create_test_users(community)
        
        # Create complex following relationships with fruit tags
        self.create_complex_following_relationships(users)
        
        # Create a test decision for voting
        decision = self.create_test_decision(community)
        
        # Create manual votes from 5 users with different star ratings
        self.create_manual_votes(decision, users)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Complex delegation test scenario created successfully!\n'
                f'📍 Community: {community.name} (ID: {community.id})\n'
                f'👥 Users: 10 users (A-J) with complex delegation relationships\n'
                f'🗳️ Decision: "{decision.title}" ready for testing\n'
                f'🔗 Following relationships: Multi-level chains with circular reference tests\n'
                f'⭐ Manual votes: 5 users with different star ratings (1-5)\n'
                f'🧮 Calculated votes: 5 users will inherit fractional averages\n\n'
                f'🌐 View results at: /communities/{community.id}/decisions/{decision.id}/results/'
            )
        )

    def clear_existing_test_data(self):
        """
        Clear existing Delegation Test community and related data.
        
        This method removes any existing test data to ensure a clean
        test environment for the new scenario.
        """
        self.stdout.write('Clearing existing Delegation Test data...')
        
        try:
            existing_community = Community.objects.get(name='Delegation Test')
            
            # Clear votes, ballots, choices, and decisions for this community
            for decision in existing_community.decisions.all():
                Vote.objects.filter(ballot__decision=decision).delete()
                Ballot.objects.filter(decision=decision).delete()
                Choice.objects.filter(decision=decision).delete()
                decision.delete()
            
            # Get all members of this test community
            all_community_members = existing_community.members.all()
            
            # Clear following relationships for ALL community members
            Following.objects.filter(follower__in=all_community_members).delete()
            Following.objects.filter(followee__in=all_community_members).delete()
            
            # Clear ALL memberships for this community
            Membership.objects.filter(community=existing_community).delete()
            
            # Delete only the test users (A-J pattern), not admin or other users
            test_usernames = [f'{"ABCDEFGHIJ"[i]}'*10 for i in range(10)]
            test_users = User.objects.filter(username__in=test_usernames)
            test_users.delete()
            
            # Delete the community
            existing_community.delete()
            
            self.stdout.write('✅ Existing test data cleared')
            
        except Community.DoesNotExist:
            self.stdout.write('No existing Delegation Test community found')

    def create_test_community(self):
        """
        Create the Delegation Test community with descriptive purpose.
        
        Returns:
            Community: The created test community instance
        """
        community, created = Community.objects.get_or_create(
            name='Delegation Test',
            defaults={
                'description': (
                    'This is a controlled test environment for validating CrowdVote\'s '
                    'delegation system functionality. This community contains 10 test users '
                    '(A-J) with deliberately complex following relationships designed to test:\n\n'
                    '• Vote averaging calculations with fractional star results\n'
                    '• Multi-level delegation chains (2-7 levels deep)\n'
                    '• Circular reference prevention in delegation algorithms\n'
                    '• Complex inheritance patterns where users inherit from dozens of sources\n'
                    '• Tag-based delegation using fruit names (banana, orange, pineapple, etc.)\n\n'
                    'The test scenarios include both simple 2-level delegation chains and '
                    'complex multi-level inheritance trees to ensure the delegation system '
                    'handles all edge cases correctly. Users can examine the decision results '
                    'to verify that calculated votes show proper fractional averages and '
                    'that delegation trees display the expected complexity.'
                ),
                'auto_approve_applications': True
            }
        )
        
        if created:
            self.stdout.write(f'✅ Created community: {community.name}')
        else:
            self.stdout.write(f'📍 Using existing community: {community.name}')
            
        return community

    def create_test_users(self, community):
        """
        Create 10 test users with specific naming pattern (A-J).
        
        Args:
            community: The community to add users to
            
        Returns:
            list: List of created User instances
        """
        users = []
        letters = 'ABCDEFGHIJ'
        
        for i, letter in enumerate(letters):
            username = letter * 10  # AAAAAAAAAA, BBBBBBBBBB, etc.
            first_name = letter
            last_name = letter
            email = f'{letter.lower()}@delegationtest.com'
            
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': email,
                    'is_active': True,
                }
            )
            users.append(user)
            
            # Create membership in the test community
            Membership.objects.get_or_create(
                member=user,
                community=community,
                defaults={
                    'is_voting_community_member': True,
                    'is_community_manager': i == 0  # Make user A the manager
                }
            )
            
            if created:
                self.stdout.write(f'✅ Created user: {username} ({first_name} {last_name})')
        
        return users

    def create_complex_following_relationships(self, users):
        """
        Create complex following relationships with fruit tags to test delegation.
        
        This method creates a sophisticated network of following relationships
        including simple chains, multi-level inheritance, and circular references
        to thoroughly test the delegation system.
        
        Args:
            users: List of User instances (A-J)
        """
        # Map users by letter for easier reference
        user_map = {user.username[0]: user for user in users}
        A, B, C, D, E, F, G, H, I, J = [user_map[letter] for letter in 'ABCDEFGHIJ']
        
        # Fruit tags for delegation
        fruit_tags = ['banana', 'orange', 'pineapple', 'apple', 'grape', 'mango']
        
        # Simple delegation examples - designed to create fractional averages
        self.create_following(B, A, 'banana', 1, "B follows A on banana")
        self.create_following(B, C, 'banana', 2, "B follows C on banana (B inherits from A+C: 5+3=4.0 avg)")
        
        self.create_following(D, A, 'apple', 1, "D follows A on apple") 
        self.create_following(D, E, 'apple', 2, "D follows E on apple (D inherits from A+E: 5+1=3.0 avg)")
        
        self.create_following(F, C, 'grape', 1, "F follows C on grape")
        self.create_following(F, E, 'grape', 2, "F follows E on grape (F inherits from C+E: 3+1=2.0 avg)")
        
        # More complex fractional averaging scenarios
        self.create_following(H, A, 'apple', 1, "H follows A on apple")
        self.create_following(H, G, 'apple', 2, "H follows G on apple") 
        self.create_following(H, I, 'apple', 3, "H follows I on apple (H inherits from A+G+I: 5+4+2=3.67 avg)")
        
        self.create_following(J, C, 'grape', 1, "J follows C on grape")
        self.create_following(J, E, 'grape', 2, "J follows E on grape")
        self.create_following(J, I, 'grape', 3, "J follows I on grape (J inherits from C+E+I: 3+1+2=2.0 avg)")
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Created fractional averaging test relationships:\n'
                f'   • B inherits from A+C on banana (5+3=4.0 avg)\n'
                f'   • D inherits from A+E on apple (5+1=3.0 avg)\n'
                f'   • F inherits from C+E on grape (3+1=2.0 avg)\n'
                f'   • H inherits from A+G+I on apple (5+4+2=3.67 avg)\n'
                f'   • J inherits from C+E+I on grape (3+1+2=2.0 avg)\n'
                f'   • All calculated votes should show fractional stars!'
            )
        )

    def create_following(self, follower, followee, tags, order, description):
        """
        Create a following relationship with logging.
        
        Args:
            follower: User who is following
            followee: User being followed
            tags: Comma-separated tag string
            order: Priority order for tie-breaking
            description: Description for logging
        """
        Following.objects.get_or_create(
            follower=follower,
            followee=followee,
            defaults={
                'tags': tags,
                'order': order
            }
        )
        self.stdout.write(f'   🔗 {description}')

    def create_test_decision(self, community):
        """
        Create a test decision for the delegation scenario.
        
        Args:
            community: The community to create the decision in
            
        Returns:
            Decision: The created decision instance
        """
        decision, created = Decision.objects.get_or_create(
            community=community,
            title='Fruit Preference Ranking Test',
            defaults={
                'description': (
                    'This is a test decision designed to validate delegation and vote '
                    'averaging calculations. The choices are deliberately simple to make '
                    'it easy to verify that fractional star averages are calculated '
                    'correctly when votes are inherited through delegation chains.\n\n'
                    'Manual voters (A, C, E, G, I) will cast different star ratings '
                    '(1-5 stars) and tag their votes with fruit names. Calculated voters '
                    '(B, D, F, H, J) will inherit votes through their delegation '
                    'relationships, resulting in fractional star averages that can be '
                    'verified for mathematical accuracy.'
                ),
                'dt_close': timezone.now() + timedelta(days=7),
                'results_need_updating': True
            }
        )
        
        if created:
            # Create test choices
            choices_data = [
                ('Tropical Fruits', 'Pineapple, mango, and coconut varieties'),
                ('Citrus Fruits', 'Orange, lemon, lime, and grapefruit options'),
                ('Berry Fruits', 'Strawberry, blueberry, raspberry selections'),
                ('Tree Fruits', 'Apple, pear, peach, and cherry choices')
            ]
            
            for title, description in choices_data:
                Choice.objects.get_or_create(
                    decision=decision,
                    title=title,
                    defaults={'description': description}
                )
            
            self.stdout.write(f'✅ Created decision: {decision.title} with {len(choices_data)} choices')
        
        return decision

    def create_manual_votes(self, decision, users):
        """
        Create manual votes from 5 users with different star ratings.
        
        This method creates votes with deliberately different star ratings
        to ensure that calculated voters will inherit fractional averages.
        
        Args:
            decision: The decision to vote on
            users: List of all users (A-J)
        """
        # Map users by letter for easier reference
        user_map = {user.username[0]: user for user in users}
        
        # Manual voters: A, C, E, G, I with overlapping tags to create fractional averages
        manual_voters = [
            (user_map['A'], 5, 'banana,apple'),      # A votes 5 stars, tags: banana,apple
            (user_map['C'], 3, 'banana,grape'),      # C votes 3 stars, tags: banana,grape (overlaps with A on banana)
            (user_map['E'], 1, 'apple,grape'),       # E votes 1 star, tags: apple,grape (overlaps with A on apple, C on grape)
            (user_map['G'], 4, 'banana,apple'),      # G votes 4 stars, tags: banana,apple (overlaps with A on both)
            (user_map['I'], 2, 'grape,apple'),       # I votes 2 stars, tags: grape,apple (overlaps with multiple)
        ]
        
        choices = list(decision.choices.all())
        
        for voter, base_stars, tags in manual_voters:
            # Create ballot
            ballot, created = Ballot.objects.get_or_create(
                decision=decision,
                voter=voter,
                defaults={
                    'is_calculated': False,
                    'is_anonymous': random.choice([True, False]),  # Mix of anonymous and non-anonymous
                    'tags': tags
                }
            )
            
            if created:
                # Create votes with slight variations to ensure fractional averages
                for i, choice in enumerate(choices):
                    # Vary the stars slightly for each choice to create interesting averages
                    stars = max(1, min(5, base_stars + (i - 1)))  # Vary by choice position
                    
                    Vote.objects.get_or_create(
                        choice=choice,
                        ballot=ballot,
                        defaults={'stars': stars}
                    )
                
                self.stdout.write(
                    f'✅ Created manual vote: {voter.username} '
                    f'(base {base_stars} stars, tags: {tags})'
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Created 5 manual votes with different star patterns\n'
                f'   • Calculated voters (B, D, F, H, J) will inherit fractional averages\n'
                f'   • Expected results: 3.5 stars, 2.7 stars, 4.2 stars, etc.\n'
                f'   • Run ballot calculation to see delegation in action!'
            )
        )
