"""
Integration tests for the global processing indicator functionality.

This module tests the end-to-end behavior of the global processing indicator,
including UI rendering, JavaScript functionality, and interaction with the
calculation system.
"""

import pytest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import json

from tests.factories.user_factory import UserFactory
from tests.factories.community_factory import CommunityFactory
from tests.factories.decision_factory import DecisionFactory
from democracy.models import DecisionSnapshot, Membership

User = get_user_model()


class GlobalIndicatorRenderingTest(TestCase):
    """Test that the global indicator renders correctly in templates."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = UserFactory()
        self.community = CommunityFactory()
        
        Membership.objects.create(
            member=self.user,
            community=self.community,
            is_voting_community_member=True
        )
    
    def test_indicator_appears_on_authenticated_pages(self):
        """Test that indicator appears on authenticated pages except home."""
        self.client.force_login(self.user)
        
        # Test dashboard page
        dashboard_url = reverse('accounts:dashboard')
        response = self.client.get(dashboard_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'global-processing-indicator')
        self.assertContains(response, 'processing-spinner')
        self.assertContains(response, 'processing-tooltip')
    
    def test_indicator_hidden_on_landing_page(self):
        """Test that indicator is hidden on the landing page."""
        # Test with unauthenticated user first
        self.client.logout()
        home_url = reverse('home')
        response = self.client.get(home_url)
        self.assertEqual(response.status_code, 200)
        # The home page should not have the actual indicator HTML element
        self.assertNotContains(response, 'id="global-processing-indicator"')
        
        # Test that authenticated users get redirected from home page
        self.client.force_login(self.user)
        response = self.client.get(home_url)
        self.assertEqual(response.status_code, 302)  # Should redirect authenticated users to profile
    
    def test_indicator_hidden_for_unauthenticated_users(self):
        """Test that indicator doesn't appear for unauthenticated users."""
        # Test docs page without authentication
        docs_url = reverse('docs')
        response = self.client.get(docs_url)
        self.assertEqual(response.status_code, 200)
        # The docs page has its own header that doesn't include the processing indicator
        # But the CSS and JS are still included in the base template
        self.assertNotContains(response, 'id="global-processing-indicator"')
    
    def test_css_animations_included(self):
        """Test that CSS animations are included in authenticated pages."""
        self.client.force_login(self.user)
        
        dashboard_url = reverse('accounts:dashboard')
        response = self.client.get(dashboard_url)
        self.assertEqual(response.status_code, 200)
        
        # Check for CSS animation classes and keyframes
        self.assertContains(response, 'processing-active')
        self.assertContains(response, 'processing-inactive')
        self.assertContains(response, '@keyframes spin')
        self.assertContains(response, 'animation: spin 1s linear infinite')
    
    def test_javascript_polling_included(self):
        """Test that JavaScript polling code is included."""
        self.client.force_login(self.user)
        
        dashboard_url = reverse('accounts:dashboard')
        response = self.client.get(dashboard_url)
        self.assertEqual(response.status_code, 200)
        
        # Check for key JavaScript functions
        self.assertContains(response, 'pollGlobalStatus')
        self.assertContains(response, 'updateProcessingIndicator')
        self.assertContains(response, 'setupActivityListener')
        self.assertContains(response, '/status/global-calculations/')


