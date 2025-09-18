"""
Comprehensive tests for democracy/views.py to improve coverage from 58% to 80%+.

This test file focuses on the missing coverage areas identified in the coverage report:
- Tree building functions (lines 59-229, 270-395)
- Decision management views (creation, editing, results)
- Vote submission and status endpoints
- Error handling and edge cases
"""

import pytest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.contrib.messages import get_messages
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock

from democracy.models import Community, Decision, Choice, Ballot, Vote, Membership, DecisionSnapshot
from accounts.models import Following
from democracy.views import (
    build_decision_delegation_tree, build_influence_tree,
    build_decision_delegation_tree_old, build_influence_tree_old
)
from tests.factories import (
    UserFactory, CommunityFactory, CommunityWithDelegationFactory,
    DecisionFactory, ChoiceFactory, BallotFactory, VoteFactory,
    MembershipFactory, FollowingFactory
)

User = get_user_model()


@pytest.mark.views
class DemocracyTreeBuildingTest(TestCase):
    """Test the tree building functions that handle delegation visualization."""
    
    def setUp(self):
        """Set up test data for tree building tests."""
        self.community = CommunityWithDelegationFactory(create_delegation_users=True)
        self.decision = DecisionFactory(community=self.community)
        self.choice1 = ChoiceFactory(decision=self.decision, title="Option A")
        self.choice2 = ChoiceFactory(decision=self.decision, title="Option B")
        
        # Get the A-H users created by the factory
        self.users = {}
        for letter in ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']:
            username = f"{letter}_test"
            try:
                self.users[letter] = User.objects.get(username=username)
            except User.DoesNotExist:
                # Fallback if factory naming is different
                self.users[letter] = UserFactory(username=username)
                MembershipFactory(
                    member=self.users[letter],
                    community=self.community,
                    is_voting_community_member=True
                )
    
    def test_build_decision_delegation_tree_no_votes(self):
        """Test decision tree building when no votes have been cast."""
        result = build_decision_delegation_tree(self.decision)
        
        self.assertIn('tree_text', result)
        self.assertIn('No votes cast for this decision yet', result['tree_text'])
        self.assertFalse(result['has_relationships'])
        self.assertEqual(result['stats']['total_participants'], 0)
    
    def test_build_decision_delegation_tree_with_votes(self):
        """Test decision tree building with actual votes and delegation."""
        # Create some ballots and votes
        ballot_a = BallotFactory(decision=self.decision, voter=self.users['A'], is_calculated=False, with_votes=False)
        VoteFactory(ballot=ballot_a, choice=self.choice1, stars=5)
        VoteFactory(ballot=ballot_a, choice=self.choice2, stars=2)
        
        ballot_b = BallotFactory(decision=self.decision, voter=self.users['B'], is_calculated=True, with_votes=False)
        VoteFactory(ballot=ballot_b, choice=self.choice1, stars=5)
        VoteFactory(ballot=ballot_b, choice=self.choice2, stars=2)
        
        # Create following relationship
        FollowingFactory(
            follower=self.users['B'],
            followee=self.users['A'],
            tags="governance"
        )
        
        result = build_decision_delegation_tree(self.decision)
        
        self.assertIn('tree_text', result)
        self.assertTrue(result['has_relationships'])
        self.assertEqual(result['stats']['total_participants'], 2)
        self.assertEqual(result['stats']['manual_voters'], 1)
        self.assertEqual(result['stats']['calculated_voters'], 1)
    
    def test_build_decision_delegation_tree_with_links_disabled(self):
        """Test decision tree building with username links disabled."""
        ballot_a = BallotFactory(decision=self.decision, voter=self.users['A'], is_calculated=False, with_votes=False)
        VoteFactory(ballot=ballot_a, choice=self.choice1, stars=4)
        
        result = build_decision_delegation_tree(self.decision, include_links=False)
        
        self.assertIn('tree_text', result)
        self.assertIn(self.users['A'].username, result['tree_text'])
        # Should not contain HTML links when include_links=False
        self.assertNotIn('<a href=', result['tree_text'])
    
    def test_build_decision_delegation_tree_old_function(self):
        """Test the old decision tree building function for backward compatibility."""
        ballot_a = BallotFactory(decision=self.decision, voter=self.users['A'], is_calculated=False, with_votes=False)
        VoteFactory(ballot=ballot_a, choice=self.choice1, stars=3)
        
        result = build_decision_delegation_tree_old(self.decision)
        
        self.assertIn('tree_text', result)
        self.assertIn('has_relationships', result)
        self.assertIn('stats', result)
    
    def test_build_influence_tree_no_relationships(self):
        """Test community influence tree when no delegation relationships exist."""
        # Create a community with no following relationships
        empty_community = CommunityFactory()
        MembershipFactory(member=self.users['A'], community=empty_community)
        
        result = build_influence_tree(empty_community)
        
        self.assertIn('tree_text', result)
        self.assertIn('No delegation relationships found', result['tree_text'])
        self.assertFalse(result['has_relationships'])
        self.assertEqual(result['stats']['total_relationships'], 0)
    
    def test_build_influence_tree_with_relationships(self):
        """Test community influence tree with delegation relationships."""
        # Ensure we have following relationships in the community
        FollowingFactory(
            follower=self.users['B'],
            followee=self.users['A'],
            tags="governance"
        )
        FollowingFactory(
            follower=self.users['C'],
            followee=self.users['A'],
            tags="budget"
        )
        
        result = build_influence_tree(self.community)
        
        self.assertIn('tree_text', result)
        self.assertTrue(result['has_relationships'])
        self.assertGreaterEqual(result['stats']['total_relationships'], 2)
        self.assertGreaterEqual(result['stats']['unique_followers'], 2)
        self.assertGreaterEqual(result['stats']['unique_followees'], 1)
    
    def test_build_influence_tree_with_links_disabled(self):
        """Test community influence tree with username links disabled."""
        FollowingFactory(
            follower=self.users['B'],
            followee=self.users['A'],
            tags="governance"
        )
        
        result = build_influence_tree(self.community, include_links=False)
        
        self.assertIn('tree_text', result)
        # Should contain some usernames (exact names may vary due to factory generation)
        self.assertTrue(len(result['tree_text']) > 100)  # Should have substantial content
        # Should not contain HTML links when include_links=False
        self.assertNotIn('<a href=', result['tree_text'])
    
    def test_build_influence_tree_old_function(self):
        """Test the old influence tree building function for backward compatibility."""
        FollowingFactory(
            follower=self.users['B'],
            followee=self.users['A'],
            tags="governance"
        )
        
        result = build_influence_tree_old(self.community)
        
        self.assertIn('tree_text', result)
        self.assertIn('has_relationships', result)
        self.assertIn('stats', result)


