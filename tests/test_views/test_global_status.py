"""
Tests for the global calculation status endpoint.

This module tests the global processing indicator functionality that shows
users when decisions are being calculated across all communities.
"""

import pytest
from django.test import TestCase, Client, TransactionTestCase
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


class GlobalCalculationStatusViewTest(TestCase):
    """Test the global calculation status endpoint."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = UserFactory()
        self.community = CommunityFactory()
        
        # Create membership for user
        Membership.objects.create(
            member=self.user,
            community=self.community,
            is_voting_community_member=True
        )
        
        # Create test decisions
        self.active_decision = DecisionFactory(
            community=self.community,
            dt_close=timezone.now() + timedelta(days=1)  # Open decision
        )
        
        self.closed_decision = DecisionFactory(
            community=self.community,
            dt_close=timezone.now() - timedelta(days=1)  # Closed decision
        )
        
        self.url = reverse('global_calculation_status')
    
    def test_requires_authentication(self):
        """Test that the endpoint requires authentication."""
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_empty_state_no_calculations(self):
        """Test response when no calculations are running."""
        self.client.force_login(self.user)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertFalse(data['has_active_calculations'])
        self.assertFalse(data['has_recent_activity'])
        self.assertEqual(len(data['decisions']), 0)
    
    def test_active_calculation_status(self):
        """Test response when there are active calculations."""
        self.client.force_login(self.user)
        
        # Create active snapshot
        snapshot = DecisionSnapshot.objects.create(
            decision=self.active_decision,
            calculation_status='staging',
            created_at=timezone.now()
        )
        
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertTrue(data['has_active_calculations'])
        self.assertTrue(data['has_recent_activity'])
        self.assertEqual(len(data['decisions']), 1)
        
        decision_data = data['decisions'][0]
        self.assertEqual(decision_data['id'], str(self.active_decision.id))
        self.assertEqual(decision_data['title'], self.active_decision.title)
        self.assertEqual(decision_data['community_name'], self.community.name)
        self.assertEqual(decision_data['status'], 'Calculating Votes...')
        self.assertEqual(decision_data['status_type'], 'active')
        self.assertIn('/communities/', decision_data['url'])
        self.assertIn('/decisions/', decision_data['url'])
        self.assertIn('/results/', decision_data['url'])
    
    def test_recent_activity_status(self):
        """Test response when there's recent activity but no active calculations."""
        self.client.force_login(self.user)
        
        # Create completed snapshot and set timestamp to 2 hours ago
        snapshot = DecisionSnapshot.objects.create(
            decision=self.active_decision,
            calculation_status='completed'
        )
        
        # Manually update the created_at field to 2 hours ago
        snapshot_time = timezone.now() - timedelta(hours=2, minutes=30)
        DecisionSnapshot.objects.filter(id=snapshot.id).update(created_at=snapshot_time)
        snapshot.refresh_from_db()
        
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertFalse(data['has_active_calculations'])
        self.assertTrue(data['has_recent_activity'])
        self.assertEqual(len(data['decisions']), 1)
        
        decision_data = data['decisions'][0]
        self.assertEqual(decision_data['status_type'], 'completed')
        self.assertIn('✅ Completed', decision_data['status'])
        # Check for time indicator (should show hours or minutes)
        self.assertRegex(decision_data['status'], r'\d+[hm] ago')
    
    def test_failed_calculation_status(self):
        """Test response for failed calculations."""
        self.client.force_login(self.user)
        
        # Create failed snapshot and set timestamp to 30 minutes ago
        snapshot = DecisionSnapshot.objects.create(
            decision=self.active_decision,
            calculation_status='failed_staging'
        )
        
        # Manually update the created_at field to 30 minutes ago
        snapshot_time = timezone.now() - timedelta(minutes=30)
        DecisionSnapshot.objects.filter(id=snapshot.id).update(created_at=snapshot_time)
        snapshot.refresh_from_db()
        
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertFalse(data['has_active_calculations'])
        self.assertTrue(data['has_recent_activity'])
        
        decision_data = data['decisions'][0]
        self.assertEqual(decision_data['status_type'], 'failed')
        self.assertIn('❌ Calculation Failed', decision_data['status'])
        # Check for minute indicator (could be 30m or less depending on timing)
        self.assertRegex(decision_data['status'], r'\d+m ago')
    
    def test_multiple_active_calculations(self):
        """Test response with multiple active calculations."""
        self.client.force_login(self.user)
        
        # Create second community and decision
        community2 = CommunityFactory()
        decision2 = DecisionFactory(
            community=community2,
            dt_close=timezone.now() + timedelta(days=1)
        )
        
        # Create active snapshots for both decisions
        DecisionSnapshot.objects.create(
            decision=self.active_decision,
            calculation_status='creating',
            created_at=timezone.now()
        )
        
        DecisionSnapshot.objects.create(
            decision=decision2,
            calculation_status='tallying',
            created_at=timezone.now()
        )
        
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertTrue(data['has_active_calculations'])
        self.assertEqual(len(data['decisions']), 2)
        
        # Check both decisions are present
        decision_ids = [d['id'] for d in data['decisions']]
        self.assertIn(str(self.active_decision.id), decision_ids)
        self.assertIn(str(decision2.id), decision_ids)
    
    def test_excludes_closed_decisions(self):
        """Test that closed decisions are excluded from results."""
        self.client.force_login(self.user)
        
        # Create snapshot for closed decision
        DecisionSnapshot.objects.create(
            decision=self.closed_decision,
            calculation_status='staging',
            created_at=timezone.now()
        )
        
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Should not include closed decision even with active calculation status
        self.assertFalse(data['has_active_calculations'])
        self.assertFalse(data['has_recent_activity'])
        self.assertEqual(len(data['decisions']), 0)
    
    def test_old_activity_excluded(self):
        """Test that activity older than 24 hours is excluded."""
        self.client.force_login(self.user)
        
        # Create completed snapshot and manually set old timestamp
        old_snapshot = DecisionSnapshot.objects.create(
            decision=self.active_decision,
            calculation_status='completed'
        )
        
        # Manually update the created_at field to 25 hours ago
        old_time = timezone.now() - timedelta(hours=25)
        DecisionSnapshot.objects.filter(id=old_snapshot.id).update(created_at=old_time)
        old_snapshot.refresh_from_db()
        
        # Verify the timestamp is correct
        self.assertTrue(old_snapshot.created_at < timezone.now() - timedelta(hours=24))
        
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # The old decision should not be included in results
        decision_ids = [d['id'] for d in data['decisions']]
        self.assertNotIn(str(self.active_decision.id), decision_ids)
        
        # Clean up
        old_snapshot.delete()
    
    def test_active_takes_priority_over_recent(self):
        """Test that active calculations take priority over recent activity for same decision."""
        self.client.force_login(self.user)
        
        # Create older completed snapshot
        DecisionSnapshot.objects.create(
            decision=self.active_decision,
            calculation_status='completed',
            created_at=timezone.now() - timedelta(hours=1)
        )
        
        # Create newer active snapshot
        DecisionSnapshot.objects.create(
            decision=self.active_decision,
            calculation_status='staging',
            created_at=timezone.now()
        )
        
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertTrue(data['has_active_calculations'])
        self.assertEqual(len(data['decisions']), 1)
        
        # Should show active status, not completed
        decision_data = data['decisions'][0]
        self.assertEqual(decision_data['status_type'], 'active')
        self.assertEqual(decision_data['status'], 'Calculating Votes...')
    
    def test_json_response_structure(self):
        """Test that the JSON response has the correct structure."""
        self.client.force_login(self.user)
        
        DecisionSnapshot.objects.create(
            decision=self.active_decision,
            calculation_status='ready',
            created_at=timezone.now()
        )
        
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        data = json.loads(response.content)
        
        # Check top-level structure
        self.assertIn('has_active_calculations', data)
        self.assertIn('has_recent_activity', data)
        self.assertIn('decisions', data)
        self.assertIsInstance(data['decisions'], list)
        
        # Check decision structure
        if data['decisions']:
            decision = data['decisions'][0]
            required_fields = ['id', 'title', 'community_name', 'status', 'status_type', 'timestamp', 'url']
            for field in required_fields:
                self.assertIn(field, decision)
    
    def test_performance_with_multiple_snapshots(self):
        """Test performance when there are multiple snapshots per decision."""
        self.client.force_login(self.user)
        
        # Create multiple snapshots for same decision (simulating history)
        for i in range(5):
            DecisionSnapshot.objects.create(
                decision=self.active_decision,
                calculation_status='completed',
                created_at=timezone.now() - timedelta(hours=i)
            )
        
        # Create most recent active snapshot
        DecisionSnapshot.objects.create(
            decision=self.active_decision,
            calculation_status='staging',
            created_at=timezone.now()
        )
        
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Should only return one entry per decision (most recent)
        self.assertEqual(len(data['decisions']), 1)
        self.assertEqual(data['decisions'][0]['status_type'], 'active')


