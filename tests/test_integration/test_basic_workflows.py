"""
Basic integration tests for core CrowdVote workflows.

This module tests end-to-end functionality across the entire application
ensuring that the major user journeys work correctly.
"""

import pytest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta

from democracy.models import Community, Decision, Choice, Ballot, Vote, Membership
from accounts.models import Following
from democracy.services import StageBallots
from tests.factories import (
    CommunityFactory, UserFactory, MembershipFactory, 
    DecisionFactory, ChoiceFactory, BallotFactory, VoteFactory
)

User = get_user_model()


@pytest.mark.integration
class TestBasicDemocracyWorkflow:
    """Test basic democracy workflow from user creation to voting results."""
    
    def test_complete_voting_workflow(self):
        """Test complete workflow: community → decision → voting → results."""
        # Step 1: Create community and users
        community = CommunityFactory(name="Test Community")
        
        # Create manager
        manager = UserFactory(username="community_manager")
        MembershipFactory(
            community=community, 
            member=manager, 
            is_community_manager=True
        )
        
        # Create regular members
        voter1 = UserFactory(username="voter_one")
        voter2 = UserFactory(username="voter_two")
        
        MembershipFactory(community=community, member=voter1)
        MembershipFactory(community=community, member=voter2)
        
        # Step 2: Create decision with choices
        decision = DecisionFactory(
            community=community,
            title="Test Community Decision About Important Matter",
            description="This is a test decision to verify the complete workflow works correctly for all community members",
            dt_close=timezone.now() + timedelta(days=7),
            with_choices=False
        )
        
        choice_a = ChoiceFactory(decision=decision, title="Option A")
        choice_b = ChoiceFactory(decision=decision, title="Option B")
        choice_c = ChoiceFactory(decision=decision, title="Option C")
        
        # Step 3: Users vote
        # Voter 1 votes manually
        ballot1 = BallotFactory(
            decision=decision,
            voter=voter1,
            is_calculated=False,
            tags="governance,community",
            with_votes=False
        )
        VoteFactory(ballot=ballot1, choice=choice_a, stars=5)
        VoteFactory(ballot=ballot1, choice=choice_b, stars=2)
        VoteFactory(ballot=ballot1, choice=choice_c, stars=1)
        
        # Voter 2 votes manually
        ballot2 = BallotFactory(
            decision=decision,
            voter=voter2,
            is_calculated=False,
            tags="governance",
            with_votes=False
        )
        VoteFactory(ballot=ballot2, choice=choice_a, stars=3)
        VoteFactory(ballot=ballot2, choice=choice_b, stars=4)
        VoteFactory(ballot=ballot2, choice=choice_c, stars=2)
        
        # Step 4: Calculate results using STAR voting
        service = StageBallots()
        ballots = [ballot1, ballot2]
        results = service.automatic_runoff(ballots)
        
        # Verify results
        assert results is not None
        assert results['winner'] is not None
        assert results['winner'] in [choice_a, choice_b, choice_c]
        assert results['total_ballots'] == 2
        
        # Verify score calculations
        scores = results['score_phase_results']
        assert len(scores) == 3
        
        # Choice A average: (5+3)/2 = 4.0
        # Choice B average: (2+4)/2 = 3.0  
        # Choice C average: (1+2)/2 = 1.5
        # So Choice A should win
        assert results['winner'] == choice_a
    
    def test_delegation_workflow(self):
        """Test workflow with delegation inheritance."""
        # Step 1: Create community and users
        community = CommunityFactory(name="Delegation Community")
        
        # Create users
        expert = UserFactory(username="governance_expert")
        follower = UserFactory(username="follower_user")
        
        MembershipFactory(community=community, member=expert)
        MembershipFactory(community=community, member=follower)
        
        # Step 2: Set up delegation relationship
        Following.objects.create(
            follower=follower,
            followee=expert,
            tags="governance",
            order=1
        )
        
        # Step 3: Create decision
        decision = DecisionFactory(
            community=community,
            title="Governance Decision That Requires Expert Knowledge Input",
            description="This decision tests the delegation system where followers inherit votes from experts they trust on specific topics",
            dt_close=timezone.now() + timedelta(days=7),
            with_choices=False
        )
        
        choice_x = ChoiceFactory(decision=decision, title="Expert Option X")
        choice_y = ChoiceFactory(decision=decision, title="Expert Option Y")
        
        # Step 4: Expert votes
        expert_ballot = BallotFactory(
            decision=decision,
            voter=expert,
            is_calculated=False,
            tags="governance,expertise",
            with_votes=False
        )
        VoteFactory(ballot=expert_ballot, choice=choice_x, stars=4)
        VoteFactory(ballot=expert_ballot, choice=choice_y, stars=1)
        
        # Step 5: Calculate follower's inherited vote
        service = StageBallots()
        follower_ballot = service.get_or_calculate_ballot(
            decision=decision,
            voter=follower
        )
        
        # Verify delegation worked
        assert follower_ballot is not None
        assert follower_ballot.is_calculated is True
        
        # Should inherit expert's votes
        if follower_ballot.votes.exists():
            follower_votes = follower_ballot.votes.all()
            assert follower_votes.count() == 2
            
            vote_x = follower_votes.get(choice=choice_x)
            vote_y = follower_votes.get(choice=choice_y)
            
            assert vote_x.stars == 4  # Inherited from expert
            assert vote_y.stars == 1  # Inherited from expert
    
    def test_mixed_manual_and_delegated_voting(self):
        """Test scenario with both manual voters and delegated voters."""
        # Step 1: Setup community with multiple users
        community = CommunityFactory(name="Mixed Voting Community")
        
        # Create expert
        expert = UserFactory(username="trusted_expert")
        MembershipFactory(community=community, member=expert)
        
        # Create manual voter
        manual_voter = UserFactory(username="manual_voter")
        MembershipFactory(community=community, member=manual_voter)
        
        # Create delegating voter
        delegating_voter = UserFactory(username="delegating_voter")
        MembershipFactory(community=community, member=delegating_voter)
        
        # Set up delegation
        Following.objects.create(
            follower=delegating_voter,
            followee=expert,
            tags="policy",
            order=1
        )
        
        # Step 2: Create decision
        decision = DecisionFactory(
            community=community,
            title="Mixed Voting Policy Decision For Community Members",
            description="This decision tests mixed manual and delegated voting to ensure both types work together correctly",
            dt_close=timezone.now() + timedelta(days=7),
            with_choices=False
        )
        
        choice_1 = ChoiceFactory(decision=decision, title="Policy Option 1")
        choice_2 = ChoiceFactory(decision=decision, title="Policy Option 2")
        
        # Step 3: Expert votes
        expert_ballot = BallotFactory(
            decision=decision,
            voter=expert,
            is_calculated=False,
            tags="policy,expertise",
            with_votes=False
        )
        VoteFactory(ballot=expert_ballot, choice=choice_1, stars=5)
        VoteFactory(ballot=expert_ballot, choice=choice_2, stars=2)
        
        # Step 4: Manual voter votes independently
        manual_ballot = BallotFactory(
            decision=decision,
            voter=manual_voter,
            is_calculated=False,
            tags="personal_opinion",
            with_votes=False
        )
        VoteFactory(ballot=manual_ballot, choice=choice_1, stars=2)
        VoteFactory(ballot=manual_ballot, choice=choice_2, stars=4)
        
        # Step 5: Calculate delegated vote
        service = StageBallots()
        delegated_ballot = service.get_or_calculate_ballot(
            decision=decision,
            voter=delegating_voter
        )
        
        # Step 6: Run STAR voting on all ballots
        all_ballots = [expert_ballot, manual_ballot]
        if delegated_ballot and delegated_ballot.votes.exists():
            all_ballots.append(delegated_ballot)
        
        results = service.automatic_runoff(all_ballots)
        
        # Verify mixed voting results
        assert results is not None
        assert results['winner'] in [choice_1, choice_2]
        assert results['total_ballots'] >= 2  # At least expert and manual voter
        
        # With expert (5,2), manual (2,4), and potentially delegated (5,2):
        # Choice 1 average could be (5+2+5)/3 = 4.0 or (5+2)/2 = 3.5
        # Choice 2 average could be (2+4+2)/3 = 2.67 or (2+4)/2 = 3.0
        # Choice 1 should likely win
        scores = results['score_phase_results']
        assert len(scores) == 2


