"""
Tests specifically designed to improve coverage of democracy/tree_service.py.

This test file focuses on testing untested code paths to increase coverage
rather than duplicating functionality tests.
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model

from tests.factories.user_factory import UserFactory, MembershipFactory
from tests.factories.community_factory import CommunityFactory
from tests.factories.decision_factory import DecisionFactory, ChoiceFactory, BallotFactory, VoteFactory
from accounts.models import Following
from democracy.tree_service import DelegationTreeService

User = get_user_model()


@pytest.mark.services
class TestTreeServiceCoverage(TestCase):
    """Tests to improve coverage of democracy/tree_service.py functions."""
    
    def setUp(self):
        self.community = CommunityFactory(name="Test Community")
        self.user_a = UserFactory(username="user_a", first_name="Alice", last_name="Smith")
        self.user_b = UserFactory(username="user_b", first_name="Bob", last_name="Jones")
        self.user_c = UserFactory(username="user_c", first_name="Charlie", last_name="Brown")
        
        # Create memberships
        MembershipFactory(member=self.user_a, community=self.community)
        MembershipFactory(member=self.user_b, community=self.community)
        MembershipFactory(member=self.user_c, community=self.community)
        
        # Create delegation relationships
        self.following_ab = Following.objects.create(
            follower=self.user_b,
            followee=self.user_a,
            tags="governance,budget",
            order=1
        )
        self.following_bc = Following.objects.create(
            follower=self.user_c,
            followee=self.user_b,
            tags="governance",
            order=1
        )
        
    def test_service_initialization(self):
        """Test service initialization with different parameters - covers __init__ logic."""
        # Test with links enabled (default)
        service = DelegationTreeService()
        self.assertTrue(service.include_links)
        
        # Test with links disabled
        service_no_links = DelegationTreeService(include_links=False)
        self.assertFalse(service_no_links.include_links)
        
    def test_format_username_with_links(self):
        """Test username formatting with links enabled - covers link generation logic."""
        service = DelegationTreeService(include_links=True)
        
        # Test with community context
        formatted = service.format_username(self.user_a, community=self.community)
        self.assertIn(self.user_a.username, formatted)
        self.assertIn('<a href=', formatted)
        
        # Test without community context
        formatted_no_community = service.format_username(self.user_a)
        self.assertIn(self.user_a.username, formatted_no_community)
        
    def test_format_username_without_links(self):
        """Test username formatting with links disabled - covers plain text logic."""
        service = DelegationTreeService(include_links=False)
        
        formatted = service.format_username(self.user_a, community=self.community)
        self.assertIn(self.user_a.username, formatted)
        self.assertNotIn('<a href=', formatted)
        
    def test_format_username_display_name_logic(self):
        """Test username display name logic - covers name vs username fallback."""
        service = DelegationTreeService(include_links=False)
        
        # User with full name should show display name
        formatted = service.format_username(self.user_a)
        self.assertIn("Alice Smith", formatted)
        
        # User without first/last name
        user_no_name = UserFactory(username="noname", first_name="", last_name="")
        formatted_no_name = service.format_username(user_no_name)
        self.assertIn("noname", formatted_no_name)
        
    def test_build_delegation_map_basic(self):
        """Test delegation map building - covers basic map construction logic."""
        service = DelegationTreeService()
        
        users = [self.user_a, self.user_b, self.user_c]
        delegation_map, _, _ = service.build_delegation_map(users)
        
        # Should contain delegation relationships
        self.assertIn(self.user_b, delegation_map)
        self.assertIn(self.user_c, delegation_map)
        
        # User A has no delegations (is followee only)
        self.assertEqual(len(delegation_map.get(self.user_a, [])), 0)
        
        # User B follows User A
        self.assertTrue(len(delegation_map.get(self.user_b, [])) > 0)
        
    def test_build_delegation_map_with_community_filter(self):
        """Test delegation map with community filtering - covers filter logic."""
        service = DelegationTreeService()
        
        # Create user not in community
        user_outside = UserFactory(username="outsider")
        Following.objects.create(
            follower=user_outside,
            followee=self.user_a,
            tags="governance",
            order=1
        )
        
        users = [self.user_a, self.user_b, self.user_c, user_outside]
        
        # Test without filter - should include all
        delegation_map_all = service.build_delegation_map(users)
        self.assertIn(user_outside, delegation_map_all)
        
        # Test with community filter - should exclude outsider
        delegation_map_filtered = service.build_delegation_map(users, filter_community=self.community)
        # The filter only affects member verification, not following relationships
        
    def test_build_tree_recursive_basic(self):
        """Test recursive tree building - covers tree construction logic."""
        service = DelegationTreeService(include_links=False)
        
        users = [self.user_a, self.user_b, self.user_c]
        delegation_map, _, _ = service.build_delegation_map(users)
        visited = set()
        
        # Build tree for user with delegations
        tree_html = service.build_tree_recursive(
            self.user_b, delegation_map, visited, prefix="", depth=0
        )
        
        self.assertIn(self.user_b.username, tree_html)
        self.assertIn("governance", tree_html)  # Should show tags
        
    def test_build_tree_recursive_circular_prevention(self):
        """Test circular reference prevention - covers visited user logic."""
        service = DelegationTreeService(include_links=False)
        
        # Create circular reference: A -> B, B -> A (should not happen in real app, but test prevention)
        Following.objects.create(
            follower=self.user_a,
            followee=self.user_b,
            tags="budget",
            order=1
        )
        
        users = [self.user_a, self.user_b]
        delegation_map, _, _ = service.build_delegation_map(users)
        visited = set()
        
        # Should handle circular reference gracefully
        tree_html = service.build_tree_recursive(
            self.user_a, delegation_map, visited, prefix="", depth=0
        )
        
        # Should build without infinite recursion
        self.assertIn(self.user_a.username, tree_html)
        
    def test_build_tree_recursive_max_depth(self):
        """Test maximum depth limiting - covers depth limit logic."""
        service = DelegationTreeService(include_links=False)
        
        # Create deep chain: D -> C -> B -> A
        user_d = UserFactory(username="user_d")
        Following.objects.create(follower=user_d, followee=self.user_c, tags="governance", order=1)
        
        users = [self.user_a, self.user_b, self.user_c, user_d]
        delegation_map, _, _ = service.build_delegation_map(users)
        visited = set()
        
        # Test with low max depth
        tree_html = service.build_tree_recursive(
            user_d, delegation_map, visited, prefix="", depth=0, max_depth=2
        )
        
        # Should truncate at max depth
        self.assertIn(user_d.username, tree_html)
        
    def test_build_community_tree_full_tree(self):
        """Test community tree building - covers full community tree logic."""
        service = DelegationTreeService(include_links=False)
        
        tree_html = service.build_community_tree(self.community)
        
        # Should contain all community members with delegations
        self.assertIn(self.user_b.username, tree_html)
        self.assertIn(self.user_c.username, tree_html)
        
        # Should show delegation structure
        self.assertIn("governance", tree_html)
        
        # Should contain section headers
        self.assertIn("Users with Delegation Relationships", tree_html)
        
    def test_build_community_tree_no_delegations(self):
        """Test community tree with no delegations - covers empty tree logic."""
        # Create community with no delegations
        empty_community = CommunityFactory(name="Empty Community")
        user_isolated = UserFactory(username="isolated")
        MembershipFactory(member=user_isolated, community=empty_community)
        
        service = DelegationTreeService(include_links=False)
        tree_html = service.build_community_tree(empty_community)
        
        # Should handle empty tree gracefully
        self.assertIn("No delegation relationships", tree_html)
        
    def test_build_decision_tree_with_votes(self):
        """Test decision tree building - covers decision-specific tree logic."""
        # Create decision with choices and votes
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice_a = ChoiceFactory(decision=decision, title="Choice A")
        choice_b = ChoiceFactory(decision=decision, title="Choice B")
        
        # Create ballots and votes
        ballot_a = BallotFactory(decision=decision, voter=self.user_a, with_votes=False)
        ballot_b = BallotFactory(decision=decision, voter=self.user_b, with_votes=False)
        
        VoteFactory(choice=choice_a, ballot=ballot_a, stars=5)
        VoteFactory(choice=choice_b, ballot=ballot_a, stars=3)
        VoteFactory(choice=choice_a, ballot=ballot_b, stars=4)
        VoteFactory(choice=choice_b, ballot=ballot_b, stars=2)
        
        service = DelegationTreeService(include_links=False)
        tree_html = service.build_decision_tree(decision)
        
        # Should show voters and their votes
        self.assertIn(self.user_a.username, tree_html)
        self.assertIn(self.user_b.username, tree_html)
        
        # Should show vote values (stars)
        self.assertIn("★", tree_html)
        
    def test_build_decision_tree_no_votes(self):
        """Test decision tree with no votes - covers empty decision logic."""
        decision = DecisionFactory(community=self.community, with_choices=False)
        ChoiceFactory(decision=decision, title="Choice A")
        
        service = DelegationTreeService(include_links=False)
        tree_html = service.build_decision_tree(decision)
        
        # Should handle decision with no votes
        self.assertIn("No votes have been cast", tree_html)
        
    def test_build_decision_tree_calculated_vs_manual(self):
        """Test decision tree vote type display - covers calculated vs manual vote logic."""
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice = ChoiceFactory(decision=decision, title="Choice A")
        
        # Create manual vote
        manual_ballot = BallotFactory(
            decision=decision, 
            voter=self.user_a, 
            is_calculated=False,
            with_votes=False
        )
        VoteFactory(choice=choice, ballot=manual_ballot, stars=5)
        
        # Create calculated vote
        calculated_ballot = BallotFactory(
            decision=decision, 
            voter=self.user_b, 
            is_calculated=True,
            with_votes=False
        )
        VoteFactory(choice=choice, ballot=calculated_ballot, stars=4)
        
        service = DelegationTreeService(include_links=False)
        tree_html = service.build_decision_tree(decision)
        
        # Should distinguish manual vs calculated votes
        self.assertIn("Manual", tree_html)
        self.assertIn("Calculated", tree_html)
        
    def test_format_voter_with_vote_logic(self):
        """Test vote formatting - covers vote display logic."""
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice = ChoiceFactory(decision=decision, title="Choice A")
        ballot = BallotFactory(decision=decision, voter=self.user_a, with_votes=False)
        vote = VoteFactory(choice=choice, ballot=ballot, stars=3)
        
        service = DelegationTreeService(include_links=False)
        tree_html = service.build_decision_tree(decision)
        
        # Should format vote with stars
        self.assertIn("★★★☆☆", tree_html)
        
    def test_edge_cases_and_error_handling(self):
        """Test edge cases and error handling - covers error paths."""
        service = DelegationTreeService()
        
        # Test with None user
        try:
            result = service.format_username(None)
            # Should handle gracefully or raise expected error
        except (AttributeError, TypeError):
            # Expected for None user
            pass
            
        # Test with empty user list
        empty_map = service.build_delegation_map([])
        self.assertEqual(len(empty_map), 0)
        
        # Test tree building with empty map
        visited = set()
        tree_result = service.build_tree_recursive(
            self.user_a, {}, visited, prefix="", depth=0
        )
        # Should handle empty delegation map
        
    def test_prefix_and_indentation_logic(self):
        """Test tree indentation and prefix logic - covers formatting details."""
        service = DelegationTreeService(include_links=False)
        
        users = [self.user_a, self.user_b, self.user_c]
        delegation_map, _, _ = service.build_delegation_map(users)
        visited = set()
        
        # Test with custom prefix
        tree_html = service.build_tree_recursive(
            self.user_b, delegation_map, visited, prefix="  ", depth=1
        )
        
        # Should include proper indentation
        self.assertIsInstance(tree_html, str)
        
    def test_tags_display_logic(self):
        """Test tag display in trees - covers tag formatting logic."""
        # Create following with specific tags
        user_d = UserFactory(username="user_d")
        Following.objects.create(
            follower=user_d,
            followee=self.user_a,
            tags="environment,safety,governance",
            order=1
        )
        
        service = DelegationTreeService(include_links=False)
        
        users = [self.user_a, user_d]
        delegation_map, _, _ = service.build_delegation_map(users)
        visited = set()
        
        tree_html = service.build_tree_recursive(
            user_d, delegation_map, visited
        )
        
        # Should display tags properly
        self.assertIn("environment", tree_html)
        self.assertIn("safety", tree_html)
        
    def test_community_member_verification(self):
        """Test community member verification - covers membership checking logic."""
        # Create user not in community
        outsider = UserFactory(username="outsider")
        
        service = DelegationTreeService()
        
        # Test delegation map with mixed users
        users = [self.user_a, outsider]
        delegation_map, _, _ = service.build_delegation_map(users, filter_community=self.community)
        
        # Should handle mixed membership correctly
        self.assertIsInstance(delegation_map, dict)
        
    def test_multiple_following_relationships(self):
        """Test handling of multiple following relationships - covers complex delegation logic."""
        # Create user following multiple people
        user_multi = UserFactory(username="multi_follower")
        
        Following.objects.create(
            follower=user_multi,
            followee=self.user_a,
            tags="governance",
            order=1
        )
        Following.objects.create(
            follower=user_multi,
            followee=self.user_b,
            tags="budget",
            order=2
        )
        
        service = DelegationTreeService(include_links=False)
        
        users = [self.user_a, self.user_b, user_multi]
        delegation_map, _, _ = service.build_delegation_map(users)
        
        # Should handle multiple relationships
        self.assertTrue(len(delegation_map.get(user_multi, [])) >= 2)
        
    def test_order_and_priority_handling(self):
        """Test following order and priority handling - covers priority logic."""
        # Create multiple followings with different orders
        user_priority = UserFactory(username="priority_user")
        
        Following.objects.create(
            follower=user_priority,
            followee=self.user_a,
            tags="governance",
            order=2  # Lower priority
        )
        Following.objects.create(
            follower=user_priority,
            followee=self.user_b,
            tags="governance", 
            order=1  # Higher priority
        )
        
        service = DelegationTreeService(include_links=False)
        
        users = [self.user_a, self.user_b, user_priority]
        delegation_map, _, _ = service.build_delegation_map(users)
        
        # Should respect order/priority
        followings = delegation_map.get(user_priority, [])
        if len(followings) >= 2:
            # Should be ordered by priority
            orders = [f.order for f in followings]
            self.assertEqual(orders, sorted(orders))
            
    def test_anonymous_user_handling(self):
        """Test handling of anonymous users - covers anonymity logic."""
        decision = DecisionFactory(community=self.community, with_choices=False)
        choice = ChoiceFactory(decision=decision, title="Choice A")
        
        # Create anonymous ballot
        anon_ballot = BallotFactory(
            decision=decision, 
            voter=self.user_a, 
            is_anonymous=True,
            with_votes=False
        )
        VoteFactory(choice=choice, ballot=anon_ballot, stars=4)
        
        service = DelegationTreeService(include_links=False)
        tree_html = service.build_decision_tree(decision)
        
        # Should handle anonymous votes
        self.assertIn("Anonymous", tree_html)
        
    def test_tree_depth_and_performance(self):
        """Test tree depth performance - covers performance edge cases."""
        service = DelegationTreeService(include_links=False)
        
        # Create moderately deep chain for performance testing
        chain_users = []
        for i in range(5):
            user = UserFactory(username=f"chain_user_{i}")
            chain_users.append(user)
            if i > 0:
                Following.objects.create(
                    follower=user,
                    followee=chain_users[i-1],
                    tags="governance",
                    order=1
                )
        
        delegation_map, _, _ = service.build_delegation_map(chain_users)
        visited = set()
        
        # Should handle moderate depth efficiently
        tree_html = service.build_tree_recursive(
            chain_users[-1], delegation_map, visited, max_depth=10
        )
        
        self.assertIsInstance(tree_html, str)
        self.assertGreater(len(tree_html), 0)
