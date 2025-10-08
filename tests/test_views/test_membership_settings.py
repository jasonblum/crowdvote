"""
Tests for membership settings (anonymity toggle) functionality.

Tests the new membership-level anonymity system where users can toggle
their anonymity status per-community via an HTMX modal.
"""
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model

from democracy.models import Community, Membership

User = get_user_model()


@pytest.mark.django_db
class TestMembershipSettingsModal:
    """Tests for the membership settings modal view."""
    
    def test_settings_modal_loads_for_member(self, client, django_user_model):
        """Test that members can access their settings modal."""
        user = django_user_model.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        community = Community.objects.create(
            name='Test Community',
            description='Test'
        )
        membership = Membership.objects.create(
            member=user,
            community=community,
            is_voting_community_member=True,
            is_anonymous=True
        )
        
        client.login(username='testuser', password='testpass123')
        url = reverse('democracy:membership_settings_modal', args=[community.id])
        response = client.get(url)
        
        assert response.status_code == 200
        assert b'My Membership in Test Community' in response.content
        assert b'Appear Anonymous' in response.content
    
    def test_settings_modal_forbidden_for_non_member(self, client, django_user_model):
        """Test that non-members cannot access settings modal."""
        user = django_user_model.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        community = Community.objects.create(
            name='Test Community',
            description='Test'
        )
        
        client.login(username='testuser', password='testpass123')
        url = reverse('democracy:membership_settings_modal', args=[community.id])
        response = client.get(url)
        
        assert response.status_code == 403
        assert b'must be a member' in response.content


@pytest.mark.django_db
class TestAnonymityToggle:
    """Tests for anonymity toggle functionality."""
    
    def test_voting_member_can_toggle_to_anonymous(self, client, django_user_model):
        """Test that voting members can become anonymous."""
        user = django_user_model.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        community = Community.objects.create(
            name='Test Community',
            description='Test'
        )
        membership = Membership.objects.create(
            member=user,
            community=community,
            is_voting_community_member=True,
            is_anonymous=False  # Start as public
        )
        
        client.login(username='testuser', password='testpass123')
        url = reverse('democracy:membership_settings_save', args=[community.id])
        response = client.post(url, {'is_anonymous': 'on'})
        
        assert response.status_code == 200
        membership.refresh_from_db()
        assert membership.is_anonymous is True
    
    def test_voting_member_can_toggle_to_public(self, client, django_user_model):
        """Test that anonymous voting members can become public."""
        user = django_user_model.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123'
        )
        community = Community.objects.create(
            name='Test Community',
            description='Test'
        )
        membership = Membership.objects.create(
            member=user,
            community=community,
            is_voting_community_member=True,
            is_anonymous=True  # Start as anonymous
        )
        
        client.login(username='testuser', password='testpass123')
        url = reverse('democracy:membership_settings_save', args=[community.id])
        # Checkbox not checked = not anonymous
        response = client.post(url, {})
        
        assert response.status_code == 200
        membership.refresh_from_db()
        assert membership.is_anonymous is False
    
    def test_lobbyist_cannot_become_anonymous(self, client, django_user_model):
        """Test that lobbyists cannot toggle to anonymous."""
        user = django_user_model.objects.create_user(
            username='lobbyist',
            email='lobby@test.com',
            password='testpass123'
        )
        community = Community.objects.create(
            name='Test Community',
            description='Test'
        )
        membership = Membership.objects.create(
            member=user,
            community=community,
            is_voting_community_member=False,  # Lobbyist
            is_anonymous=False
        )
        
        client.login(username='lobbyist', password='testpass123')
        url = reverse('democracy:membership_settings_save', args=[community.id])
        response = client.post(url, {'is_anonymous': 'on'})
        
        assert response.status_code == 403
        assert b'Lobbyists cannot' in response.content
        membership.refresh_from_db()
        assert membership.is_anonymous is False


@pytest.mark.django_db
class TestAnonymityInViews:
    """Tests for anonymity display in various views."""
    
    def test_anonymous_member_shows_in_member_table(self, client, django_user_model):
        """Test that anonymous members appear as 'Anonymous' in member table."""
        user = django_user_model.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
        community = Community.objects.create(
            name='Test Community',
            description='Test'
        )
        membership = Membership.objects.create(
            member=user,
            community=community,
            is_voting_community_member=True,
            is_anonymous=True
        )
        
        admin = django_user_model.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='admin123'
        )
        Membership.objects.create(
            member=admin,
            community=community,
            is_voting_community_member=True,
            is_community_manager=True,
            is_anonymous=False
        )
        
        client.login(username='admin', password='admin123')
        url = reverse('democracy:community_detail', args=[community.id])
        response = client.get(url)
        
        assert response.status_code == 200
        # Should show real name in Member column
        assert b'John Doe' in response.content
        # Should show Anonymous in Username column
        assert b'Anonymous' in response.content
        # Should NOT show actual username
        assert b'@testuser' not in response.content

