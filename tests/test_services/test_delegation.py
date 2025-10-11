"""
Comprehensive tests for delegation algorithms in democracy/services.py.

This module tests the core delegation functionality including vote inheritance,
circular reference prevention, tag-specific delegation, and multi-level chains.
"""

import pytest
from django.utils import timezone
from datetime import timedelta

from democracy.services import StageBallots
from democracy.models import Decision, Choice, Ballot, Vote
from democracy.models import Following
from democracy.models import Membership
from tests.factories import (
    CommunityWithDelegationFactory, DecisionFactory, ChoiceFactory,
    BallotFactory, VoteFactory, UserFactory, MembershipFactory,
    SpecificFollowingFactory
)


@pytest.mark.services
class TestStageBallotsDelegation:
    """Test the StageBallots service delegation algorithms."""
    
    def test_delegation_service_initialization(self):
        """Test that StageBallots service initializes properly."""
        service = StageBallots()
        assert hasattr(service, 'delegation_tree_data')
        assert 'nodes' in service.delegation_tree_data
        assert 'edges' in service.delegation_tree_data
        assert 'inheritance_chains' in service.delegation_tree_data
    
    def test_single_level_delegation(self):
        """Test B→A delegation inheritance."""
        # Create community with A-H delegation pattern
        community = CommunityWithDelegationFactory(create_delegation_users=True)
        delegation_users = community._delegation_users
        
        # Create decision and choices
        decision = DecisionFactory(community=community, with_choices=False)
        choice1 = ChoiceFactory(decision=decision, title="Option A")
        choice2 = ChoiceFactory(decision=decision, title="Option B")
        
        # User A votes manually
        ballot_a = BallotFactory(
            decision=decision,
            voter=delegation_users['A'],
            is_calculated=False,
            with_votes=False,
            tags="apple,orange"
        )
        VoteFactory(ballot=ballot_a, choice=choice1, stars=5)
        VoteFactory(ballot=ballot_a, choice=choice2, stars=2)
        
        # Initialize service and calculate B's ballot
        service = StageBallots()
        ballot_b = service.get_or_calculate_ballot(
            decision=decision,
            voter=delegation_users['B']
        )
        
        # Verify B inherited A's vote through apple tag delegation
        assert ballot_b.is_calculated is True
        assert "apple" in ballot_b.tags
        
        # Verify vote inheritance
        votes_b = ballot_b.votes.all()
        assert votes_b.count() == 2
        
        # Check specific vote values match A's votes
        vote_b_choice1 = votes_b.get(choice=choice1)
        vote_b_choice2 = votes_b.get(choice=choice2)
        assert vote_b_choice1.stars == 5
        assert vote_b_choice2.stars == 2
    
    def test_multi_level_delegation_chain(self):
        """Test D→C→A and E→C→A delegation chains."""
        # Create community with delegation setup
        community = CommunityWithDelegationFactory(create_delegation_users=True)
        delegation_users = community._delegation_users
        
        # Create decision
        decision = DecisionFactory(community=community, with_choices=False)
        choice1 = ChoiceFactory(decision=decision, title="Option A")
        choice2 = ChoiceFactory(decision=decision, title="Option B")
        
        # User A votes manually on orange tag
        ballot_a = BallotFactory(
            decision=decision,
            voter=delegation_users['A'],
            is_calculated=False,
            tags="orange",
            with_votes=False
        )
        VoteFactory(ballot=ballot_a, choice=choice1, stars=4)
        VoteFactory(ballot=ballot_a, choice=choice2, stars=1)
        
        # Initialize service
        service = StageBallots()
        
        # Calculate D's ballot (D→C→A chain)
        ballot_d = service.get_or_calculate_ballot(
            decision=decision,
            voter=delegation_users['D']
        )
        
        # Calculate E's ballot (E→C→A chain)
        ballot_e = service.get_or_calculate_ballot(
            decision=decision,
            voter=delegation_users['E']
        )
        
        # Verify both D and E inherited through the chain
        assert ballot_d.is_calculated is True
        assert ballot_e.is_calculated is True
        
        # Both should have orange tag from inheritance
        assert "orange" in ballot_d.tags
        assert "orange" in ballot_e.tags
        
        # Verify vote values match A's original votes
        votes_d = ballot_d.votes.all()
        votes_e = ballot_e.votes.all()
        
        vote_d_choice1 = votes_d.get(choice=choice1)
        vote_e_choice1 = votes_e.get(choice=choice1)
        
        assert vote_d_choice1.stars == 4
        assert vote_e_choice1.stars == 4
    
    def test_duplicate_inheritance_prevention(self):
        """Test that F inherits from A only once despite multiple paths."""
        # F should inherit from A only once despite F→A and F→D→C→A paths
        community = CommunityWithDelegationFactory(create_delegation_users=True)
        delegation_users = community._delegation_users
        
        # Create decision
        decision = DecisionFactory(community=community, with_choices=False)
        choice1 = ChoiceFactory(decision=decision, title="Option A")
        
        # User A votes manually - ensure no votes created by factory
        ballot_a = BallotFactory(
            decision=decision,
            voter=delegation_users['A'],
            is_calculated=False,
            tags="apple,banana",
            with_votes=False
        )
        VoteFactory(ballot=ballot_a, choice=choice1, stars=5)
        
        # Initialize service
        service = StageBallots()
        
        # Calculate F's ballot
        ballot_f = service.get_or_calculate_ballot(
            decision=decision,
            voter=delegation_users['F']
        )
        
        # Verify F inherited but only counted A once
        assert ballot_f.is_calculated is True
        
        # Check vote value is A's value, not doubled
        vote_f = ballot_f.votes.get(choice=choice1)
        assert vote_f.stars == 5  # Should be A's vote, not 10 (doubled)
    
    def test_circular_reference_prevention(self):
        """Test that circular references are prevented."""
        community = CommunityWithDelegationFactory()
        user_a = UserFactory(username="circular_a")
        user_b = UserFactory(username="circular_b")
        user_c = UserFactory(username="circular_c")
        
        # Add users to community
        for user in [user_a, user_b, user_c]:
            MembershipFactory(community=community, member=user)
        
        # Create circular following: A→B→C→A
        Following.objects.create(
            follower=user_a, followee=user_b, tags="governance", order=1
        )
        Following.objects.create(
            follower=user_b, followee=user_c, tags="governance", order=1
        )
        Following.objects.create(
            follower=user_c, followee=user_a, tags="governance", order=1
        )
        
        # Create decision
        decision = DecisionFactory(community=community, with_choices=False)
        choice = ChoiceFactory(decision=decision)
        
        # Initialize service
        service = StageBallots()
        
        # This should not cause infinite recursion
        ballot_a = service.get_or_calculate_ballot(
            decision=decision,
            voter=user_a,
            follow_path=[]
        )
        
        # Should complete without error and create a ballot
        assert ballot_a is not None
        assert isinstance(ballot_a, Ballot)
    
    def test_tag_specific_delegation(self):
        """Test that delegation only works for matching tags."""
        community = CommunityWithDelegationFactory()
        user_follower = UserFactory(username="tag_follower")
        user_leader = UserFactory(username="tag_leader")
        
        # Add to community
        for user in [user_follower, user_leader]:
            MembershipFactory(community=community, member=user)
        
        # Follower follows leader only on "budget" tag
        Following.objects.create(
            follower=user_follower,
            followee=user_leader,
            tags="budget",
            order=1
        )
        
        # Create decision
        decision = DecisionFactory(community=community, with_choices=False)
        choice = ChoiceFactory(decision=decision)
        
        # Leader votes with "environment" tag (different from "budget")
        ballot_leader = BallotFactory(
            decision=decision,
            voter=user_leader,
            is_calculated=False,
            tags="environment",
            with_votes=False
        )
        VoteFactory(ballot=ballot_leader, choice=choice, stars=4)
        
        # Initialize service
        service = StageBallots()
        
        # Follower should NOT inherit because tags don't match
        ballot_follower = service.get_or_calculate_ballot(
            decision=decision,
            voter=user_follower
        )
        
        # Should not have inherited the vote (different tags)
        # The ballot might be created but should be marked as not calculated
        # or have no votes if no matching tags found
        votes = ballot_follower.votes.all()
        if votes.exists():
            # If votes exist, they should not match the leader's vote
            vote = votes.get(choice=choice)
            # Should be default value, not the leader's 4 stars
            assert vote.stars != 4
    
    def test_tag_inheritance_with_votes(self):
        """Test that tags are inherited along with votes."""
        community = CommunityWithDelegationFactory()
        user_follower = UserFactory(username="tag_inheritor")
        user_leader = UserFactory(username="tag_source")
        
        # Add to community
        for user in [user_follower, user_leader]:
            MembershipFactory(community=community, member=user)
        
        # Set up following relationship
        Following.objects.create(
            follower=user_follower,
            followee=user_leader,
            tags="governance",
            order=1
        )
        
        # Create decision
        decision = DecisionFactory(community=community, with_choices=False)
        choice = ChoiceFactory(decision=decision)
        
        # Leader votes with specific tags
        ballot_leader = BallotFactory(
            decision=decision,
            voter=user_leader,
            is_calculated=False,
            tags="governance,transparency",
            with_votes=False
        )
        VoteFactory(ballot=ballot_leader, choice=choice, stars=3)
        
        # Initialize service
        service = StageBallots()
        
        # Calculate follower's ballot
        ballot_follower = service.get_or_calculate_ballot(
            decision=decision,
            voter=user_follower
        )
        
        # Verify tag inheritance
        assert ballot_follower.is_calculated is True
        follower_tags = ballot_follower.tags.split(',') if ballot_follower.tags else []
        
        # Should inherit tags from the leader
        assert "governance" in follower_tags or "transparency" in follower_tags
        
        # Should also inherit the vote
        vote_follower = ballot_follower.votes.get(choice=choice)
        assert vote_follower.stars == 3
    
    def test_lobbyist_exclusion(self):
        """Test that lobbyists can be followed but don't count in tallies."""
        community = CommunityWithDelegationFactory()
        lobbyist = UserFactory(username="lobbyist_expert")
        voter = UserFactory(username="regular_voter")
        
        # Add lobbyist as non-voting member
        MembershipFactory(
            community=community,
            member=lobbyist,
            is_voting_community_member=False
        )
        
        # Add regular voter
        MembershipFactory(
            community=community,
            member=voter,
            is_voting_community_member=True
        )
        
        # Voter follows lobbyist
        Following.objects.create(
            follower=voter,
            followee=lobbyist,
            tags="expertise",
            order=1
        )
        
        # Create decision
        decision = DecisionFactory(community=community, with_choices=False)
        choice = ChoiceFactory(decision=decision)
        
        # Lobbyist "votes" (but shouldn't count in tallies)
        ballot_lobbyist = BallotFactory(
            decision=decision,
            voter=lobbyist,
            is_calculated=False,
            tags="expertise",
            with_votes=False
        )
        VoteFactory(ballot=ballot_lobbyist, choice=choice, stars=5)
        
        # Initialize service
        service = StageBallots()
        
        # Calculate voter's ballot
        ballot_voter = service.get_or_calculate_ballot(
            decision=decision,
            voter=voter
        )
        
        # Voter should inherit from lobbyist
        assert ballot_voter.is_calculated is True
        vote_voter = ballot_voter.votes.get(choice=choice)
        assert vote_voter.stars == 5
        
        # But when counting for tallies, only voting members should count
        from .test_star_voting import TestSTARVoting
        voting_ballots = decision.ballots.filter(
            voter__memberships__community=community,
            voter__memberships__is_voting_community_member=True
        )
        
        # Should only include the regular voter, not the lobbyist
        assert voting_ballots.count() == 1
        assert voting_ballots.first().voter == voter
    
    def test_delegation_tree_data_capture(self):
        """Test that delegation tree data is properly captured."""
        community = CommunityWithDelegationFactory(create_delegation_users=True)
        delegation_users = community._delegation_users
        
        # Create decision
        decision = DecisionFactory(community=community, with_choices=False)
        choice = ChoiceFactory(decision=decision)
        
        # User A votes manually
        ballot_a = BallotFactory(
            decision=decision,
            voter=delegation_users['A'],
            is_calculated=False,
            tags="apple",
            with_votes=False
        )
        VoteFactory(ballot=ballot_a, choice=choice, stars=4)
        
        # Initialize service
        service = StageBallots()
        
        # Calculate B's ballot (should inherit from A)
        service.get_or_calculate_ballot(
            decision=decision,
            voter=delegation_users['B']
        )
        
        # Check that delegation tree data was captured
        tree_data = service.delegation_tree_data
        
        assert len(tree_data['nodes']) >= 2  # At least A and B
        assert len(tree_data['edges']) >= 1  # At least B→A edge
        
        # Find nodes for A and B (usernames now have unique suffixes)
        node_a = next((n for n in tree_data['nodes'] if n['username'].startswith('A_delegationtest')), None)
        node_b = next((n for n in tree_data['nodes'] if n['username'].startswith('B_delegationtest')), None)
        
        assert node_a is not None
        assert node_b is not None
        
        # Verify node properties
        assert node_a['vote_type'] == 'manual'
        assert node_b['vote_type'] == 'calculated'
        
        # Check that edge exists (edges use user IDs, not usernames)
        user_a_id = str(delegation_users['A'].id)
        user_b_id = str(delegation_users['B'].id)
        edge_b_to_a = next((e for e in tree_data['edges'] 
                           if e['follower'] == user_b_id 
                           and e['followee'] == user_a_id), None)
        assert edge_b_to_a is not None
        assert 'apple' in edge_b_to_a['tags']


