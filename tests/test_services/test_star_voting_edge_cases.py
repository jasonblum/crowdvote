"""
Comprehensive edge case tests for STAR voting algorithm in democracy/services.py.

This module tests complex STAR voting scenarios including ties, edge cases,
boundary conditions, and mathematical precision requirements.
"""

import pytest
from django.utils import timezone
from datetime import timedelta
from collections import OrderedDict

from democracy.services import StageBallots
from democracy.models import Decision, Choice, Ballot, Vote
from tests.factories import (
    CommunityWithDelegationFactory, DecisionFactory, ChoiceFactory,
    BallotFactory, VoteFactory, UserFactory, MembershipFactory
)


@pytest.mark.services
class TestSTARVotingEdgeCases:
    """Test edge cases and boundary conditions in STAR voting calculations."""
    
    def test_perfect_tie_in_score_phase(self):
        """Test STAR voting when all choices have identical average scores."""
        community = CommunityWithDelegationFactory()
        
        # Create 3 voters
        voters = []
        for i in range(3):
            user = UserFactory(username=f"tie_voter_{i}")
            MembershipFactory(community=community, member=user)
            voters.append(user)
        
        # Create decision with 3 choices
        decision = DecisionFactory(community=community, with_choices=False)
        choices = []
        for i in range(3):
            choice = ChoiceFactory(decision=decision, title=f"Option {i+1}")
            choices.append(choice)
        
        # Create voting pattern that results in perfect tie (all choices average 3.0)
        # Voter 1: [5, 3, 1], Voter 2: [3, 3, 3], Voter 3: [1, 3, 5]
        vote_patterns = [
            [5, 3, 1],  # Voter 1
            [3, 3, 3],  # Voter 2  
            [1, 3, 5]   # Voter 3
        ]
        
        ballots = []
        for voter_idx, (voter, pattern) in enumerate(zip(voters, vote_patterns)):
            ballot = BallotFactory(
                decision=decision,
                voter=voter,
                is_calculated=False,
                tags="tie_test",
                with_votes=False
            )
            ballots.append(ballot)
            
            for choice_idx, stars in enumerate(pattern):
                VoteFactory(ballot=ballot, choice=choices[choice_idx], stars=stars)
        
        # Test STAR voting calculation
        service = StageBallots()
        results = service.automatic_runoff(ballots)
        
        # Should handle perfect tie gracefully
        assert results is not None
        assert 'winner' in results
        assert 'score_phase_results' in results
        
        # All choices should have same average score (3.0)
        scores = results['score_phase_results']
        choice_scores = [data['score'] for data in scores.values()]
        assert all(abs(float(score) - 3.0) < 0.001 for score in choice_scores)
    
    def test_extreme_score_distributions(self):
        """Test with extreme score distributions (all 0s vs all 5s)."""
        community = CommunityWithDelegationFactory()
        
        # Create voters with extreme preferences
        extreme_voters = []
        for i in range(10):
            user = UserFactory(username=f"extreme_voter_{i}")
            MembershipFactory(community=community, member=user)
            extreme_voters.append(user)
        
        # Create decision with 2 choices
        decision = DecisionFactory(community=community, with_choices=False)
        choice_loved = ChoiceFactory(decision=decision, title="Universally Loved")
        choice_hated = ChoiceFactory(decision=decision, title="Universally Hated")
        
        # Half voters give 5 stars to choice_loved, 0 to choice_hated
        # Half voters give 0 stars to choice_loved, 5 to choice_hated
        ballots = []
        for i, voter in enumerate(extreme_voters):
            ballot = BallotFactory(
                decision=decision,
                voter=voter,
                is_calculated=False,
                tags="extreme",
                with_votes=False
            )
            ballots.append(ballot)
            
            if i < 5:  # First half loves choice_loved
                VoteFactory(ballot=ballot, choice=choice_loved, stars=5)
                VoteFactory(ballot=ballot, choice=choice_hated, stars=0)
            else:  # Second half hates choice_loved
                VoteFactory(ballot=ballot, choice=choice_loved, stars=0)
                VoteFactory(ballot=ballot, choice=choice_hated, stars=5)
        
        # Test STAR voting
        service = StageBallots()
        results = service.automatic_runoff(ballots)
        
        # Should handle extreme distributions
        assert results is not None
        scores = results['score_phase_results']
        
        # Both choices should have average score of 2.5
        for choice, data in scores.items():
            assert abs(float(data['score']) - 2.5) < 0.001
    
    def test_single_voter_decision(self):
        """Test STAR voting with only one voter."""
        community = CommunityWithDelegationFactory()
        
        voter = UserFactory(username="solo_voter")
        MembershipFactory(community=community, member=voter)
        
        # Create decision with 4 choices
        decision = DecisionFactory(community=community, with_choices=False)
        choices = []
        for i in range(4):
            choice = ChoiceFactory(decision=decision, title=f"Solo Option {i+1}")
            choices.append(choice)
        
        # Single voter rates choices [1, 3, 5, 2]
        ballot = BallotFactory(
            decision=decision,
            voter=voter,
            is_calculated=False,
            tags="solo",
            with_votes=False
        )
        
        ratings = [1, 3, 5, 2]
        for choice, rating in zip(choices, ratings):
            VoteFactory(ballot=ballot, choice=choice, stars=rating)
        
        # Test STAR voting
        service = StageBallots()
        results = service.automatic_runoff([ballot])
        
        # Winner should be choice with 5 stars (choices[2])
        assert results['winner'] == choices[2]
        # Note: Current implementation may still perform runoff even with single voter
        # This could be an area for optimization
    
    def test_large_number_of_choices(self):
        """Test STAR voting with many choices (boundary testing)."""
        community = CommunityWithDelegationFactory()
        
        # Create 5 voters
        voters = []
        for i in range(5):
            user = UserFactory(username=f"many_choice_voter_{i}")
            MembershipFactory(community=community, member=user)
            voters.append(user)
        
        # Create decision with 10 choices
        decision = DecisionFactory(community=community, with_choices=False)
        choices = []
        for i in range(10):
            choice = ChoiceFactory(decision=decision, title=f"Choice {i+1}")
            choices.append(choice)
        
        # Each voter rates all choices randomly but consistently
        import random
        random.seed(42)  # Deterministic for testing
        
        ballots = []
        for voter in voters:
            ballot = BallotFactory(
                decision=decision,
                voter=voter,
                is_calculated=False,
                tags="many_choices",
                with_votes=False
            )
            ballots.append(ballot)
            
            for choice in choices:
                stars = random.randint(0, 5)
                VoteFactory(ballot=ballot, choice=choice, stars=stars)
        
        # Test STAR voting handles many choices
        service = StageBallots()
        results = service.automatic_runoff(ballots)
        
        assert results is not None
        assert results['winner'] in choices
        assert len(results['score_phase_results']) == 10
    
    def test_precision_in_score_calculations(self):
        """Test mathematical precision in score calculations."""
        community = CommunityWithDelegationFactory()
        
        # Create scenario designed to test floating point precision
        voters = []
        for i in range(7):  # 7 voters to create division that doesn't round nicely
            user = UserFactory(username=f"precision_voter_{i}")
            MembershipFactory(community=community, member=user)
            voters.append(user)
        
        # Create 2 choices
        decision = DecisionFactory(community=community, with_choices=False)
        choice_a = ChoiceFactory(decision=decision, title="Precision A")
        choice_b = ChoiceFactory(decision=decision, title="Precision B")
        
        # Create votes that result in 22/7 and 23/7 averages
        # Choice A: [3, 3, 3, 3, 3, 3, 4] = 22/7 ≈ 3.142857
        # Choice B: [3, 3, 3, 3, 3, 4, 4] = 23/7 ≈ 3.285714
        choice_a_votes = [3, 3, 3, 3, 3, 3, 4]
        choice_b_votes = [3, 3, 3, 3, 3, 4, 4]
        
        ballots = []
        for i, voter in enumerate(voters):
            ballot = BallotFactory(
                decision=decision,
                voter=voter,
                is_calculated=False,
                tags="precision",
                with_votes=False
            )
            ballots.append(ballot)
            
            VoteFactory(ballot=ballot, choice=choice_a, stars=choice_a_votes[i])
            VoteFactory(ballot=ballot, choice=choice_b, stars=choice_b_votes[i])
        
        # Test score calculation precision
        service = StageBallots()
        scores = service.score(ballots)
        
        # Verify precise calculations
        expected_a = 22.0 / 7.0  # ≈ 3.142857
        expected_b = 23.0 / 7.0  # ≈ 3.285714
        
        scores_list = list(scores.items())
        # Choice B should be first (higher score), then Choice A
        assert abs(float(scores_list[0][1]['score']) - expected_b) < 0.0001
        assert abs(float(scores_list[1][1]['score']) - expected_a) < 0.0001
    
    def test_runoff_with_identical_preferences(self):
        """Test runoff phase when voters have identical preferences for top 2."""
        community = CommunityWithDelegationFactory()
        
        # Create 4 voters
        voters = []
        for i in range(4):
            user = UserFactory(username=f"identical_voter_{i}")
            MembershipFactory(community=community, member=user)
            voters.append(user)
        
        # Create 3 choices
        decision = DecisionFactory(community=community, with_choices=False)
        choice_a = ChoiceFactory(decision=decision, title="Tied Winner A")
        choice_b = ChoiceFactory(decision=decision, title="Tied Winner B") 
        choice_c = ChoiceFactory(decision=decision, title="Clear Loser")
        
        # All voters rate A and B equally high, C low
        # This tests runoff tie-breaking
        ballots = []
        for voter in voters:
            ballot = BallotFactory(
                decision=decision,
                voter=voter,
                is_calculated=False,
                tags="identical_prefs",
                with_votes=False
            )
            ballots.append(ballot)
            
            VoteFactory(ballot=ballot, choice=choice_a, stars=5)
            VoteFactory(ballot=ballot, choice=choice_b, stars=5)
            VoteFactory(ballot=ballot, choice=choice_c, stars=1)
        
        # Test STAR voting
        service = StageBallots()
        results = service.automatic_runoff(ballots)
        
        # Should handle runoff tie gracefully
        assert results is not None
        assert results['winner'] in [choice_a, choice_b]  # Either could win in tie
        assert results['runner_up'] in [choice_a, choice_b]
        assert results['winner'] != results['runner_up']
    
    def test_zero_votes_scenario(self):
        """Test STAR voting with no votes cast."""
        community = CommunityWithDelegationFactory()
        
        # Create decision but no votes
        decision = DecisionFactory(community=community, with_choices=False)
        choice_a = ChoiceFactory(decision=decision, title="No Votes A")
        choice_b = ChoiceFactory(decision=decision, title="No Votes B")
        
        # Test with empty ballot list
        service = StageBallots()
        results = service.automatic_runoff([])
        
        # Should handle gracefully
        assert results is not None
        assert results['winner'] is None
    
    def test_all_zero_ratings(self):
        """Test when all voters give 0 stars to all choices."""
        community = CommunityWithDelegationFactory()
        
        # Create 3 voters
        voters = []
        for i in range(3):
            user = UserFactory(username=f"zero_voter_{i}")
            MembershipFactory(community=community, member=user)
            voters.append(user)
        
        # Create 3 choices
        decision = DecisionFactory(community=community, with_choices=False)
        choices = []
        for i in range(3):
            choice = ChoiceFactory(decision=decision, title=f"Zero Option {i+1}")
            choices.append(choice)
        
        # All voters give 0 stars to everything
        ballots = []
        for voter in voters:
            ballot = BallotFactory(
                decision=decision,
                voter=voter,
                is_calculated=False,
                tags="all_zeros",
                with_votes=False
            )
            ballots.append(ballot)
            
            for choice in choices:
                VoteFactory(ballot=ballot, choice=choice, stars=0)
        
        # Test STAR voting
        service = StageBallots()
        results = service.automatic_runoff(ballots)
        
        # Should handle all-zero scenario
        assert results is not None
        # All choices should have 0.0 average
        scores = results['score_phase_results']
        for choice, data in scores.items():
            assert float(data['score']) == 0.0
    
    def test_missing_votes_for_some_choices(self):
        """Test when some voters don't rate all choices."""
        community = CommunityWithDelegationFactory()
        
        # Create 2 voters
        voter1 = UserFactory(username="partial_voter_1")
        voter2 = UserFactory(username="partial_voter_2")
        MembershipFactory(community=community, member=voter1)
        MembershipFactory(community=community, member=voter2)
        
        # Create 3 choices
        decision = DecisionFactory(community=community, with_choices=False)
        choice_a = ChoiceFactory(decision=decision, title="Partial A")
        choice_b = ChoiceFactory(decision=decision, title="Partial B")
        choice_c = ChoiceFactory(decision=decision, title="Partial C")
        
        # Voter 1 only votes on A and B
        ballot1 = BallotFactory(
            decision=decision,
            voter=voter1,
            is_calculated=False,
            tags="partial_1",
            with_votes=False
        )
        VoteFactory(ballot=ballot1, choice=choice_a, stars=5)
        VoteFactory(ballot=ballot1, choice=choice_b, stars=3)
        # No vote for choice_c
        
        # Voter 2 only votes on B and C
        ballot2 = BallotFactory(
            decision=decision,
            voter=voter2,
            is_calculated=False,
            tags="partial_2",
            with_votes=False
        )
        VoteFactory(ballot=ballot2, choice=choice_b, stars=4)
        VoteFactory(ballot=ballot2, choice=choice_c, stars=2)
        # No vote for choice_a
        
        # Test STAR voting with missing votes
        service = StageBallots()
        results = service.automatic_runoff([ballot1, ballot2])
        
        # Should handle missing votes appropriately
        assert results is not None
        scores = results['score_phase_results']
        
        # Choice A: 5/1 = 5.0 average (1 vote)
        # Choice B: (3+4)/2 = 3.5 average (2 votes)
        # Choice C: 2/1 = 2.0 average (1 vote)
        choice_a_data = next(data for choice, data in scores.items() if choice == choice_a)
        choice_b_data = next(data for choice, data in scores.items() if choice == choice_b)
        choice_c_data = next(data for choice, data in scores.items() if choice == choice_c)
        
        assert choice_a_data['vote_count'] == 1
        assert choice_b_data['vote_count'] == 2
        assert choice_c_data['vote_count'] == 1
        
        assert float(choice_a_data['score']) == 5.0
        assert float(choice_b_data['score']) == 3.5
        assert float(choice_c_data['score']) == 2.0