class GlobalStatusIntegrationTest(TestCase):
    """Integration tests for the global status functionality."""
    
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
        
        self.url = reverse('global_calculation_status')
    
    def test_calculation_lifecycle_status_updates(self):
        """Test status updates through a complete calculation lifecycle."""
        self.client.force_login(self.user)
        
        # 1. Creating snapshot
        snapshot = DecisionSnapshot.objects.create(
            decision=self.decision,
            calculation_status='creating'
        )
        
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertTrue(data['has_active_calculations'])
        self.assertEqual(data['decisions'][0]['status'], 'Creating Snapshot...')
        
        # 2. Ready for calculation
        snapshot.calculation_status = 'ready'
        snapshot.save()
        
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertEqual(data['decisions'][0]['status'], 'Ready for Calculation')
        
        # 3. Staging ballots
        snapshot.calculation_status = 'staging'
        snapshot.save()
        
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertEqual(data['decisions'][0]['status'], 'Calculating Votes...')
        
        # 4. Tallying results
        snapshot.calculation_status = 'tallying'
        snapshot.save()
        
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertEqual(data['decisions'][0]['status'], 'Tallying Results...')
        
        # 5. Completed
        snapshot.calculation_status = 'completed'
        snapshot.save()
        
        response = self.client.get(self.url)
        data = json.loads(response.content)
        self.assertFalse(data['has_active_calculations'])
        self.assertTrue(data['has_recent_activity'])
        self.assertIn('✅ Completed', data['decisions'][0]['status'])
    
    def test_multiple_communities_status(self):
        """Test status across multiple communities."""
        self.client.force_login(self.user)
        
        # Create additional communities and decisions
        communities = [CommunityFactory() for _ in range(3)]
        decisions = [DecisionFactory(
            community=community,
            dt_close=timezone.now() + timedelta(days=1)
        ) for community in communities]
        
        # Create snapshots with different statuses
        statuses = ['creating', 'staging', 'completed']
        for decision, status in zip(decisions, statuses):
            DecisionSnapshot.objects.create(
                decision=decision,
                calculation_status=status,
                created_at=timezone.now() - timedelta(minutes=30)
            )
        
        response = self.client.get(self.url)
        data = json.loads(response.content)
        
        # Should have 2 active (creating, staging) and 1 recent (completed)
        active_count = len([d for d in data['decisions'] if d['status_type'] == 'active'])
        recent_count = len([d for d in data['decisions'] if d['status_type'] == 'completed'])
        
        self.assertEqual(active_count, 2)
        self.assertEqual(recent_count, 1)
        self.assertTrue(data['has_active_calculations'])
        self.assertTrue(data['has_recent_activity'])
