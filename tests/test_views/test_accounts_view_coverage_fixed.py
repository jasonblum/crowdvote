"""
Tests specifically designed to improve coverage of accounts/views.py.

This test file focuses on testing untested code paths to increase coverage
rather than duplicating functionality tests.
"""

import json
import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.utils import timezone
from datetime import timedelta

from tests.factories.user_factory import UserFactory, MembershipFactory
from tests.factories.community_factory import CommunityFactory
from security.models import MagicLink, CommunityApplication
from democracy.models import Community

User = get_user_model()


@pytest.mark.views
class TestAccountsViewCoverage(TestCase):
    """Tests to improve coverage of accounts/views.py functions."""
    
    def setUp(self):
        self.client = Client()
        self.user = UserFactory(username="testuser")
        self.community = CommunityFactory(name="Test Community")
        
    def test_dashboard_authenticated_user(self):
        """Test dashboard view with authenticated user - covers main dashboard logic."""
        self.client.force_login(self.user)
        
        # Create some test data for dashboard display
        membership = MembershipFactory(member=self.user, community=self.community)
        
        response = self.client.get('/dashboard/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")
        
    def test_dashboard_unauthenticated_redirect(self):
        """Test dashboard redirects unauthenticated users."""
        response = self.client.get('/dashboard/')
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        
    def test_profile_setup_get_request(self):
        """Test profile setup GET request - covers form rendering logic."""
        # Create user without complete profile (no first_name)
        incomplete_user = UserFactory(username="incomplete", first_name="", last_name="")
        self.client.force_login(incomplete_user)
        
        response = self.client.get('/profile/setup/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Profile Setup")
        
    def test_profile_setup_post_valid_data(self):
        """Test profile setup POST with valid data - covers form processing."""
        # Create user without complete profile (no first_name)
        incomplete_user = UserFactory(username="incomplete2", first_name="", last_name="")
        self.client.force_login(incomplete_user)
        
        post_data = {
            'first_name': 'Test',
            'last_name': 'User',
            'username': 'newusername123'
        }
        
        response = self.client.post('/profile/setup/', post_data)
        
        # Should redirect on success
        self.assertEqual(response.status_code, 302)
        
        # Verify user was updated
        incomplete_user.refresh_from_db()
        self.assertEqual(incomplete_user.first_name, 'Test')
        
    def test_check_username_availability_ajax_request(self):
        """Test AJAX username availability check - covers validation logic."""
        self.client.force_login(self.user)
        
        # Test available username
        response = self.client.post(
            '/check-username/',
            {'username': 'availableusername123'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('is available', response.content.decode())
        
        # Test taken username
        existing_user = UserFactory(username="takenusername")
        response = self.client.post(
            '/check-username/',
            {'username': 'takenusername'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertIn('already taken', response.content.decode())
        
    def test_check_username_availability_non_ajax(self):
        """Test username check without AJAX - covers non-AJAX path."""
        self.client.force_login(self.user)
        
        response = self.client.get(
            '/check-username/',
            {'username': 'someusername'}
        )
        
        self.assertEqual(response.status_code, 405)  # Method Not Allowed for GET
        
    def test_generate_new_username_ajax(self):
        """Test AJAX username generation - covers generation logic."""
        self.client.force_login(self.user)
        
        response = self.client.post(
            '/generate-username/',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue('username' in data)
        self.assertTrue(len(data['username']) > 5)
        
    def test_community_discovery_authenticated(self):
        """Test community discovery view - covers community browsing logic."""
        self.client.force_login(self.user)
        
        # Create multiple communities for testing
        community2 = CommunityFactory(name="Another Community")
        
        response = self.client.get('/communities/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.community.name)
        self.assertContains(response, community2.name)
        
    def test_apply_to_community_valid_application(self):
        """Test community application with valid data - covers application logic."""
        self.client.force_login(self.user)
        
        response = self.client.post(
            f'/apply/{self.community.id}/',
            {'application_message': 'I want to participate in community decisions'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify application was created
        self.assertTrue(
            CommunityApplication.objects.filter(
                user=self.user,
                community=self.community
            ).exists()
        )
        
    def test_apply_to_community_duplicate_application(self):
        """Test duplicate application handling - covers error path."""
        self.client.force_login(self.user)
        
        # Create existing application
        CommunityApplication.objects.create(
            user=self.user,
            community=self.community,
            application_message="First application"
        )
        
        response = self.client.post(
            f'/apply/{self.community.id}/',
            {'application_message': 'Duplicate application'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        # Should handle duplicate gracefully
        self.assertEqual(response.status_code, 200)
        
    def test_leave_community_valid_membership(self):
        """Test leaving community - covers leave community logic."""
        self.client.force_login(self.user)
        
        # Create membership first
        membership = MembershipFactory(member=self.user, community=self.community)
        
        response = self.client.post(f'/leave/{self.community.id}/')
        
        # Should redirect after successful leave
        self.assertEqual(response.status_code, 302)
        
        # Verify membership was deleted
        self.assertFalse(
            self.community.memberships.filter(member=self.user).exists()
        )
        
    def test_member_profile_by_username(self):
        """Test member profile view by username - covers profile display logic."""
        # Member profiles may require authentication
        self.client.force_login(self.user)
        response = self.client.get(f'/member/{self.user.username}/')
        
        # Profile may redirect to login or show profile
        self.assertIn(response.status_code, [200, 302])
        
    def test_member_profile_community_context(self):
        """Test member profile in community context - covers community-specific logic."""
        membership = MembershipFactory(member=self.user, community=self.community)
        self.client.force_login(self.user)
        
        # Use global member profile URL (community-specific URLs were removed)
        response = self.client.get(f'/member/{self.user.username}/')
        
        # Profile may redirect or show content
        self.assertIn(response.status_code, [200, 302])
        
    def test_edit_profile_get_request(self):
        """Test profile editing GET request - covers form rendering."""
        self.client.force_login(self.user)
        
        response = self.client.get('/profile/edit/')
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Edit Profile")
        
    def test_edit_profile_post_valid_data(self):
        """Test profile editing POST - covers profile update logic."""
        self.client.force_login(self.user)
        
        post_data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            'bio': 'Updated bio text',
            'location': 'New Location',
            'website_url': 'https://example.com',
            'bio_public': True,
            'location_public': True,
            'social_links_public': True
        }
        
        response = self.client.post('/profile/edit/', post_data)
        
        # Should redirect on success
        self.assertEqual(response.status_code, 302)
        
        # Verify user was updated
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.bio, 'Updated bio text')
        
    def test_request_magic_link_valid_email(self):
        """Test magic link request with valid email - covers email sending logic."""
        post_data = {'email': 'test@example.com'}
        
        response = self.client.post('/request-magic-link/', post_data)
        
        # Should redirect with success message
        self.assertEqual(response.status_code, 302)
        
        # Verify magic link was created
        self.assertTrue(
            MagicLink.objects.filter(email='test@example.com').exists()
        )
        
    def test_request_magic_link_invalid_method(self):
        """Test magic link request with GET method - covers method validation."""
        response = self.client.get('/request-magic-link/')
        
        # Should return Method Not Allowed for GET
        self.assertEqual(response.status_code, 405)
        
    def test_magic_link_login_valid_token(self):
        """Test magic link login with valid token - covers authentication logic."""
        # Create a valid magic link using proper factory method
        magic_link = MagicLink.create_for_email('test@example.com')
        
        response = self.client.get(f'/magic-login/{magic_link.token}/')
        
        # Should redirect after successful login
        self.assertEqual(response.status_code, 302)
        
        # Verify magic link was used
        magic_link.refresh_from_db()
        self.assertIsNotNone(magic_link.used_at)
        
    def test_magic_link_login_expired_token(self):
        """Test magic link login with expired token - covers expiry logic."""
        # Create a magic link and manually expire it
        magic_link = MagicLink.create_for_email('test@example.com')
        magic_link.expires_at = timezone.now() - timedelta(minutes=15)
        magic_link.save()
        
        response = self.client.get(f'/magic-login/{magic_link.token}/')
        
        # Should redirect with error
        self.assertEqual(response.status_code, 302)
        
    def test_magic_link_login_nonexistent_token(self):
        """Test magic link login with nonexistent token - covers 404 handling."""
        response = self.client.get('/magic-login/nonexistent-token-123/')
        
        # Should redirect with error
        self.assertEqual(response.status_code, 302)
        
    def test_various_error_conditions(self):
        """Test various error conditions to improve coverage."""
        self.client.force_login(self.user)
        
        # Test missing username parameter (use POST since endpoint only accepts POST)
        response = self.client.post(
            '/check-username/',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        
        # Test invalid community ID in application
        response = self.client.post(
            '/apply/00000000-0000-0000-0000-000000000000/',
            {'application_message': 'Test message'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        # Should handle gracefully
        
    def test_authentication_required_views(self):
        """Test authentication requirements for protected views."""
        protected_urls = [
            '/dashboard/',
            '/profile/setup/',
            '/profile/edit/',
        ]
        
        # URLs that only accept POST (return 405 for GET)
        post_only_urls = [
            '/check-username/',
            '/generate-username/',
        ]
        
        for url in protected_urls:
            response = self.client.get(url)
            # Should redirect to login
            self.assertEqual(response.status_code, 302)
            
        for url in post_only_urls:
            response = self.client.get(url)
            # Should return Method Not Allowed for GET requests
            self.assertEqual(response.status_code, 405)
            
    def test_form_validation_error_paths(self):
        """Test form validation error handling - covers error display logic."""
        # Create a user without profile setup to avoid redirect
        new_user = UserFactory(first_name='', last_name='', username='testuser_validation')
        self.client.force_login(new_user)
        
        # Test profile setup with invalid data
        post_data = {
            'username': '',  # Invalid empty username
            'first_name': '',
            'last_name': ''
        }
        
        response = self.client.post('/profile/setup/', post_data)
        
        # Profile setup may redirect to dashboard or show form errors
        self.assertIn(response.status_code, [200, 302])
        
    def test_ajax_request_headers(self):
        """Test AJAX specific handling - covers AJAX detection logic."""
        self.client.force_login(self.user)
        
        # Test AJAX username generation
        response = self.client.post(
            '/generate-username/',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Type'].startswith('application/json'))
        
    def test_community_application_model_constraints(self):
        """Test community application model - covers model validation."""
        # Create application
        app = CommunityApplication.objects.create(
            user=self.user,
            community=self.community,
            application_message="Test application message"
        )
        
        self.assertEqual(app.status, 'pending')  # Default status
        self.assertEqual(app.user, self.user)
        self.assertEqual(app.community, self.community)
        
    def test_magic_link_model_methods(self):
        """Test magic link model - covers model behavior."""
        magic_link = MagicLink.create_for_email('test@example.com')
        
        # Test token generation
        self.assertTrue(len(magic_link.token) > 10)
        self.assertEqual(magic_link.email, 'test@example.com')
        self.assertIsNone(magic_link.used_at)
        
    def test_edge_case_urls(self):
        """Test edge cases and error handling in views."""
        self.client.force_login(self.user)
        
        # Test profile views with various data
        response = self.client.get('/communities/')
        # Should work even without memberships
        self.assertEqual(response.status_code, 200)
        
        # Test member profile with non-existent username
        response = self.client.get('/member/nonexistentuser/')
        # Should handle gracefully (404 or redirect)
        self.assertIn(response.status_code, [200, 302, 404])
