"""
Tests for Plan #21 Snapshot Isolation Vote Calculation System.

This module tests the snapshot creation and isolation functionality that ensures
vote calculations are not affected by concurrent user activity.
"""

import pytest
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import transaction

from democracy.models import Decision, DecisionSnapshot, Community, Choice, Ballot, Vote, Membership, Following
from democracy.services import CreateCalculationSnapshot, SnapshotBasedStageBallots
from security.models import CustomUser
from tests.factories.user_factory import UserFactory
from tests.factories.community_factory import CommunityFactory
from tests.factories.decision_factory import DecisionFactory


class TestDecisionSnapshotModel(TestCase):
    """Test the DecisionSnapshot model validation and behavior."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.community = CommunityFactory()
        self.membership = Membership.objects.create(
            member=self.user,
            community=self.community,
            is_voting_community_member=True
        )
        self.decision = DecisionFactory(community=self.community)
    
    def test_snapshot_creation_basic(self):
        """Test basic snapshot creation."""
        snapshot = DecisionSnapshot.objects.create(
            decision=self.decision,
            calculation_status='ready',
            total_eligible_voters=1,
            total_votes_cast=0
        )
        
        self.assertEqual(snapshot.decision, self.decision)
        self.assertEqual(snapshot.calculation_status, 'ready')
        self.assertFalse(snapshot.is_final)
        self.assertEqual(snapshot.retry_count, 0)
        self.assertIsNone(snapshot.last_error)
    
    def test_final_snapshot_uniqueness_validation(self):
        """Test that only one final snapshot is allowed per decision."""
        # Close the decision first
        self.decision.dt_close = timezone.now() - timedelta(hours=1)
        self.decision.save()
        
        # Create first final snapshot
        DecisionSnapshot.objects.create(
            decision=self.decision,
            is_final=True,
            calculation_status='completed'
        )
        
        # Try to create second final snapshot - should fail
        with self.assertRaises(ValidationError) as cm:
            snapshot = DecisionSnapshot(
                decision=self.decision,
                is_final=True,
                calculation_status='completed'
            )
            snapshot.full_clean()
        
        self.assertIn('Only one final snapshot is allowed per decision', str(cm.exception))
    
    def test_final_snapshot_for_open_decision_validation(self):
        """Test that final snapshots cannot be created for open decisions."""
        # Ensure decision is open
        self.decision.dt_close = timezone.now() + timedelta(hours=1)
        self.decision.save()
        
        with self.assertRaises(ValidationError) as cm:
            snapshot = DecisionSnapshot(
                decision=self.decision,
                is_final=True,
                calculation_status='completed'
            )
            snapshot.save()
        
        self.assertIn('Cannot create final snapshot for open decision', str(cm.exception))
    
    def test_decision_snapshot_methods(self):
        """Test Decision model snapshot-related methods."""
        # Create some snapshots
        snapshot1 = DecisionSnapshot.objects.create(
            decision=self.decision,
            calculation_status='completed'
        )
        snapshot2 = DecisionSnapshot.objects.create(
            decision=self.decision,
            calculation_status='ready'
        )
        
        # Test get_latest_snapshot
        latest = self.decision.get_latest_snapshot()
        self.assertEqual(latest, snapshot2)  # Most recent
        
        # Test get_final_snapshot (none exists)
        final = self.decision.get_final_snapshot()
        self.assertIsNone(final)
        
        # Close decision and create final snapshot
        self.decision.dt_close = timezone.now() - timedelta(hours=1)
        self.decision.save()
        
        snapshot1.is_final = True
        snapshot1.save()
        
        final = self.decision.get_final_snapshot()
        self.assertEqual(final, snapshot1)
    
    def test_snapshot_participation_rate_calculation(self):
        """Test participation rate calculation."""
        snapshot = DecisionSnapshot.objects.create(
            decision=self.decision,
            total_eligible_voters=100,
            total_votes_cast=25,
            total_calculated_votes=45
        )
        
        # Total participation: (25 + 45) / 100 = 70%
        self.assertEqual(snapshot.participation_rate, 70.0)
        
        # Test delegation rate: 45 / (25 + 45) = 64.29%
        self.assertAlmostEqual(snapshot.delegation_rate, 64.29, places=2)
    
    def test_snapshot_zero_voters_edge_case(self):
        """Test participation rate with zero eligible voters."""
        snapshot = DecisionSnapshot.objects.create(
            decision=self.decision,
            total_eligible_voters=0,
            total_votes_cast=0,
            total_calculated_votes=0
        )
        
        self.assertEqual(snapshot.participation_rate, 0.0)
        self.assertEqual(snapshot.delegation_rate, 0.0)


class TestCreateCalculationSnapshotService(TestCase):
    """Test the CreateCalculationSnapshot service."""
    
    def setUp(self):
        """Set up test data."""
        self.user1 = UserFactory(username='voter1')
        self.user2 = UserFactory(username='voter2')
        self.user3 = UserFactory(username='follower1')
        
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
        self.membership3 = Membership.objects.create(
            member=self.user3,
            community=self.community,
            is_voting_community_member=True
        )
        
        # Create following relationship (Membership to Membership)
        Following.objects.create(
            follower=self.membership3,
            followee=self.membership1,
            tags='governance,budget',
            order=1
        )
        
        self.decision = DecisionFactory(community=self.community)
        # Clear any choices created by factory
        self.decision.choices.all().delete()
        
        self.choice1 = Choice.objects.create(
            decision=self.decision,
            title='Option A',
            description='First option'
        )
        self.choice2 = Choice.objects.create(
            decision=self.decision,
            title='Option B',
            description='Second option'
        )
        
        # Create some votes
        ballot = Ballot.objects.create(
            decision=self.decision,
            voter=self.user1,
            tags='governance'
        )
        Vote.objects.create(ballot=ballot, choice=self.choice1, stars=5)
        Vote.objects.create(ballot=ballot, choice=self.choice2, stars=2)
    
    def test_snapshot_creation_success(self):
        """Test successful snapshot creation."""
        service = CreateCalculationSnapshot(self.decision.id)
        snapshot = service.process()
        
        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot.decision, self.decision)
        self.assertEqual(snapshot.calculation_status, 'ready')
        self.assertEqual(snapshot.total_eligible_voters, 3)  # 3 voting members
        self.assertEqual(snapshot.total_votes_cast, 1)  # 1 ballot
        
        # Check snapshot data structure
        snapshot_data = snapshot.snapshot_data
        self.assertIn('metadata', snapshot_data)
        self.assertIn('community_memberships', snapshot_data)
        self.assertIn('followings', snapshot_data)
        self.assertIn('existing_ballots', snapshot_data)
        self.assertIn('decision_data', snapshot_data)
        self.assertIn('choices_data', snapshot_data)
        
        # Verify captured data
        self.assertEqual(len(snapshot_data['community_memberships']), 3)
        self.assertEqual(len(snapshot_data['existing_ballots']), 1)
        self.assertEqual(len(snapshot_data['choices_data']), 2)
        
        # Check following relationships
        followings = snapshot_data['followings']
        self.assertIn(str(self.user3.id), followings)
        user3_followings = followings[str(self.user3.id)]
        self.assertEqual(len(user3_followings), 1)
        self.assertEqual(user3_followings[0]['followee_id'], str(self.user1.id))
        self.assertEqual(user3_followings[0]['tags'], 'governance,budget')
    
    def test_snapshot_captures_vote_data(self):
        """Test that snapshot captures complete vote data."""
        service = CreateCalculationSnapshot(self.decision.id)
        snapshot = service.process()
        
        snapshot_data = snapshot.snapshot_data
        existing_ballots = snapshot_data['existing_ballots']
        
        # Should have one ballot for user1
        self.assertIn(str(self.user1.id), existing_ballots)
        ballot_data = existing_ballots[str(self.user1.id)]
        
        self.assertEqual(ballot_data['voter_id'], str(self.user1.id))
        self.assertEqual(ballot_data['tags'], 'governance')
        self.assertFalse(ballot_data['is_calculated'])
        
        # Check vote data (stored as strings for JSON compatibility with Decimal)
        votes = ballot_data['votes']
        self.assertEqual(len(votes), 2)
        self.assertEqual(votes[str(self.choice1.id)], '5.00')
        self.assertEqual(votes[str(self.choice2.id)], '2.00')
    
    def test_snapshot_error_handling(self):
        """Test snapshot creation error handling."""
        # Use invalid decision ID
        service = CreateCalculationSnapshot('invalid-uuid')
        
        with self.assertRaises(Exception):
            service.process()
    
    def test_snapshot_final_flag_for_closed_decision(self):
        """Test that closed decisions create final snapshots."""
        # Close the decision
        self.decision.dt_close = timezone.now() - timedelta(hours=1)
        self.decision.save()
        
        service = CreateCalculationSnapshot(self.decision.id)
        snapshot = service.process()
        
        self.assertTrue(snapshot.is_final)
    
    def test_snapshot_final_flag_for_open_decision(self):
        """Test that open decisions create non-final snapshots."""
        # Ensure decision is open
        self.decision.dt_close = timezone.now() + timedelta(hours=1)
        self.decision.save()
        
        service = CreateCalculationSnapshot(self.decision.id)
        snapshot = service.process()
        
        self.assertFalse(snapshot.is_final)


class TestSnapshotBasedStageBallots(TestCase):
    """Test the SnapshotBasedStageBallots service."""
    
    def setUp(self):
        """Set up test data."""
        self.user = UserFactory()
        self.community = CommunityFactory()
        self.membership = Membership.objects.create(
            member=self.user,
            community=self.community,
            is_voting_community_member=True
        )
        self.decision = DecisionFactory(community=self.community)
        
        # Create a snapshot
        self.snapshot = DecisionSnapshot.objects.create(
            decision=self.decision,
            calculation_status='ready',
            snapshot_data={
                'metadata': {
                    'calculation_timestamp': timezone.now().isoformat(),
                    'decision_status': 'active'
                },
                'community_memberships': [str(self.user.id)],
                'followings': {},
                'existing_ballots': {},
                'decision_data': {
                    'id': str(self.decision.id),
                    'title': self.decision.title
                },
                'choices_data': []
            }
        )
    
    def test_snapshot_based_processing_success(self):
        """Test successful snapshot-based processing."""
        service = SnapshotBasedStageBallots(self.snapshot.id)
        results = service.process()
        
        self.assertIsNotNone(results)
        self.assertIn('total_members', results)
        self.assertIn('manual_ballots', results)
        self.assertIn('calculated_ballots', results)
        self.assertIn('no_ballot', results)
        
        # Check snapshot status was updated
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.calculation_status, 'completed')
    
    def test_snapshot_based_processing_error_handling(self):
        """Test error handling in snapshot-based processing."""
        # Use invalid snapshot ID
        service = SnapshotBasedStageBallots('invalid-uuid')
        
        with self.assertRaises(Exception):
            service.process()
    
    def test_snapshot_status_tracking(self):
        """Test that snapshot status is properly tracked."""
        service = SnapshotBasedStageBallots(self.snapshot.id)
        
        # Initial status should be ready
        self.assertEqual(self.snapshot.calculation_status, 'ready')
        
        # Process should update status
        service.process()
        
        self.snapshot.refresh_from_db()
        self.assertEqual(self.snapshot.calculation_status, 'completed')


class TestSnapshotIsolationIntegration(TestCase):
    """Integration tests for snapshot isolation functionality."""
    
    def setUp(self):
        """Set up complex test scenario."""
        self.users = [UserFactory(username=f'user{i}') for i in range(5)]
        self.community = CommunityFactory(name='Integration Test Community')
        
        # Create memberships
        self.memberships = []
        for user in self.users:
            membership = Membership.objects.create(
                member=user,
                community=self.community,
                is_voting_community_member=True
            )
            self.memberships.append(membership)
        
        # Create following relationships (Membership to Membership)
        Following.objects.create(
            follower=self.memberships[1],
            followee=self.memberships[0],
            tags='governance',
            order=1
        )
        Following.objects.create(
            follower=self.memberships[2],
            followee=self.memberships[1],
            tags='governance',
            order=1
        )
        
        self.decision = DecisionFactory(community=self.community)
        self.choices = [
            Choice.objects.create(decision=self.decision, title=f'Choice {i}')
            for i in range(3)
        ]
        
        # Create some initial votes
        ballot = Ballot.objects.create(
            decision=self.decision,
            voter=self.users[0],
            tags='governance'
        )
        for i, choice in enumerate(self.choices):
            Vote.objects.create(ballot=ballot, choice=choice, stars=i + 1)
    
    def test_complete_snapshot_workflow(self):
        """Test complete snapshot creation and processing workflow."""
        # Step 1: Create snapshot
        create_service = CreateCalculationSnapshot(self.decision.id)
        snapshot = create_service.process()
        
        self.assertEqual(snapshot.calculation_status, 'ready')
        self.assertEqual(snapshot.total_eligible_voters, 5)
        self.assertEqual(snapshot.total_votes_cast, 1)
        
        # Step 2: Process snapshot
        process_service = SnapshotBasedStageBallots(snapshot.id)
        results = process_service.process()
        
        self.assertIsNotNone(results)
        
        # Step 3: Verify final state
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.calculation_status, 'completed')
    
    def test_concurrent_data_changes_isolation(self):
        """Test that snapshot isolates against concurrent data changes."""
        # Create initial snapshot
        create_service = CreateCalculationSnapshot(self.decision.id)
        snapshot = create_service.process()
        
        # Capture initial state
        initial_data = snapshot.snapshot_data
        initial_ballots = len(initial_data['existing_ballots'])
        initial_followings = len(initial_data['followings'])
        
        # Simulate concurrent changes (new vote, new following)
        new_ballot = Ballot.objects.create(
            decision=self.decision,
            voter=self.users[3],
            tags='budget'
        )
        Vote.objects.create(ballot=new_ballot, choice=self.choices[0], stars=4)
        
        Following.objects.create(
            follower=self.memberships[4],
            followee=self.memberships[2],
            tags='budget',
            order=1
        )
        
        # Process the original snapshot
        process_service = SnapshotBasedStageBallots(snapshot.id)
        results = process_service.process()
        
        # Verify snapshot data hasn't changed
        snapshot.refresh_from_db()
        final_data = snapshot.snapshot_data
        
        self.assertEqual(len(final_data['existing_ballots']), initial_ballots)
        self.assertEqual(len(final_data['followings']), initial_followings)
        
        # The snapshot should reflect the state at creation time, not current state
        current_ballots = Ballot.objects.filter(decision=self.decision).count()
        current_followings = Following.objects.count()
        
        self.assertGreater(current_ballots, initial_ballots)
        self.assertGreater(current_followings, initial_followings)
    
    def test_multiple_snapshots_per_decision(self):
        """Test that multiple snapshots can exist for one decision."""
        # Create first snapshot
        snapshot1 = CreateCalculationSnapshot(self.decision.id).process()
        
        # Add more data
        ballot = Ballot.objects.create(
            decision=self.decision,
            voter=self.users[1],
            tags='governance'
        )
        Vote.objects.create(ballot=ballot, choice=self.choices[0], stars=3)
        
        # Create second snapshot
        snapshot2 = CreateCalculationSnapshot(self.decision.id).process()
        
        # Verify both snapshots exist and have different data
        self.assertNotEqual(snapshot1.id, snapshot2.id)
        self.assertEqual(snapshot1.total_votes_cast, 1)
        self.assertEqual(snapshot2.total_votes_cast, 2)
        
        # Verify latest snapshot method
        latest = self.decision.get_latest_snapshot()
        self.assertEqual(latest, snapshot2)


@pytest.mark.django_db
class TestSnapshotErrorRecovery:
    """Test error recovery and retry mechanisms."""
    
    def test_snapshot_retry_count_increment(self):
        """Test that retry count increments on failures."""
        user = UserFactory()
        community = CommunityFactory()
        decision = DecisionFactory(community=community)
        
        snapshot = DecisionSnapshot.objects.create(
            decision=decision,
            calculation_status='failed_staging',
            error_log='Test error',
            retry_count=0
        )
        
        # Simulate retry
        snapshot.retry_count += 1
        snapshot.last_error = timezone.now()
        snapshot.save()
        
        assert snapshot.retry_count == 1
        assert snapshot.last_error is not None
    
    def test_snapshot_error_logging(self):
        """Test that errors are properly logged."""
        user = UserFactory()
        community = CommunityFactory()
        decision = DecisionFactory(community=community)
        
        error_message = "Database connection failed during snapshot creation"
        
        snapshot = DecisionSnapshot.objects.create(
            decision=decision,
            calculation_status='failed_snapshot',
            error_log=error_message,
            last_error=timezone.now()
        )
        
        assert snapshot.error_log == error_message
        assert snapshot.calculation_status == 'failed_snapshot'
        assert snapshot.last_error is not None
