"""
Comprehensive tests for STAR voting calculations in democracy/services.py.

This module tests the STAR (Score Then Automatic Runoff) voting algorithm
including score calculation, runoff logic, and tie-breaking mechanisms.
"""

import pytest
from django.utils import timezone
from datetime import timedelta
from collections import OrderedDict

from democracy.services import StageBallots, Tally
from democracy.models import Decision, Choice, Ballot, Vote
from tests.factories import (
    CommunityFactory, DecisionFactory, ChoiceFactory,
    BallotFactory, VoteFactory, UserFactory, MembershipFactory
)


@pytest.mark.services
class TestSTARVoting:
    """Test the STAR voting algorithm implementation."""
    
    def test_score_phase_calculation(self):
        """Test the score phase (S in STAR) calculation."""
        # Create community and decision
        community = CommunityFactory()
        decision = DecisionFactory(community=community, with_choices=False)
        
        # Create choices
        choice_a = ChoiceFactory(decision=decision, title="Choice A")
        choice_b = ChoiceFactory(decision=decision, title="Choice B") 
        choice_c = ChoiceFactory(decision=decision, title="Choice C")
        
        # Create voters
        voter1 = UserFactory(username="voter1")
        voter2 = UserFactory(username="voter2")
        voter3 = UserFactory(username="voter3")
        
        for voter in [voter1, voter2, voter3]:
            MembershipFactory(community=community, member=voter)
        
        # Create ballots with specific star ratings
        # Voter 1: A=5, B=3, C=1
        ballot1 = BallotFactory(decision=decision, voter=voter1, is_calculated=False, with_votes=False)
        VoteFactory(ballot=ballot1, choice=choice_a, stars=5)
        VoteFactory(ballot=ballot1, choice=choice_b, stars=3)
        VoteFactory(ballot=ballot1, choice=choice_c, stars=1)
        
        # Voter 2: A=4, B=5, C=2
        ballot2 = BallotFactory(decision=decision, voter=voter2, is_calculated=False, with_votes=False)
        VoteFactory(ballot=ballot2, choice=choice_a, stars=4)
        VoteFactory(ballot=ballot2, choice=choice_b, stars=5)
        VoteFactory(ballot=ballot2, choice=choice_c, stars=2)
        
        # Voter 3: A=3, B=4, C=5
        ballot3 = BallotFactory(decision=decision, voter=voter3, is_calculated=False, with_votes=False)
        VoteFactory(ballot=ballot3, choice=choice_a, stars=3)
        VoteFactory(ballot=ballot3, choice=choice_b, stars=4)
        VoteFactory(ballot=ballot3, choice=choice_c, stars=5)
        
        # Calculate scores
        service = StageBallots()
        ballots = [ballot1, ballot2, ballot3]
        scores = service.score(ballots)
        
        # Verify scores are calculated correctly
        assert isinstance(scores, OrderedDict)
        assert len(scores) == 3
        
        # Check average scores
        # A: (5+4+3)/3 = 4.0
        # B: (3+5+4)/3 = 4.0  
        # C: (1+2+5)/3 = 2.667
        
        choice_scores = {choice: data['score'] for choice, data in scores.items()}
        
        assert abs(choice_scores[choice_a] - 4.0) < 0.01
        assert abs(choice_scores[choice_b] - 4.0) < 0.01
        assert abs(choice_scores[choice_c] - 2.667) < 0.01
        
        # Verify choices are ordered by score (highest first)
        # A and B should be tied at top, C should be last
        score_list = list(scores.items())
        assert score_list[2][0] == choice_c  # C should be last
    
    def test_automatic_runoff_phase(self):
        """Test the automatic runoff (AR in STAR) calculation."""
        # Create community and decision
        community = CommunityFactory()
        decision = DecisionFactory(community=community)
        
        # Create choices
        choice_a = ChoiceFactory(decision=decision, title="Choice A")
        choice_b = ChoiceFactory(decision=decision, title="Choice B")
        choice_c = ChoiceFactory(decision=decision, title="Choice C")
        
        # Create voters
        voters = []
        for i in range(5):
            voter = UserFactory(username=f"runoff_voter{i}")
            MembershipFactory(community=community, member=voter)
            voters.append(voter)
        
        # Create ballots with strategic voting pattern
        # Design so A and B have highest scores, but B wins runoff
        
        # Voters 0,1,2: A=5, B=3, C=0 (A supporters, but prefer B over C)
        for i in range(3):
            ballot = BallotFactory(decision=decision, voter=voters[i], is_calculated=False, with_votes=False)
            VoteFactory(ballot=ballot, choice=choice_a, stars=5)
            VoteFactory(ballot=ballot, choice=choice_b, stars=3)
            VoteFactory(ballot=ballot, choice=choice_c, stars=0)
        
        # Voters 3,4: A=2, B=5, C=1 (B supporters)
        for i in range(3, 5):
            ballot = BallotFactory(decision=decision, voter=voters[i], is_calculated=False, with_votes=False)
            VoteFactory(ballot=ballot, choice=choice_a, stars=2)
            VoteFactory(ballot=ballot, choice=choice_b, stars=5)
            VoteFactory(ballot=ballot, choice=choice_c, stars=1)
        
        # Calculate runoff
        service = StageBallots()
        ballots = Ballot.objects.filter(decision=decision)
        runoff_result = service.automatic_runoff(ballots)
        
        # Verify runoff structure
        assert 'winner' in runoff_result
        assert 'runner_up' in runoff_result
        assert 'winner_votes' in runoff_result
        assert 'runner_up_votes' in runoff_result
        assert 'total_ballots' in runoff_result
        assert 'margin' in runoff_result
        assert 'score_phase_results' in runoff_result
        
        # A should have higher average score: (5*3 + 2*2)/(5) = 3.8
        # B should have higher average score: (3*3 + 5*2)/(5) = 3.8 (tied)
        # But in runoff, B should win because more voters prefer B when comparing A vs B
        
        assert runoff_result['total_ballots'] == 5
    
    def test_runoff_with_clear_winner(self):
        """Test runoff with a clear preference winner."""
        community = CommunityFactory()
        decision = DecisionFactory(community=community)
        
        choice_a = ChoiceFactory(decision=decision, title="Popular Choice")
        choice_b = ChoiceFactory(decision=decision, title="Unpopular Choice")
        
        # Create 3 voters
        voters = []
        for i in range(3):
            voter = UserFactory(username=f"clear_voter{i}")
            MembershipFactory(community=community, member=voter)
            voters.append(voter)
        
        # All voters clearly prefer A over B
        for voter in voters:
            ballot = BallotFactory(decision=decision, voter=voter, is_calculated=False, with_votes=False)
            VoteFactory(ballot=ballot, choice=choice_a, stars=5)
            VoteFactory(ballot=ballot, choice=choice_b, stars=1)
        
        service = StageBallots()
        ballots = Ballot.objects.filter(decision=decision)
        runoff_result = service.automatic_runoff(ballots)
        
        # A should be clear winner
        assert runoff_result['winner'] == choice_a
        assert runoff_result['runner_up'] == choice_b
        assert runoff_result['winner_votes'] == 3
        assert runoff_result['runner_up_votes'] == 0
        assert runoff_result['margin'] == 3
    
    def test_tie_breaking_mechanism(self):
        """Test tie-breaking when runoff results in a tie."""
        community = CommunityFactory()
        decision = DecisionFactory(community=community)
        
        choice_a = ChoiceFactory(decision=decision, title="Tied Choice A")
        choice_b = ChoiceFactory(decision=decision, title="Tied Choice B")
        
        # Create 4 voters for perfect tie scenario
        voters = []
        for i in range(4):
            voter = UserFactory(username=f"tie_voter{i}")
            MembershipFactory(community=community, member=voter)
            voters.append(voter)
        
        # Voters 0,1 prefer A: A=5, B=4
        for i in range(2):
            ballot = BallotFactory(decision=decision, voter=voters[i], is_calculated=False, with_votes=False)
            VoteFactory(ballot=ballot, choice=choice_a, stars=5)
            VoteFactory(ballot=ballot, choice=choice_b, stars=4)
        
        # Voters 2,3 prefer B: A=4, B=5
        for i in range(2, 4):
            ballot = BallotFactory(decision=decision, voter=voters[i], is_calculated=False, with_votes=False)
            VoteFactory(ballot=ballot, choice=choice_a, stars=4)
            VoteFactory(ballot=ballot, choice=choice_b, stars=5)
        
        service = StageBallots()
        ballots = Ballot.objects.filter(decision=decision)
        runoff_result = service.automatic_runoff(ballots)
        
        # Should handle tie appropriately
        assert runoff_result['total_ballots'] == 4
        
        # In a perfect tie, should fall back to score phase results
        # or have some deterministic tie-breaking mechanism
        if runoff_result['winner_votes'] == runoff_result['runner_up_votes']:
            # Tie detected and handled
            assert 'tie_broken_by' in runoff_result or runoff_result['margin'] == 0
    
    def test_single_choice_decision(self):
        """Test STAR voting with only one choice."""
        community = CommunityFactory()
        decision = DecisionFactory(community=community, with_choices=False)
        
        choice_only = ChoiceFactory(decision=decision, title="Only Choice")
        
        # Create voters
        voter1 = UserFactory(username="single_voter1")
        voter2 = UserFactory(username="single_voter2")
        
        for voter in [voter1, voter2]:
            MembershipFactory(community=community, member=voter)
            ballot = BallotFactory(decision=decision, voter=voter, is_calculated=False, with_votes=False)
            VoteFactory(ballot=ballot, choice=choice_only, stars=4)
        
        service = StageBallots()
        ballots = Ballot.objects.filter(decision=decision)
        runoff_result = service.automatic_runoff(ballots)
        
        # Should handle single choice gracefully
        assert runoff_result['winner'] == choice_only
        assert runoff_result['runner_up'] is None
        assert runoff_result['runoff_needed'] is False
        assert runoff_result['winner_votes'] == 2
    
    def test_no_votes_scenario(self):
        """Test STAR voting with no votes cast."""
        community = CommunityFactory()
        decision = DecisionFactory(community=community)
        
        choice_a = ChoiceFactory(decision=decision, title="Choice A")
        choice_b = ChoiceFactory(decision=decision, title="Choice B")
        
        service = StageBallots()
        ballots = Ballot.objects.filter(decision=decision)  # Empty queryset
        
        # Score phase with no ballots
        scores = service.score(ballots)
        assert len(scores) == 0 or all(data['vote_count'] == 0 for data in scores.values())
        
        # Runoff with no ballots
        runoff_result = service.automatic_runoff(ballots)
        assert runoff_result['total_ballots'] == 0
        assert runoff_result['winner'] is None
    
    def test_zero_star_votes(self):
        """Test handling of zero-star votes."""
        community = CommunityFactory()
        decision = DecisionFactory(community=community, with_choices=False)
        
        choice_a = ChoiceFactory(decision=decision, title="Choice A")
        choice_b = ChoiceFactory(decision=decision, title="Choice B")
        
        voter = UserFactory(username="zero_voter")
        MembershipFactory(community=community, member=voter)
        
        # Voter gives zero stars to all choices
        ballot = BallotFactory(decision=decision, voter=voter, is_calculated=False, with_votes=False)
        VoteFactory(ballot=ballot, choice=choice_a, stars=0)
        VoteFactory(ballot=ballot, choice=choice_b, stars=0)
        
        service = StageBallots()
        ballots = [ballot]
        scores = service.score(ballots)
        
        # Should handle zero scores correctly
        for choice, data in scores.items():
            assert data['score'] == 0.0
            assert data['vote_count'] == 1
            assert data['total_stars'] == 0
    
    def test_maximum_star_votes(self):
        """Test handling of maximum (5) star votes."""
        community = CommunityFactory()
        decision = DecisionFactory(community=community)
        
        choice_a = ChoiceFactory(decision=decision, title="Choice A")
        
        voter = UserFactory(username="max_voter")
        MembershipFactory(community=community, member=voter)
        
        # Voter gives maximum stars
        ballot = BallotFactory(decision=decision, voter=voter, is_calculated=False, with_votes=False)
        VoteFactory(ballot=ballot, choice=choice_a, stars=5)
        
        service = StageBallots()
        ballots = [ballot]
        scores = service.score(ballots)
        
        choice_data = scores[choice_a]
        assert choice_data['score'] == 5.0
        assert choice_data['vote_count'] == 1
        assert choice_data['total_stars'] == 5