class GlobalIndicatorBehaviorTest(TestCase):
    """Test the behavior of the global indicator with different calculation states."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = UserFactory()
        self.community = CommunityFactory()
        
        Membership.objects.create(
            member=self.user,
            community=self.community,
            is_voting_community_member=True
        )
        
        self.decision = DecisionFactory(
            community=self.community,
            dt_close=timezone.now() + timedelta(days=1)
        )
    
    def test_inactive_state_response(self):
        """Test indicator response when no calculations are running."""
        self.client.force_login(self.user)
        
        status_url = reverse('global_calculation_status')
        response = self.client.get(status_url)
        data = json.loads(response.content)
        
        self.assertFalse(data['has_active_calculations'])
        self.assertFalse(data['has_recent_activity'])
        self.assertEqual(len(data['decisions']), 0)
    
    def test_active_calculation_response(self):
        """Test indicator response during active calculations."""
        self.client.force_login(self.user)
        
        # Create active snapshot
        DecisionSnapshot.objects.create(
            decision=self.decision,
            calculation_status='staging',
            created_at=timezone.now()
        )
        
        status_url = reverse('global_calculation_status')
        response = self.client.get(status_url)
        data = json.loads(response.content)
        
        self.assertTrue(data['has_active_calculations'])
        self.assertTrue(data['has_recent_activity'])
        self.assertEqual(len(data['decisions']), 1)
        
        decision_data = data['decisions'][0]
        self.assertEqual(decision_data['status_type'], 'active')
        self.assertEqual(decision_data['title'], self.decision.title)
        self.assertEqual(decision_data['community_name'], self.community.name)
    
    def test_recent_activity_response(self):
        """Test indicator response with recent completed activity."""
        self.client.force_login(self.user)
        
        # Create completed snapshot and set timestamp to 1 hour ago
        snapshot = DecisionSnapshot.objects.create(
            decision=self.decision,
            calculation_status='completed'
        )
        
        # Manually update the created_at field to 1 hour ago
        snapshot_time = timezone.now() - timedelta(hours=1, minutes=30)
        DecisionSnapshot.objects.filter(id=snapshot.id).update(created_at=snapshot_time)
        snapshot.refresh_from_db()
        
        status_url = reverse('global_calculation_status')
        response = self.client.get(status_url)
        data = json.loads(response.content)
        
        self.assertFalse(data['has_active_calculations'])
        self.assertTrue(data['has_recent_activity'])
        self.assertEqual(len(data['decisions']), 1)
        
        decision_data = data['decisions'][0]
        self.assertEqual(decision_data['status_type'], 'completed')
        self.assertIn('✅ Completed', decision_data['status'])
        # Check for hour indicator (should be 1h ago)
        self.assertRegex(decision_data['status'], r'\d+h ago')


class GlobalIndicatorWorkflowTest(TestCase):
    """Test the global indicator through complete voting and calculation workflows."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = UserFactory()
        self.community = CommunityFactory()
        
        Membership.objects.create(
            member=self.user,
            community=self.community,
            is_voting_community_member=True
        )
        
        self.decision = DecisionFactory(
            community=self.community,
            dt_close=timezone.now() + timedelta(days=1)
        )
    
    def test_calculation_workflow_status_progression(self):
        """Test status progression through a complete calculation workflow."""
        self.client.force_login(self.user)
        status_url = reverse('global_calculation_status')
        
        # 1. No calculations initially
        response = self.client.get(status_url)
        data = json.loads(response.content)
        self.assertFalse(data['has_active_calculations'])
        
        # 2. Start calculation - creating snapshot
        snapshot = DecisionSnapshot.objects.create(
            decision=self.decision,
            calculation_status='creating'
        )
        
        response = self.client.get(status_url)
        data = json.loads(response.content)
        self.assertTrue(data['has_active_calculations'])
        self.assertEqual(data['decisions'][0]['status'], 'Creating Snapshot...')
        
        # 3. Move to staging
        snapshot.calculation_status = 'staging'
        snapshot.save()
        
        response = self.client.get(status_url)
        data = json.loads(response.content)
        self.assertTrue(data['has_active_calculations'])
        self.assertEqual(data['decisions'][0]['status'], 'Calculating Votes...')
        
        # 4. Move to tallying
        snapshot.calculation_status = 'tallying'
        snapshot.save()
        
        response = self.client.get(status_url)
        data = json.loads(response.content)
        self.assertTrue(data['has_active_calculations'])
        self.assertEqual(data['decisions'][0]['status'], 'Tallying Results...')
        
        # 5. Complete calculation
        snapshot.calculation_status = 'completed'
        snapshot.save()
        
        response = self.client.get(status_url)
        data = json.loads(response.content)
        self.assertFalse(data['has_active_calculations'])
        self.assertTrue(data['has_recent_activity'])
        self.assertIn('✅ Completed', data['decisions'][0]['status'])
    
    def test_multiple_simultaneous_calculations(self):
        """Test indicator with multiple calculations running simultaneously."""
        self.client.force_login(self.user)
        
        # Create multiple communities and decisions
        community2 = CommunityFactory()
        community3 = CommunityFactory()
        
        decision2 = DecisionFactory(
            community=community2,
            dt_close=timezone.now() + timedelta(days=1)
        )
        decision3 = DecisionFactory(
            community=community3,
            dt_close=timezone.now() + timedelta(days=1)
        )
        
        # Create snapshots with different active statuses
        DecisionSnapshot.objects.create(
            decision=self.decision,
            calculation_status='creating',
            created_at=timezone.now()
        )
        
        DecisionSnapshot.objects.create(
            decision=decision2,
            calculation_status='staging',
            created_at=timezone.now()
        )
        
        DecisionSnapshot.objects.create(
            decision=decision3,
            calculation_status='tallying',
            created_at=timezone.now()
        )
        
        status_url = reverse('global_calculation_status')
        response = self.client.get(status_url)
        data = json.loads(response.content)
        
        self.assertTrue(data['has_active_calculations'])
        self.assertEqual(len(data['decisions']), 3)
        
        # Check all decisions are present with correct statuses
        statuses = [d['status'] for d in data['decisions']]
        self.assertIn('Creating Snapshot...', statuses)
        self.assertIn('Calculating Votes...', statuses)
        self.assertIn('Tallying Results...', statuses)
    
    def test_mixed_active_and_recent_activity(self):
        """Test indicator with both active calculations and recent activity."""
        self.client.force_login(self.user)
        
        # Create second decision
        decision2 = DecisionFactory(
            community=self.community,
            dt_close=timezone.now() + timedelta(days=1)
        )
        
        # Active calculation
        DecisionSnapshot.objects.create(
            decision=self.decision,
            calculation_status='staging',
            created_at=timezone.now()
        )
        
        # Recent completed calculation
        DecisionSnapshot.objects.create(
            decision=decision2,
            calculation_status='completed',
            created_at=timezone.now() - timedelta(hours=2)
        )
        
        status_url = reverse('global_calculation_status')
        response = self.client.get(status_url)
        data = json.loads(response.content)
        
        self.assertTrue(data['has_active_calculations'])
        self.assertTrue(data['has_recent_activity'])
        self.assertEqual(len(data['decisions']), 2)
        
        # Check we have one active and one completed
        active_decisions = [d for d in data['decisions'] if d['status_type'] == 'active']
        completed_decisions = [d for d in data['decisions'] if d['status_type'] == 'completed']
        
        self.assertEqual(len(active_decisions), 1)
        self.assertEqual(len(completed_decisions), 1)
    
    def test_error_handling_in_calculations(self):
        """Test indicator behavior when calculations fail."""
        self.client.force_login(self.user)
        
        # Create failed snapshot and set timestamp to 45 minutes ago
        snapshot = DecisionSnapshot.objects.create(
            decision=self.decision,
            calculation_status='failed_staging',
            error_log='Test error message'
        )
        
        # Manually update the created_at field to 45 minutes ago
        snapshot_time = timezone.now() - timedelta(minutes=45)
        DecisionSnapshot.objects.filter(id=snapshot.id).update(created_at=snapshot_time)
        snapshot.refresh_from_db()
        
        status_url = reverse('global_calculation_status')
        response = self.client.get(status_url)
        data = json.loads(response.content)
        
        self.assertFalse(data['has_active_calculations'])
        self.assertTrue(data['has_recent_activity'])
        
        decision_data = data['decisions'][0]
        self.assertEqual(decision_data['status_type'], 'failed')
        self.assertIn('❌ Calculation Failed', decision_data['status'])
        # Check for minute indicator (should be 45m ago)
        self.assertRegex(decision_data['status'], r'\d+m ago')


