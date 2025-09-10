"""
Shared test fixtures and configuration for CrowdVote test suite.

This module provides common test fixtures used across all test modules,
including user creation, community setup, and database transactions.
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.utils import timezone
from datetime import timedelta

from accounts.models import Following, CommunityApplication  
from democracy.models import Community, Decision, Choice, Ballot, Vote, Membership
from crowdvote.models import BaseModel

User = get_user_model()


@pytest.fixture
def client():
    """Provide a Django test client."""
    return Client()


@pytest.fixture
def user_factory():
    """Factory function for creating users."""
    def create_user(username=None, email=None, **kwargs):
        if not username:
            username = f"testuser_{User.objects.count() + 1}"
        if not email:
            email = f"{username}@example.com"
        
        return User.objects.create_user(
            username=username,
            email=email,
            **kwargs
        )
    return create_user


@pytest.fixture
def community_factory():
    """Factory function for creating communities."""
    def create_community(name=None, **kwargs):
        if not name:
            name = f"Test Community {Community.objects.count() + 1}"
        
        defaults = {
            'description': f'Test description for {name}',
            'auto_approve_applications': True,
        }
        defaults.update(kwargs)
        
        return Community.objects.create(name=name, **defaults)
    return create_community


@pytest.fixture
def decision_factory():
    """Factory function for creating decisions."""
    def create_decision(community, title=None, **kwargs):
        if not title:
            title = f"Test Decision {Decision.objects.count() + 1}"
        
        defaults = {
            'description': f'Test description for {title}',
            'dt_close': timezone.now() + timedelta(days=7),
        }
        defaults.update(kwargs)
        
        return Decision.objects.create(
            community=community,
            title=title,
            **defaults
        )
    return create_decision


@pytest.fixture
def test_user(user_factory):
    """Create a standard test user."""
    return user_factory(username="testuser", email="test@example.com")


@pytest.fixture
def test_manager(user_factory):
    """Create a user with manager privileges."""
    return user_factory(username="manager", email="manager@example.com")


@pytest.fixture
def test_community(community_factory):
    """Create a standard test community."""
    return community_factory(name="Test Community")


@pytest.fixture
def community_with_members(test_community, test_user, test_manager):
    """Create a community with test members."""
    # Add manager
    Membership.objects.create(
        member=test_manager,
        community=test_community,
        is_voting_community_member=True,
        is_community_manager=True
    )
    
    # Add regular member
    Membership.objects.create(
        member=test_user,
        community=test_community,
        is_voting_community_member=True,
        is_community_manager=False
    )
    
    return test_community


@pytest.fixture
def test_decision(community_with_members, decision_factory):
    """Create a test decision with choices."""
    decision = decision_factory(
        community=community_with_members,
        title="Test Voting Decision"
    )
    
    # Add some choices
    Choice.objects.create(
        decision=decision,
        title="Option A",
        description="First test option"
    )
    Choice.objects.create(
        decision=decision,
        title="Option B", 
        description="Second test option"
    )
    Choice.objects.create(
        decision=decision,
        title="Option C",
        description="Third test option"
    )
    
    return decision


@pytest.fixture
def delegation_users(user_factory, test_community):
    """Create users with delegation relationships for testing."""
    # Create test users following the A-H pattern from AGENTS.md
    users = {}
    
    # User A: Manual voter with tags
    users['A'] = user_factory(username="A_testuser", email="a@example.com")
    
    # User B: Follows A on specific tags
    users['B'] = user_factory(username="B_testuser", email="b@example.com")
    
    # User C: Follows A on different tags
    users['C'] = user_factory(username="C_testuser", email="c@example.com")
    
    # User D: Follows C (creates chain D→C→A)
    users['D'] = user_factory(username="D_testuser", email="d@example.com")
    
    # User E: Follows C (creates chain E→C→A) 
    users['E'] = user_factory(username="E_testuser", email="e@example.com")
    
    # User F: Dual inheritance scenario
    users['F'] = user_factory(username="F_testuser", email="f@example.com")
    
    # Add all users to community as voting members
    for user in users.values():
        Membership.objects.create(
            member=user,
            community=test_community,
            is_voting_community_member=True,
            is_community_manager=False
        )
    
    # Set up delegation relationships
    Following.objects.create(
        follower=users['B'],
        followee=users['A'],
        tags="apple",
        order=1
    )
    
    Following.objects.create(
        follower=users['C'],
        followee=users['A'],
        tags="orange",
        order=1
    )
    
    Following.objects.create(
        follower=users['D'],
        followee=users['C'],
        tags="orange",
        order=1
    )
    
    Following.objects.create(
        follower=users['E'],
        followee=users['C'],
        tags="orange",
        order=1
    )
    
    Following.objects.create(
        follower=users['F'],
        followee=users['A'],
        tags="apple",
        order=1
    )
    
    Following.objects.create(
        follower=users['F'],
        followee=users['D'],
        tags="banana",
        order=2
    )
    
    return users


@pytest.fixture
def authenticated_client(client, test_user):
    """Provide an authenticated client."""
    client.force_login(test_user)
    return client


@pytest.fixture
def manager_client(client, test_manager):
    """Provide a client authenticated as a community manager."""
    client.force_login(test_manager)
    return client


# Database transaction fixtures
@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Enable database access for all tests.
    
    This fixture is automatically used for all tests, ensuring database
    access is available without needing to add @pytest.mark.django_db
    to each test function.
    """
    pass


@pytest.fixture
def transactional_db(transactional_db):
    """
    Provide transactional database access for tests that need it.
    
    Use this fixture for tests that need to test database transactions
    or use multiple threads.
    """
    pass