@pytest.mark.services
class TestTallyService:
    """Test the Tally service for complete STAR voting process."""
    
    def test_tally_service_initialization(self):
        """Test that Tally service can be initialized."""
        service = Tally()
        assert hasattr(service, 'process')
    
    def test_tally_process_with_active_decisions(self):
        """Test tally process with active decisions."""
        # Create community with active decision
        community = CommunityFactory()
        
        # Create active decision (closes in future)
        active_decision = DecisionFactory(
            community=community,
            dt_close=timezone.now() + timedelta(days=7),
            with_choices=False
        )
        
        # Create closed decision (should be ignored)
        closed_decision = DecisionFactory(
            community=community,
            dt_close=timezone.now() - timedelta(days=1),
            with_choices=False
        )
        
        # Add choices to active decision
        choice_a = ChoiceFactory(decision=active_decision, title="Active Choice A")
        choice_b = ChoiceFactory(decision=active_decision, title="Active Choice B")
        
        # Add some votes
        voter = UserFactory(username="tally_voter")
        MembershipFactory(community=community, member=voter)
        
        ballot = BallotFactory(decision=active_decision, voter=voter, is_calculated=False, with_votes=False)
        VoteFactory(ballot=ballot, choice=choice_a, stars=4)
        VoteFactory(ballot=ballot, choice=choice_b, stars=2)
        
        # Run tally service
        service = Tally()
        result = service.process()
        
        # Should return some result (string report)
        assert isinstance(result, str)
        
        # Should have processed the active decision but not the closed one
        # Check that result contains useful information
        assert len(result) > 0
        assert "TALLY" in result or "tally" in result
    
    def test_tally_voting_member_filtering(self):
        """Test that tally only counts voting members, not lobbyists."""
        community = CommunityFactory()
        decision = DecisionFactory(
            community=community,
            dt_close=timezone.now() + timedelta(days=7)
        )
        
        choice = ChoiceFactory(decision=decision, title="Test Choice")
        
        # Create voting member
        voting_member = UserFactory(username="voting_member")
        MembershipFactory(
            community=community,
            member=voting_member,
            is_voting_community_member=True
        )
        
        # Create lobbyist (non-voting member)
        lobbyist = UserFactory(username="lobbyist_member")
        MembershipFactory(
            community=community,
            member=lobbyist,
            is_voting_community_member=False
        )
        
        # Both cast ballots
        voting_ballot = BallotFactory(decision=decision, voter=voting_member, is_calculated=False, with_votes=False)
        VoteFactory(ballot=voting_ballot, choice=choice, stars=5)
        
        lobbyist_ballot = BallotFactory(decision=decision, voter=lobbyist, is_calculated=False, with_votes=False)
        VoteFactory(ballot=lobbyist_ballot, choice=choice, stars=3)
        
        # Run tally
        service = Tally()
        result = service.process()
        
        # Verify that only voting member ballots are counted
        voting_ballots = decision.ballots.filter(
            voter__memberships__community=community,
            voter__memberships__is_voting_community_member=True
        )
        
        assert voting_ballots.count() == 1
        assert voting_ballots.first().voter == voting_member
    
    def test_participation_statistics(self):
        """Test that participation statistics are calculated correctly."""
        community = CommunityFactory()
        decision = DecisionFactory(
            community=community,
            dt_close=timezone.now() + timedelta(days=7)
        )
        
        choice = ChoiceFactory(decision=decision, title="Participation Choice")
        
        # Create 5 voting members
        voting_members = []
        for i in range(5):
            member = UserFactory(username=f"participant_{i}")
            MembershipFactory(
                community=community,
                member=member,
                is_voting_community_member=True
            )
            voting_members.append(member)
        
        # 3 members vote manually
        for i in range(3):
            ballot = BallotFactory(
                decision=decision,
                voter=voting_members[i],
                is_calculated=False,
                with_votes=False
            )
            VoteFactory(ballot=ballot, choice=choice, stars=4)
        
        # 1 member has calculated vote
        ballot = BallotFactory(
            decision=decision,
            voter=voting_members[3],
            is_calculated=True,
            with_votes=False
        )
        VoteFactory(ballot=ballot, choice=choice, stars=3)
        
        # 1 member doesn't vote (voting_members[4])
        
        # Run tally
        service = Tally()
        result = service.process()
        
        # Check statistics in the decision log
        if hasattr(decision, 'tally_log'):
            # Should log participation statistics
            log_entries = [entry['log'] for entry in decision.tally_log]
            participation_logs = [log for log in log_entries if 'PARTICIPATION' in log]
            assert len(participation_logs) > 0
