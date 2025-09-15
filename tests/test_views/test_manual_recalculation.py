"""
Tests for manual recalculation view and UI integration.

This test suite validates the manual recalculation functionality
added in Plan #22, including:
- Manager-only access controls
- AJAX response handling
- UI status updates
- Error handling and messaging
- Integration with background threading
"""

import pytest
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from democracy.models import Community, Decision, Choice, DecisionSnapshot, Membership
from tests.factories.user_factory import UserFactory
from tests.factories.community_factory import CommunityFactory
from tests.factories.decision_factory import DecisionFactory

User = get_user_model()


class ManualRecalculationViewTest(TestCase):
    """
    Test manual recalculation view functionality.
    
    Tests the AJAX endpoint that allows community managers
    to manually trigger vote recalculation.
    """
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        
        # Create users with different roles
        self.manager = UserFactory(username='manager_user')
        self.regular_member = UserFactory(username='regular_member')
        self.non_member = UserFactory(username='non_member')
        self.other_manager = UserFactory(username='other_manager')
        
        # Create communities
        self.community = CommunityFactory(name='Test Community')
        self.other_community = CommunityFactory(name='Other Community')
        
        # Create memberships
        self.manager_membership = Membership.objects.create(
            member=self.manager,
            community=self.community,
            is_voting_community_member=True,
            is_community_manager=True
        )
        
        self.regular_membership = Membership.objects.create(
            member=self.regular_member,
            community=self.community,
            is_voting_community_member=True,
            is_community_manager=False
        )
        
        self.other_manager_membership = Membership.objects.create(
            member=self.other_manager,
            community=self.other_community,
            is_voting_community_member=True,
            is_community_manager=True
        )
        
        # Create decisions
        self.open_decision = DecisionFactory(
            community=self.community,
            title='Open Decision',
            dt_close=timezone.now() + timedelta(days=1)
        )
        
        self.closed_decision = DecisionFactory(
            community=self.community,
            title='Closed Decision',
            dt_close=timezone.now() - timedelta(hours=1)
        )
        
        # Create choices
        Choice.objects.create(
            decision=self.open_decision,
            title='Choice 1',
            description='First choice'
        )
        Choice.objects.create(
            decision=self.open_decision,
            title='Choice 2',
            description='Second choice'
        )
    
    def get_recalc_url(self, community_id=None, decision_id=None):
        """Helper to get manual recalculation URL."""
        community_id = community_id or self.community.id
        decision_id = decision_id or self.open_decision.id
        return reverse('democracy:manual_recalculation', args=[community_id, decision_id])
    
    def test_manual_recalculation_requires_authentication(self):
        """Test that unauthenticated users cannot access manual recalculation."""
        url = self.get_recalc_url()
        response = self.client.post(url)
        
        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)
    
    def test_manual_recalculation_requires_post_method(self):
        """Test that only POST method is allowed."""
        self.client.force_login(self.manager)
        url = self.get_recalc_url()
        
        # Test GET method
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)  # Method Not Allowed
        
        # Test PUT method
        response = self.client.put(url)
        self.assertEqual(response.status_code, 405)  # Method Not Allowed
        
        # Test DELETE method
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 405)  # Method Not Allowed
    
    @patch('democracy.views.threading.Thread')
    @patch('democracy.views.logging.getLogger')
    def test_successful_manual_recalculation_by_manager(self, mock_logger, mock_thread):
        """Test successful manual recalculation by community manager."""
        self.client.force_login(self.manager)
        url = self.get_recalc_url()
        
        # Mock logger instance
        mock_logger_instance = MagicMock()
        mock_logger.return_value = mock_logger_instance
        
        response = self.client.post(url)
        
        # Verify response
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('Recalculation started', data['message'])
        self.assertIn(self.open_decision.title, data['message'])
        self.assertIn('decision_status', data)
        
        # Verify thread was created and started
        mock_thread.assert_called_once()
        thread_call = mock_thread.call_args
        
        # Check thread configuration
        self.assertEqual(thread_call[1]['target'].__name__, 'recalculate_community_decisions_async')
        self.assertEqual(thread_call[1]['args'][0], self.community.id)
        self.assertIn('manual_recalc_by_manager_user', thread_call[1]['args'][1])
        self.assertEqual(thread_call[1]['args'][2], self.manager.id)
        self.assertTrue(thread_call[1]['daemon'])
        
        # Verify thread.start() was called
        mock_thread.return_value.start.assert_called_once()
        
        # Verify logging
        mock_logger_instance.info.assert_any_call(
            f'[MANUAL_RECALC] [manager_user] - Manual recalculation triggered for decision \'{self.open_decision.title}\''
        )
    
    def test_manual_recalculation_denied_for_regular_member(self):
        """Test that regular community members cannot trigger manual recalculation."""
        self.client.force_login(self.regular_member)
        url = self.get_recalc_url()
        
        response = self.client.post(url)
        
        # Verify response
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Only community managers', data['error'])
    
    def test_manual_recalculation_denied_for_non_member(self):
        """Test that non-community members cannot trigger manual recalculation."""
        self.client.force_login(self.non_member)
        url = self.get_recalc_url()
        
        response = self.client.post(url)
        
        # Verify response
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('must be a community member', data['error'])
    
    def test_manual_recalculation_denied_for_other_community_manager(self):
        """Test that managers from other communities cannot trigger recalculation."""
        self.client.force_login(self.other_manager)
        url = self.get_recalc_url()
        
        response = self.client.post(url)
        
        # Verify response
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('must be a community member', data['error'])
    
    def test_manual_recalculation_denied_for_closed_decision(self):
        """Test that manual recalculation is denied for closed decisions."""
        self.client.force_login(self.manager)
        url = self.get_recalc_url(decision_id=self.closed_decision.id)
        
        response = self.client.post(url)
        
        # Verify response
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Cannot recalculate closed decisions', data['error'])
    
    def test_manual_recalculation_denied_when_already_calculating(self):
        """Test that manual recalculation is denied when calculation is in progress."""
        # Create active calculation snapshot
        DecisionSnapshot.objects.create(
            decision=self.open_decision,
            calculation_status='staging',
            snapshot_data={}
        )
        
        self.client.force_login(self.manager)
        url = self.get_recalc_url()
        
        response = self.client.post(url)
        
        # Verify response
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('already in progress', data['error'])
    
    def test_manual_recalculation_nonexistent_community(self):
        """Test manual recalculation with nonexistent community."""
        self.client.force_login(self.manager)
        
        import uuid
        fake_community_id = uuid.uuid4()
        url = reverse('democracy:manual_recalculation', args=[fake_community_id, self.open_decision.id])
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
    
    def test_manual_recalculation_nonexistent_decision(self):
        """Test manual recalculation with nonexistent decision."""
        self.client.force_login(self.manager)
        
        import uuid
        fake_decision_id = uuid.uuid4()
        url = reverse('democracy:manual_recalculation', args=[self.community.id, fake_decision_id])
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
    
    def test_manual_recalculation_decision_from_different_community(self):
        """Test manual recalculation with decision from different community."""
        # Create decision in other community
        other_decision = DecisionFactory(
            community=self.other_community,
            title='Other Community Decision',
            dt_close=timezone.now() + timedelta(days=1)
        )
        
        self.client.force_login(self.manager)
        url = reverse('democracy:manual_recalculation', args=[self.community.id, other_decision.id])
        
        response = self.client.post(url)
        self.assertEqual(response.status_code, 404)
    
    @patch('democracy.views.threading.Thread')
    def test_manual_recalculation_with_calculation_already_in_progress_different_status(self, mock_thread):
        """Test various calculation statuses that should block manual recalculation."""
        blocking_statuses = ['creating', 'staging', 'tallying']
        
        for status in blocking_statuses:
            with self.subTest(status=status):
                # Clear existing snapshots
                DecisionSnapshot.objects.filter(decision=self.open_decision).delete()
                
                # Create snapshot with blocking status
                DecisionSnapshot.objects.create(
                    decision=self.open_decision,
                    calculation_status=status,
                    snapshot_data={}
                )
                
                self.client.force_login(self.manager)
                url = self.get_recalc_url()
                
                response = self.client.post(url)
                
                # Verify response
                self.assertEqual(response.status_code, 400)
                data = response.json()
                self.assertFalse(data['success'])
                self.assertIn('already in progress', data['error'])
                
                # Verify no thread was started
                mock_thread.assert_not_called()
                mock_thread.reset_mock()
    
    @patch('democracy.views.threading.Thread')
    def test_manual_recalculation_with_completed_calculation(self, mock_thread):
        """Test that manual recalculation works when previous calculation is completed."""
        # Create completed calculation snapshot
        DecisionSnapshot.objects.create(
            decision=self.open_decision,
            calculation_status='completed',
            snapshot_data={}
        )
        
        self.client.force_login(self.manager)
        url = self.get_recalc_url()
        
        response = self.client.post(url)
        
        # Verify response - should succeed
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        
        # Verify thread was started
        mock_thread.assert_called_once()
    
    @patch('democracy.views.threading.Thread')
    def test_manual_recalculation_with_failed_calculation(self, mock_thread):
        """Test that manual recalculation works when previous calculation failed."""
        failed_statuses = ['failed_snapshot', 'failed_staging', 'failed_tallying', 'corrupted']
        
        for status in failed_statuses:
            with self.subTest(status=status):
                # Clear existing snapshots
                DecisionSnapshot.objects.filter(decision=self.open_decision).delete()
                
                # Create failed calculation snapshot
                DecisionSnapshot.objects.create(
                    decision=self.open_decision,
                    calculation_status=status,
                    snapshot_data={},
                    error_log='Test error'
                )
                
                self.client.force_login(self.manager)
                url = self.get_recalc_url()
                
                response = self.client.post(url)
                
                # Verify response - should succeed
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertTrue(data['success'])
                
                # Verify thread was started
                mock_thread.assert_called_once()
                mock_thread.reset_mock()
    
    @patch('democracy.views.recalculate_community_decisions_async')
    @patch('democracy.views.logging.getLogger')
    def test_manual_recalculation_exception_handling(self, mock_logger, mock_recalc_func):
        """Test exception handling in manual recalculation view."""
        # Mock logger instance
        mock_logger_instance = MagicMock()
        mock_logger.return_value = mock_logger_instance
        
        # Mock recalculation function to raise exception during import
        mock_recalc_func.side_effect = Exception('Import error')
        
        self.client.force_login(self.manager)
        url = self.get_recalc_url()
        
        with patch('democracy.views.threading.Thread') as mock_thread:
            # Mock thread creation to raise exception
            mock_thread.side_effect = Exception('Thread creation failed')
            
            response = self.client.post(url)
        
        # Verify error response
        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('error occurred while starting recalculation', data['error'])
        
        # Verify error logging
        mock_logger_instance.error.assert_called()


