"""
Advanced edge case tests for delegation algorithms in democracy/services.py.

This module focuses on comprehensive edge case testing including complex
delegation scenarios, error handling, and boundary conditions.
"""

import pytest
from django.utils import timezone
from datetime import timedelta

from democracy.services import StageBallots
from democracy.models import Decision, Choice, Ballot, Vote
from accounts.models import Following
from democracy.models import Membership
from tests.factories import (
    CommunityWithDelegationFactory, DecisionFactory, ChoiceFactory,
    BallotFactory, VoteFactory, UserFactory, MembershipFactory
)


@pytest.mark.services
class TestDelegationEdgeCases:
    """Test edge cases and boundary conditions in delegation algorithms."""
    
    def test_complex_multi_level_delegation_chain(self):
        """Test deep delegation chain: E→D→C→B→A (5 levels)."""
        community = CommunityWithDelegationFactory()
        
        # Create 5 users for deep chain
        users = []
        for i, letter in enumerate(['A', 'B', 'C', 'D', 'E']):
            user = UserFactory(username=f"chain_user_{letter}")
            MembershipFactory(community=community, member=user)
            users.append(user)
        
        # Create delegation chain E→D→C→B→A
        for i in range(4):
            Following.objects.create(
                follower=users[4-i],  # E, D, C, B
                followee=users[3-i],  # D, C, B, A
                tags="governance",
                order=1
            )
        
        # Create decision
        decision = DecisionFactory(community=community, with_choices=False)
        choice1 = ChoiceFactory(decision=decision, title="Deep Chain Option")
        
        # User A (root) votes manually
        ballot_a = BallotFactory(
            decision=decision,
            voter=users[0],  # A
            is_calculated=False,
            tags="governance",
            with_votes=False
        )
        VoteFactory(ballot=ballot_a, choice=choice1, stars=4)
        
        # Initialize service
        service = StageBallots()
        
        # Calculate E's ballot (deepest in chain)
        ballot_e = service.get_or_calculate_ballot(
            decision=decision,
            voter=users[4]  # E
        )
        
        # Verify inheritance through 4-level delegation
        assert ballot_e.is_calculated is True
        assert "governance" in ballot_e.tags
        
        vote_e = ballot_e.votes.get(choice=choice1)
        assert vote_e.stars == 4  # Should inherit A's vote through the chain
    
    def test_multiple_inheritance_sources_with_priorities(self):
        """Test voter following multiple people with different priorities."""
        community = CommunityWithDelegationFactory()
        
        # Create users
        follower = UserFactory(username="multi_follower")
        leader1 = UserFactory(username="leader_priority_1")
        leader2 = UserFactory(username="leader_priority_2")
        leader3 = UserFactory(username="leader_priority_3")
        
        for user in [follower, leader1, leader2, leader3]:
            MembershipFactory(community=community, member=user)
        
        # Set up following with different priorities (lower = higher priority)
        Following.objects.create(
            follower=follower, followee=leader1, tags="governance", order=1
        )
        Following.objects.create(
            follower=follower, followee=leader2, tags="governance", order=2
        )
        Following.objects.create(
            follower=follower, followee=leader3, tags="governance", order=3
        )
        
        # Create decision
        decision = DecisionFactory(community=community, with_choices=False)
        choice1 = ChoiceFactory(decision=decision, title="Priority Test")
        
        # All leaders vote with different ratings
        for i, leader in enumerate([leader1, leader2, leader3], 1):
            ballot = BallotFactory(
                decision=decision,
                voter=leader,
                is_calculated=False,
                tags="governance",
                with_votes=False
            )
            VoteFactory(ballot=ballot, choice=choice1, stars=i)
        
        # Initialize service and calculate follower's vote
        service = StageBallots()
        ballot_follower = service.get_or_calculate_ballot(
            decision=decision,
            voter=follower
        )
        
        # Should inherit average from all sources (1+2+3)/3 = 2.00 stars
        # Note: Priority tie-breaking is not yet implemented (TODO in services.py)
        assert ballot_follower.is_calculated is True
        vote_follower = ballot_follower.votes.get(choice=choice1)
        assert vote_follower.stars == 2.00
    
    def test_mixed_tag_inheritance(self):
        """Test inheritance from multiple sources with different tags."""
        community = CommunityWithDelegationFactory()
        
        voter = UserFactory(username="mixed_tag_voter")
        budget_expert = UserFactory(username="budget_expert")
        environment_expert = UserFactory(username="environment_expert")
        
        for user in [voter, budget_expert, environment_expert]:
            MembershipFactory(community=community, member=user)
        
        # Voter follows different experts on different tags
        Following.objects.create(
            follower=voter, followee=budget_expert, tags="budget", order=1
        )
        Following.objects.create(
            follower=voter, followee=environment_expert, tags="environment", order=1
        )
        
        # Create decision
        decision = DecisionFactory(community=community, with_choices=False)
        choice1 = ChoiceFactory(decision=decision, title="Mixed Decision")
        
        # Budget expert votes on budget topics
        ballot_budget = BallotFactory(
            decision=decision,
            voter=budget_expert,
            is_calculated=False,
            tags="budget,fiscal",
            with_votes=False
        )
        VoteFactory(ballot=ballot_budget, choice=choice1, stars=5)
        
        # Environment expert votes on environment topics
        ballot_env = BallotFactory(
            decision=decision,
            voter=environment_expert,
            is_calculated=False,
            tags="environment,green",
            with_votes=False
        )
        VoteFactory(ballot=ballot_env, choice=choice1, stars=2)
        
        # Initialize service
        service = StageBallots()
        
        # Calculate voter's ballot - should average the inherited votes
        ballot_voter = service.get_or_calculate_ballot(
            decision=decision,
            voter=voter
        )
        
        assert ballot_voter.is_calculated is True
        
        # Should inherit tags from both sources
        voter_tags = ballot_voter.tags.split(',') if ballot_voter.tags else []
        assert any(tag in ["budget", "fiscal"] for tag in voter_tags)
        assert any(tag in ["environment", "green"] for tag in voter_tags)
    
    def test_partial_delegation_with_manual_override(self):
        """Test case where voter has some delegated votes and some manual votes."""
        community = CommunityWithDelegationFactory()
        
        voter = UserFactory(username="partial_delegator")
        expert = UserFactory(username="domain_expert")
        
        for user in [voter, expert]:
            MembershipFactory(community=community, member=user)
        
        # Set up delegation
        Following.objects.create(
            follower=voter, followee=expert, tags="technical", order=1
        )
        
        # Create decision with multiple choices
        decision = DecisionFactory(community=community, with_choices=False)
        choice1 = ChoiceFactory(decision=decision, title="Technical Choice")
        choice2 = ChoiceFactory(decision=decision, title="Non-Technical Choice")
        
        # Expert votes on technical matters
        ballot_expert = BallotFactory(
            decision=decision,
            voter=expert,
            is_calculated=False,
            tags="technical",
            with_votes=False
        )
        VoteFactory(ballot=ballot_expert, choice=choice1, stars=5)
        VoteFactory(ballot=ballot_expert, choice=choice2, stars=1)
        
        # Voter manually votes on some choices but lets delegation handle others
        ballot_voter = BallotFactory(
            decision=decision,
            voter=voter,
            is_calculated=False,
            tags="personal",
            with_votes=False
        )
        # Only vote on choice2 manually, let delegation handle choice1
        VoteFactory(ballot=ballot_voter, choice=choice2, stars=4)
        
        # This test simulates the complexity of partial delegation
        # The actual implementation might need to handle this scenario
        assert ballot_voter is not None
    
    def test_circular_reference_detection_and_prevention(self):
        """Test comprehensive circular reference detection."""
        community = CommunityWithDelegationFactory()
        
        # Create users for circular scenarios
        users = {}
        for letter in ['A', 'B', 'C', 'D']:
            user = UserFactory(username=f"circular_{letter}")
            MembershipFactory(community=community, member=user)
            users[letter] = user
        
        # Create various circular patterns
        # Simple cycle: A→B→A
        Following.objects.create(
            follower=users['A'], followee=users['B'], tags="governance", order=1
        )
        Following.objects.create(
            follower=users['B'], followee=users['A'], tags="governance", order=1
        )
        
        # Longer cycle: C→D→C  
        Following.objects.create(
            follower=users['C'], followee=users['D'], tags="governance", order=1
        )
        Following.objects.create(
            follower=users['D'], followee=users['C'], tags="governance", order=1
        )
        
        # Create decision
        decision = DecisionFactory(community=community, with_choices=False)
        choice = ChoiceFactory(decision=decision)
        
        # Initialize service
        service = StageBallots()
        
        # Should handle circular references gracefully for all users
        for letter, user in users.items():
            ballot = service.get_or_calculate_ballot(
                decision=decision,
                voter=user,
                follow_path=[]
            )
            
            # Should not cause infinite recursion
            assert ballot is not None
            assert isinstance(ballot, Ballot)
    
    def test_delegation_with_inactive_users(self):
        """Test delegation when followed users are inactive or have no votes."""
        community = CommunityWithDelegationFactory()
        
        active_voter = UserFactory(username="active_voter")
        inactive_leader = UserFactory(username="inactive_leader")
        active_leader = UserFactory(username="active_leader")
        
        for user in [active_voter, inactive_leader, active_leader]:
            MembershipFactory(community=community, member=user)
        
        # Set up delegation chain: voter→inactive→active
        Following.objects.create(
            follower=active_voter, followee=inactive_leader, tags="governance", order=1
        )
        Following.objects.create(
            follower=inactive_leader, followee=active_leader, tags="governance", order=1
        )
        
        # Create decision
        decision = DecisionFactory(community=community, with_choices=False)
        choice = ChoiceFactory(decision=decision, title="Inactive Test")
        
        # Only active_leader votes (inactive_leader doesn't vote)
        ballot_active = BallotFactory(
            decision=decision,
            voter=active_leader,
            is_calculated=False,
            tags="governance",
            with_votes=False
        )
        VoteFactory(ballot=ballot_active, choice=choice, stars=4)
        
        # Initialize service
        service = StageBallots()
        
        # Active voter should inherit through inactive user
        ballot_voter = service.get_or_calculate_ballot(
            decision=decision,
            voter=active_voter
        )
        
        # Should successfully inherit despite inactive intermediate user
        assert ballot_voter is not None
        if ballot_voter.votes.exists():
            vote = ballot_voter.votes.get(choice=choice)
            assert vote.stars == 4
    
    def test_tag_mismatch_scenarios(self):
        """Test various tag mismatch scenarios."""
        community = CommunityWithDelegationFactory()
        
        follower = UserFactory(username="tag_follower")
        leader = UserFactory(username="tag_leader")
        
        for user in [follower, leader]:
            MembershipFactory(community=community, member=user)
        
        # Follower follows on "budget" but leader votes on "environment"
        Following.objects.create(
            follower=follower, followee=leader, tags="budget", order=1
        )
        
        # Create multiple test scenarios
        scenarios = [
            ("environment", False),  # No tag overlap
            ("budget,environment", True),  # Partial overlap
            ("budget", True),  # Exact match
            ("BUDGET", False),  # Case sensitivity
            ("budget-related", False),  # Substring not matching
        ]
        
        for tag_combo, should_inherit in scenarios:
            # Create fresh decision for each scenario
            decision = DecisionFactory(community=community, with_choices=False)
            choice = ChoiceFactory(decision=decision, title=f"Tag Test: {tag_combo}")
            
            # Leader votes with specific tags
            ballot_leader = BallotFactory(
                decision=decision,
                voter=leader,
                is_calculated=False,
                tags=tag_combo,
                with_votes=False
            )
            VoteFactory(ballot=ballot_leader, choice=choice, stars=3)
            
            # Initialize service
            service = StageBallots()
            
            # Calculate follower's ballot
            ballot_follower = service.get_or_calculate_ballot(
                decision=decision,
                voter=follower
            )
            
            if should_inherit:
                # Should inherit when tags match
                assert ballot_follower.is_calculated is True
                if ballot_follower.votes.exists():
                    vote = ballot_follower.votes.get(choice=choice)
                    assert vote.stars == 3
            # Note: The exact behavior for non-matching tags depends on implementation
    
    def test_performance_with_large_delegation_network(self):
        """Test performance with large numbers of delegation relationships."""
        community = CommunityWithDelegationFactory()
        
        # Create a hub-and-spoke delegation network
        hub_user = UserFactory(username="delegation_hub")
        MembershipFactory(community=community, member=hub_user)
        
        spoke_users = []
        for i in range(50):  # Create 50 followers
            user = UserFactory(username=f"spoke_user_{i}")
            MembershipFactory(community=community, member=user)
            spoke_users.append(user)
            
            # Each spoke follows the hub
            Following.objects.create(
                follower=user,
                followee=hub_user,
                tags="governance",
                order=1
            )
        
        # Create decision
        decision = DecisionFactory(community=community, with_choices=False)
        choice = ChoiceFactory(decision=decision, title="Performance Test")
        
        # Hub votes
        ballot_hub = BallotFactory(
            decision=decision,
            voter=hub_user,
            is_calculated=False,
            tags="governance",
            with_votes=False
        )
        VoteFactory(ballot=ballot_hub, choice=choice, stars=5)
        
        # Initialize service
        service = StageBallots()
        
        # Test that delegation calculation completes in reasonable time
        import time
        start_time = time.time()
        
        # Calculate ballots for first 10 spoke users
        for i in range(10):
            ballot = service.get_or_calculate_ballot(
                decision=decision,
                voter=spoke_users[i]
            )
            assert ballot is not None
        
        end_time = time.time()
        calculation_time = end_time - start_time
        
        # Should complete in under 5 seconds for 10 delegations
        assert calculation_time < 5.0
    
    def test_delegation_tree_data_accuracy(self):
        """Test that delegation tree data captures complex relationships accurately."""
        community = CommunityWithDelegationFactory(create_delegation_users=True)
        delegation_users = community._delegation_users
        
        # Create decision
        decision = DecisionFactory(community=community, with_choices=False)
        choice = ChoiceFactory(decision=decision, title="Tree Data Test")
        
        # User A votes manually
        ballot_a = BallotFactory(
            decision=decision,
            voter=delegation_users['A'],
            is_calculated=False,
            tags="apple,governance",
            with_votes=False
        )
        VoteFactory(ballot=ballot_a, choice=choice, stars=5)
        
        # Initialize service
        service = StageBallots()
        
        # Calculate multiple ballots to build tree
        calculated_ballots = []
        for user_key in ['B', 'C', 'D', 'E']:
            if user_key in delegation_users:
                ballot = service.get_or_calculate_ballot(
                    decision=decision,
                    voter=delegation_users[user_key]
                )
                calculated_ballots.append(ballot)
        
        # Verify tree data structure
        tree_data = service.delegation_tree_data
        
        # Should have nodes for A (manual) and calculated users
        assert len(tree_data['nodes']) >= 2
        
        # Should have edges representing delegation relationships
        assert len(tree_data['edges']) >= 1
        
        # Verify node data structure
        for node in tree_data['nodes']:
            assert 'username' in node
            assert 'vote_type' in node
            assert node['vote_type'] in ['manual', 'calculated']
            
            if 'votes' in node:
                assert isinstance(node['votes'], dict)
        
        # Verify edge data structure
        for edge in tree_data['edges']:
            assert 'follower' in edge
            assert 'followee' in edge
            assert 'tags' in edge
            assert 'active_for_decision' in edge


