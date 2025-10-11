"""
Comprehensive test coverage for Follow/Unfollow UI functionality from Plan #17.

This test file focuses on achieving 100% coverage of the follow/unfollow views
and related functionality, including edge cases, error conditions, and HTMX interactions.
"""

import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.http import Http404

from democracy.models import Following
from security.forms import FollowForm
from democracy.models import Community, Membership
from tests.factories.user_factory import UserFactory, MembershipFactory
from tests.factories.community_factory import CommunityFactory

User = get_user_model()


class FollowViewsComprehensiveTestCase(TestCase):
    """Comprehensive test coverage for follow/unfollow views."""
    
    def setUp(self):
        """Set up test data for follow/unfollow testing."""
        self.client = Client()
        self.user = UserFactory(username="follower_user")
        self.followee = UserFactory(username="followee_user")
        self.community = CommunityFactory()
        
        # Create memberships so users can see each other
        MembershipFactory(community=self.community, member=self.user)
        MembershipFactory(community=self.community, member=self.followee)
        
        self.client.force_login(self.user)
    
    def test_follow_user_get_returns_modal(self):
        """Test GET request to follow_user returns follow modal."""
        url = reverse('accounts:follow_user', kwargs={'user_id': self.followee.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'form')
        self.assertContains(response, 'followee')
        self.assertIsInstance(response.context['form'], FollowForm)
        self.assertEqual(response.context['followee'], self.followee)
    
    def test_follow_user_get_nonexistent_user_404(self):
        """Test GET request with nonexistent user returns 404."""
        url = reverse('accounts:follow_user', kwargs={'user_id': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
    
    def test_follow_user_post_valid_creates_following(self):
        """Test POST request with valid data creates following relationship."""
        url = reverse('accounts:follow_user', kwargs={'user_id': self.followee.id})
        data = {
            'followee': self.followee.id,
            'tags': 'governance, budget',
            'order': 1
        }
        response = self.client.post(url, data)
        
        # Should redirect to member profile
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('accounts:member_profile', kwargs={'username': self.followee.username}))
        
        # Following should be created
        self.assertTrue(Following.objects.filter(follower=self.user, followee=self.followee).exists())
        following = Following.objects.get(follower=self.user, followee=self.followee)
        # Tags are cleaned by form (lowercase, formatted)
        self.assertEqual(following.tags, 'governance, budget')
        self.assertEqual(following.order, 1)
        
        # Success message should be present
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Now following" in str(message) for message in messages))
    
    def test_follow_user_post_update_existing_following(self):
        """Test POST request updates existing following relationship."""
        # Create existing following
        Following.objects.create(
            follower=self.user,
            followee=self.followee,
            tags='old_tag',
            order=1
        )
        
        url = reverse('accounts:follow_user', kwargs={'user_id': self.followee.id})
        data = {
            'followee': self.followee.id,
            'tags': 'new_tag, another_tag',
            'order': 2
        }
        response = self.client.post(url, data)
        
        # Should redirect to member profile
        self.assertEqual(response.status_code, 302)
        
        # Following should be updated
        following = Following.objects.get(follower=self.user, followee=self.followee)
        self.assertEqual(following.tags, 'new_tag, another_tag')
        self.assertEqual(following.order, 2)
        
        # Update message should be present
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Updated" in str(message) for message in messages))
    
    def test_follow_user_post_invalid_form_redirects_with_error(self):
        """Test POST request with invalid form data handles errors."""
        url = reverse('accounts:follow_user', kwargs={'user_id': self.followee.id})
        data = {
            'tags': '',  # Empty tags should be invalid
            'order': 'invalid'  # Invalid order
        }
        response = self.client.post(url, data)
        
        # Should redirect back to member profile
        self.assertEqual(response.status_code, 302)
        
        # No following should be created
        self.assertFalse(Following.objects.filter(follower=self.user, followee=self.followee).exists())
    
    def test_follow_user_htmx_post_valid_form_creates_following(self):
        """Test HTMX POST request with valid form creates following."""
        url = reverse('accounts:follow_user', kwargs={'user_id': self.followee.id})
        data = {
            'followee': self.followee.id,
            'tags': 'governance',
            'order': 1
        }
        response = self.client.post(url, data, HTTP_HX_REQUEST='true')
        
        # Should create following relationship
        following = Following.objects.get(follower=self.user, followee=self.followee)
        self.assertEqual(following.tags, 'governance')
        self.assertEqual(following.order, 1)
    
    def test_follow_user_htmx_post_invalid_form_returns_modal_with_errors(self):
        """Test HTMX POST with invalid form returns modal with errors."""
        url = reverse('accounts:follow_user', kwargs={'user_id': self.followee.id})
        data = {
            'tags': '',  # Invalid empty tags
            'order': 1
        }
        response = self.client.post(url, data, HTTP_HX_REQUEST='true')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'form')
        self.assertContains(response, 'followee')
        # Form should have errors
        self.assertTrue(response.context['form'].errors)
    
    def test_follow_user_self_following_prevention(self):
        """Test that users cannot follow themselves."""
        url = reverse('accounts:follow_user', kwargs={'user_id': self.user.id})
        response = self.client.get(url)
        
        # Should redirect to member profile with error message
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('accounts:member_profile', kwargs={'username': self.user.username}))
        
        # Error message should be present
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("cannot follow yourself" in str(message) for message in messages))
    
    def test_unfollow_user_removes_following(self):
        """Test unfollow_user removes following relationship."""
        # Create following to remove
        Following.objects.create(
            follower=self.user,
            followee=self.followee,
            tags='governance',
            order=1
        )
        
        url = reverse('accounts:unfollow_user', kwargs={'user_id': self.followee.id})
        response = self.client.post(url)
        
        # Should redirect to member profile
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('accounts:member_profile', kwargs={'username': self.followee.username}))
        
        # Following should be deleted
        self.assertFalse(Following.objects.filter(follower=self.user, followee=self.followee).exists())
        
        # Success message should be present
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("Stopped following" in str(message) for message in messages))
    
    def test_unfollow_user_htmx_removes_following(self):
        """Test HTMX unfollow request removes following relationship."""
        # Create following to remove
        Following.objects.create(
            follower=self.user,
            followee=self.followee,
            tags='governance',
            order=1
        )
        
        url = reverse('accounts:unfollow_user', kwargs={'user_id': self.followee.id})
        response = self.client.post(url, HTTP_HX_REQUEST='true')
        
        self.assertEqual(response.status_code, 200)
        # Following should be deleted
        self.assertFalse(Following.objects.filter(follower=self.user, followee=self.followee).exists())
    
    def test_unfollow_user_not_following_error(self):
        """Test unfollow when not following returns error message."""
        url = reverse('accounts:unfollow_user', kwargs={'user_id': self.followee.id})
        response = self.client.post(url)
        
        # Should redirect to member profile
        self.assertEqual(response.status_code, 302)
        
        # Error message should be present
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("not following this user" in str(message) for message in messages))
    
    def test_unfollow_user_nonexistent_user_404(self):
        """Test unfollow with nonexistent user returns 404."""
        url = reverse('accounts:unfollow_user', kwargs={'user_id': 99999})
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
    
    def test_edit_follow_get_returns_modal_with_current_values(self):
        """Test edit_follow GET returns modal with current following values."""
        # Create following to edit
        following = Following.objects.create(
            follower=self.user,
            followee=self.followee,
            tags='governance, budget',
            order=2
        )
        
        url = reverse('accounts:edit_follow', kwargs={'user_id': self.followee.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'form')
        self.assertContains(response, 'followee')
        self.assertContains(response, 'Edit Following')  # Check for actual text in template
        
        # Form should have current values
        form = response.context['form']
        self.assertEqual(form.initial['tags'], 'governance, budget')
        self.assertEqual(form.initial['order'], 2)
        self.assertTrue(response.context.get('editing', False))
    
    def test_edit_follow_not_following_error(self):
        """Test edit_follow when not following returns error."""
        url = reverse('accounts:edit_follow', kwargs={'user_id': self.followee.id})
        response = self.client.get(url)
        
        # Should redirect to member profile
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('accounts:member_profile', kwargs={'username': self.followee.username}))
        
        # Error message should be present
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any("not following this user" in str(message) for message in messages))
    
    def test_edit_follow_nonexistent_user_404(self):
        """Test edit_follow with nonexistent user returns 404."""
        url = reverse('accounts:edit_follow', kwargs={'user_id': 99999})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
    
    def test_edit_follow_post_redirects_to_follow_user(self):
        """Test edit_follow POST redirects to follow_user for processing."""
        # Create following to edit
        Following.objects.create(
            follower=self.user,
            followee=self.followee,
            tags='governance',
            order=1
        )
        
        url = reverse('accounts:edit_follow', kwargs={'user_id': self.followee.id})
        response = self.client.post(url, {'tags': 'new_tags', 'order': 2})
        
        # Should redirect to follow_user
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('accounts:follow_user', kwargs={'user_id': self.followee.id}))