@pytest.mark.views
class DecisionManagementViewsTest(TestCase):
    """Test decision creation, editing, and management views."""
    
    def setUp(self):
        """Set up test data for decision management tests."""
        self.client = Client()
        self.user = UserFactory()
        self.community = CommunityFactory()
        self.membership = MembershipFactory(
            member=self.user,
            community=self.community,
            is_community_manager=True,
            is_voting_community_member=True
        )
        self.client.force_login(self.user)
    
    def test_decision_create_get_request(self):
        """Test GET request to decision creation page."""
        url = reverse('democracy:decision_create', kwargs={'community_id': self.community.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create Decision')
        self.assertContains(response, self.community.name)
    
    def test_decision_create_post_valid_data(self):
        """Test POST request to create a decision with valid data."""
        url = reverse('democracy:decision_create', kwargs={'community_id': self.community.id})
        
        # Future date for deadline
        future_date = timezone.now() + timedelta(days=7)
        
        data = {
            'title': 'Test Decision',
            'description': 'This is a test decision for our community to vote on.',
            'dt_close': future_date.strftime('%Y-%m-%dT%H:%M'),
            'choices-TOTAL_FORMS': '2',
            'choices-INITIAL_FORMS': '0',
            'choices-MIN_NUM_FORMS': '2',
            'choices-MAX_NUM_FORMS': '10',
            'choices-0-title': 'Option A',
            'choices-0-description': 'First option',
            'choices-1-title': 'Option B',
            'choices-1-description': 'Second option',
        }
        
        response = self.client.post(url, data)
        
        # Should redirect after successful creation
        self.assertEqual(response.status_code, 302)
        
        # Verify decision was created
        decision = Decision.objects.get(title='Test Decision')
        self.assertEqual(decision.community, self.community)
        self.assertEqual(decision.choices.count(), 2)
    
    def test_decision_create_post_invalid_data(self):
        """Test POST request with invalid data."""
        url = reverse('democracy:decision_create', kwargs={'community_id': self.community.id})
        
        # Past date for deadline (invalid)
        past_date = timezone.now() - timedelta(days=1)
        
        data = {
            'title': '',  # Empty title (invalid)
            'description': 'Test',
            'dt_close': past_date.strftime('%Y-%m-%dT%H:%M'),
            'choices-TOTAL_FORMS': '1',  # Only 1 choice (invalid, need at least 2)
            'choices-INITIAL_FORMS': '0',
            'choices-0-title': 'Option A',
        }
        
        response = self.client.post(url, data)
        
        # Should stay on the same page with errors
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'error')  # Should show form errors
    
    def test_decision_create_non_manager_access(self):
        """Test that non-managers cannot access decision creation."""
        # Create a regular member (not manager)
        regular_user = UserFactory()
        MembershipFactory(
            member=regular_user,
            community=self.community,
            is_community_manager=False,
            is_voting_community_member=True
        )
        
        self.client.force_login(regular_user)
        url = reverse('democracy:decision_create', kwargs={'community_id': self.community.id})
        
        response = self.client.get(url)
        
        # Should be forbidden or redirect
        self.assertIn(response.status_code, [403, 302])
    
    def test_decision_edit_get_request(self):
        """Test GET request to decision edit page."""
        decision = DecisionFactory(community=self.community)
        ChoiceFactory(decision=decision, title="Original Choice")
        
        url = reverse('democracy:decision_edit', kwargs={
            'community_id': self.community.id,
            'decision_id': decision.id
        })
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Edit Decision')
        self.assertContains(response, decision.title)
    
    def test_decision_edit_post_valid_data(self):
        """Test POST request to edit a decision."""
        decision = DecisionFactory(community=self.community, title="Original Title")
        choice = ChoiceFactory(decision=decision, title="Original Choice")
        
        url = reverse('democracy:decision_edit', kwargs={
            'community_id': self.community.id,
            'decision_id': decision.id
        })
        
        future_date = timezone.now() + timedelta(days=7)
        
        data = {
            'title': 'Updated Decision Title',
            'description': decision.description,
            'dt_close': future_date.strftime('%Y-%m-%dT%H:%M'),
            'choices-TOTAL_FORMS': '2',
            'choices-INITIAL_FORMS': '1',
            'choices-MIN_NUM_FORMS': '2',
            'choices-MAX_NUM_FORMS': '10',
            f'choices-0-id': choice.id,
            'choices-0-title': 'Updated Choice',
            'choices-0-description': choice.description,
            'choices-1-title': 'New Choice',
            'choices-1-description': 'A new choice added',
        }
        
        response = self.client.post(url, data)
        
        # Should redirect after successful edit
        self.assertEqual(response.status_code, 302)
        
        # Verify decision was updated
        decision.refresh_from_db()
        self.assertEqual(decision.title, 'Updated Decision Title')
        # Should have at least 2 choices (may have more from factory)
        self.assertGreaterEqual(decision.choices.count(), 2)
    
    def test_decision_edit_with_existing_votes(self):
        """Test that decisions with votes cannot be edited."""
        decision = DecisionFactory(community=self.community)
        choice = ChoiceFactory(decision=decision)
        
        # Create a ballot (simulating that votes have been cast)
        voter = UserFactory()
        MembershipFactory(member=voter, community=self.community)
        BallotFactory(decision=decision, voter=voter)
        
        url = reverse('democracy:decision_edit', kwargs={
            'community_id': self.community.id,
            'decision_id': decision.id
        })
        
        response = self.client.get(url)
        
        # Should redirect or show error since votes exist
        self.assertIn(response.status_code, [302, 403])


@pytest.mark.views
class VoteSubmissionViewsTest(TestCase):
    """Test vote submission and related endpoints."""
    
    def setUp(self):
        """Set up test data for vote submission tests."""
        self.client = Client()
        self.user = UserFactory()
        self.community = CommunityFactory()
        self.membership = MembershipFactory(
            member=self.user,
            community=self.community,
            is_voting_community_member=True
        )
        
        # Create a decision with choices
        future_date = timezone.now() + timedelta(days=7)
        self.decision = DecisionFactory(
            community=self.community,
            dt_close=future_date
        )
        self.choice1 = ChoiceFactory(decision=self.decision, title="Option A")
        self.choice2 = ChoiceFactory(decision=self.decision, title="Option B")
        
        self.client.force_login(self.user)
    
    def test_vote_submit_valid_vote(self):
        """Test submitting a valid vote."""
        url = reverse('democracy:vote_submit', kwargs={
            'community_id': self.community.id,
            'decision_id': self.decision.id
        })
        
        data = {
            f'choice_{self.choice1.id}': '5',
            f'choice_{self.choice2.id}': '3',
            'tags': 'governance, budget',
            'vote_anonymously': 'false'
        }
        
        response = self.client.post(url, data)
        
        # Should redirect after successful vote
        self.assertEqual(response.status_code, 302)
        
        # Verify ballot and votes were created
        ballot = Ballot.objects.get(decision=self.decision, voter=self.user)
        self.assertFalse(ballot.is_calculated)
        self.assertEqual(ballot.votes.count(), 2)
        
        # Check vote values
        vote1 = Vote.objects.get(ballot=ballot, choice=self.choice1)
        vote2 = Vote.objects.get(ballot=ballot, choice=self.choice2)
        self.assertEqual(float(vote1.stars), 5.0)
        self.assertEqual(float(vote2.stars), 3.0)
    
    def test_vote_submit_anonymous_vote(self):
        """Test submitting an anonymous vote."""
        url = reverse('democracy:vote_submit', kwargs={
            'community_id': self.community.id,
            'decision_id': self.decision.id
        })
        
        data = {
            f'choice_{self.choice1.id}': '4',
            f'choice_{self.choice2.id}': '2',
            'tags': 'environment',
            'vote_anonymously': 'true'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 302)
        
        # Verify anonymous ballot was created
        ballot = Ballot.objects.get(decision=self.decision, voter=self.user)
        self.assertTrue(ballot.is_anonymous)
        self.assertIsNotNone(ballot.hashed_username)
    
    def test_vote_submit_update_existing_vote(self):
        """Test updating an existing vote."""
        # Create initial ballot
        ballot = BallotFactory(decision=self.decision, voter=self.user)
        VoteFactory(ballot=ballot, choice=self.choice1, stars=2)
        VoteFactory(ballot=ballot, choice=self.choice2, stars=4)
        
        url = reverse('democracy:vote_submit', kwargs={
            'community_id': self.community.id,
            'decision_id': self.decision.id
        })
        
        data = {
            f'choice_{self.choice1.id}': '5',  # Changed from 2 to 5
            f'choice_{self.choice2.id}': '1',  # Changed from 4 to 1
            'tags': 'updated_tags',
            'vote_anonymously': 'false'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, 302)
        
        # Verify votes were updated
        ballot.refresh_from_db()
        vote1 = Vote.objects.get(ballot=ballot, choice=self.choice1)
        vote2 = Vote.objects.get(ballot=ballot, choice=self.choice2)
        self.assertEqual(float(vote1.stars), 5.0)
        self.assertEqual(float(vote2.stars), 1.0)
    
    def test_vote_submit_closed_decision(self):
        """Test that votes cannot be submitted to closed decisions."""
        # Create a closed decision
        past_date = timezone.now() - timedelta(days=1)
        closed_decision = DecisionFactory(
            community=self.community,
            dt_close=past_date
        )
        choice = ChoiceFactory(decision=closed_decision)
        
        url = reverse('democracy:vote_submit', kwargs={
            'community_id': self.community.id,
            'decision_id': closed_decision.id
        })
        
        data = {
            f'choice_{choice.id}': '3',
            'tags': 'test',
            'vote_anonymously': 'false'
        }
        
        response = self.client.post(url, data)
        
        # Should redirect with error or show forbidden
        self.assertIn(response.status_code, [302, 403])
        
        # Verify no ballot was created
        self.assertFalse(Ballot.objects.filter(
            decision=closed_decision,
            voter=self.user
        ).exists())
    
    def test_vote_submit_non_member_access(self):
        """Test that non-members cannot vote."""
        non_member = UserFactory()
        self.client.force_login(non_member)
        
        url = reverse('democracy:vote_submit', kwargs={
            'community_id': self.community.id,
            'decision_id': self.decision.id
        })
        
        data = {
            f'choice_{self.choice1.id}': '3',
            'tags': 'test',
            'vote_anonymously': 'false'
        }
        
        response = self.client.post(url, data)
        
        # Should be forbidden or redirect
        self.assertIn(response.status_code, [403, 302])


@pytest.mark.views
class DecisionStatusViewsTest(TestCase):
    """Test decision status and calculation endpoints."""
    
    def setUp(self):
        """Set up test data for status tests."""
        self.client = Client()
        self.user = UserFactory()
        self.community = CommunityFactory()
        self.membership = MembershipFactory(
            member=self.user,
            community=self.community,
            is_community_manager=True,
            is_voting_community_member=True
        )
        
        self.decision = DecisionFactory(community=self.community)
        self.choice = ChoiceFactory(decision=self.decision)
        
        self.client.force_login(self.user)
    
    def test_calculation_status_endpoint(self):
        """Test the calculation status JSON endpoint."""
        url = reverse('democracy:calculation_status', kwargs={
            'community_id': self.community.id,
            'decision_id': self.decision.id
        })
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        data = response.json()
        self.assertIn('status', data)
        self.assertIn('last_calculated', data)
        self.assertIn('is_calculating', data)
    
    @patch('democracy.views.recalculate_community_decisions_async')
    def test_manual_recalculation_endpoint(self, mock_recalc):
        """Test the manual recalculation endpoint."""
        url = reverse('democracy:manual_recalculation', kwargs={
            'community_id': self.community.id,
            'decision_id': self.decision.id
        })
        
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/json')
        
        # Verify the async function was called
        mock_recalc.assert_called_once()
        
        data = response.json()
        self.assertIn('status', data)
        self.assertEqual(data['status'], 'success')
    
    def test_manual_recalculation_non_manager_access(self):
        """Test that non-managers cannot trigger manual recalculation."""
        regular_user = UserFactory()
        MembershipFactory(
            member=regular_user,
            community=self.community,
            is_community_manager=False,
            is_voting_community_member=True
        )
        
        self.client.force_login(regular_user)
        
        url = reverse('democracy:manual_recalculation', kwargs={
            'community_id': self.community.id,
            'decision_id': self.decision.id
        })
        
        response = self.client.post(url)
        
        # Should be forbidden
        self.assertEqual(response.status_code, 403)
    
    @patch('democracy.views.recalculate_community_decisions_async')
    def test_manual_recalculation_already_calculating(self, mock_recalc):
        """Test manual recalculation when calculation is already in progress."""
        # Create a snapshot that indicates calculation is in progress
        DecisionSnapshot.objects.create(
            decision=self.decision,
            calculation_status='staging',
            snapshot_data={'test': 'data'},
            is_final=False
        )
        
        url = reverse('democracy:manual_recalculation', kwargs={
            'community_id': self.community.id,
            'decision_id': self.decision.id
        })
        
        response = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertEqual(data['status'], 'already_calculating')
        
        # Should not call the async function if already calculating
        mock_recalc.assert_not_called()


@pytest.mark.views
class DecisionResultsViewTest(TestCase):
    """Test decision results display and functionality."""
    
    def setUp(self):
        """Set up test data for results tests."""
        self.client = Client()
        self.user = UserFactory()
        self.community = CommunityFactory()
        self.membership = MembershipFactory(
            member=self.user,
            community=self.community,
            is_voting_community_member=True
        )
        
        self.decision = DecisionFactory(community=self.community)
        self.choice1 = ChoiceFactory(decision=self.decision, title="Option A")
        self.choice2 = ChoiceFactory(decision=self.decision, title="Option B")
        
        self.client.force_login(self.user)
    
    def test_decision_results_get_request(self):
        """Test GET request to decision results page."""
        url = reverse('democracy:decision_results', kwargs={
            'community_id': self.community.id,
            'decision_id': self.decision.id
        })
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.decision.title)
        self.assertContains(response, 'Decision Results')
    
    @patch('democracy.services.CreateCalculationSnapshot')
    def test_decision_results_creates_snapshot(self, mock_snapshot_service):
        """Test that viewing results creates a calculation snapshot."""
        mock_snapshot_instance = MagicMock()
        mock_snapshot_service.return_value = mock_snapshot_instance
        
        url = reverse('democracy:decision_results', kwargs={
            'community_id': self.community.id,
            'decision_id': self.decision.id
        })
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        
        # Verify snapshot service was called
        mock_snapshot_service.assert_called_once_with(self.decision.id)
        mock_snapshot_instance.process.assert_called_once()
    
    def test_decision_results_with_existing_votes(self):
        """Test results page with actual votes cast."""
        # Create some votes
        voter1 = UserFactory()
        voter2 = UserFactory()
        
        MembershipFactory(member=voter1, community=self.community)
        MembershipFactory(member=voter2, community=self.community)
        
        ballot1 = BallotFactory(decision=self.decision, voter=voter1)
        VoteFactory(ballot=ballot1, choice=self.choice1, stars=5)
        VoteFactory(ballot=ballot1, choice=self.choice2, stars=2)
        
        ballot2 = BallotFactory(decision=self.decision, voter=voter2)
        VoteFactory(ballot=ballot2, choice=self.choice1, stars=3)
        VoteFactory(ballot=ballot2, choice=self.choice2, stars=4)
        
        url = reverse('democracy:decision_results', kwargs={
            'community_id': self.community.id,
            'decision_id': self.decision.id
        })
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, voter1.username)
        self.assertContains(response, voter2.username)
        self.assertContains(response, 'Option A')
        self.assertContains(response, 'Option B')
    
    def test_decision_results_non_member_access(self):
        """Test that non-members can view results (public transparency)."""
        non_member = UserFactory()
        self.client.force_login(non_member)
        
        url = reverse('democracy:decision_results', kwargs={
            'community_id': self.community.id,
            'decision_id': self.decision.id
        })
        
        response = self.client.get(url)
        
        # Results should be publicly viewable for transparency
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.decision.title)
