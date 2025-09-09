"""
Tests for accounts app models.

This module tests the CustomUser, Following, and related model validations,
business logic, and constraints for the CrowdVote accounts system.
"""
import pytest
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from accounts.models import Following
from democracy.models import Membership, Community
from tests.factories import UserFactory, FollowingFactory, CommunityFactory, MembershipFactory

User = get_user_model()


@pytest.mark.models
class TestCustomUserModel:
    """Test CustomUser model validation and business logic."""
    
    def test_user_creation_with_defaults(self):
        """Test user creation with specific field values."""
        user = UserFactory(
            bio="",
            location="",
            website_url="",
            twitter_url="",
            linkedin_url="",
            bio_public=True,
            location_public=True,
            social_links_public=True
        )
        
        assert user.username is not None
        assert user.email is not None
        assert user.bio == ""
        assert user.location == ""
        assert user.website_url == ""
        assert user.twitter_url == ""
        assert user.linkedin_url == ""
        assert user.bio_public is True
        assert user.location_public is True
        assert user.social_links_public is True
    
    def test_user_string_representation(self):
        """Test user __str__ method returns username."""
        user = UserFactory(username="test_user")
        assert str(user) == "test_user"
    
    def test_get_display_name_with_full_name(self):
        """Test get_display_name returns full name when available."""
        user = UserFactory(first_name="John", last_name="Doe", username="johndoe")
        assert user.get_display_name() == "John Doe"
    
    def test_get_display_name_with_partial_name(self):
        """Test get_display_name with only first name."""
        user = UserFactory(first_name="John", last_name="", username="johndoe")
        assert user.get_display_name() == "John"
    
    def test_get_display_name_fallback_to_username(self):
        """Test get_display_name falls back to username when no name."""
        user = UserFactory(first_name="", last_name="", username="johndoe")
        assert user.get_display_name() == "johndoe"
    
    def test_avatar_generation_methods(self):
        """Test avatar HTML and value generation methods."""
        user = UserFactory()
        
        # Test avatar value generation (returns user ID as string)
        avatar_value = user.get_avatar_value()
        assert avatar_value == str(user.id)
        
        # Test avatar HTML generation
        avatar_html = user.get_avatar_html(size=32)
        assert 'data-jdenticon-value' in avatar_html
        assert f'"{user.id}"' in avatar_html
        assert 'width="32"' in avatar_html
        assert 'height="32"' in avatar_html
    
    def test_bio_validation_length(self):
        """Test bio field length validation.""" 
        user = UserFactory()
        # Bio should accept reasonable lengths (under 1000 chars)
        user.bio = "A" * 500
        # Skip password validation for this test
        user.full_clean(exclude=['password'])  # Should not raise
        
        # Bio should reject content over max_length of 1000
        user.bio = "A" * 1001
        with pytest.raises(ValidationError):
            user.full_clean(exclude=['password'])
    
    def test_url_field_validation(self):
        """Test URL field validation for social links."""
        user = UserFactory()
        
        # Valid URLs should pass
        user.website_url = "https://example.com"
        user.twitter_url = "https://twitter.com/username"
        user.linkedin_url = "https://linkedin.com/in/username"
        user.full_clean(exclude=['password'])  # Should not raise
        
        # Invalid URLs should fail
        user.website_url = "not-a-url"
        with pytest.raises(ValidationError):
            user.full_clean(exclude=['password'])