class MemberProfileViewComprehensiveTestCase(TestCase):
    """Comprehensive test coverage for member profile view."""
    
    def setUp(self):
        """Set up test data for member profile testing."""
        self.client = Client()
        self.user = UserFactory(username="viewer_user")
        self.member = UserFactory(username="profile_member")
        self.community1 = CommunityFactory(name="Community 1")
        self.community2 = CommunityFactory(name="Community 2")
        
        # Create memberships
        MembershipFactory(community=self.community1, member=self.user)
        MembershipFactory(community=self.community1, member=self.member)
        MembershipFactory(community=self.community2, member=self.member)
        
        self.client.force_login(self.user)
    
    def test_member_profile_displays_basic_information(self):
        """Test member profile displays basic member information."""
        url = reverse('accounts:member_profile', kwargs={'username': self.member.username})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.member.get_display_name())
        self.assertEqual(response.context['member'], self.member)
    
    def test_member_profile_shows_visible_memberships_only(self):
        """Test member profile only shows memberships in shared communities."""
        url = reverse('accounts:member_profile', kwargs={'username': self.member.username})
        response = self.client.get(url)
        
        visible_memberships = response.context['visible_memberships']
        
        # Should only show Community 1 (shared membership)
        self.assertEqual(visible_memberships.count(), 1)
        self.assertEqual(visible_memberships.first().community, self.community1)
    
    def test_member_profile_shows_following_relationships(self):
        """Test member profile displays following and followers."""
        other_user = UserFactory()
        
        # Create following relationships
        Following.objects.create(follower=self.member, followee=other_user, tags='tag1', order=1)
        Following.objects.create(follower=other_user, followee=self.member, tags='tag2', order=1)
        
        url = reverse('accounts:member_profile', kwargs={'username': self.member.username})
        response = self.client.get(url)
        
        following = response.context['following']
        followers = response.context['followers']
        
        self.assertEqual(following.count(), 1)
        self.assertEqual(followers.count(), 1)
        self.assertEqual(following.first().followee, other_user)
        self.assertEqual(followers.first().follower, other_user)
    
    def test_member_profile_shows_current_following_status(self):
        """Test member profile shows if current user is following the member."""
        # Create following relationship
        following = Following.objects.create(
            follower=self.user,
            followee=self.member,
            tags='governance',
            order=1
        )
        
        url = reverse('accounts:member_profile', kwargs={'username': self.member.username})
        response = self.client.get(url)
        
        self.assertTrue(response.context['is_following'])
        self.assertEqual(response.context['current_following'], following)
    
    def test_member_profile_not_following_status(self):
        """Test member profile when current user is not following the member."""
        url = reverse('accounts:member_profile', kwargs={'username': self.member.username})
        response = self.client.get(url)
        
        self.assertFalse(response.context['is_following'])
        self.assertIsNone(response.context['current_following'])
    
    def test_member_profile_self_view_no_following_check(self):
        """Test member profile when viewing own profile doesn't check following."""
        url = reverse('accounts:member_profile', kwargs={'username': self.user.username})
        response = self.client.get(url)
        
        self.assertFalse(response.context['is_following'])
        self.assertIsNone(response.context['current_following'])
    
    def test_member_profile_unauthenticated_user_redirects(self):
        """Test member profile redirects unauthenticated users to login."""
        self.client.logout()
        
        url = reverse('accounts:member_profile', kwargs={'username': self.member.username})
        response = self.client.get(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
    
    def test_member_profile_nonexistent_user_404(self):
        """Test member profile with nonexistent user returns 404."""
        url = reverse('accounts:member_profile', kwargs={'username': 'nonexistent'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)


class FollowViewsAuthenticationTestCase(TestCase):
    """Test authentication requirements for follow views."""
    
    def setUp(self):
        """Set up test data for authentication testing."""
        self.client = Client()
        self.user = UserFactory()
        self.followee = UserFactory()
    
    def test_follow_user_requires_authentication(self):
        """Test follow_user requires user to be logged in."""
        url = reverse('accounts:follow_user', kwargs={'user_id': self.followee.id})
        response = self.client.get(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
    
    def test_unfollow_user_requires_authentication(self):
        """Test unfollow_user requires user to be logged in."""
        url = reverse('accounts:unfollow_user', kwargs={'user_id': self.followee.id})
        response = self.client.post(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
    
    def test_edit_follow_requires_authentication(self):
        """Test edit_follow requires user to be logged in."""
        url = reverse('accounts:edit_follow', kwargs={'user_id': self.followee.id})
        response = self.client.get(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)


class FollowViewsHTTPMethodTestCase(TestCase):
    """Test HTTP method restrictions for follow views."""
    
    def setUp(self):
        """Set up test data for HTTP method testing."""
        self.client = Client()
        self.user = UserFactory()
        self.followee = UserFactory()
        self.client.force_login(self.user)
    
    def test_unfollow_user_requires_post(self):
        """Test unfollow_user only accepts POST requests."""
        url = reverse('accounts:unfollow_user', kwargs={'user_id': self.followee.id})
        
        # GET should return 405
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)
        
        # PUT should return 405
        response = self.client.put(url)
        self.assertEqual(response.status_code, 405)
        
        # DELETE should return 405
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 405)
    
    def test_follow_user_accepts_get_and_post(self):
        """Test follow_user accepts both GET and POST requests."""
        url = reverse('accounts:follow_user', kwargs={'user_id': self.followee.id})
        
        # GET should work
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        # POST should work
        response = self.client.post(url, {'tags': 'test', 'order': 1})
        self.assertEqual(response.status_code, 302)
        
        # PUT should return 405
        response = self.client.put(url)
        self.assertEqual(response.status_code, 405)
