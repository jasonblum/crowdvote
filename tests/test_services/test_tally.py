"""
Tests for the complete tally service integration.

This module tests the integration of delegation and STAR voting
through the complete tally process.
"""

import pytest
from django.utils import timezone
from datetime import timedelta

from democracy.services import StageBallots, Tally
from democracy.models import Decision, Choice, Ballot, Vote, Community
from accounts.models import Following
from democracy.models import Membership
from tests.factories import (
    TestCommunityWithDelegationFactory, DecisionFactory, ChoiceFactory,
    BallotFactory, VoteFactory, UserFactory, MembershipFactory
)


@pytest.mark.services
@pytest.mark.integration
class TestCompleteTallyProcess:
    """Test the complete tally process with delegation and STAR voting."""
    
    def test_end_to_end_delegation_and_star_voting(self):
        """Test complete process: delegation → inheritance → STAR voting."""
        # Create community with A-H delegation pattern
        community = TestCommunityWithDelegationFactory(create_delegation_users=True)
        delegation_users = community._delegation_users
        
        # Create active decision
        decision = DecisionFactory(
            community=community,
            dt_close=timezone.now() + timedelta(days=7)
        )
        
        # Create choices
        choice_a = ChoiceFactory(decision=decision, title="World Domination Plan A")
        choice_b = ChoiceFactory(decision=decision, title="World Domination Plan B") 
        choice_c = ChoiceFactory(decision=decision, title="World Domination Plan C")
        
        # User A votes manually (seed vote)
        ballot_a = BallotFactory(
            decision=decision,
            voter=delegation_users['A'],
            is_calculated=False,
            tags="apple,orange,banana",
            with_votes=False
        )
        VoteFactory(ballot=ballot_a, choice=choice_a, stars=5)
        VoteFactory(ballot=ballot_a, choice=choice_b, stars=3)
        VoteFactory(ballot=ballot_a, choice=choice_c, stars=1)
        
        # Process through StageBallots service to calculate inheritance
        service = StageBallots()
        
        # Calculate ballots for all users
        for letter in ['B', 'C', 'D', 'E', 'F']:
            service.get_or_calculate_ballot(
                decision=decision,
                voter=delegation_users[letter]
            )
        
        # Verify delegation worked
        ballot_b = Ballot.objects.get(decision=decision, voter=delegation_users['B'])
        ballot_f = Ballot.objects.get(decision=decision, voter=delegation_users['F'])
        
        assert ballot_b.is_calculated is True
        assert ballot_f.is_calculated is True
        
        # Verify vote inheritance
        vote_b_a = ballot_b.votes.get(choice=choice_a)
        vote_f_a = ballot_f.votes.get(choice=choice_a)
        
        assert vote_b_a.stars == 5  # Inherited from A
        assert vote_f_a.stars == 5  # Inherited from A (not doubled)
        
        # Run complete STAR voting
        all_ballots = Ballot.objects.filter(decision=decision)
        runoff_result = service.automatic_runoff(all_ballots)
        
        # Verify STAR results
        assert runoff_result['winner'] == choice_a
        assert runoff_result['total_ballots'] > 1
    
    def test_mixed_manual_and_calculated_votes(self):
        """Test scenario with both manual voters and delegation inheritance."""
        community = TestCommunityWithDelegationFactory()
        
        # Create additional manual voters
        manual_voter1 = UserFactory(username="manual1")
        manual_voter2 = UserFactory(username="manual2")
        
        for voter in [manual_voter1, manual_voter2]:
            MembershipFactory(community=community, member=voter)
        
        # Get delegation users
        delegation_users = community._delegation_users
        
        # Create decision
        decision = DecisionFactory(
            community=community,
            dt_close=timezone.now() + timedelta(days=7)
        )
        
        choice_a = ChoiceFactory(decision=decision, title="Option A")
        choice_b = ChoiceFactory(decision=decision, title="Option B")
        
        # Manual voters vote directly
        ballot_m1 = BallotFactory(
            decision=decision,
            voter=manual_voter1,
            is_calculated=False,
            tags="independent",
            with_votes=False
        )
        VoteFactory(ballot=ballot_m1, choice=choice_a, stars=2)
        VoteFactory(ballot=ballot_m1, choice=choice_b, stars=4)
        
        ballot_m2 = BallotFactory(
            decision=decision,
            voter=manual_voter2,
            is_calculated=False,
            tags="independent",
            with_votes=False
        )
        VoteFactory(ballot=ballot_m2, choice=choice_a, stars=1)
        VoteFactory(ballot=ballot_m2, choice=choice_b, stars=5)
        
        # User A votes (will be inherited by others)
        ballot_a = BallotFactory(
            decision=decision,
            voter=delegation_users['A'],
            is_calculated=False,
            with_votes=False,
            tags="apple,orange"
        )
        VoteFactory(ballot=ballot_a, choice=choice_a, stars=5)
        VoteFactory(ballot=ballot_a, choice=choice_b, stars=2)
        
        # Process delegation
        service = StageBallots()
        for letter in ['B', 'C', 'D', 'E', 'F']:
            service.get_or_calculate_ballot(
                decision=decision,
                voter=delegation_users[letter]
            )
        
        # Run STAR voting on all ballots
        all_ballots = Ballot.objects.filter(decision=decision)
        runoff_result = service.automatic_runoff(all_ballots)
        
        # Should have mixed manual and calculated votes
        manual_count = all_ballots.filter(is_calculated=False).count()
        calculated_count = all_ballots.filter(is_calculated=True).count()
        
        assert manual_count >= 3  # At least manual1, manual2, A
        assert calculated_count >= 4  # At least B, C, D, E, F (some may inherit)
        
        # Results should reflect both manual votes and inheritance
        assert runoff_result['total_ballots'] >= 7
    
    def test_tally_service_complete_process(self):
        """Test the Tally service with complete delegation scenario."""
        # Create community
        community = TestCommunityWithDelegationFactory(create_delegation_users=True)
        delegation_users = community._delegation_users
        
        # Create active decision
        decision = DecisionFactory(
            community=community,
            title="Community Banana Budget Allocation",
            dt_close=timezone.now() + timedelta(days=7)
        )
        
        # Create realistic choices
        choice_smoothies = ChoiceFactory(
            decision=decision,
            title="60% Smoothies, 40% Fresh"
        )
        choice_balanced = ChoiceFactory(
            decision=decision,
            title="40% Fresh, 40% Smoothies, 20% Bread"
        )
        choice_fresh = ChoiceFactory(
            decision=decision,
            title="80% Fresh, 20% Emergency Reserve"
        )
        
        # User A votes as community expert
        ballot_a = BallotFactory(
            decision=decision,
            voter=delegation_users['A'],
            is_calculated=False,
            tags="budget,nutrition,economics",
            with_votes=False  # Don't auto-create votes, we'll create them manually
        )
        VoteFactory(ballot=ballot_a, choice=choice_smoothies, stars=2)
        VoteFactory(ballot=ballot_a, choice=choice_balanced, stars=5)
        VoteFactory(ballot=ballot_a, choice=choice_fresh, stars=3)
        
        # Add a few manual voters with different preferences
        contrarian = UserFactory(username="contrarian_voter")
        MembershipFactory(community=community, member=contrarian)
        
        ballot_contrarian = BallotFactory(
            decision=decision,
            voter=contrarian,
            is_calculated=False,
            tags="individual_choice",
            with_votes=False  # Manual vote creation
        )
        VoteFactory(ballot=ballot_contrarian, choice=choice_smoothies, stars=5)
        VoteFactory(ballot=ballot_contrarian, choice=choice_balanced, stars=1)
        VoteFactory(ballot=ballot_contrarian, choice=choice_fresh, stars=2)
        
        # Run complete tally service
        tally_service = Tally()
        result = tally_service.process()
        
        # Verify tally service ran
        assert isinstance(result, str)
        assert len(result) > 0
        
        # Verify the result contains tally information
        assert "STAR VOTING TALLY" in result
        assert decision.title in result
        assert "SCORE PHASE" in result
        assert "AUTOMATIC RUNOFF" in result
    
    def test_delegation_tree_data_in_tally(self):
        """Test that delegation tree data is captured during tally."""
        community = TestCommunityWithDelegationFactory(create_delegation_users=True)
        delegation_users = community._delegation_users
        
        # Create decision
        decision = DecisionFactory(
            community=community,
            dt_close=timezone.now() + timedelta(days=7)
        )
        
        choice = ChoiceFactory(decision=decision, title="Test Choice")
        
        # User A votes manually
        ballot_a = BallotFactory(
            decision=decision,
            voter=delegation_users['A'],
            is_calculated=False,
            tags="apple",  # B follows A on apple tags
            with_votes=False  # Manual vote creation
        )
        VoteFactory(ballot=ballot_a, choice=choice, stars=4)
        
        # Process through StageBallots to build delegation tree
        service = StageBallots()
        
        # Calculate ballots for delegation chain
        for letter in ['B', 'C', 'D', 'E']:
            service.get_or_calculate_ballot(
                decision=decision,
                voter=delegation_users[letter]
            )
        
        # Verify delegation tree data was captured
        tree_data = service.delegation_tree_data
        
        assert len(tree_data['nodes']) >= 2  # At least A and B
        assert isinstance(tree_data['edges'], list)  # Should have edges list
        
        # Verify that tree data contains user information
        usernames = [n['username'] for n in tree_data['nodes']]
        assert any(u.startswith('A_delegationtest') for u in usernames)
        assert any(u.startswith('B_delegationtest') for u in usernames)
        
        # Verify that nodes have required fields
        for node in tree_data['nodes']:
            assert 'username' in node
            assert 'vote_type' in node
            assert node['vote_type'] in ['manual', 'calculated']
    
    def test_complex_multi_community_scenario(self):
        """Test tally service with multiple communities."""
        # Create two communities
        community1 = TestCommunityWithDelegationFactory(name="Community Alpha")
        community2 = TestCommunityWithDelegationFactory(name="Community Beta")
        
        # Create decisions in both communities
        decision1 = DecisionFactory(
            community=community1,
            title="Alpha Decision",
            dt_close=timezone.now() + timedelta(days=7)
        )
        decision2 = DecisionFactory(
            community=community2,
            title="Beta Decision", 
            dt_close=timezone.now() + timedelta(days=7)
        )
        
        # Add choices to both
        choice1 = ChoiceFactory(decision=decision1, title="Alpha Choice")
        choice2 = ChoiceFactory(decision=decision2, title="Beta Choice")
        
        # Add votes to both decisions
        user1 = UserFactory(username="multi_voter1")
        user2 = UserFactory(username="multi_voter2")
        
        # User1 in community1
        MembershipFactory(community=community1, member=user1)
        ballot1 = BallotFactory(decision=decision1, voter=user1, is_calculated=False, with_votes=False)
        VoteFactory(ballot=ballot1, choice=choice1, stars=3)
        
        # User2 in community2
        MembershipFactory(community=community2, member=user2)
        ballot2 = BallotFactory(decision=decision2, voter=user2, is_calculated=False, with_votes=False)
        VoteFactory(ballot=ballot2, choice=choice2, stars=4)
        
        # Run tally service
        tally_service = Tally()
        result = tally_service.process()
        
        # Should process both communities
        assert isinstance(result, str)
        assert len(result) > 0
        
        # Should contain information about both decisions
        assert "Alpha Decision" in result
        assert "Beta Decision" in result
    
    def test_performance_with_large_delegation_chains(self):
        """Test performance with complex delegation scenarios."""
        community = TestCommunityWithDelegationFactory()
        
        # Create a larger set of users with complex delegation
        users = []
        for i in range(20):
            user = UserFactory(username=f"perf_user_{i}")
            MembershipFactory(community=community, member=user)
            users.append(user)
        
        # Create complex delegation network
        # Each user follows the previous user
        for i in range(1, 20):
            Following.objects.create(
                follower=users[i],
                followee=users[i-1],
                tags="performance",
                order=1
            )
        
        # Create decision
        decision = DecisionFactory(
            community=community,
            dt_close=timezone.now() + timedelta(days=7)
        )
        choice = ChoiceFactory(decision=decision, title="Performance Choice")
        
        # First user votes (will propagate through chain)
        ballot_root = BallotFactory(
            decision=decision,
            voter=users[0],
            is_calculated=False,
            tags="performance",
            with_votes=False  # Manual vote creation
        )
        VoteFactory(ballot=ballot_root, choice=choice, stars=3)
        
        # Process all ballots
        service = StageBallots()
        
        # Time the delegation calculation
        import time
        start_time = time.time()
        
        for user in users[1:]:
            service.get_or_calculate_ballot(decision=decision, voter=user)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Should complete in reasonable time (adjust threshold as needed)
        assert processing_time < 10.0  # Should take less than 10 seconds
        
        # Verify all ballots were created
        total_ballots = Ballot.objects.filter(decision=decision).count()
        assert total_ballots == 20
        
        # Verify delegation worked through the chain
        last_ballot = Ballot.objects.get(decision=decision, voter=users[-1])
        assert last_ballot.is_calculated is True
        
        last_vote = last_ballot.votes.get(choice=choice)
        assert last_vote.stars == 3  # Should inherit from root user
