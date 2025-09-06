import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from accounts.models import Following
from democracy.models import Community, Membership

User = get_user_model()


class Command(BaseCommand):
    help = 'Generate realistic dummy data for CrowdVote development and testing'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users-per-community',
            type=int,
            default=100,
            help='Number of users per community (default: 100)'
        )

    def handle(self, *args, **options):
        users_per_community = options['users_per_community']
        
        self.stdout.write(
            self.style.SUCCESS(f'Generating dummy data with {users_per_community} users per community...')
        )

        # Create communities
        communities = self.create_communities()
        
        # Create users for each community
        all_users = []
        for community in communities:
            users = self.create_users_for_community(community, users_per_community)
            all_users.extend(users)
        
        # Create following relationships (simplified without tags for now)
        self.create_following_relationships(all_users)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully generated dummy data:\n'
                f'- {len(communities)} communities\n'
                f'- {len(all_users)} users\n'
                f'- Following relationships with multi-level delegation chains'
            )
        )

    def create_communities(self):
        """Create the two test communities."""
        communities_data = [
            {
                'name': 'Minion Collective',
                'description': 'A democratic community of Minions making daily decisions about bananas, lunch choices, and world domination plans. Features the classic Minion hierarchy with Kevin, Stuart, and Bob as natural leaders.'
            },
            {
                'name': 'Springfield Town Council',
                'description': 'The municipal government of Springfield, where citizens participate in local democracy. From nuclear plant safety to donut shop regulations, every decision matters in this quirky American town.'
            }
        ]
        
        communities = []
        for data in communities_data:
            community, created = Community.objects.get_or_create(
                name=data['name'],
                defaults={'description': data['description']}
            )
            if created:
                self.stdout.write(f'Created community: {community.name}')
            else:
                self.stdout.write(f'Community already exists: {community.name}')
            communities.append(community)
        
        return communities

    def create_users_for_community(self, community, count):
        """Create users and memberships for a community."""
        if community.name == 'Minion Collective':
            users = self.create_minion_users(count)
        else:  # Springfield Town Council
            users = self.create_springfield_users(count)
        
        # Create memberships
        for i, user in enumerate(users):
            # First 10% are community managers
            is_manager = i < count * 0.1
            # 80% are voting members, 20% are lobbyists
            is_voter = i < count * 0.8
            # Random anonymity preference
            is_anonymous = random.choice([True, True, True, False])  # 75% prefer anonymity
            
            membership, created = Membership.objects.get_or_create(
                member=user,
                community=community,
                defaults={
                    'is_community_manager': is_manager,
                    'is_voting_community_member': is_voter,
                    'is_anonymous_by_default': is_anonymous,
                }
            )
            
            if created:
                self.stdout.write(f'Added {user.username} to {community.name}')
        
        return users

    def create_minion_users(self, count):
        """Create Minion-themed users."""
        # Famous Minions
        famous_minions = [
            ('kevin_minion', 'Kevin', 'Minion', 'kevin@minions.com'),
            ('stuart_minion', 'Stuart', 'Minion', 'stuart@minions.com'),
            ('bob_minion', 'Bob', 'Minion', 'bob@minions.com'),
            ('jerry_minion', 'Jerry', 'Minion', 'jerry@minions.com'),
            ('dave_minion', 'Dave', 'Minion', 'dave@minions.com'),
            ('carl_minion', 'Carl', 'Minion', 'carl@minions.com'),
            ('phil_minion', 'Phil', 'Minion', 'phil@minions.com'),
            ('tim_minion', 'Tim', 'Minion', 'tim@minions.com'),
        ]
        
        # Minion name patterns
        minion_names = [
            'banana', 'yellow', 'goggles', 'overalls', 'gru', 'despicable',
            'bello', 'poopaye', 'tulaliloo', 'gelato', 'papoy', 'tank',
            'bee', 'fire', 'bottom', 'papaya', 'potato', 'toy'
        ]
        
        users = []
        
        # Create famous minions first
        for username, first_name, last_name, email in famous_minions[:min(8, count)]:
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
        
        # Create additional minions
        for i in range(len(users), count):
            name1 = random.choice(minion_names)
            name2 = random.choice(minion_names)
            username = f'{name1}_{name2}_{i}'
            
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': name1.title(),
                    'last_name': name2.title(),
                    'email': f'{username}@minions.com',
                    'is_active': True,
                }
            )
            users.append(user)
        
        return users

    def create_springfield_users(self, count):
        """Create Springfield-themed users."""
        # Famous Springfield residents
        famous_residents = [
            ('homer_simpson', 'Homer', 'Simpson', 'homer@springfield.gov'),
            ('marge_simpson', 'Marge', 'Simpson', 'marge@springfield.gov'),
            ('lisa_simpson', 'Lisa', 'Simpson', 'lisa@springfield.gov'),
            ('bart_simpson', 'Bart', 'Simpson', 'bart@springfield.gov'),
            ('ned_flanders', 'Ned', 'Flanders', 'ned@springfield.gov'),
            ('moe_szyslak', 'Moe', 'Szyslak', 'moe@springfield.gov'),
            ('chief_wiggum', 'Chief', 'Wiggum', 'chief@springfield.gov'),
            ('apu_nahasapeemapetilon', 'Apu', 'Nahasapeemapetilon', 'apu@springfield.gov'),
        ]
        
        # Springfield name patterns
        first_names = [
            'Homer', 'Marge', 'Bart', 'Lisa', 'Maggie', 'Ned', 'Moe', 'Barney',
            'Carl', 'Lenny', 'Apu', 'Chief', 'Lou', 'Eddie', 'Selma', 'Patty',
            'Milhouse', 'Nelson', 'Ralph', 'Martin', 'Jimbo', 'Dolph', 'Kearney'
        ]
        
        last_names = [
            'Simpson', 'Flanders', 'Wiggum', 'Van Houten', 'Muntz', 'Prince',
            'Szyslak', 'Gumble', 'Carlson', 'Leonard', 'Nahasapeemapetilon',
            'Bouvier', 'Lovejoy', 'Krabappel', 'Skinner', 'Burns', 'Smithers'
        ]
        
        users = []
        
        # Create famous residents first
        for username, first_name, last_name, email in famous_residents[:min(8, count)]:
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
        
        # Create additional residents
        for i in range(len(users), count):
            first_name = random.choice(first_names)
            last_name = random.choice(last_names)
            username = f'{first_name.lower()}_{last_name.lower()}_{i}'
            
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'email': f'{username}@springfield.gov',
                    'is_active': True,
                }
            )
            users.append(user)
        
        return users

    def create_following_relationships(self, all_users):
        """Create realistic following relationships (simplified without tags for now)."""
        # Get community-specific users
        minion_users = [u for u in all_users if 'minion' in u.username or any(
            name in u.username for name in ['banana', 'yellow', 'kevin', 'stuart', 'bob']
        )]
        springfield_users = [u for u in all_users if u not in minion_users]
        
        # Create following relationships for each community
        self.create_community_following(minion_users, 'Minion')
        self.create_community_following(springfield_users, 'Springfield')
        
        # Create some cross-community following (10% chance)
        for user in all_users:
            if random.random() < 0.1:  # 10% chance
                other_community_users = springfield_users if user in minion_users else minion_users
                if other_community_users:
                    followee = random.choice(other_community_users)
                    self.create_following_relationship(user, followee)

    def create_community_following(self, users, community_name):
        """Create following relationships within a community."""
        if not users:
            return
            
        # Identify leaders (first 5-10 users are natural leaders)
        leaders = users[:min(10, len(users) // 10)]
        regular_users = users[len(leaders):]
        
        # 60% of users follow 1-3 others directly (single-level)
        single_level_count = int(len(regular_users) * 0.6)
        single_level_users = regular_users[:single_level_count]
        
        for user in single_level_users:
            # Follow 1-3 people
            follow_count = random.randint(1, 3)
            potential_followees = [u for u in users if u != user]
            followees = random.sample(potential_followees, min(follow_count, len(potential_followees)))
            
            for followee in followees:
                self.create_following_relationship(user, followee)
        
        # 30% create 2-3 level delegation chains (multi-level)
        multi_level_count = int(len(regular_users) * 0.3)
        multi_level_users = regular_users[single_level_count:single_level_count + multi_level_count]
        
        for user in multi_level_users:
            # Create a chain: user -> intermediate -> leader
            if len(regular_users) > 1:
                intermediate = random.choice([u for u in regular_users if u != user])
                leader = random.choice(leaders)
                
                # User follows intermediate
                self.create_following_relationship(user, intermediate)
                
                # Intermediate follows leader (if not already)
                self.create_following_relationship(intermediate, leader)
        
        # 10% create complex patterns (remaining users)
        complex_users = regular_users[single_level_count + multi_level_count:]
        
        for user in complex_users:
            # Follow multiple people on different topics
            follow_count = random.randint(2, 4)
            potential_followees = [u for u in users if u != user]
            followees = random.sample(potential_followees, min(follow_count, len(potential_followees)))
            
            for followee in followees:
                self.create_following_relationship(user, followee)
        
        self.stdout.write(f'Created following relationships for {community_name} community')

    def create_following_relationship(self, follower, followee):
        """Create a following relationship, avoiding duplicates."""
        # Check if relationship already exists
        existing = Following.objects.filter(follower=follower, followee=followee).first()
        
        if not existing:
            # Create new relationship
            Following.objects.create(follower=follower, followee=followee)