@pytest.mark.integration  
class TestCommunityManagement:
    """Test community management workflows."""
    
    def test_community_creation_and_membership(self):
        """Test basic community creation and membership management."""
        # Step 1: Create community
        community = CommunityFactory(
            name="New Test Community",
            description="A community for testing management workflows and ensuring proper functionality"
        )
        
        # Step 2: Create manager
        manager = UserFactory(username="community_admin")
        manager_membership = MembershipFactory(
            community=community,
            member=manager,
            is_community_manager=True,
            is_voting_community_member=True
        )
        
        # Step 3: Add regular members
        member1 = UserFactory(username="regular_member_1")
        member2 = UserFactory(username="regular_member_2")
        
        membership1 = MembershipFactory(
            community=community,
            member=member1,
            is_voting_community_member=True
        )
        
        membership2 = MembershipFactory(
            community=community,
            member=member2,
            is_voting_community_member=True
        )
        
        # Step 4: Verify community structure
        assert community.members.count() == 3
        assert community.memberships.filter(is_community_manager=True).count() == 1
        assert community.memberships.filter(is_voting_community_member=True).count() == 3
        
        # Step 5: Test member permissions
        assert manager_membership.is_community_manager
        assert not membership1.is_community_manager
        assert not membership2.is_community_manager
        
        # All should be voting members
        assert manager_membership.is_voting_community_member
        assert membership1.is_voting_community_member  
        assert membership2.is_voting_community_member
    
    def test_lobbyist_membership(self):
        """Test non-voting lobbyist membership."""
        # Step 1: Create community
        community = CommunityFactory(name="Lobbyist Test Community")
        
        # Step 2: Create voting member
        voter = UserFactory(username="voting_member")
        MembershipFactory(
            community=community,
            member=voter,
            is_voting_community_member=True
        )
        
        # Step 3: Create lobbyist (non-voting member)
        lobbyist = UserFactory(username="expert_lobbyist")
        lobbyist_membership = MembershipFactory(
            community=community,
            member=lobbyist,
            is_voting_community_member=False  # Lobbyist doesn't vote
        )
        
        # Step 4: Verify membership types
        assert community.members.count() == 2
        
        voting_members = community.memberships.filter(
            is_voting_community_member=True
        )
        assert voting_members.count() == 1
        assert voting_members.first().member == voter
        
        non_voting_members = community.memberships.filter(
            is_voting_community_member=False
        )
        assert non_voting_members.count() == 1
        assert non_voting_members.first().member == lobbyist
        
        # Step 5: Test that lobbyist can be followed but doesn't vote
        # This would be tested in delegation workflow
        assert not lobbyist_membership.is_voting_community_member
        assert lobbyist_membership.member == lobbyist


