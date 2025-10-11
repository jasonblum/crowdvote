"""
Tests for follow/unfollow view functionality.

Tests the follow/unfollow UI system including forms, views, and HTMX responses.
"""

import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from democracy.models import Following
from security.forms import FollowForm
from tests.factories.user_factory import UserFactory

User = get_user_model()


class FollowViewsTestCase(TestCase):
    """Test follow/unfollow view functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.follower = UserFactory(username='follower_user')
        self.followee = UserFactory(username='followee_user')
        
    def test_follow_user_get_returns_modal(self):
        """Test GET request to follow_user returns modal template."""
        self.client.force_login(self.follower)
        
        response = self.client.get(
            reverse('accounts:follow_user', kwargs={'user_id': self.followee.id})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Follow')
        self.assertContains(response, self.followee.get_display_name())
        
    def test_follow_user_post_creates_following(self):
        """Test POST request creates following relationship."""
        self.client.force_login(self.follower)
        
        response = self.client.post(
            reverse('accounts:follow_user', kwargs={'user_id': self.followee.id}),
            data={
                'followee': self.followee.id,
                'tags': 'budget, environment',
                'order': 1
            }
        )
        
        # Should redirect on successful creation
        self.assertEqual(response.status_code, 302)
        
        # Verify following relationship was created
        following = Following.objects.get(
            follower=self.follower,
            followee=self.followee
        )
        self.assertEqual(following.tags, 'budget, environment')
        self.assertEqual(following.order, 1)
        
    def test_follow_user_htmx_post_returns_button(self):
        """Test HTMX POST request returns updated follow button."""
        self.client.force_login(self.follower)
        
        response = self.client.post(
            reverse('accounts:follow_user', kwargs={'user_id': self.followee.id}),
            data={
                'followee': self.followee.id,
                'tags': 'governance',
                'order': 1
            },
            HTTP_HX_REQUEST='true'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Following on: governance')
        
    def test_unfollow_user_removes_following(self):
        """Test unfollow removes following relationship."""
        # Create following relationship first
        Following.objects.create(
            follower=self.follower,
            followee=self.followee,
            tags='budget',
            order=1
        )
        
        self.client.force_login(self.follower)
        
        response = self.client.post(
            reverse('accounts:unfollow_user', kwargs={'user_id': self.followee.id})
        )
        
        self.assertEqual(response.status_code, 302)
        
        # Verify following relationship was deleted
        self.assertFalse(
            Following.objects.filter(
                follower=self.follower,
                followee=self.followee
            ).exists()
        )
        
    def test_cannot_follow_self(self):
        """Test user cannot follow themselves."""
        self.client.force_login(self.follower)
        
        response = self.client.get(
            reverse('accounts:follow_user', kwargs={'user_id': self.follower.id})
        )
        
        self.assertEqual(response.status_code, 302)  # Should redirect
        
    def test_edit_follow_returns_modal_with_current_values(self):
        """Test edit follow returns modal with existing values."""
        # Create following relationship first
        following = Following.objects.create(
            follower=self.follower,
            followee=self.followee,
            tags='environment, safety',
            order=2
        )
        
        self.client.force_login(self.follower)
        
        response = self.client.get(
            reverse('accounts:edit_follow', kwargs={'user_id': self.followee.id})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'environment, safety')
        self.assertContains(response, 'value="2"')  # Order field
        
    def test_follow_form_tag_cleaning(self):
        """Test FollowForm properly cleans and validates tags."""
        form = FollowForm(data={
            'followee': self.followee.id,
            'tags': '  Budget , Environment,  governance  ',
            'order': 1
        }, followee=self.followee)
        
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['tags'], 'budget, environment, governance')
        
    def test_follow_form_max_tags_validation(self):
        """Test FollowForm validates maximum number of tags."""
        too_many_tags = ', '.join([f'tag{i}' for i in range(15)])  # 15 tags
        
        form = FollowForm(data={
            'followee': self.followee.id,
            'tags': too_many_tags,
            'order': 1
        }, followee=self.followee)
        
        self.assertFalse(form.is_valid())
        self.assertIn('Maximum 10 tags allowed', str(form.errors))


@pytest.mark.integration
class FollowIntegrationTestCase(TestCase):
    """Integration tests for follow functionality."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user1 = UserFactory(username='user1')
        self.user2 = UserFactory(username='user2')
        
        # Create shared community so users can see follow buttons
        from tests.factories.community_factory import CommunityFactory
        from tests.factories.user_factory import MembershipFactory
        self.community = CommunityFactory(name='Test Community')
        MembershipFactory(member=self.user1, community=self.community)
        MembershipFactory(member=self.user2, community=self.community)
        
    def test_member_profile_shows_follow_button(self):
        """Test member profile page shows follow button for other users."""
        self.client.force_login(self.user1)
        
        response = self.client.get(
            reverse('accounts:member_profile', kwargs={'username': self.user2.username})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'Follow {self.user2.get_display_name()}')
        
    def test_member_profile_shows_following_status(self):
        """Test member profile shows current following status."""
        # Create following relationship
        Following.objects.create(
            follower=self.user1,
            followee=self.user2,
            tags='budget',
            order=1
        )
        
        self.client.force_login(self.user1)
        
        response = self.client.get(
            reverse('accounts:member_profile', kwargs={'username': self.user2.username})
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Following on: budget')
