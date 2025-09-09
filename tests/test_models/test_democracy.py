"""
Tests for democracy app models.

This module tests the Community, Decision, Choice, Ballot, Vote, and Result models
for validation, business logic, and constraints in the CrowdVote democracy system.
"""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta

from democracy.models import (
    Community, Decision, Choice, Ballot, Vote, Result, Membership
)
from tests.factories import (
    UserFactory, CommunityFactory, DecisionFactory, ChoiceFactory,
    BallotFactory, VoteFactory, MembershipFactory
)


@pytest.mark.models
class TestCommunityModel:
    """Test Community model validation and business logic."""
    
    def test_community_creation(self):
        """Test basic community creation."""
        community = CommunityFactory(
            name="Test Community",
            description="A test community for testing."
        )
        
        assert community.name == "Test Community"
        assert community.description == "A test community for testing."
        assert community.auto_approve_applications is False  # Default
    
    def test_community_string_representation(self):
        """Test Community __str__ method."""
        community = CommunityFactory(name="Test Community")
        assert str(community) == "Test Community"
    
    def test_community_name_validation(self):
        """Test community name validation."""
        community = CommunityFactory()
        
        # Name should be required and have reasonable length
        community.name = ""
        with pytest.raises(ValidationError):
            community.full_clean()
        
        # Very long names should be rejected
        community.name = "A" * 300
        with pytest.raises(ValidationError):
            community.full_clean()
    
    def test_community_unique_name(self):
        """Test that community names must be unique."""
        CommunityFactory(name="Unique Community")
        
        # Second community with same name should fail
        with pytest.raises(IntegrityError):
            CommunityFactory(name="Unique Community")
    
    def test_auto_approve_settings(self):
        """Test auto-approval settings for communities."""
        # Demo community with auto-approval
        demo_community = CommunityFactory(auto_approve_applications=True)
        assert demo_community.auto_approve_applications is True
        
        # Production community without auto-approval
        prod_community = CommunityFactory(auto_approve_applications=False)
        assert prod_community.auto_approve_applications is False


@pytest.mark.models
class TestDecisionModel:
    """Test Decision model validation and business logic."""
    
    def test_decision_creation(self):
        """Test basic decision creation."""
        community = CommunityFactory()
        decision = DecisionFactory(
            community=community,
            title="Test Decision",
            description="A test decision.",
            with_choices=False
        )
        
        assert decision.community == community
        assert decision.title == "Test Decision"
        assert decision.description == "A test decision."
        assert decision.results_need_updating is True  # Default
    
    def test_decision_string_representation(self):
        """Test Decision __str__ method."""
        decision = DecisionFactory(title="Test Decision", with_choices=False)
        assert str(decision) == "Test Decision"
    
    def test_decision_deadline_validation(self):
        """Test decision deadline validation."""
        community = CommunityFactory()
        
        # Future deadline should be valid
        future_date = timezone.now() + timedelta(days=7)
        decision = DecisionFactory(
            community=community,
            dt_close=future_date,
            with_choices=False
        )
        decision.full_clean()  # Should not raise
        
        # Past deadline should be rejected for new decisions
        past_date = timezone.now() - timedelta(days=1)
        decision = Decision(
            community=community,
            title="Test Decision",
            description="Test",
            dt_close=past_date
        )
        with pytest.raises(ValidationError):
            decision.full_clean()
    
    def test_decision_title_validation(self):
        """Test decision title validation."""
        community = CommunityFactory()
        decision = Decision(community=community, description="Test")
        
        # Empty title should fail
        decision.title = ""
        with pytest.raises(ValidationError):
            decision.full_clean()
        
        # Very long title should fail
        decision.title = "A" * 300
        with pytest.raises(ValidationError):
            decision.full_clean()
    
    def test_decision_status_properties(self):
        """Test decision status property methods."""
        # Active decision
        future_date = timezone.now() + timedelta(days=7)
        active_decision = DecisionFactory(
            dt_close=future_date,
            with_choices=False
        )
        assert active_decision.is_active() is True
        assert active_decision.is_closed() is False
        
        # Closed decision
        past_date = timezone.now() - timedelta(days=1)
        closed_decision = DecisionFactory(with_choices=False)
        closed_decision.dt_close = past_date
        closed_decision.save()
        assert closed_decision.is_active() is False
        assert closed_decision.is_closed() is True


