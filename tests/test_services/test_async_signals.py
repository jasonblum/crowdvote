"""
Tests for asynchronous vote calculation signals and threading system.

This test suite validates Plan #22 implementation:
- Django signals trigger automatic recalculation
- Background threading works correctly
- UI status indicators function properly
- Manual recalculation controls work for managers
- Comprehensive logging captures all events
- Integration with Plan #21 snapshot isolation system
"""

import pytest
import threading
import time
from unittest.mock import patch, MagicMock, call
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.test.utils import override_settings

from security.models import CustomUser
from democracy.models import Community, Decision, Choice, Ballot, Vote, DecisionSnapshot, Membership, Following
from democracy.signals import (
    recalculate_community_decisions_async,
    vote_changed,
    following_changed,
    membership_changed,
    ballot_tags_changed,
    decision_status_changed
)
from tests.factories.user_factory import UserFactory
from tests.factories.community_factory import CommunityFactory
from tests.factories.decision_factory import DecisionFactory

User = get_user_model()


@pytest.mark.django_db(transaction=True)
class AsyncCalculationSignalsTest(TransactionTestCase):
    """
    Test Django signals for automatic vote recalculation.
    
    Uses TransactionTestCase to properly test signal handling
    with database transactions and threading.
    """
    
    def setUp(self):
        """Set up test data for signal testing."""
        # Mock the async function during setup to prevent background threads
        with patch('democracy.signals.recalculate_community_decisions_async'):
            self.user1 = UserFactory(username='voter1')
            self.user2 = UserFactory(username='voter2')
            self.manager = UserFactory(username='manager')
            
            self.community = CommunityFactory(name='Test Community')
            
            # Create memberships
            self.membership1 = Membership.objects.create(
                member=self.user1,
                community=self.community,
                is_voting_community_member=True
            )
            self.membership2 = Membership.objects.create(
                member=self.user2,
                community=self.community,
                is_voting_community_member=True
            )
            self.manager_membership = Membership.objects.create(
                member=self.manager,
                community=self.community,
                is_voting_community_member=True,
                is_community_manager=True
            )
            
            # Create open decision
            self.decision = DecisionFactory(
                community=self.community,
                title='Test Decision',
                dt_close=timezone.now() + timedelta(days=1)
            )
            
            # Create choices
            self.choice1 = Choice.objects.create(
                decision=self.decision,
                title='Choice 1',
                description='First choice'
            )
            self.choice2 = Choice.objects.create(
                decision=self.decision,
                title='Choice 2',
                description='Second choice'
            )
    
    @patch('democracy.signals.threading.Thread')
    @patch('democracy.signals.CreateCalculationSnapshot')
    @patch('democracy.signals.SnapshotBasedStageBallots')
    @patch('democracy.signals.Tally')
    def test_vote_cast_triggers_recalculation(self, mock_tally, mock_stage, mock_snapshot, mock_thread):
        """Test that casting a vote triggers automatic recalculation."""
        # Create ballot and vote
        ballot = Ballot.objects.create(
            decision=self.decision,
            voter=self.user1,
            is_calculated=False
        )
        
        # This should trigger the vote_changed signal
        vote = Vote.objects.create(
            choice=self.choice1,
            ballot=ballot,
            stars=4
        )
        
        # Verify thread was started
        mock_thread.assert_called_once()
        thread_call = mock_thread.call_args
        
        # Check thread target and arguments
        self.assertEqual(thread_call[1]['target'], recalculate_community_decisions_async)
        self.assertEqual(thread_call[1]['args'][0], self.community.id)  # community_id
        self.assertEqual(thread_call[1]['args'][1], 'vote_cast')  # trigger_event
        self.assertEqual(thread_call[1]['args'][2], self.user1.id)  # user_id
        self.assertTrue(thread_call[1]['daemon'])
        
        # Verify thread.start() was called
        mock_thread.return_value.start.assert_called_once()
    
    @patch('democracy.signals.threading.Thread')
    def test_vote_update_triggers_recalculation(self, mock_thread):
        """Test that updating a vote triggers automatic recalculation."""
        # Create ballot and vote
        ballot = Ballot.objects.create(
            decision=self.decision,
            voter=self.user1,
            is_calculated=False
        )
        vote = Vote.objects.create(
            choice=self.choice1,
            ballot=ballot,
            stars=3
        )
        
        # Clear the mock from vote creation
        mock_thread.reset_mock()
        
        # Update the vote (this should trigger vote_changed with created=False)
        vote.stars = 5
        vote.save()
        
        # Verify thread was started for update
        mock_thread.assert_called_once()
        thread_call = mock_thread.call_args
        self.assertEqual(thread_call[1]['args'][1], 'vote_updated')
    
    @patch('democracy.signals.threading.Thread')
    def test_vote_delete_triggers_recalculation(self, mock_thread):
        """Test that deleting a vote triggers automatic recalculation."""
        # Create ballot and vote
        ballot = Ballot.objects.create(
            decision=self.decision,
            voter=self.user1,
            is_calculated=False
        )
        vote = Vote.objects.create(
            choice=self.choice1,
            ballot=ballot,
            stars=3
        )
        
        # Clear the mock from vote creation
        mock_thread.reset_mock()
        
        # Delete the vote (this should trigger vote_deleted signal)
        vote.delete()
        
        # Verify thread was started for deletion
        mock_thread.assert_called_once()
        thread_call = mock_thread.call_args
        self.assertEqual(thread_call[1]['args'][1], 'vote_deleted')
    
    @patch('democracy.signals.threading.Thread')
    def test_following_created_triggers_recalculation(self, mock_thread):
        """Test that creating a following relationship triggers recalculation."""
        # Create following relationship (Plan #6: Following is now Membership→Membership)
        following = Following.objects.create(
            follower=self.membership1,
            followee=self.membership2,
            tags='governance,budget',
            order=1
        )
        
        # Verify thread was started
        mock_thread.assert_called_once()
        thread_call = mock_thread.call_args
        self.assertEqual(thread_call[1]['args'][1], 'following_started')
        self.assertEqual(thread_call[1]['args'][2], self.user1.id)
    
    @patch('democracy.signals.threading.Thread')
    def test_following_deleted_triggers_recalculation(self, mock_thread):
        """Test that deleting a following relationship triggers recalculation."""
        # Create following relationship (Plan #6: Following is now Membership→Membership)
        following = Following.objects.create(
            follower=self.membership1,
            followee=self.membership2,
            tags='governance',
            order=1
        )
        
        # Clear the mock from creation
        mock_thread.reset_mock()
        
        # Delete the following relationship
        following.delete()
        
        # Verify thread was started for deletion
        mock_thread.assert_called_once()
        thread_call = mock_thread.call_args
        self.assertEqual(thread_call[1]['args'][1], 'following_deleted')
    
    @patch('democracy.signals.threading.Thread')
    def test_membership_created_triggers_recalculation(self, mock_thread):
        """Test that creating a membership triggers recalculation."""
        new_user = UserFactory(username='new_member')
        
        # Create membership (this should trigger membership_changed signal)
        membership = Membership.objects.create(
            member=new_user,
            community=self.community,
            is_voting_community_member=True
        )
        
        # Verify thread was started
        mock_thread.assert_called_once()
        thread_call = mock_thread.call_args
        self.assertEqual(thread_call[1]['args'][1], 'member_joined')
        self.assertEqual(thread_call[1]['args'][2], new_user.id)
    
    @patch('democracy.signals.threading.Thread')
    def test_membership_deleted_triggers_recalculation(self, mock_thread):
        """Test that deleting a membership triggers recalculation."""
        # Delete existing membership
        self.membership1.delete()
        
        # Verify thread was started
        mock_thread.assert_called_once()
        thread_call = mock_thread.call_args
        self.assertEqual(thread_call[1]['args'][1], 'member_left')
        self.assertEqual(thread_call[1]['args'][2], self.user1.id)
    
    def test_closed_decision_no_recalculation(self):
        """Test that votes on closed decisions don't trigger recalculation."""
        # Close the decision
        self.decision.dt_close = timezone.now() - timedelta(hours=1)
        self.decision.save()
        
        with patch('democracy.signals.threading.Thread') as mock_thread:
            # Create vote on closed decision
            ballot = Ballot.objects.create(
                decision=self.decision,
                voter=self.user1,
                is_calculated=False
            )
            Vote.objects.create(
                choice=self.choice1,
                ballot=ballot,
                stars=4
            )
            
            # Verify no thread was started
            mock_thread.assert_not_called()
    
    @patch('democracy.signals.threading.Thread')
    def test_decision_published_triggers_recalculation(self, mock_thread):
        """Test that publishing a decision triggers initial recalculation."""
        # Create new decision that's open for voting
        new_decision = DecisionFactory(
            community=self.community,
            title='New Decision',
            dt_close=timezone.now() + timedelta(days=1)
        )
        
        # Verify thread was started for decision publication
        mock_thread.assert_called_once()
        thread_call = mock_thread.call_args
        self.assertEqual(thread_call[1]['args'][1], 'decision_published')


