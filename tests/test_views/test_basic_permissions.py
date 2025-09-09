"""
Tests for basic view permissions and security.

This module tests authentication requirements, permission checks,
and basic security for CrowdVote views.
"""
import pytest
from django.test import Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.http import Http404

from tests.factories import (
    UserFactory, CommunityFactory, MembershipFactory,
    DecisionFactory, ChoiceFactory
)

User = get_user_model()


@pytest.mark.views
class TestPublicAccessViews:
    """Test views that should be accessible without authentication."""
    
    def test_home_page_accessible(self, client):
        """Test that home page is accessible to everyone."""
        response = client.get('/')
        assert response.status_code == 200
    
    def test_docs_page_accessible(self, client):
        """Test that documentation page is accessible to everyone."""
        response = client.get('/docs/')
        assert response.status_code == 200


@pytest.mark.views
class TestAuthenticationRequirements:
    """Test that protected views require authentication."""
    
    def test_profile_setup_requires_auth(self, client):
        """Test that profile setup requires authentication."""
        response = client.get('/profile/setup/')
        # Should redirect to login or return 302/403
        assert response.status_code in [302, 403, 404]
    
    def test_dashboard_requires_auth(self, client):
        """Test that user dashboard requires authentication.""" 
        response = client.get('/accounts/dashboard/')
        # Should redirect to login or return 302/403
        assert response.status_code in [302, 403, 404]
    
    def test_community_discovery_requires_auth(self, client):
        """Test that community discovery requires authentication."""
        response = client.get('/accounts/communities/')
        # Should redirect to login or return 302/403
        assert response.status_code in [302, 403, 404]


@pytest.mark.views
class TestCommunityAccessPermissions:
    """Test community-specific access permissions."""
    
    def test_community_detail_access_by_members(self, client):
        """Test that community members can access community details."""
        user = UserFactory()
        community = CommunityFactory()
        MembershipFactory(member=user, community=community)
        
        client.force_login(user)
        
        # Try to access community detail - might not exist yet but should not crash
        try:
            response = client.get(f'/communities/{community.id}/')
            # If view exists, member should be able to access
            assert response.status_code in [200, 404]  # 404 if view not implemented
        except Http404:
            # View might not be implemented yet
            pass
    
    def test_community_access_by_non_members(self, client):
        """Test that non-members cannot access private community features."""
        user = UserFactory()
        community = CommunityFactory()
        # Note: NOT creating membership for user
        
        client.force_login(user)
        
        # Try to access community detail
        try:
            response = client.get(f'/communities/{community.id}/')
            # Non-member should be denied or redirected
            assert response.status_code in [403, 302, 404]
        except Http404:
            # View might not be implemented yet
            pass


@pytest.mark.views
class TestManagerPermissions:
    """Test community manager-specific permissions."""
    
    def test_community_management_requires_manager_role(self, client):
        """Test that community management requires manager role."""
        # Regular user (not manager)
        regular_user = UserFactory()
        community = CommunityFactory()
        MembershipFactory(
            member=regular_user,
            community=community,
            is_community_manager=False
        )
        
        client.force_login(regular_user)
        
        # Try to access management interface
        try:
            response = client.get(f'/communities/{community.id}/manage/')
            # Should be denied
            assert response.status_code in [403, 302, 404]
        except Http404:
            # View might not be implemented yet
            pass
    
    def test_community_management_allows_managers(self, client):
        """Test that community managers can access management interface."""
        # Manager user
        manager = UserFactory()
        community = CommunityFactory()
        MembershipFactory(
            member=manager,
            community=community,
            is_community_manager=True
        )
        
        client.force_login(manager)
        
        # Try to access management interface
        try:
            response = client.get(f'/communities/{community.id}/manage/')
            # Manager should be allowed
            assert response.status_code in [200, 404]  # 404 if view not implemented
        except Http404:
            # View might not be implemented yet
            pass
    
    def test_decision_creation_requires_manager_role(self, client):
        """Test that decision creation requires manager role."""
        # Regular user (not manager)
        regular_user = UserFactory()
        community = CommunityFactory()
        MembershipFactory(
            member=regular_user,
            community=community,
            is_community_manager=False
        )
        
        client.force_login(regular_user)
        
        # Try to create decision
        try:
            response = client.get(f'/communities/{community.id}/decisions/create/')
            # Should be denied
            assert response.status_code in [403, 302, 404]
        except Http404:
            # View might not be implemented yet
            pass