@pytest.mark.models
class TestChoiceModel:
    """Test Choice model validation and business logic."""
    
    def test_choice_creation(self):
        """Test basic choice creation."""
        decision = DecisionFactory(with_choices=False)
        choice = ChoiceFactory(
            decision=decision,
            title="Test Choice",
            description="A test choice."
        )
        
        assert choice.decision == decision
        assert choice.title == "Test Choice"
        assert choice.description == "A test choice."
        assert choice.score == 0.0  # Default
        assert choice.runoff_score == 0.0  # Default
    
    def test_choice_string_representation(self):
        """Test Choice __str__ method."""
        choice = ChoiceFactory(title="Test Choice")
        assert str(choice) == "Test Choice"
    
    def test_choice_title_validation(self):
        """Test choice title validation."""
        decision = DecisionFactory(with_choices=False)
        choice = Choice(decision=decision)
        
        # Empty title should fail
        choice.title = ""
        with pytest.raises(ValidationError):
            choice.full_clean()
        
        # Very long title should fail
        choice.title = "A" * 300
        with pytest.raises(ValidationError):
            choice.full_clean()
    
    def test_choice_score_validation(self):
        """Test choice score field validation."""
        choice = ChoiceFactory()
        
        # Valid scores
        choice.score = 0.0
        choice.full_clean()  # Should not raise
        
        choice.score = 5.0
        choice.full_clean()  # Should not raise
        
        choice.score = 2.5
        choice.full_clean()  # Should not raise
        
        # Negative scores should be rejected
        choice.score = -1.0
        with pytest.raises(ValidationError):
            choice.full_clean()
        
        # Scores above 5 should be rejected
        choice.score = 6.0
        with pytest.raises(ValidationError):
            choice.full_clean()
    
    def test_multiple_choices_per_decision(self):
        """Test that decisions can have multiple choices."""
        decision = DecisionFactory(with_choices=False)
        
        choice1 = ChoiceFactory(decision=decision, title="Choice 1")
        choice2 = ChoiceFactory(decision=decision, title="Choice 2")
        choice3 = ChoiceFactory(decision=decision, title="Choice 3")
        
        choices = list(decision.choices.all())
        assert len(choices) == 3
        assert choice1 in choices
        assert choice2 in choices
        assert choice3 in choices


@pytest.mark.models
class TestBallotModel:
    """Test Ballot model validation and business logic."""
    
    def test_ballot_creation(self):
        """Test basic ballot creation."""
        user = UserFactory()
        decision = DecisionFactory(with_choices=False)
        
        ballot = BallotFactory(
            decision=decision,
            voter=user,
            is_calculated=False,
            is_anonymous=False,
            tags="governance,budget",
            with_votes=False
        )
        
        assert ballot.decision == decision
        assert ballot.voter == user
        assert ballot.is_calculated is False
        assert ballot.is_anonymous is False
        assert ballot.tags == "governance,budget"
    
    def test_ballot_string_representation(self):
        """Test Ballot __str__ method."""
        user = UserFactory(username="testuser")
        decision = DecisionFactory(title="Test Decision", with_choices=False)
        ballot = BallotFactory(
            decision=decision,
            voter=user,
            with_votes=False
        )
        
        expected = "testuser's ballot for Test Decision"
        assert str(ballot) == expected
    
    def test_ballot_unique_constraint(self):
        """Test that voter can only have one ballot per decision."""
        user = UserFactory()
        decision = DecisionFactory(with_choices=False)
        
        # First ballot should work
        BallotFactory(decision=decision, voter=user, with_votes=False)
        
        # Second ballot for same voter/decision should fail
        with pytest.raises(IntegrityError):
            BallotFactory(decision=decision, voter=user, with_votes=False)
    
    def test_ballot_calculated_vs_manual(self):
        """Test calculated vs manual ballot types."""
        user = UserFactory()
        decision = DecisionFactory(with_choices=False)
        
        # Manual ballot
        manual_ballot = BallotFactory(
            decision=decision,
            voter=user,
            is_calculated=False,
            with_votes=False
        )
        assert manual_ballot.is_calculated is False
        
        # Create a second decision for calculated ballot
        decision2 = DecisionFactory(with_choices=False)
        
        # Calculated ballot (from delegation)
        calculated_ballot = BallotFactory(
            decision=decision2,
            voter=user,
            is_calculated=True,
            with_votes=False
        )
        assert calculated_ballot.is_calculated is True
    
    def test_ballot_anonymity_settings(self):
        """Test ballot anonymity settings."""
        user = UserFactory()
        decision = DecisionFactory(with_choices=False)
        
        # Anonymous ballot
        anonymous_ballot = BallotFactory(
            decision=decision,
            voter=user,
            is_anonymous=True,
            with_votes=False
        )
        assert anonymous_ballot.is_anonymous is True
        
        # Create a second decision for non-anonymous ballot
        decision2 = DecisionFactory(with_choices=False)
        
        # Non-anonymous ballot
        public_ballot = BallotFactory(
            decision=decision2,
            voter=user,
            is_anonymous=False,
            with_votes=False
        )
        assert public_ballot.is_anonymous is False