@pytest.mark.django_db(transaction=True)
class AsyncCalculationFunctionTest(TestCase):
    """
    Test the async calculation function itself.
    
    Tests the core recalculate_community_decisions_async function
    with mocked services to verify integration with Plan #21.
    """
    
    def setUp(self):
        """Set up test data."""
        # Mock the async function during setup to prevent background threads
        with patch('democracy.signals.recalculate_community_decisions_async'):
            self.community = CommunityFactory(name='Test Community')
            self.decision = DecisionFactory(
                community=self.community,
                title='Test Decision',
                dt_close=timezone.now() + timedelta(days=1)
            )
    
    @patch('democracy.signals.Tally')
    @patch('democracy.signals.SnapshotBasedStageBallots')
    @patch('democracy.signals.CreateCalculationSnapshot')
    @patch('democracy.signals.logger')
    def test_recalculate_community_decisions_async_success(self, mock_logger, mock_snapshot_service, mock_stage_service, mock_tally_service):
        """Test successful async recalculation with Plan #21 services."""
        # Mock service instances and snapshot
        mock_snapshot = MagicMock()
        mock_snapshot.id = 'test-snapshot-id'
        
        mock_snapshot_instance = MagicMock()
        mock_snapshot_instance.process.return_value = mock_snapshot
        mock_snapshot_service.return_value = mock_snapshot_instance
        
        mock_stage_instance = MagicMock()
        mock_stage_service.return_value = mock_stage_instance
        
        mock_tally_instance = MagicMock()
        mock_tally_service.return_value = mock_tally_instance
        
        # Run the async function
        recalculate_community_decisions_async(
            self.community.id,
            trigger_event='test_trigger',
            user_id=None
        )
        
        # Verify services were called correctly
        mock_snapshot_service.assert_called_once_with(self.decision.id)
        mock_snapshot_instance.process.assert_called_once()
        
        mock_stage_service.assert_called_once_with(mock_snapshot.id)
        mock_stage_instance.process.assert_called_once()
        
        mock_tally_service.assert_called_once()
        mock_tally_instance.process.assert_called_once()
        
        # Verify logging
        mock_logger.info.assert_any_call(
            f'[RECALC_START] [system] - Background recalculation triggered by test_trigger in community {self.community.id}'
        )
        mock_logger.info.assert_any_call(
            f'[SNAPSHOT_CREATE_COMPLETE] [system] - Snapshot created successfully: test-snapshot-id'
        )
    
    @patch('democracy.signals.logger')
    def test_recalculate_nonexistent_community(self, mock_logger):
        """Test handling of nonexistent community."""
        import uuid
        fake_community_id = uuid.uuid4()
        
        # Run the async function with fake community ID
        recalculate_community_decisions_async(
            fake_community_id,
            trigger_event='test_trigger',
            user_id=None
        )
        
        # Verify error logging
        mock_logger.error.assert_called_once_with(
            f'[RECALC_ERROR] [system] - Community {fake_community_id} not found'
        )
    
    @patch('democracy.signals.CreateCalculationSnapshot')
    @patch('democracy.signals.logger')
    def test_recalculate_snapshot_creation_error(self, mock_logger, mock_snapshot_service):
        """Test handling of snapshot creation errors."""
        # Mock service to raise exception
        mock_snapshot_instance = MagicMock()
        mock_snapshot_instance.process.side_effect = Exception('Snapshot creation failed')
        mock_snapshot_service.return_value = mock_snapshot_instance
        
        # Run the async function
        recalculate_community_decisions_async(
            self.community.id,
            trigger_event='test_trigger',
            user_id=None
        )
        
        # Verify error logging
        mock_logger.error.assert_any_call(
            f"[RECALC_ERROR] [system] - Failed to recalculate decision '{self.decision.title}': Snapshot creation failed"
        )


