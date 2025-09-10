"""
Tests specifically designed to improve coverage of democracy/models.py.

This test file focuses on testing untested code paths to increase coverage
rather than duplicating functionality tests.
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError

from tests.factories.user_factory import UserFactory, MembershipFactory
from tests.factories.community_factory import CommunityFactory
from tests.factories.decision_factory import DecisionFactory, ChoiceFactory, BallotFactory, VoteFactory
from democracy.models import Community, Decision, Choice, Membership, Ballot, Vote, Result

User = get_user_model()


@pytest.mark.models
class TestDemocracyModelsCoverage(TestCase):
    """Tests to improve coverage of democracy/models.py functions."""
    
    def setUp(self):
        self.community = CommunityFactory(name="Test Community")
        self.user = UserFactory(username="testuser")
        self.membership = MembershipFactory(member=self.user, community=self.community)
        
    def test_membership_str_method(self):
        """Test Membership __str__ method - covers string representation."""
        membership = MembershipFactory(
            member=self.user, 
            community=self.community
        )
        
        expected = f"{self.user.username} in {self.community.name}"
        self.assertEqual(str(membership), expected)
        
    def test_membership_role_display_manager_voter(self):
        """Test Membership role_display for manager who votes - covers manager + voter path."""
        membership = MembershipFactory(
            member=self.user,
            community=self.community,
            is_community_manager=True,
            is_voting_community_member=True
        )
        
        role_display = membership.role_display
        self.assertIn("Manager", role_display)
        self.assertIn("Voter", role_display)
        
    def test_membership_role_display_lobbyist(self):
        """Test Membership role_display for lobbyist - covers lobbyist path."""
        membership = MembershipFactory(
            member=self.user,
            community=self.community,
            is_community_manager=False,
            is_voting_community_member=False
        )
        
        role_display = membership.role_display
        self.assertIn("Lobbyist", role_display)
        self.assertNotIn("Voter", role_display)
        
    def test_membership_role_display_manager_only(self):
        """Test Membership role_display for manager who doesn't vote - covers manager + lobbyist path."""
        membership = MembershipFactory(
            member=self.user,
            community=self.community,
            is_community_manager=True,
            is_voting_community_member=False
        )
        
        role_display = membership.role_display
        self.assertIn("Manager", role_display)
        self.assertIn("Lobbyist", role_display)
        
    def test_ballot_get_total_stars_cast(self):
        """Test Ballot get_total_stars_cast method - covers star counting logic."""
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice_a = ChoiceFactory(decision=decision, title="Choice A")
        choice_b = ChoiceFactory(decision=decision, title="Choice B")
        
        ballot = BallotFactory(decision=decision, voter=self.user, with_votes=False)
        VoteFactory(choice=choice_a, ballot=ballot, stars=4)
        VoteFactory(choice=choice_b, ballot=ballot, stars=2)
        
        total_stars = ballot.get_total_stars_cast()
        self.assertEqual(total_stars, 6)  # 4 + 2
        
    def test_ballot_get_total_stars_cast_no_votes(self):
        """Test Ballot get_total_stars_cast with no votes - covers zero case."""
        decision = DecisionFactory(community=self.community, with_choices=False)
        ballot = BallotFactory(decision=decision, voter=self.user, with_votes=False)
        
        total_stars = ballot.get_total_stars_cast()
        self.assertEqual(total_stars, 0)
        
    def test_ballot_is_complete_all_choices_voted(self):
        """Test Ballot is_complete when all choices voted - covers complete case."""
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice_a = ChoiceFactory(decision=decision, title="Choice A")
        choice_b = ChoiceFactory(decision=decision, title="Choice B")
        
        ballot = BallotFactory(decision=decision, voter=self.user, with_votes=False)
        VoteFactory(choice=choice_a, ballot=ballot, stars=3)
        VoteFactory(choice=choice_b, ballot=ballot, stars=1)
        
        self.assertTrue(ballot.is_complete())
        
    def test_ballot_is_complete_partial_votes(self):
        """Test Ballot is_complete with partial votes - covers incomplete case."""
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice_a = ChoiceFactory(decision=decision, title="Choice A")
        choice_b = ChoiceFactory(decision=decision, title="Choice B")
        
        ballot = BallotFactory(decision=decision, voter=self.user, with_votes=False)
        VoteFactory(choice=choice_a, ballot=ballot, stars=3)
        # Only voted on choice A, not choice B
        
        self.assertFalse(ballot.is_complete())
        
    def test_ballot_get_display_name_anonymous(self):
        """Test Ballot get_display_name for anonymous ballot - covers anonymity logic."""
        decision = DecisionFactory(community=self.community)
        ballot = BallotFactory(
            decision=decision, 
            voter=self.user, 
            is_anonymous=True,
            with_votes=False
        )
        
        display_name = ballot.get_display_name()
        self.assertIn("Anonymous", display_name)
        self.assertNotIn(self.user.username, display_name)
        
    def test_ballot_get_display_name_non_anonymous(self):
        """Test Ballot get_display_name for non-anonymous ballot - covers normal case."""
        decision = DecisionFactory(community=self.community)
        ballot = BallotFactory(
            decision=decision, 
            voter=self.user, 
            is_anonymous=False,
            with_votes=False
        )
        
        display_name = ballot.get_display_name()
        # Should use voter's display name
        self.assertNotIn("Anonymous", display_name)
        
    def test_result_get_winner_exists(self):
        """Test Result get_winner when winner exists - covers winner extraction."""
        decision = DecisionFactory(community=self.community)
        
        result = Result.objects.create(
            decision=decision,
            report="Test results",
            stats={
                'winner': {
                    'choice': 'Choice A',
                    'score': 4.5,
                    'votes': 10
                }
            }
        )
        
        winner = result.get_winner()
        self.assertIsNotNone(winner)
        self.assertEqual(winner['choice'], 'Choice A')
        self.assertEqual(winner['score'], 4.5)
        
    def test_result_get_winner_none(self):
        """Test Result get_winner when no winner - covers no winner case."""
        decision = DecisionFactory(community=self.community)
        
        result = Result.objects.create(
            decision=decision,
            report="Test results",
            stats={}  # No winner in stats
        )
        
        winner = result.get_winner()
        self.assertIsNone(winner)
        
    def test_result_get_score_phase_results_exists(self):
        """Test Result get_score_phase_results when data exists - covers score phase extraction."""
        decision = DecisionFactory(community=self.community)
        
        score_phase_data = [
            {'choice': 'Choice A', 'average_score': 4.2},
            {'choice': 'Choice B', 'average_score': 3.8}
        ]
        
        result = Result.objects.create(
            decision=decision,
            report="Test results",
            stats={'score_phase': score_phase_data}
        )
        
        score_results = result.get_score_phase_results()
        self.assertEqual(len(score_results), 2)
        self.assertEqual(score_results[0]['choice'], 'Choice A')
        
    def test_result_get_score_phase_results_empty(self):
        """Test Result get_score_phase_results when no data - covers empty case."""
        decision = DecisionFactory(community=self.community)
        
        result = Result.objects.create(
            decision=decision,
            report="Test results",
            stats={}  # No score_phase data
        )
        
        score_results = result.get_score_phase_results()
        self.assertEqual(score_results, [])
        
    def test_result_get_runoff_results_exists(self):
        """Test Result get_runoff_results when data exists - covers runoff extraction."""
        decision = DecisionFactory(community=self.community)
        
        runoff_data = [
            {'choice': 'Choice A', 'preference_count': 15},
            {'choice': 'Choice B', 'preference_count': 10}
        ]
        
        result = Result.objects.create(
            decision=decision,
            report="Test results",
            stats={'runoff_phase': runoff_data}
        )
        
        runoff_results = result.get_runoff_results()
        self.assertEqual(len(runoff_results), 2)
        self.assertEqual(runoff_results[0]['choice'], 'Choice A')
        
    def test_result_get_runoff_results_empty(self):
        """Test Result get_runoff_results when no data - covers empty case."""
        decision = DecisionFactory(community=self.community)
        
        result = Result.objects.create(
            decision=decision,
            report="Test results",
            stats={}  # No runoff_phase data
        )
        
        runoff_results = result.get_runoff_results()
        self.assertEqual(runoff_results, [])
        
    def test_decision_str_method(self):
        """Test Decision __str__ method - covers string representation."""
        decision = DecisionFactory(
            community=self.community,
            title="Should we paint the community room?",
            with_choices=False
        )
        
        expected = f"{decision.title} ({self.community.name})"
        self.assertEqual(str(decision), expected)
        
    def test_choice_str_method(self):
        """Test Choice __str__ method - covers string representation."""
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice = ChoiceFactory(decision=decision, title="Paint it blue")
        
        expected = f"Paint it blue (Should we paint the community room?)"
        self.assertIn("Paint it blue", str(choice))
        
    def test_vote_str_method(self):
        """Test Vote __str__ method - covers string representation."""
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice = ChoiceFactory(decision=decision, title="Choice A")
        ballot = BallotFactory(decision=decision, voter=self.user, with_votes=False)
        vote = VoteFactory(choice=choice, ballot=ballot, stars=4)
        
        expected = "4 stars for Choice A"
        self.assertEqual(str(vote), expected)
        
    def test_community_get_stats(self):
        """Test Community get_stats method - covers statistics calculation."""
        # Create some test data
        MembershipFactory.create_batch(5, community=self.community)
        decision = DecisionFactory(community=self.community)
        
        stats = self.community.get_stats()
        
        self.assertIn('total_members', stats)
        self.assertIn('total_decisions', stats)
        self.assertGreaterEqual(stats['total_members'], 5)  # At least our test users
        self.assertGreaterEqual(stats['total_decisions'], 1)
        
    def test_decision_get_participation_stats(self):
        """Test Decision get_participation_stats method - covers participation calculation."""
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice = ChoiceFactory(decision=decision, title="Choice A")
        
        # Create some ballots
        ballot1 = BallotFactory(decision=decision, voter=self.user, with_votes=False)
        ballot2 = BallotFactory(decision=decision, voter=UserFactory(), with_votes=False)
        VoteFactory(choice=choice, ballot=ballot1, stars=3)
        VoteFactory(choice=choice, ballot=ballot2, stars=4)
        
        stats = decision.get_participation_stats()
        
        self.assertIn('total_ballots', stats)
        self.assertIn('manual_ballots', stats)
        self.assertIn('calculated_ballots', stats)
        self.assertGreaterEqual(stats['total_ballots'], 2)
        
    def test_choice_get_average_score(self):
        """Test Choice get_average_score method - covers score calculation."""
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice = ChoiceFactory(decision=decision, title="Choice A")
        
        # Create votes with different scores
        ballot1 = BallotFactory(decision=decision, voter=self.user, with_votes=False)
        ballot2 = BallotFactory(decision=decision, voter=UserFactory(), with_votes=False)
        VoteFactory(choice=choice, ballot=ballot1, stars=4)  
        VoteFactory(choice=choice, ballot=ballot2, stars=2)  # Average should be 3.0
        
        average = choice.get_average_score()
        self.assertEqual(average, 3.0)
        
    def test_choice_get_average_score_no_votes(self):
        """Test Choice get_average_score with no votes - covers zero case."""
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice = ChoiceFactory(decision=decision, title="Choice A")
        
        average = choice.get_average_score()
        self.assertEqual(average, 0.0)
        
    def test_model_validation_edge_cases(self):
        """Test model validation edge cases - covers validation logic."""
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice = ChoiceFactory(decision=decision, title="Choice A")
        ballot = BallotFactory(decision=decision, voter=self.user, with_votes=False)
        
        # Test vote validation with boundary values
        vote_max = VoteFactory(choice=choice, ballot=ballot, stars=5)
        self.assertEqual(vote_max.stars, 5)
        
        # Test vote with minimum value
        vote_min = Vote.objects.create(choice=choice, ballot=ballot, stars=0)
        self.assertEqual(vote_min.stars, 0)
        
    def test_decision_is_open_property(self):
        """Test Decision is_open property - covers open/closed logic."""
        # Create decision that closes in the future
        future_close = timezone.now() + timedelta(days=1)
        open_decision = DecisionFactory(
            community=self.community,
            dt_close=future_close,
            with_choices=False
        )
        self.assertTrue(open_decision.is_open)
        
        # Create decision that has already closed
        past_close = timezone.now() - timedelta(days=1)
        closed_decision = DecisionFactory(
            community=self.community,
            dt_close=past_close,
            with_choices=False
        )
        self.assertFalse(closed_decision.is_open)
        
    def test_decision_is_active_method(self):
        """Test Decision is_active method - covers active status logic."""
        future_close = timezone.now() + timedelta(days=1)
        decision = DecisionFactory(
            community=self.community,
            dt_close=future_close,
            with_choices=False
        )
        
        self.assertTrue(decision.is_active())
        
    def test_decision_is_closed_method(self):
        """Test Decision is_closed method - covers closed status logic."""
        past_close = timezone.now() - timedelta(days=1)
        decision = DecisionFactory(
            community=self.community,
            dt_close=past_close,
            with_choices=False
        )
        
        self.assertTrue(decision.is_closed())
        
    def test_ballot_clean_method(self):
        """Test Ballot clean method - covers validation logic."""
        decision = DecisionFactory(community=self.community)
        ballot = BallotFactory(decision=decision, voter=self.user, with_votes=False)
        
        # Should not raise exception for valid ballot
        try:
            ballot.clean()
        except ValidationError:
            self.fail("Ballot.clean() raised ValidationError unexpectedly")
            
    def test_community_member_count_property(self):
        """Test Community member_count property - covers count calculation."""
        # Add some members
        MembershipFactory.create_batch(3, community=self.community)
        
        # Should count all memberships including the one from setUp
        count = self.community.member_count
        self.assertGreaterEqual(count, 4)  # At least 4 members
        
    def test_decision_choice_count_property(self):
        """Test Decision choice_count property - covers choice counting."""
        decision = DecisionFactory(community=self.community, with_choices=False)
        ChoiceFactory.create_batch(3, decision=decision)
        
        count = decision.choice_count
        self.assertEqual(count, 3)
        
    def test_choice_vote_count_property(self):
        """Test Choice vote_count property - covers vote counting."""
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice = ChoiceFactory(decision=decision, title="Choice A")
        
        # Create votes for this choice
        ballot1 = BallotFactory(decision=decision, voter=self.user, with_votes=False)
        ballot2 = BallotFactory(decision=decision, voter=UserFactory(), with_votes=False)
        VoteFactory(choice=choice, ballot=ballot1, stars=3)
        VoteFactory(choice=choice, ballot=ballot2, stars=4)
        
        count = choice.vote_count
        self.assertEqual(count, 2)