class GlobalIndicatorPerformanceTest(TestCase):
    """Test performance aspects of the global indicator."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = UserFactory()
        self.community = CommunityFactory()
        
        Membership.objects.create(
            member=self.user,
            community=self.community,
            is_voting_community_member=True
        )
    
    def test_response_time_with_many_decisions(self):
        """Test response time with many decisions and snapshots."""
        self.client.force_login(self.user)
        
        # Create many decisions
        decisions = []
        for i in range(20):
            decision = DecisionFactory(
                community=self.community,
                dt_close=timezone.now() + timedelta(days=1)
            )
            decisions.append(decision)
            
            # Create multiple snapshots per decision
            for j in range(5):
                DecisionSnapshot.objects.create(
                    decision=decision,
                    calculation_status='completed',
                    created_at=timezone.now() - timedelta(hours=j)
                )
        
        # Create a few active calculations
        for i in range(3):
            DecisionSnapshot.objects.create(
                decision=decisions[i],
                calculation_status='staging',
                created_at=timezone.now()
            )
        
        status_url = reverse('global_calculation_status')
        
        import time
        start_time = time.time()
        response = self.client.get(status_url)
        end_time = time.time()
        
        # Response should be fast (under 1 second)
        self.assertLess(end_time - start_time, 1.0)
        self.assertEqual(response.status_code, 200)
        
        data = json.loads(response.content)
        
        # Should only return most recent snapshot per decision
        # 3 active + up to 17 recent (within 24h) = max 20
        self.assertLessEqual(len(data['decisions']), 20)
        self.assertTrue(data['has_active_calculations'])
    
    def test_database_query_efficiency(self):
        """Test that the endpoint uses efficient database queries."""
        self.client.force_login(self.user)
        
        # Create test data
        decisions = [DecisionFactory(
            community=self.community,
            dt_close=timezone.now() + timedelta(days=1)
        ) for _ in range(5)]
        
        for decision in decisions:
            DecisionSnapshot.objects.create(
                decision=decision,
                calculation_status='staging',
                created_at=timezone.now()
            )
        
        status_url = reverse('global_calculation_status')
        
        # Test with query counting (if available)
        from django.test.utils import override_settings
        from django.db import connection
        
        with override_settings(DEBUG=True):
            connection.queries_log.clear()
            response = self.client.get(status_url)
            
            # Should use efficient queries with select_related
            # Expect reasonable number of queries (not N+1)
            query_count = len(connection.queries)
            self.assertLess(query_count, 10)  # Should be efficient
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data['decisions']), 5)