@pytest.mark.django_db(transaction=True)
class DecisionStatusMethodsTest(TestCase):
    """
    Test Decision model status methods for UI indicators.
    
    Tests the new methods added for Plan #22:
    - is_calculating()
    - get_calculation_status()
    - last_calculated property
    """
    
    def setUp(self):
        """Set up test data."""
        self.community = CommunityFactory(name='Test Community')
        self.decision = DecisionFactory(
            community=self.community,
            title='Test Decision',
            dt_close=timezone.now() + timedelta(days=1)
        )
    
    def test_is_calculating_no_snapshots(self):
        """Test is_calculating returns False when no snapshots exist."""
        self.assertFalse(self.decision.is_calculating())
    
    def test_is_calculating_with_active_snapshot(self):
        """Test is_calculating returns True when active calculation exists."""
        # Create snapshot with active calculation status
        DecisionSnapshot.objects.create(
            decision=self.decision,
            calculation_status='staging',
            snapshot_data={}
        )
        
        self.assertTrue(self.decision.is_calculating())
    
    def test_is_calculating_with_completed_snapshot(self):
        """Test is_calculating returns False when calculation is completed."""
        # Create completed snapshot
        DecisionSnapshot.objects.create(
            decision=self.decision,
            calculation_status='completed',
            snapshot_data={}
        )
        
        self.assertFalse(self.decision.is_calculating())
    
    def test_get_calculation_status_closed_decision(self):
        """Test get_calculation_status for closed decision."""
        # Close the decision
        self.decision.dt_close = timezone.now() - timedelta(hours=1)
        self.decision.save()
        
        self.assertEqual(self.decision.get_calculation_status(), 'Closed')
    
    def test_get_calculation_status_no_snapshots(self):
        """Test get_calculation_status when no snapshots exist."""
        self.assertEqual(self.decision.get_calculation_status(), 'Ready for Calculation')
    
    def test_get_calculation_status_various_states(self):
        """Test get_calculation_status for various snapshot states."""
        status_tests = [
            ('creating', 'Creating Snapshot...'),
            ('ready', 'Ready'),
            ('staging', 'Calculating Votes...'),
            ('tallying', 'Tallying Results...'),
            ('completed', 'Up to Date'),
            ('failed_snapshot', 'Error (Snapshot Failed)'),
            ('failed_staging', 'Error (Calculation Failed)'),
            ('failed_tallying', 'Error (Tally Failed)'),
            ('corrupted', 'Error (Data Corrupted)'),
        ]
        
        for status, expected_display in status_tests:
            with self.subTest(status=status):
                # Clear existing snapshots
                self.decision.snapshots.all().delete()
                
                # Create snapshot with specific status
                DecisionSnapshot.objects.create(
                    decision=self.decision,
                    calculation_status=status,
                    snapshot_data={}
                )
                
                self.assertEqual(self.decision.get_calculation_status(), expected_display)
    
    def test_last_calculated_no_completed_snapshots(self):
        """Test last_calculated property when no completed snapshots exist."""
        # Create non-completed snapshot
        DecisionSnapshot.objects.create(
            decision=self.decision,
            calculation_status='staging',
            snapshot_data={}
        )
        
        self.assertIsNone(self.decision.last_calculated)
    
    def test_last_calculated_with_completed_snapshot(self):
        """Test last_calculated property with completed snapshot."""
        # Create completed snapshot
        snapshot = DecisionSnapshot.objects.create(
            decision=self.decision,
            calculation_status='completed',
            snapshot_data={}
        )
        
        self.assertEqual(self.decision.last_calculated, snapshot.created)


