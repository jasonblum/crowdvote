"""
Tests specifically designed to improve coverage of accounts/models.py.

This test file focuses on testing untested code paths to increase coverage
rather than duplicating functionality tests.
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from collections import Counter

from tests.factories.user_factory import UserFactory
from tests.factories.community_factory import CommunityFactory
from tests.factories.decision_factory import DecisionFactory, BallotFactory
from accounts.models import Following, CommunityApplication

User = get_user_model()


@pytest.mark.models
class TestAccountsModelsCoverage(TestCase):
    """Tests to improve coverage of accounts/models.py functions."""
    
    def setUp(self):
        self.user = UserFactory(username="testuser")
        self.community = CommunityFactory(name="Test Community")
        
    def test_user_get_tag_usage_frequency_with_tags(self):
        """Test CustomUser get_tag_usage_frequency with tagged ballots - covers tag counting logic."""
        # Create a decision and some ballots with tags
        decision = DecisionFactory(community=self.community, with_choices=False)
        
        # Create ballots with different tags
        ballot1 = BallotFactory(
            decision=decision, 
            voter=self.user, 
            is_calculated=False,
            tags="governance,budget",
            with_votes=False
        )
        ballot2 = BallotFactory(
            decision=decision, 
            voter=self.user, 
            is_calculated=False,
            tags="governance,environment",
            with_votes=False
        )
        ballot3 = BallotFactory(
            decision=decision, 
            voter=self.user, 
            is_calculated=False,
            tags="governance",
            with_votes=False
        )
        
        # Get tag usage frequency
        tag_frequency = self.user.get_tag_usage_frequency()
        
        # Convert to dict for easier testing
        tag_dict = dict(tag_frequency)
        
        # "governance" should appear 3 times, others 1 time each
        self.assertEqual(tag_dict.get('governance'), 3)
        self.assertEqual(tag_dict.get('budget'), 1)
        self.assertEqual(tag_dict.get('environment'), 1)
        
    def test_user_get_tag_usage_frequency_empty_tags(self):
        """Test CustomUser get_tag_usage_frequency with empty tags - covers empty tag filtering."""
        # Create ballots with empty or no tags
        decision = DecisionFactory(community=self.community, with_choices=False)
        
        ballot1 = BallotFactory(
            decision=decision, 
            voter=self.user, 
            is_calculated=False,
            tags="",  # Empty string
            with_votes=False
        )
        ballot2 = BallotFactory(
            decision=decision, 
            voter=self.user, 
            is_calculated=False,
            tags=None,  # No tags
            with_votes=False
        )
        
        tag_frequency = self.user.get_tag_usage_frequency()
        
        # Should return empty list since no valid tags
        self.assertEqual(tag_frequency, [])
        
    def test_user_get_tag_usage_frequency_skip_calculated_ballots(self):
        """Test CustomUser get_tag_usage_frequency skips calculated ballots - covers manual ballot filtering."""
        decision = DecisionFactory(community=self.community, with_choices=False)
        
        # Create manual ballot (should be counted)
        manual_ballot = BallotFactory(
            decision=decision, 
            voter=self.user, 
            is_calculated=False,
            tags="governance",
            with_votes=False
        )
        
        # Create calculated ballot (should be skipped)
        calculated_ballot = BallotFactory(
            decision=decision, 
            voter=self.user, 
            is_calculated=True,
            tags="budget",
            with_votes=False
        )
        
        tag_frequency = self.user.get_tag_usage_frequency()
        tag_dict = dict(tag_frequency)
        
        # Only manual ballot tags should be counted
        self.assertEqual(tag_dict.get('governance'), 1)
        self.assertNotIn('budget', tag_dict)  # Calculated ballot tag should not appear
        
    def test_user_get_delegation_network_with_followers_and_following(self):
        """Test CustomUser get_delegation_network - covers delegation relationship extraction."""
        followee = UserFactory(username="followee")
        follower = UserFactory(username="follower")
        
        # Create following relationships
        Following.objects.create(
            follower=self.user,
            followee=followee,
            tags="governance,budget",
            order=1
        )
        Following.objects.create(
            follower=follower,
            followee=self.user,
            tags="environment",
            order=2
        )
        
        network = self.user.get_delegation_network()
        
        # Check following structure
        self.assertEqual(len(network['following']), 1)
        following_item = network['following'][0]
        self.assertEqual(following_item['user'], followee)
        self.assertEqual(following_item['tags'], ['governance', 'budget'])
        self.assertEqual(following_item['order'], 1)
        
        # Check followers structure
        self.assertEqual(len(network['followers']), 1)
        follower_item = network['followers'][0]
        self.assertEqual(follower_item['user'], follower)
        self.assertEqual(follower_item['tags'], ['environment'])
        self.assertEqual(follower_item['order'], 2)
        
    def test_user_get_delegation_network_no_tags(self):
        """Test CustomUser get_delegation_network with no tags - covers 'all topics' default."""
        followee = UserFactory(username="followee")
        
        # Create following with no tags
        Following.objects.create(
            follower=self.user,
            followee=followee,
            tags="",  # Empty tags
            order=1
        )
        
        network = self.user.get_delegation_network()
        
        following_item = network['following'][0]
        self.assertEqual(following_item['tags'], ['all topics'])
        
    def test_community_application_str_method(self):
        """Test CommunityApplication __str__ method - covers string representation."""
        application = CommunityApplication.objects.create(
            user=self.user,
            community=self.community,
            status='pending'
        )
        
        expected = f"{self.user.username} → {self.community.name} (pending)"
        self.assertEqual(str(application), expected)
        
    def test_community_application_is_pending_property(self):
        """Test CommunityApplication is_pending property - covers pending status check."""
        application = CommunityApplication.objects.create(
            user=self.user,
            community=self.community,
            status='pending'
        )
        
        self.assertTrue(application.is_pending)
        
        # Test with non-pending status
        application.status = 'approved'
        self.assertFalse(application.is_pending)
        
    def test_community_application_is_approved_property(self):
        """Test CommunityApplication is_approved property - covers approved status check."""
        application = CommunityApplication.objects.create(
            user=self.user,
            community=self.community,
            status='approved'
        )
        
        self.assertTrue(application.is_approved)
        
        # Test with non-approved status
        application.status = 'pending'
        self.assertFalse(application.is_approved)
        
    def test_community_application_can_be_reviewed_property(self):
        """Test CommunityApplication can_be_reviewed property - covers review eligibility."""
        application = CommunityApplication.objects.create(
            user=self.user,
            community=self.community,
            status='pending'
        )
        
        self.assertTrue(application.can_be_reviewed)
        
        # Test with reviewed status
        application.status = 'approved'
        self.assertFalse(application.can_be_reviewed)
        
    def test_community_application_reject_valid(self):
        """Test CommunityApplication reject method with valid status - covers rejection flow."""
        reviewer = UserFactory(username="reviewer")
        application = CommunityApplication.objects.create(
            user=self.user,
            community=self.community,
            status='pending'
        )
        
        application.reject(reviewer, "Insufficient qualifications")
        
        # Check status was updated
        self.assertEqual(application.status, 'rejected')
        self.assertEqual(application.reviewed_by, reviewer)
        self.assertEqual(application.reviewer_notes, "Insufficient qualifications")
        self.assertIsNotNone(application.reviewed_at)
        
    def test_community_application_reject_invalid_status(self):
        """Test CommunityApplication reject method with invalid status - covers error handling."""
        reviewer = UserFactory(username="reviewer")
        application = CommunityApplication.objects.create(
            user=self.user,
            community=self.community,
            status='approved'  # Cannot reject approved application
        )
        
        with self.assertRaises(ValueError) as cm:
            application.reject(reviewer, "Cannot reject")
            
        self.assertIn("Cannot reject application with status: approved", str(cm.exception))
        
    def test_community_application_withdraw_valid(self):
        """Test CommunityApplication withdraw method with valid status - covers withdrawal flow."""
        application = CommunityApplication.objects.create(
            user=self.user,
            community=self.community,
            status='pending'
        )
        
        application.withdraw()
        
        # Check status was updated
        self.assertEqual(application.status, 'withdrawn')
        
    def test_community_application_withdraw_invalid_status(self):
        """Test CommunityApplication withdraw method with invalid status - covers error handling."""
        application = CommunityApplication.objects.create(
            user=self.user,
            community=self.community,
            status='approved'  # Cannot withdraw approved application
        )
        
        with self.assertRaises(ValueError) as cm:
            application.withdraw()
            
        self.assertIn("Cannot withdraw application with status: approved", str(cm.exception))
        
    def test_following_model_str_method(self):
        """Test Following __str__ method - covers string representation."""
        followee = UserFactory(username="expert")
        following = Following.objects.create(
            follower=self.user,
            followee=followee,
            tags="governance",
            order=1
        )
        
        # Check string representation includes key information
        str_repr = str(following)
        self.assertIn(self.user.username, str_repr)
        self.assertIn(followee.username, str_repr)
        
    def test_user_get_avatar_value_method(self):
        """Test CustomUser get_avatar_value method - covers avatar generation."""
        # This method should return a string based on user ID for avatar generation
        avatar_value = self.user.get_avatar_value()
        
        # Should return a non-empty string
        self.assertIsInstance(avatar_value, str)
        self.assertGreater(len(avatar_value), 0)
        
    def test_user_get_avatar_html_method(self):
        """Test CustomUser get_avatar_html method - covers HTML avatar generation."""
        # Test with default size
        avatar_html = self.user.get_avatar_html()
        self.assertIn('svg', avatar_html)
        self.assertIn('jdenticon', avatar_html)
        
        # Test with custom size
        avatar_html_large = self.user.get_avatar_html(64)
        self.assertIn('width="64"', avatar_html_large)
        self.assertIn('height="64"', avatar_html_large)
        
    def test_user_get_display_name_with_full_name(self):
        """Test CustomUser get_display_name with full name - covers name preference logic."""
        user_with_name = UserFactory(
            username="jdoe",
            first_name="John",
            last_name="Doe"
        )
        
        display_name = user_with_name.get_display_name()
        self.assertEqual(display_name, "John Doe")
        
    def test_user_get_display_name_without_full_name(self):
        """Test CustomUser get_display_name without full name - covers username fallback."""
        user_no_name = UserFactory(
            username="jdoe",
            first_name="",
            last_name=""
        )
        
        display_name = user_no_name.get_display_name()
        self.assertEqual(display_name, "jdoe")
        
    def test_user_get_display_name_partial_name(self):
        """Test CustomUser get_display_name with partial name - covers mixed name scenarios."""
        user_partial = UserFactory(
            username="jdoe",
            first_name="John",
            last_name=""  # Only first name
        )
        
        display_name = user_partial.get_display_name()
        self.assertEqual(display_name, "John")
        
    def test_following_clean_method_validation(self):
        """Test Following clean method - covers validation logic."""
        followee = UserFactory(username="expert")
        following = Following(
            follower=self.user,
            followee=followee,
            tags="governance",
            order=1
        )
        
        # Should not raise exception for valid following
        try:
            following.clean()
        except ValidationError:
            self.fail("Following.clean() raised ValidationError unexpectedly")
            
    def test_following_with_empty_tags(self):
        """Test Following model with empty tags - covers empty tag handling."""
        followee = UserFactory(username="expert")
        following = Following.objects.create(
            follower=self.user,
            followee=followee,
            tags="",  # Empty tags
            order=1
        )
        
        self.assertEqual(following.tags, "")
        self.assertIsNotNone(following.id)  # Should save successfully
