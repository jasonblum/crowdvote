"""
Factory classes for Community-related models.

Provides factories for Community models with realistic test data generation
and member population.
"""

import factory
from factory.django import DjangoModelFactory
from faker import Faker

from democracy.models import Community
# User factory imports handled in methods to avoid circular imports

fake = Faker()


class CommunityFactory(DjangoModelFactory):
    """Factory for creating Community instances."""
    
    class Meta:
        model = Community
        skip_postgeneration_save = True
    
    name = factory.Faker('company')
    description = factory.Faker('text', max_nb_chars=1000)
    # auto_approve_applications uses model default (False) unless explicitly set
    
    @factory.post_generation
    def with_members(obj, create, extracted, **kwargs):
        """Optionally populate community with members."""
        if not create or not extracted:
            return
        
        from .user_factory import MembershipFactory, ManagerMembershipFactory, LobbyistMembershipFactory
        
        # Create manager
        manager_membership = ManagerMembershipFactory(community=obj)
        
        # Create regular voting members
        num_voters = extracted.get('num_voters', 10)
        for _ in range(num_voters):
            MembershipFactory(community=obj)
        
        # Create lobbyists
        num_lobbyists = extracted.get('num_lobbyists', 3)
        for _ in range(num_lobbyists):
            LobbyistMembershipFactory(community=obj)


class MinionCommunityFactory(CommunityFactory):
    """Factory for creating Minion-themed test community."""
    
    name = "Minion Collective"
    description = "A community of loyal minions working together for world domination and banana management."
    auto_approve_applications = True  # Demo community
    
    @factory.post_generation
    def create_minion_members(obj, create, extracted, **kwargs):
        """Create minion-themed users."""
        if not create:
            return
        
        minion_names = ['Kevin', 'Stuart', 'Bob', 'Jerry', 'Phil', 'Tim', 'Mark', 'Dave']
        
        from .user_factory import UserFactory, MembershipFactory
        
        for i, name in enumerate(minion_names):
            user = UserFactory(
                username=f"{name.lower()}_minion",
                first_name=name,
                last_name="Minion",
                email=f"{name.lower()}@minions.com"
            )
            
            # First user is manager
            is_manager = (i == 0)
            MembershipFactory(
                community=obj,
                member=user,
                is_community_manager=is_manager
            )


class SpringfieldCommunityFactory(CommunityFactory):
    """Factory for creating Springfield-themed test community."""
    
    name = "Springfield Town Council"
    description = "Democratic decision-making for the citizens of Springfield."
    auto_approve_applications = True  # Demo community
    
    @factory.post_generation
    def create_simpson_members(obj, create, extracted, **kwargs):
        """Create Simpson-themed users."""
        if not create:
            return
        
        characters = [
            ('Homer', 'Simpson'), ('Marge', 'Simpson'), ('Lisa', 'Simpson'),
            ('Bart', 'Simpson'), ('Ned', 'Flanders'), ('Moe', 'Szyslak'),
            ('Barney', 'Gumble'), ('Apu', 'Nahasapeemapetilon')
        ]
        
        from .user_factory import UserFactory, MembershipFactory
        
        for i, (first, last) in enumerate(characters):
            user = UserFactory(
                username=f"{first.lower()}_{last.lower()}",
                first_name=first,
                last_name=last,
                email=f"{first.lower()}.{last.lower()}@springfield.com"
            )
            
            # First user is manager
            is_manager = (i == 0)
            MembershipFactory(
                community=obj,
                member=user,
                is_community_manager=is_manager
            )


class TestCommunityWithDelegationFactory(CommunityFactory):
    """Factory for creating communities with A-H delegation pattern."""
    
    name = "Test Delegation Community"
    description = "Community specifically designed for testing delegation algorithms."
    
    @factory.post_generation
    def create_delegation_users(obj, create, extracted, **kwargs):
        """Create users with A-H delegation pattern from AGENTS.md."""
        if not create:
            return
        
        from .user_factory import UserFactory, MembershipFactory, SpecificFollowingFactory
        
        users = {}
        
        # Create test users A-H with unique names per community
        community_suffix = str(obj.id)[-6:]  # Use last 6 chars of UUID for uniqueness
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']:
            user = UserFactory(
                username=f"{letter}_delegationtest_{community_suffix}",
                first_name=f"User {letter}",
                last_name=f"DelegationTest-{community_suffix}",
                email=f"{letter.lower()}.{community_suffix}@delegationtest.com"
            )
            users[letter] = user
            
            # Add to community
            MembershipFactory(
                community=obj,
                member=user,
                is_community_manager=(letter == 'A')  # A is manager
            )
        
        # Set up delegation relationships per AGENTS.md pattern
        # B follows A on apple tag
        SpecificFollowingFactory.create_apple_following(
            follower=users['B'], followee=users['A'], order=1
        )
        
        # C follows A on orange tag
        SpecificFollowingFactory.create_orange_following(
            follower=users['C'], followee=users['A'], order=1
        )
        
        # D follows C on orange tag (creates D→C→A chain)
        SpecificFollowingFactory.create_orange_following(
            follower=users['D'], followee=users['C'], order=1
        )
        
        # E follows C on orange tag (creates E→C→A chain)
        SpecificFollowingFactory.create_orange_following(
            follower=users['E'], followee=users['C'], order=1
        )
        
        # F follows A on apple tag
        SpecificFollowingFactory.create_apple_following(
            follower=users['F'], followee=users['A'], order=1
        )
        
        # F also follows D on banana tag (creates dual inheritance)
        SpecificFollowingFactory.create_banana_following(
            follower=users['F'], followee=users['D'], order=2
        )
        
        # Store users on the community object for easy access
        obj._delegation_users = users
        return users