@pytest.mark.models
class TestVoteModel:
    """Test Vote model validation and business logic."""
    
    def test_vote_creation(self):
        """Test basic vote creation."""
        ballot = BallotFactory(with_votes=False)
        choice = ChoiceFactory(decision=ballot.decision)
        
        vote = VoteFactory(
            ballot=ballot,
            choice=choice,
            stars=4
        )
        
        assert vote.ballot == ballot
        assert vote.choice == choice
        assert vote.stars == 4
    
    def test_vote_string_representation(self):
        """Test Vote __str__ method."""
        ballot = BallotFactory(with_votes=False)
        choice = ChoiceFactory(decision=ballot.decision, title="Test Choice")
        vote = VoteFactory(ballot=ballot, choice=choice, stars=3)
        
        expected = f"3 stars for Test Choice"
        assert str(vote) == expected
    
    def test_vote_stars_validation(self):
        """Test vote stars field validation."""
        ballot = BallotFactory(with_votes=False)
        choice = ChoiceFactory(decision=ballot.decision)
        
        # Valid star ratings (0-5)
        for stars in range(0, 6):
            vote = VoteFactory(ballot=ballot, choice=choice, stars=stars)
            vote.full_clean()  # Should not raise
            vote.delete()  # Clean up for next iteration
        
        # Invalid star ratings should fail
        vote = Vote(ballot=ballot, choice=choice, stars=-1)
        with pytest.raises(ValidationError):
            vote.full_clean()
        
        vote = Vote(ballot=ballot, choice=choice, stars=6)
        with pytest.raises(ValidationError):
            vote.full_clean()
    
    def test_vote_unique_constraint(self):
        """Test that ballot-choice combinations must be unique."""
        ballot = BallotFactory(with_votes=False)
        choice = ChoiceFactory(decision=ballot.decision)
        
        # First vote should work
        VoteFactory(ballot=ballot, choice=choice, stars=3)
        
        # Second vote for same ballot/choice should fail
        with pytest.raises(IntegrityError):
            VoteFactory(ballot=ballot, choice=choice, stars=5)
    
    def test_multiple_votes_per_ballot(self):
        """Test that ballots can have multiple votes for different choices."""
        decision = DecisionFactory(with_choices=False)
        choice1 = ChoiceFactory(decision=decision, title="Choice 1")
        choice2 = ChoiceFactory(decision=decision, title="Choice 2")
        choice3 = ChoiceFactory(decision=decision, title="Choice 3")
        
        ballot = BallotFactory(decision=decision, with_votes=False)
        
        vote1 = VoteFactory(ballot=ballot, choice=choice1, stars=5)
        vote2 = VoteFactory(ballot=ballot, choice=choice2, stars=3)
        vote3 = VoteFactory(ballot=ballot, choice=choice3, stars=1)
        
        votes = list(ballot.votes.all())
        assert len(votes) == 3
        assert vote1 in votes
        assert vote2 in votes
        assert vote3 in votes


