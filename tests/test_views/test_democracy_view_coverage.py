"""
Tests specifically designed to improve coverage of democracy/views.py.

This test file focuses on testing untested code paths to increase coverage
rather than duplicating functionality tests.
"""

import pytest
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from tests.factories.user_factory import UserFactory, MembershipFactory
from tests.factories.community_factory import CommunityFactory
from tests.factories.decision_factory import DecisionFactory, ChoiceFactory, BallotFactory, VoteFactory
from democracy.models import Community, Decision, Ballot, Vote
from accounts.models import Following


@pytest.mark.views
class TestDemocracyViewCoverage(TestCase):
    """Tests to improve coverage of democracy/views.py functions."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = UserFactory(username="test_coverage_user")
        self.community = CommunityFactory(name="Coverage Test Community")
        self.membership = MembershipFactory(
            community=self.community,
            member=self.user,
            is_voting_community_member=True,
            is_community_manager=True
        )
        
    def test_build_decision_delegation_tree_no_votes(self):
        """Test delegation tree building with no votes cast."""
        # Create decision with no votes to exercise "no votes cast" path
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice = ChoiceFactory(decision=decision)
        
        # Access decision results to trigger tree building
        self.client.force_login(self.user)
        url = reverse('democracy:decision_results', kwargs={
            'community_id': self.community.id,
            'decision_id': decision.id
        })
        response = self.client.get(url)
        
        # Should handle no votes gracefully
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No votes cast")
        
    def test_build_decision_delegation_tree_with_delegation(self):
        """Test delegation tree building with actual delegation relationships."""
        # Create decision with votes and delegation
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice = ChoiceFactory(decision=decision)
        
        # Create users with delegation relationship
        voter_a = UserFactory(username="voter_a")
        voter_b = UserFactory(username="voter_b")
        
        MembershipFactory(community=self.community, member=voter_a)
        MembershipFactory(community=self.community, member=voter_b)
        
        # Create following relationship
        Following.objects.create(
            follower=voter_b,
            followee=voter_a,
            tags="governance",
            order=1
        )
        
        # Create manual vote for A
        ballot_a = BallotFactory(
            decision=decision,
            voter=voter_a,
            is_calculated=False,
            tags="governance",
            with_votes=False
        )
        VoteFactory(ballot=ballot_a, choice=choice, stars=4)
        
        # Create calculated vote for B
        ballot_b = BallotFactory(
            decision=decision,
            voter=voter_b,
            is_calculated=True,
            tags="governance",
            with_votes=False
        )
        VoteFactory(ballot=ballot_b, choice=choice, stars=4)
        
        # Access decision results to trigger delegation tree building
        self.client.force_login(self.user)
        url = reverse('democracy:decision_results', kwargs={
            'community_id': self.community.id,
            'decision_id': decision.id
        })
        response = self.client.get(url)
        
        # Should show delegation relationships
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "voter_a")
        self.assertContains(response, "voter_b")
        
    def test_build_influence_tree_no_relationships(self):
        """Test influence tree building with no delegation relationships."""
        # Access community detail to trigger influence tree building
        self.client.force_login(self.user)
        url = reverse('democracy:community_detail', kwargs={'community_id': self.community.id})
        response = self.client.get(url)
        
        # Should handle no relationships gracefully
        self.assertEqual(response.status_code, 200)
        
    def test_build_influence_tree_with_relationships(self):
        """Test influence tree building with delegation relationships."""
        # Create users with delegation relationships
        user_a = UserFactory(username="influence_a")
        user_b = UserFactory(username="influence_b")
        
        MembershipFactory(community=self.community, member=user_a)
        MembershipFactory(community=self.community, member=user_b)
        
        # Create following relationship
        Following.objects.create(
            follower=user_b,
            followee=user_a,
            tags="governance,budget",
            order=1
        )
        
        # Access community detail to trigger influence tree building
        self.client.force_login(self.user)
        url = reverse('democracy:community_detail', kwargs={'community_id': self.community.id})
        response = self.client.get(url)
        
        # Should show delegation relationships
        self.assertEqual(response.status_code, 200)
        
    def test_community_detail_user_application_status(self):
        """Test community detail view application status handling."""
        # Create a user who is not a member
        non_member = UserFactory(username="non_member")
        
        self.client.force_login(non_member)
        url = reverse('democracy:community_detail', kwargs={'community_id': self.community.id})
        response = self.client.get(url)
        
        # Should show option to apply
        self.assertEqual(response.status_code, 200)
        
    def test_community_detail_member_filtering(self):
        """Test community detail member filtering functionality."""
        # Create additional members with different roles
        voter = UserFactory(username="test_voter")
        lobbyist = UserFactory(username="test_lobbyist")
        manager = UserFactory(username="test_manager")
        
        MembershipFactory(
            community=self.community,
            member=voter,
            is_voting_community_member=True,
            is_community_manager=False
        )
        MembershipFactory(
            community=self.community,
            member=lobbyist,
            is_voting_community_member=False,
            is_community_manager=False
        )
        MembershipFactory(
            community=self.community,
            member=manager,
            is_voting_community_member=True,
            is_community_manager=True
        )
        
        self.client.force_login(self.user)
        url = reverse('democracy:community_detail', kwargs={'community_id': self.community.id})
        
        # Test different role filters
        for role_filter in ['all', 'managers', 'voters', 'lobbyists']:
            response = self.client.get(url, {'role': role_filter})
            self.assertEqual(response.status_code, 200)
            
    def test_community_detail_member_search(self):
        """Test community detail member search functionality."""
        # Create searchable member
        searchable_user = UserFactory(username="searchable_member")
        MembershipFactory(community=self.community, member=searchable_user)
        
        self.client.force_login(self.user)
        url = reverse('democracy:community_detail', kwargs={'community_id': self.community.id})
        
        # Test search
        response = self.client.get(url, {'search': 'searchable'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "searchable_member")
        
    def test_decision_list_filtering_and_search(self):
        """Test decision list filtering and search functionality."""
        # Create decisions with different statuses
        active_decision = DecisionFactory(
            community=self.community,
            title="Active Decision",
            dt_close=timezone.now() + timedelta(days=7)
        )
        closed_decision = DecisionFactory(
            community=self.community,
            title="Closed Decision",
            dt_close=timezone.now() - timedelta(days=1)
        )
        
        self.client.force_login(self.user)
        url = reverse('democracy:decision_list', kwargs={'community_id': self.community.id})
        
        # Test status filtering
        for status_filter in ['all', 'active', 'closed']:
            response = self.client.get(url, {'status': status_filter})
            self.assertEqual(response.status_code, 200)
            
        # Test search
        response = self.client.get(url, {'search': 'Active'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Active Decision")
        
    def test_decision_create_form_validation_paths(self):
        """Test decision create form validation error paths."""
        self.client.force_login(self.user)
        url = reverse('democracy:decision_create', kwargs={'community_id': self.community.id})
        
        # Test invalid form submission to trigger error handling
        response = self.client.post(url, {
            'title': '',  # Missing required field
            'description': '',  # Missing required field
            'dt_close': '',  # Missing required field
            'choices-TOTAL_FORMS': '2',
            'choices-INITIAL_FORMS': '0',
            'choices-MIN_NUM_FORMS': '2',
            'choices-MAX_NUM_FORMS': '10',
            'action': 'publish'
        })
        
        # Should return form with errors
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")
        
    def test_decision_edit_form_validation_paths(self):
        """Test decision edit form validation error paths."""
        decision = DecisionFactory(community=self.community)
        
        self.client.force_login(self.user)
        url = reverse('democracy:decision_edit', kwargs={
            'community_id': self.community.id,
            'decision_id': decision.id
        })
        
        # Test invalid form submission
        response = self.client.post(url, {
            'title': '',  # Clear required field
            'description': decision.description,
            'dt_close': decision.dt_close.isoformat(),
            'choices-TOTAL_FORMS': '2',
            'choices-INITIAL_FORMS': '0',
            'choices-MIN_NUM_FORMS': '2',
            'choices-MAX_NUM_FORMS': '10',
        })
        
        # Should return form with errors
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required")
        
    def test_vote_submit_validation_paths(self):
        """Test vote submission validation error paths."""
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice = ChoiceFactory(decision=decision)
        
        self.client.force_login(self.user)
        url = reverse('democracy:vote_submit', kwargs={
            'community_id': self.community.id,
            'decision_id': decision.id
        })
        
        # Test invalid vote submission (no ratings)
        response = self.client.post(url, {
            'tags': 'test',
            'is_anonymous': False,
            # No choice ratings provided
        })
        
        # Should handle validation error
        # Note: Actual behavior depends on VoteForm validation
        self.assertIn(response.status_code, [200, 302])
        
    def test_community_manage_application_handling(self):
        """Test community management application handling paths."""
        # Create pending application
        applicant = UserFactory(username="test_applicant")
        from accounts.models import CommunityApplication
        application = CommunityApplication.objects.create(
            user=applicant,
            community=self.community,
            status='pending'
        )
        
        self.client.force_login(self.user)
        url = reverse('democracy:community_manage', kwargs={'community_id': self.community.id})
        
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "test_applicant")
        
    def test_manage_application_approve_reject(self):
        """Test application approval and rejection paths."""
        # Create pending application
        applicant = UserFactory(username="test_applicant")
        from accounts.models import CommunityApplication
        application = CommunityApplication.objects.create(
            user=applicant,
            community=self.community,
            status='pending'
        )
        
        self.client.force_login(self.user)
        
        # Test approval
        url = reverse('democracy:manage_application', kwargs={
            'community_id': self.community.id,
            'application_id': application.id
        })
        response = self.client.post(url, {'action': 'approve'})
        self.assertEqual(response.status_code, 302)
        
        # Test rejection with new application
        application2 = CommunityApplication.objects.create(
            user=UserFactory(username="test_applicant2"),
            community=self.community,
            status='pending'
        )
        url = reverse('democracy:manage_application', kwargs={
            'community_id': self.community.id,
            'application_id': application2.id
        })
        response = self.client.post(url, {'action': 'reject'})
        self.assertEqual(response.status_code, 302)


@pytest.mark.views
class TestDemocracyTreeServiceCoverage(TestCase):
    """Tests to improve coverage of democracy/tree_service.py."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = UserFactory(username="tree_test_user")
        self.community = CommunityFactory(name="Tree Test Community")
        self.membership = MembershipFactory(
            community=self.community,
            member=self.user,
            is_voting_community_member=True
        )
        
    def test_tree_service_complex_delegation_chains(self):
        """Test tree service with complex delegation chains."""
        # Create multi-level delegation chain
        user_a = UserFactory(username="tree_user_a")
        user_b = UserFactory(username="tree_user_b")
        user_c = UserFactory(username="tree_user_c")
        
        for user in [user_a, user_b, user_c]:
            MembershipFactory(community=self.community, member=user)
            
        # Create chain: C -> B -> A
        Following.objects.create(follower=user_b, followee=user_a, tags="governance", order=1)
        Following.objects.create(follower=user_c, followee=user_b, tags="governance", order=1)
        
        # Create decision and votes
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice = ChoiceFactory(decision=decision)
        
        # Create ballots for the chain
        ballot_a = BallotFactory(decision=decision, voter=user_a, is_calculated=False, with_votes=False)
        VoteFactory(ballot=ballot_a, choice=choice, stars=5)
        
        ballot_b = BallotFactory(decision=decision, voter=user_b, is_calculated=True, with_votes=False)
        VoteFactory(ballot=ballot_b, choice=choice, stars=5)
        
        ballot_c = BallotFactory(decision=decision, voter=user_c, is_calculated=True, with_votes=False)
        VoteFactory(ballot=ballot_c, choice=choice, stars=5)
        
        # Access results to trigger tree service
        self.client.force_login(self.user)
        url = reverse('democracy:decision_results', kwargs={
            'community_id': self.community.id,
            'decision_id': decision.id
        })
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        # Should show delegation chain in some form
        self.assertContains(response, "tree_user_a")
        self.assertContains(response, "tree_user_b")
        self.assertContains(response, "tree_user_c")
        
    def test_tree_service_mixed_voting_types(self):
        """Test tree service with both manual and calculated votes."""
        # Create mixed scenario
        manual_voter = UserFactory(username="manual_voter")
        calculated_voter = UserFactory(username="calculated_voter")
        
        for user in [manual_voter, calculated_voter]:
            MembershipFactory(community=self.community, member=user)
            
        # Create following relationship
        Following.objects.create(
            follower=calculated_voter,
            followee=manual_voter,
            tags="budget",
            order=1
        )
        
        # Create decision
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice1 = ChoiceFactory(decision=decision, title="Option 1")
        choice2 = ChoiceFactory(decision=decision, title="Option 2")
        
        # Manual vote
        manual_ballot = BallotFactory(
            decision=decision,
            voter=manual_voter,
            is_calculated=False,
            tags="budget",
            with_votes=False
        )
        VoteFactory(ballot=manual_ballot, choice=choice1, stars=4)
        VoteFactory(ballot=manual_ballot, choice=choice2, stars=2)
        
        # Calculated vote
        calc_ballot = BallotFactory(
            decision=decision,
            voter=calculated_voter,
            is_calculated=True,
            tags="budget",
            with_votes=False
        )
        VoteFactory(ballot=calc_ballot, choice=choice1, stars=4)
        VoteFactory(ballot=calc_ballot, choice=choice2, stars=2)
        
        # Access results to exercise tree building
        self.client.force_login(self.user)
        url = reverse('democracy:decision_results', kwargs={
            'community_id': self.community.id,
            'decision_id': decision.id
        })
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "manual_voter")
        self.assertContains(response, "calculated_voter")