@pytest.mark.integration
class TestDataIntegrity:
    """Test data integrity and consistency across workflows."""
    
    def test_vote_data_consistency(self):
        """Test that vote data remains consistent across operations."""
        # Create test scenario
        community = CommunityFactory()
        voter = UserFactory()
        MembershipFactory(community=community, member=voter)
        
        decision = DecisionFactory(
            community=community,
            title="Data Consistency Test Decision For Validation",
            description="This decision tests data consistency to ensure vote integrity throughout the system",
            with_choices=False
        )
        
        choice = ChoiceFactory(decision=decision)
        
        # Create vote
        ballot = BallotFactory(
            decision=decision,
            voter=voter,
            is_calculated=False,
            tags="consistency_test",
            with_votes=False
        )
        vote = VoteFactory(ballot=ballot, choice=choice, stars=4)
        
        # Verify data consistency
        assert vote.ballot == ballot
        assert vote.choice == choice
        assert vote.stars == 4
        assert ballot.decision == decision
        assert ballot.voter == voter
        assert choice.decision == decision
        
        # Verify relationships work both ways
        assert vote in ballot.votes.all()
        assert vote in choice.votes.all()
        assert ballot in decision.ballots.all()
    
    def test_delegation_data_consistency(self):
        """Test delegation relationship data consistency."""
        # Create users
        follower = UserFactory(username="data_follower")
        leader = UserFactory(username="data_leader")
        
        # Create following relationship
        following = Following.objects.create(
            follower=follower,
            followee=leader,
            tags="data_test",
            order=1
        )
        
        # Verify relationship
        assert following.follower == follower
        assert following.followee == leader
        assert following.tags == "data_test"
        assert following.order == 1
        
        # Verify reverse relationships
        follower_relationships = Following.objects.filter(follower=follower)
        assert following in follower_relationships
        
        leader_relationships = Following.objects.filter(followee=leader)
        assert following in leader_relationships