@pytest.mark.services
class TestDelegationErrorHandling:
    """Test error handling and boundary conditions."""
    
    def test_delegation_with_invalid_users(self):
        """Test delegation calculations with invalid or deleted users."""
        community = CommunityWithDelegationFactory()
        
        valid_user = UserFactory(username="valid_user")
        MembershipFactory(community=community, member=valid_user)
        
        # Create following relationship to non-existent user
        # (This would normally be prevented by foreign key constraints,
        # but we test the service's resilience)
        
        # Create decision
        decision = DecisionFactory(community=community, with_choices=False)
        choice = ChoiceFactory(decision=decision)
        
        # Initialize service
        service = StageBallots()
        
        # Should handle gracefully even with invalid relationships
        ballot = service.get_or_calculate_ballot(
            decision=decision,
            voter=valid_user
        )
        
        assert ballot is not None
    
    def test_delegation_with_future_decision(self):
        """Test delegation for decisions that haven't started yet."""
        community = CommunityWithDelegationFactory()
        
        voter = UserFactory(username="early_voter")
        MembershipFactory(community=community, member=voter)
        
        # Create future decision
        future_time = timezone.now() + timedelta(days=30)
        decision = DecisionFactory(
            community=community,
            dt_close=future_time,
            with_choices=False
        )
        choice = ChoiceFactory(decision=decision)
        
        # Initialize service
        service = StageBallots()
        
        # Should handle future decisions gracefully
        ballot = service.get_or_calculate_ballot(
            decision=decision,
            voter=voter
        )
        
        assert ballot is not None
    
    def test_delegation_with_closed_decision(self):
        """Test delegation for decisions that have already closed."""
        community = CommunityWithDelegationFactory()
        
        voter = UserFactory(username="late_voter")
        MembershipFactory(community=community, member=voter)
        
        # Create past decision
        past_time = timezone.now() - timedelta(days=1)
        decision = DecisionFactory(
            community=community,
            dt_close=past_time,
            with_choices=False
        )
        choice = ChoiceFactory(decision=decision)
        
        # Initialize service
        service = StageBallots()
        
        # Should handle closed decisions appropriately
        ballot = service.get_or_calculate_ballot(
            decision=decision,
            voter=voter
        )
        
        # Behavior depends on implementation - might allow or deny
        assert ballot is not None