class ManualRecalculationUIIntegrationTest(TestCase):
    """
    Test UI integration for manual recalculation functionality.
    
    Tests the JavaScript and template integration that provides
    the manual recalculation button and status updates.
    """
    
    def setUp(self):
        """Set up test data."""
        self.manager = UserFactory(username='manager')
        self.community = CommunityFactory(name='Test Community')
        
        self.manager_membership = Membership.objects.create(
            member=self.manager,
            community=self.community,
            is_voting_community_member=True,
            is_community_manager=True
        )
        
        self.decision = DecisionFactory(
            community=self.community,
            title='Test Decision',
            dt_close=timezone.now() + timedelta(days=1)
        )
        
        Choice.objects.create(
            decision=self.decision,
            title='Choice 1',
            description='First choice'
        )
    
    def test_decision_detail_includes_manual_recalc_button_for_managers(self):
        """Test that decision detail page includes manual recalculation button for managers."""
        self.client.force_login(self.manager)
        url = reverse('democracy:decision_detail', args=[self.community.id, self.decision.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'manual-recalc-btn')
        self.assertContains(response, 'triggerManualRecalculation()')
        self.assertContains(response, '🔄 Recalculate Now')
    
    def test_decision_detail_excludes_manual_recalc_button_for_regular_members(self):
        """Test that decision detail page excludes manual recalculation button for regular members."""
        regular_user = UserFactory(username='regular')
        Membership.objects.create(
            member=regular_user,
            community=self.community,
            is_voting_community_member=True,
            is_community_manager=False
        )
        
        self.client.force_login(regular_user)
        url = reverse('democracy:decision_detail', args=[self.community.id, self.decision.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'manual-recalc-btn')
        self.assertNotContains(response, 'triggerManualRecalculation()')
    
    def test_decision_detail_shows_calculation_status(self):
        """Test that decision detail page shows calculation status."""
        self.client.force_login(self.manager)
        url = reverse('democracy:decision_detail', args=[self.community.id, self.decision.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'calculation-status')
        self.assertContains(response, 'Calculation</span>')
        
        # Should show default status for decision with no snapshots
        self.assertContains(response, 'Ready for Calculation')
    
    def test_decision_detail_shows_last_calculated_time(self):
        """Test that decision detail page shows last calculated time when available."""
        # Create completed snapshot
        snapshot = DecisionSnapshot.objects.create(
            decision=self.decision,
            calculation_status='completed',
            snapshot_data={}
        )
        
        self.client.force_login(self.manager)
        url = reverse('democracy:decision_detail', args=[self.community.id, self.decision.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Last Updated')
        self.assertContains(response, 'ago')
    
    def test_decision_detail_javascript_includes_recalc_functions(self):
        """Test that decision detail page includes manual recalculation JavaScript functions."""
        self.client.force_login(self.manager)
        url = reverse('democracy:decision_detail', args=[self.community.id, self.decision.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Check for JavaScript functions
        self.assertContains(response, 'function triggerManualRecalculation()')
        self.assertContains(response, 'function pollCalculationStatus()')
        
        # Check for AJAX setup
        self.assertContains(response, 'X-CSRFToken')
        self.assertContains(response, 'manual_recalculation')
        
        # Check for UI update elements
        self.assertContains(response, 'recalc-message')
        self.assertContains(response, 'calculation-status')
    
    def test_closed_decision_excludes_manual_recalc_button(self):
        """Test that closed decisions don't show manual recalculation button even for managers."""
        # Close the decision
        self.decision.dt_close = timezone.now() - timedelta(hours=1)
        self.decision.save()
        
        self.client.force_login(self.manager)
        url = reverse('democracy:decision_detail', args=[self.community.id, self.decision.id])
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'manual-recalc-btn')
        self.assertNotContains(response, '🔄 Recalculate Now')