@pytest.mark.models
class TestFollowingModel:
    """Test Following model validation and business logic."""
    
    def test_following_creation(self):
        """Test basic following relationship creation."""
        follower = UserFactory()
        followee = UserFactory()
        
        following = FollowingFactory(
            follower=follower,
            followee=followee,
            tags="governance,budget",
            order=1
        )
        
        assert following.follower == follower
        assert following.followee == followee
        assert following.tags == "governance,budget"
        assert following.order == 1
    
    def test_following_string_representation(self):
        """Test Following __str__ method."""
        follower = UserFactory(username="alice")
        followee = UserFactory(username="bob")
        following = FollowingFactory(
            follower=follower,
            followee=followee,
            tags="governance"
        )
        
        expected = "alice follows bob"
        assert str(following) == expected
    
    def test_following_unique_constraint(self):
        """Test that follower-followee pairs must be unique."""
        follower = UserFactory()
        followee = UserFactory()
        
        # First following should work
        FollowingFactory(follower=follower, followee=followee)
        
        # Second following with same users should fail
        with pytest.raises(IntegrityError):
            FollowingFactory(follower=follower, followee=followee)
    
    def test_self_following_prevention(self):
        """Test that users cannot follow themselves."""
        user = UserFactory()
        
        following = Following(follower=user, followee=user)
        with pytest.raises(ValidationError):
            following.full_clean()
    
    def test_tag_cleaning_and_validation(self):
        """Test tag field cleaning and validation."""
        follower = UserFactory()
        followee = UserFactory()
        
        # Tags should be cleaned and normalized
        following = FollowingFactory(
            follower=follower,
            followee=followee,
            tags="  governance , budget,  environment  "
        )
        
        # Should be cleaned of extra spaces
        expected_tags = "governance,budget,environment"
        assert following.tags == expected_tags
    
    def test_order_validation(self):
        """Test order field validation."""
        follower = UserFactory()
        followee = UserFactory()
        
        # Valid order should work
        following = FollowingFactory(
            follower=follower,
            followee=followee,
            order=5
        )
        following.full_clean()  # Should not raise
        
        # Order should be positive
        following.order = 0
        with pytest.raises(ValidationError):
            following.full_clean()
        
        following.order = -1
        with pytest.raises(ValidationError):
            following.full_clean()
    
    def test_following_with_empty_tags(self):
        """Test following with empty tags (general following)."""
        follower = UserFactory()
        followee = UserFactory()
        
        following = FollowingFactory(
            follower=follower,
            followee=followee,
            tags=""  # Empty tags means follow on all topics
        )
        
        assert following.tags == ""
        following.full_clean()  # Should not raise


@pytest.mark.models
class TestMembershipIntegration:
    """Test integration between User and Membership models."""
    
    def test_user_membership_creation(self):
        """Test creating membership relationships."""
        user = UserFactory()
        community = CommunityFactory()
        
        membership = MembershipFactory(
            member=user,
            community=community,
            is_voting_community_member=True,
            is_community_manager=False
        )
        
        assert membership.member == user
        assert membership.community == community
        assert membership.is_voting_community_member is True
        assert membership.is_community_manager is False
    
    def test_membership_unique_constraint(self):
        """Test that user can only have one membership per community."""
        user = UserFactory()
        community = CommunityFactory()
        
        # First membership should work
        MembershipFactory(member=user, community=community)
        
        # Second membership for same user/community should fail
        with pytest.raises(IntegrityError):
            MembershipFactory(member=user, community=community)
    
    def test_user_can_join_multiple_communities(self):
        """Test that user can be member of multiple communities."""
        user = UserFactory()
        community1 = CommunityFactory()
        community2 = CommunityFactory()
        
        membership1 = MembershipFactory(member=user, community=community1)
        membership2 = MembershipFactory(member=user, community=community2)
        
        assert membership1.member == user
        assert membership2.member == user
        assert membership1.community != membership2.community


@pytest.mark.models 
class TestModelPermissionsAndRoles:
    """Test model-level permission and role logic."""
    
    def test_manager_permissions(self):
        """Test community manager role permissions."""
        user = UserFactory()
        community = CommunityFactory()
        
        # Create manager membership
        membership = MembershipFactory(
            member=user,
            community=community,
            is_voting_community_member=True,
            is_community_manager=True
        )
        
        assert membership.is_community_manager is True
        assert membership.is_voting_community_member is True  # Managers are also voters
    
    def test_lobbyist_permissions(self):
        """Test lobbyist role permissions."""
        user = UserFactory()
        community = CommunityFactory()
        
        # Create lobbyist membership  
        membership = MembershipFactory(
            member=user,
            community=community,
            is_voting_community_member=False,  # Lobbyists don't vote
            is_community_manager=False
        )
        
        assert membership.is_community_manager is False
        assert membership.is_voting_community_member is False
    
    def test_regular_voter_permissions(self):
        """Test regular voting member permissions."""
        user = UserFactory()
        community = CommunityFactory()
        
        # Create regular voter membership
        membership = MembershipFactory(
            member=user,
            community=community,
            is_voting_community_member=True,
            is_community_manager=False
        )
        
        assert membership.is_community_manager is False
        assert membership.is_voting_community_member is True