@pytest.mark.django_db(transaction=True)
class ManualRecalculationViewTest(TestCase):
    """
    Test the manual recalculation view for community managers.
    
    Tests the manual_recalculation view that allows managers
    to trigger recalculation on demand.
    """
    
    def setUp(self):
        """Set up test data."""
        # Mock the async function during setup to prevent background threads
        with patch('democracy.signals.recalculate_community_decisions_async'):
            self.manager = UserFactory(username='manager')
            self.regular_user = UserFactory(username='regular')
            self.non_member = UserFactory(username='non_member')
            
            self.community = CommunityFactory(name='Test Community')
            
            # Create memberships
            self.manager_membership = Membership.objects.create(
                member=self.manager,
                community=self.community,
                is_voting_community_member=True,
                is_community_manager=True
            )
            self.regular_membership = Membership.objects.create(
                member=self.regular_user,
                community=self.community,
                is_voting_community_member=True,
                is_community_manager=False
            )
            
            # Create open decision
            self.decision = DecisionFactory(
                community=self.community,
                title='Test Decision',
                dt_close=timezone.now() + timedelta(days=1)
            )
        
        self.url = f'/communities/{self.community.id}/decisions/{self.decision.id}/recalculate/'
    
    def test_manual_recalculation_requires_login(self):
        """Test that manual recalculation requires authentication."""
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_manual_recalculation_requires_post(self):
        """Test that manual recalculation requires POST method."""
        self.client.force_login(self.manager)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)  # Method not allowed
    
    @patch('democracy.views.threading.Thread')
    def test_manual_recalculation_success_manager(self, mock_thread):
        """Test successful manual recalculation by manager."""
        self.client.force_login(self.manager)
        
        response = self.client.post(self.url)
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('Recalculation started', data['message'])
        self.assertIn(self.decision.title, data['message'])
        
        # Verify thread was started
        mock_thread.assert_called_once()
    
    def test_manual_recalculation_denied_regular_user(self):
        """Test that regular users cannot trigger manual recalculation."""
        self.client.force_login(self.regular_user)
        
        response = self.client.post(self.url)
        
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Only community managers', data['error'])
    
    def test_manual_recalculation_denied_non_member(self):
        """Test that non-members cannot trigger manual recalculation."""
        self.client.force_login(self.non_member)
        
        response = self.client.post(self.url)
        
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('must be a community member', data['error'])
    
    def test_manual_recalculation_closed_decision(self):
        """Test that manual recalculation is denied for closed decisions."""
        # Close the decision
        self.decision.dt_close = timezone.now() - timedelta(hours=1)
        self.decision.save()
        
        self.client.force_login(self.manager)
        response = self.client.post(self.url)
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('Cannot recalculate closed decisions', data['error'])
    
    def test_manual_recalculation_already_calculating(self):
        """Test that manual recalculation is denied when already calculating."""
        # Create active calculation snapshot
        DecisionSnapshot.objects.create(
            decision=self.decision,
            calculation_status='staging',
            snapshot_data={}
        )
        
        self.client.force_login(self.manager)
        response = self.client.post(self.url)
        
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])
        self.assertIn('already in progress', data['error'])


