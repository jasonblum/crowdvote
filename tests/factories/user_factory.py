"""
Factory classes for User-related models.

Provides factories for CustomUser, Following, and Membership models
with realistic test data generation.
"""

import factory
from factory.django import DjangoModelFactory
from faker import Faker
from django.contrib.auth import get_user_model

from accounts.models import Following
from democracy.models import Membership

fake = Faker()
User = get_user_model()


class UserFactory(DjangoModelFactory):
    """Factory for creating CustomUser instances."""
    
    class Meta:
        model = User
        django_get_or_create = ('username',)
    
    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    bio = factory.Faker('text', max_nb_chars=500)
    location = factory.Faker('city')
    website_url = factory.Faker('url')
    
    # Privacy settings (randomized)
    bio_public = factory.Faker('boolean', chance_of_getting_true=70)
    location_public = factory.Faker('boolean', chance_of_getting_true=60)
    social_links_public = factory.Faker('boolean', chance_of_getting_true=50)
    
    @factory.post_generation
    def social_links(obj, create, extracted, **kwargs):
        """Add realistic social media links, respecting explicitly set values."""
        if create:
            # Only set social links if they weren't explicitly provided (empty means explicitly set to empty)
            if not obj.twitter_url and fake.boolean(chance_of_getting_true=40):
                obj.twitter_url = f"https://twitter.com/{obj.username}"
            if not obj.linkedin_url and fake.boolean(chance_of_getting_true=30):
                obj.linkedin_url = f"https://linkedin.com/in/{obj.username}"
            obj.save()


class ManagerUserFactory(UserFactory):
    """Factory for creating users who will be community managers."""
    
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    bio = factory.LazyAttribute(lambda obj: f"Community manager and leader in democratic participation. Experienced in {fake.job()}.")
    bio_public = True


class LobbyistUserFactory(UserFactory):
    """Factory for creating users who will be lobbyists (non-voting)."""
    
    bio = factory.LazyAttribute(lambda obj: f"Subject matter expert specializing in {fake.job()}. Available for consultation on community decisions.")
    bio_public = True


class FollowingFactory(DjangoModelFactory):
    """Factory for creating Following relationships."""
    
    class Meta:
        model = Following
    
    follower = factory.SubFactory(UserFactory)
    followee = factory.SubFactory(UserFactory)
    tags = factory.Faker('words', nb=2, ext_word_list=['governance', 'budget', 'environment', 'safety', 'maintenance', 'social'])
    order = factory.Sequence(lambda n: n + 1)
    
    @factory.lazy_attribute
    def tags(self):
        """Generate realistic tag combinations."""
        tag_options = ['governance', 'budget', 'environment', 'safety', 'maintenance', 'social', 'infrastructure']
        num_tags = fake.random_int(min=1, max=3)
        selected_tags = fake.random_choices(tag_options, length=num_tags)
        return ','.join(selected_tags)


class SpecificFollowingFactory(FollowingFactory):
    """Factory for creating Following relationships with specific tags."""
    
    @classmethod
    def create_apple_following(cls, follower, followee, order=1):
        """Create following relationship for 'apple' tag."""
        return cls.create(
            follower=follower,
            followee=followee,
            tags="apple",
            order=order
        )
    
    @classmethod
    def create_orange_following(cls, follower, followee, order=1):
        """Create following relationship for 'orange' tag."""
        return cls.create(
            follower=follower,
            followee=followee,
            tags="orange",
            order=order
        )
    
    @classmethod
    def create_banana_following(cls, follower, followee, order=1):
        """Create following relationship for 'banana' tag."""
        return cls.create(
            follower=follower,
            followee=followee,
            tags="banana",
            order=order
        )


class MembershipFactory(DjangoModelFactory):
    """Factory for creating Membership relationships."""
    
    class Meta:
        model = Membership
    
    member = factory.SubFactory(UserFactory)
    # community will be set by the calling code
    is_voting_community_member = True
    is_community_manager = False
    is_anonymous_by_default = factory.Faker('boolean', chance_of_getting_true=30)


class ManagerMembershipFactory(MembershipFactory):
    """Factory for creating manager memberships."""
    
    member = factory.SubFactory(ManagerUserFactory)
    is_voting_community_member = True
    is_community_manager = True


class LobbyistMembershipFactory(MembershipFactory):
    """Factory for creating lobbyist memberships."""
    
    member = factory.SubFactory(LobbyistUserFactory)
    is_voting_community_member = False
    is_community_manager = False