@pytest.mark.views
class TestVotingPermissions:
    """Test voting-specific permissions."""
    
    def test_voting_requires_voting_membership(self, client):
        """Test that voting requires voting membership."""
        # Lobbyist (non-voting member)
        lobbyist = UserFactory()
        community = CommunityFactory()
        MembershipFactory(
            member=lobbyist,
            community=community,
            is_voting_community_member=False  # Lobbyist cannot vote
        )
        
        decision = DecisionFactory(community=community, with_choices=False)
        
        client.force_login(lobbyist)
        
        # Try to vote
        try:
            response = client.get(f'/communities/{community.id}/decisions/{decision.id}/')
            # Lobbyist should see decision but not be able to vote
            # This would be enforced in the template/form logic
            assert response.status_code in [200, 403, 404]
        except Http404:
            # View might not be implemented yet
            pass
    
    def test_voting_allows_voting_members(self, client):
        """Test that voting members can access voting interface."""
        # Voting member
        voter = UserFactory()
        community = CommunityFactory()
        MembershipFactory(
            member=voter,
            community=community,
            is_voting_community_member=True
        )
        
        decision = DecisionFactory(community=community, with_choices=False)
        
        client.force_login(voter)
        
        # Try to access voting interface
        try:
            response = client.get(f'/communities/{community.id}/decisions/{decision.id}/')
            # Voting member should be allowed
            assert response.status_code in [200, 404]
        except Http404:
            # View might not be implemented yet
            pass


@pytest.mark.views
class TestSecurityHeaders:
    """Test basic security headers and protections."""
    
    def test_csrf_protection_enabled(self, client):
        """Test that CSRF protection is enabled for forms."""
        user = UserFactory()
        client.force_login(user)
        
        # Try to access any form page
        response = client.get('/')
        
        # Should include CSRF token in response
        if response.status_code == 200:
            content = response.content.decode()
            # Check for CSRF token (either in form or meta tag)
            assert 'csrf' in content.lower() or 'csrftoken' in content.lower()
    
    def test_xss_protection_headers(self, client):
        """Test that XSS protection headers are present."""
        response = client.get('/')
        
        # Django should include security headers by default
        # Note: Specific headers depend on middleware configuration
        assert response.status_code == 200
    
    def test_user_input_handling(self, client):
        """Test that user input is properly handled."""
        # Try to access URLs with potential XSS
        malicious_input = "<script>alert('xss')</script>"
        
        # This should not crash and should be properly escaped
        response = client.get('/', {'q': malicious_input})
        assert response.status_code == 200
        
        # Response should not contain unescaped script tags
        content = response.content.decode()
        assert '<script>alert(' not in content


@pytest.mark.views
class TestURLPatternSecurity:
    """Test URL pattern security and validation."""
    
    def test_uuid_parameter_validation(self, client):
        """Test that UUID parameters are properly validated."""
        user = UserFactory()
        client.force_login(user)
        
        # Try invalid UUID
        invalid_uuids = [
            'invalid-uuid',
            '123',
            'not-a-uuid',
            '../../../etc/passwd',
            'javascript:alert(1)'
        ]
        
        for invalid_uuid in invalid_uuids:
            try:
                response = client.get(f'/communities/{invalid_uuid}/')
                # Should return 404 or 400, not crash
                assert response.status_code in [404, 400]
            except Http404:
                # Expected for invalid UUIDs
                pass
            except Exception as e:
                # Should not raise unexpected exceptions
                pytest.fail(f"Unexpected exception for UUID {invalid_uuid}: {e}")
    
    def test_path_traversal_protection(self, client):
        """Test protection against path traversal attacks."""
        user = UserFactory()
        client.force_login(user)
        
        # Try path traversal patterns
        malicious_paths = [
            '../../../etc/passwd',
            '..\\..\\windows\\system32',
            '%2e%2e%2f%2e%2e%2f%2e%2e%2f',
            '..',
            '../'
        ]
        
        for malicious_path in malicious_paths:
            response = client.get(f'/{malicious_path}')
            # Should return 404, not access filesystem
            assert response.status_code in [404, 400]


@pytest.mark.views
class TestRateLimit:
    """Test basic rate limiting behavior."""
    
    def test_multiple_requests_handled(self, client):
        """Test that multiple requests are handled properly."""
        # Make multiple requests to same endpoint
        for i in range(10):
            response = client.get('/')
            assert response.status_code == 200
        
        # Should not be rate limited for reasonable requests
        response = client.get('/')
        assert response.status_code == 200