@pytest.mark.django_db(transaction=True)
class LoggingIntegrationTest(TestCase):
    """
    Test comprehensive logging integration for Plan #22.
    
    Verifies that all important events are properly logged
    with the correct format and information.
    """
    
    def setUp(self):
        """Set up test data."""
        # Mock the async function during setup to prevent background threads
        with patch('democracy.signals.recalculate_community_decisions_async'):
            self.user = UserFactory(username='test_user')
            self.community = CommunityFactory(name='Test Community')
            self.membership = Membership.objects.create(
                member=self.user,
                community=self.community,
                is_voting_community_member=True
            )
    
    @patch('democracy.signals.logger')
    def test_vote_cast_logging(self, mock_logger):
        """Test that vote casting is properly logged."""
        decision = DecisionFactory(
            community=self.community,
            title='Test Decision',
            dt_close=timezone.now() + timedelta(days=1)
        )
        choice = Choice.objects.create(
            decision=decision,
            title='Test Choice',
            description='Test choice description'
        )
        
        # Create ballot and vote
        ballot = Ballot.objects.create(
            decision=decision,
            voter=self.user,
            is_calculated=False
        )
        
        with patch('democracy.signals.threading.Thread'):
            Vote.objects.create(
                choice=choice,
                ballot=ballot,
                stars=4
            )
        
        # Verify logging
        mock_logger.info.assert_any_call(
            f'[VOTE_CAST] [{self.user.username}] - Vote cast on decision \'{decision.title}\' (Choice: {choice.title}, Stars: 4)'
        )
    
    @patch('democracy.signals.logger')
    def test_following_created_logging(self, mock_logger):
        """Test that following creation is properly logged."""
        user2 = UserFactory(username='followee')
        membership2 = Membership.objects.create(
            member=user2,
            community=self.community,
            is_voting_community_member=True
        )
        
        # Get user's membership
        membership1 = Membership.objects.get(member=self.user, community=self.community)
        
        with patch('democracy.signals.threading.Thread'):
            Following.objects.create(
                follower=membership1,
                followee=membership2,
                tags='governance,budget',
                order=1
            )
        
        # Verify logging (note: action.title() capitalizes "Started")
        mock_logger.info.assert_any_call(
            f'[FOLLOWING_STARTED] [{self.user.username}] - Started following {user2.username} on tags: governance,budget (priority: 1)'
        )
    
    @patch('democracy.signals.logger')
    def test_member_joined_logging(self, mock_logger):
        """Test that member joining is properly logged."""
        new_user = UserFactory(username='new_member')
        
        with patch('democracy.signals.threading.Thread'):
            Membership.objects.create(
                member=new_user,
                community=self.community,
                is_voting_community_member=True
            )
        
        # Verify logging
        mock_logger.info.assert_any_call(
            f'[MEMBER_JOINED] [{new_user.username}] - Joined community \'{self.community.name}\' (Voting: True)'
        )