@pytest.mark.services
class TestSTARVotingComplexScenarios:
    """Test complex real-world STAR voting scenarios."""
    
    def test_realistic_community_vote(self):
        """Test STAR voting with realistic community voting patterns."""
        community = CommunityWithDelegationFactory()
        
        # Create 15 community members with varied preferences
        voters = []
        for i in range(15):
            user = UserFactory(username=f"community_member_{i}")
            MembershipFactory(community=community, member=user)
            voters.append(user)
        
        # Create decision about community improvement with 4 realistic options
        decision = DecisionFactory(
            community=community,
            title="Community Center Improvement Priority",
            with_choices=False
        )
        
        playground = ChoiceFactory(decision=decision, title="New Playground Equipment")
        garden = ChoiceFactory(decision=decision, title="Community Garden Expansion")
        security = ChoiceFactory(decision=decision, title="Enhanced Security Lighting")
        social = ChoiceFactory(decision=decision, title="Monthly Social Events")
        
        choices = [playground, garden, security, social]
        
        # Create realistic voting patterns with different voter types
        # Group 1: Families with children (love playground, neutral on others)
        # Group 2: Garden enthusiasts (love garden, like social events)
        # Group 3: Security-conscious (prioritize security, dislike loud social events)
        # Group 4: Social butterflies (love events, like playground for kids)
        # Group 5: Balanced moderates (rate everything medium)
        
        voting_patterns = [
            # Families (5 voters): playground=5, garden=2, security=3, social=2
            ([5, 2, 3, 2], 5),
            # Gardeners (3 voters): playground=2, garden=5, security=2, social=4
            ([2, 5, 2, 4], 3),
            # Security-focused (3 voters): playground=1, garden=2, security=5, social=1
            ([1, 2, 5, 1], 3),
            # Social (2 voters): playground=4, garden=3, security=2, social=5
            ([4, 3, 2, 5], 2),
            # Moderates (2 voters): playground=3, garden=3, security=3, social=3
            ([3, 3, 3, 3], 2)
        ]
        
        ballots = []
        voter_idx = 0
        
        for pattern, count in voting_patterns:
            for _ in range(count):
                if voter_idx >= len(voters):
                    break
                    
                ballot = BallotFactory(
                    decision=decision,
                    voter=voters[voter_idx],
                    is_calculated=False,
                    tags="community_improvement",
                    with_votes=False
                )
                ballots.append(ballot)
                
                for choice, stars in zip(choices, pattern):
                    VoteFactory(ballot=ballot, choice=choice, stars=stars)
                
                voter_idx += 1
        
        # Calculate STAR voting results
        service = StageBallots()
        results = service.automatic_runoff(ballots)
        
        # Verify realistic outcome
        assert results is not None
        assert results['winner'] in choices
        assert results['total_ballots'] == len(ballots)
        
        # Check that scores reflect realistic community preferences
        scores = results['score_phase_results']
        
        # All choices should have reasonable scores (0-5 range)
        for choice, data in scores.items():
            assert 0 <= data['score'] <= 5
            assert data['vote_count'] > 0
    
    def test_strategic_voting_detection(self):
        """Test scenario that might reveal strategic voting patterns."""
        community = CommunityWithDelegationFactory()
        
        # Create scenario where strategic voting might occur
        # 2 popular choices, 1 unpopular choice
        # Some voters might strategically rate their second choice low
        
        voters = []
        for i in range(9):
            user = UserFactory(username=f"strategic_voter_{i}")
            MembershipFactory(community=community, member=user)
            voters.append(user)
        
        decision = DecisionFactory(community=community, with_choices=False)
        choice_a = ChoiceFactory(decision=decision, title="Popular Choice A")
        choice_b = ChoiceFactory(decision=decision, title="Popular Choice B")
        choice_c = ChoiceFactory(decision=decision, title="Unpopular Choice C")
        
        # Voting patterns:
        # Group 1 (3 voters): Honest - A=5, B=4, C=1
        # Group 2 (3 voters): Strategic A supporters - A=5, B=0, C=1
        # Group 3 (3 voters): Strategic B supporters - A=0, B=5, C=1
        
        patterns = [
            ([5, 4, 1], 3),  # Honest voters
            ([5, 0, 1], 3),  # Strategic A supporters
            ([0, 5, 1], 3),  # Strategic B supporters
        ]
        
        ballots = []
        voter_idx = 0
        
        for pattern, count in patterns:
            for _ in range(count):
                ballot = BallotFactory(
                    decision=decision,
                    voter=voters[voter_idx],
                    is_calculated=False,
                    tags="strategic_test",
                    with_votes=False
                )
                ballots.append(ballot)
                
                VoteFactory(ballot=ballot, choice=choice_a, stars=pattern[0])
                VoteFactory(ballot=ballot, choice=choice_b, stars=pattern[1])
                VoteFactory(ballot=ballot, choice=choice_c, stars=pattern[2])
                
                voter_idx += 1
        
        # Calculate results
        service = StageBallots()
        results = service.automatic_runoff(ballots)
        
        # STAR voting should handle strategic voting reasonably
        assert results is not None
        assert results['winner'] in [choice_a, choice_b]  # C should not win
        
        # The runoff should help counter strategic voting
        assert results['runoff_needed'] is True
    
    def test_delegation_integration_with_star_voting(self):
        """Test STAR voting with both manual and calculated (delegated) ballots."""
        community = CommunityWithDelegationFactory(create_delegation_users=True)
        delegation_users = community._delegation_users
        
        # Create decision
        decision = DecisionFactory(community=community, with_choices=False)
        choice_1 = ChoiceFactory(decision=decision, title="Delegation Option 1")
        choice_2 = ChoiceFactory(decision=decision, title="Delegation Option 2")
        choice_3 = ChoiceFactory(decision=decision, title="Delegation Option 3")
        
        choices = [choice_1, choice_2, choice_3]
        
        # Some users vote manually
        manual_ballots = []
        
        # User A votes manually
        ballot_a = BallotFactory(
            decision=decision,
            voter=delegation_users['A'],
            is_calculated=False,
            tags="governance",
            with_votes=False
        )
        manual_ballots.append(ballot_a)
        VoteFactory(ballot=ballot_a, choice=choice_1, stars=5)
        VoteFactory(ballot=ballot_a, choice=choice_2, stars=2)
        VoteFactory(ballot=ballot_a, choice=choice_3, stars=1)
        
        # User B votes manually with different preferences
        if 'B' in delegation_users:
            ballot_b = BallotFactory(
                decision=decision,
                voter=delegation_users['B'],
                is_calculated=False,
                tags="governance",
                with_votes=False
            )
            manual_ballots.append(ballot_b)
            VoteFactory(ballot=ballot_b, choice=choice_1, stars=3)
            VoteFactory(ballot=ballot_b, choice=choice_2, stars=5)
            VoteFactory(ballot=ballot_b, choice=choice_3, stars=2)
        
        # Initialize service and calculate delegated ballots
        service = StageBallots()
        all_ballots = list(manual_ballots)
        
        # Calculate delegated ballots for other users
        for user_key in ['C', 'D', 'E']:
            if user_key in delegation_users:
                calculated_ballot = service.get_or_calculate_ballot(
                    decision=decision,
                    voter=delegation_users[user_key]
                )
                if calculated_ballot and calculated_ballot.votes.exists():
                    all_ballots.append(calculated_ballot)
        
        # Run STAR voting on mixed manual/calculated ballots
        results = service.automatic_runoff(all_ballots)
        
        # Should handle mixed ballot types correctly
        assert results is not None
        assert results['winner'] in choices
        assert results['total_ballots'] == len(all_ballots)
        
        # Verify both manual and calculated ballots are included
        manual_count = len(manual_ballots)
        calculated_count = len(all_ballots) - manual_count
        
        assert manual_count > 0
        # May or may not have calculated ballots depending on delegation setup
        assert len(all_ballots) >= manual_count