@pytest.mark.models
class TestModelRelationships:
    """Test relationships between democracy models."""
    
    def test_community_decisions_relationship(self):
        """Test community-decisions relationship."""
        community = CommunityFactory()
        
        decision1 = DecisionFactory(community=community, with_choices=False)
        decision2 = DecisionFactory(community=community, with_choices=False)
        
        decisions = list(community.decisions.all())
        assert len(decisions) == 2
        assert decision1 in decisions
        assert decision2 in decisions
    
    def test_decision_choices_relationship(self):
        """Test decision-choices relationship."""
        decision = DecisionFactory(with_choices=False)
        
        choice1 = ChoiceFactory(decision=decision)
        choice2 = ChoiceFactory(decision=decision)
        choice3 = ChoiceFactory(decision=decision)
        
        choices = list(decision.choices.all())
        assert len(choices) == 3
        assert choice1 in choices
        assert choice2 in choices
        assert choice3 in choices
    
    def test_decision_ballots_relationship(self):
        """Test decision-ballots relationship."""
        decision = DecisionFactory(with_choices=False)
        user1 = UserFactory()
        user2 = UserFactory()
        
        ballot1 = BallotFactory(decision=decision, voter=user1, with_votes=False)
        ballot2 = BallotFactory(decision=decision, voter=user2, with_votes=False)
        
        ballots = list(decision.ballots.all())
        assert len(ballots) == 2
        assert ballot1 in ballots
        assert ballot2 in ballots
    
    def test_cascade_deletions(self):
        """Test that related objects are properly deleted."""
        decision = DecisionFactory(with_choices=False)
        choice = ChoiceFactory(decision=decision)
        ballot = BallotFactory(decision=decision, with_votes=False)
        vote = VoteFactory(ballot=ballot, choice=choice)
        
        # Verify objects exist
        assert Choice.objects.filter(id=choice.id).exists()
        assert Ballot.objects.filter(id=ballot.id).exists()
        assert Vote.objects.filter(id=vote.id).exists()
        
        # Delete decision
        decision.delete()
        
        # Related objects should be deleted due to CASCADE
        assert not Choice.objects.filter(id=choice.id).exists()
        assert not Ballot.objects.filter(id=ballot.id).exists()
        assert not Vote.objects.filter(id=vote.id).exists()


@pytest.mark.models
class TestSTARVotingConstraints:
    """Test model constraints specific to STAR voting."""
    
    def test_star_rating_range_enforcement(self):
        """Test that star ratings are enforced at model level."""
        ballot = BallotFactory(with_votes=False)
        choice = ChoiceFactory(decision=ballot.decision)
        
        # Test boundary values
        vote_0 = VoteFactory(ballot=ballot, choice=choice, stars=0)
        assert vote_0.stars == 0
        vote_0.delete()
        
        vote_5 = VoteFactory(ballot=ballot, choice=choice, stars=5)
        assert vote_5.stars == 5
        vote_5.delete()
        
        # Test invalid values
        with pytest.raises(ValidationError):
            vote = Vote(ballot=ballot, choice=choice, stars=-1)
            vote.full_clean()
        
        with pytest.raises(ValidationError):
            vote = Vote(ballot=ballot, choice=choice, stars=6)
            vote.full_clean()
    
    def test_choice_score_calculations(self):
        """Test choice score field ranges for STAR voting."""
        choice = ChoiceFactory()
        
        # Valid score ranges (0.0 to 5.0)
        choice.score = 0.0
        choice.full_clean()
        
        choice.score = 5.0
        choice.full_clean()
        
        choice.score = 2.5
        choice.full_clean()
        
        # Invalid scores
        choice.score = -0.1
        with pytest.raises(ValidationError):
            choice.full_clean()
        
        choice.score = 5.1
        with pytest.raises(ValidationError):
            choice.full_clean()