@pytest.mark.services
class TestDelegationEdgeCases:
    """Test edge cases and error conditions in delegation."""
    
    def test_self_following_prevention(self):
        """Test that users cannot follow themselves."""
        community = CommunityWithDelegationFactory()
        user = UserFactory(username="self_follower")
        MembershipFactory(community=community, member=user)
        
        # Attempt to create self-following (should be prevented at model level)
        with pytest.raises(Exception):  # Should raise validation error
            Following.objects.create(
                follower=user,
                followee=user,
                tags="governance",
                order=1
            )
    
    def test_delegation_with_no_votes(self):
        """Test delegation when the followed user has no votes."""
        community = CommunityWithDelegationFactory()
        user_follower = UserFactory(username="follower_no_votes")
        user_leader = UserFactory(username="leader_no_votes")
        
        for user in [user_follower, user_leader]:
            MembershipFactory(community=community, member=user)
        
        # Set up following
        Following.objects.create(
            follower=user_follower,
            followee=user_leader,
            tags="governance",
            order=1
        )
        
        # Create decision but leader doesn't vote
        decision = DecisionFactory(community=community, with_choices=False)
        choice = ChoiceFactory(decision=decision)
        
        # Initialize service
        service = StageBallots()
        
        # Should handle gracefully when leader has no votes
        ballot_follower = service.get_or_calculate_ballot(
            decision=decision,
            voter=user_follower
        )
        
        # Should create ballot but may not have votes or have default votes
        assert ballot_follower is not None
    
    def test_delegation_depth_limit(self):
        """Test that delegation depth is tracked and could be limited."""
        community = CommunityWithDelegationFactory()
        
        # Create a long chain: E→D→C→B→A
        users = []
        for i in range(5):
            user = UserFactory(username=f"depth_user_{i}")
            MembershipFactory(community=community, member=user)
            users.append(user)
        
        # Create chain E→D→C→B→A
        for i in range(4):
            Following.objects.create(
                follower=users[i],
                followee=users[i+1],
                tags="governance",
                order=1
            )
        
        # A (users[4]) votes
        decision = DecisionFactory(community=community, with_choices=False)
        choice = ChoiceFactory(decision=decision)
        
        ballot_a = BallotFactory(
            decision=decision,
            voter=users[4],  # A
            is_calculated=False,
            tags="governance",
            with_votes=False
        )
        VoteFactory(ballot=ballot_a, choice=choice, stars=3)
        
        # Initialize service
        service = StageBallots()
        
        # Calculate E's ballot (deepest in chain)
        ballot_e = service.get_or_calculate_ballot(
            decision=decision,
            voter=users[0]  # E
        )
        
        # Should handle deep delegation gracefully
        assert ballot_e is not None
        
        # Check delegation depth in tree data
        tree_data = service.delegation_tree_data
        node_e = next((n for n in tree_data['nodes'] 
                      if n['username'] == 'depth_user_0'), None)
        
        if node_e:
            # Should track delegation depth
            assert 'delegation_depth' in node_e
            assert node_e['delegation_depth'] >= 0
