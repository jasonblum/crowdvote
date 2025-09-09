"""
Tree visualization service for CrowdVote delegation trees.

This module provides unified tree building services for both community-wide
delegation trees and decision-specific participation trees. It ensures
consistent formatting, visual structure, and functionality across the application.
"""

from collections import defaultdict
from django.urls import reverse
from accounts.models import Following


class DelegationTreeService:
    """
    Service class for building delegation trees with consistent formatting.
    
    Provides unified methods for creating ASCII delegation trees that show
    how votes flow through trust networks in CrowdVote's delegative democracy.
    """
    
    def __init__(self, include_links=True):
        """
        Initialize the tree service.
        
        Args:
            include_links (bool): Whether to include HTML links to member profiles
        """
        self.include_links = include_links
    
    def format_username(self, user, community=None):
        """
        Format username with optional link to profile and avatar.
        
        Args:
            user: User object to format
            community: Community object for profile link context
            
        Returns:
            str: Formatted username with avatar (HTML if include_links=True)
        """
        display_name = user.get_display_name() if hasattr(user, 'get_display_name') else user.username
        avatar_html = user.get_avatar_html(20) if hasattr(user, 'get_avatar_html') else ''
        
        if self.include_links and community:
            try:
                profile_url = reverse('accounts:member_profile', args=[community.id, user.id])
                return f'<span class="inline-flex items-center space-x-2">{avatar_html}<a href="{profile_url}" class="text-blue-600 hover:text-blue-800 underline">{display_name}</a></span>'
            except Exception as e:
                return f'<span class="inline-flex items-center space-x-2">{avatar_html}<span>{display_name}</span></span>'
        else:
            return f'<span class="inline-flex items-center space-x-2">{avatar_html}<span>{display_name}</span></span>'
    
    def build_delegation_map(self, users, filter_community=None):
        """
        Build delegation relationships map for given users.
        
        Args:
            users: Queryset or list of users to include
            filter_community: Optional community to filter relationships
            
        Returns:
            tuple: (delegation_map, all_followers, all_followees)
        """
        delegation_map = defaultdict(list)
        all_followers = set()
        all_followees = set()
        
        # Get following relationships for these users
        followings_query = Following.objects.filter(
            follower__in=users,
            followee__in=users
        ).select_related('follower', 'followee')
        
        if filter_community:
            # Only include relationships between community members
            community_members = filter_community.members.all()
            followings_query = followings_query.filter(
                follower__in=community_members,
                followee__in=community_members
            )
        
        for following in followings_query:
            tags_display = following.tags if following.tags else "all topics"
            delegation_map[following.follower].append({
                'followee': following.followee,
                'tags': tags_display,
                'order': following.order
            })
            all_followers.add(following.follower)
            all_followees.add(following.followee)
        
        return delegation_map, all_followers, all_followees
    
    def build_tree_recursive(self, user, delegation_map, visited, prefix="", depth=0, max_depth=6, community=None):
        """
        Recursively build delegation tree structure for a user.
        
        Args:
            user: User to build tree for
            delegation_map: Map of user -> list of delegations
            visited: Set of already visited users (prevents cycles)
            prefix: Current indentation prefix
            depth: Current recursion depth
            max_depth: Maximum depth to prevent infinite recursion
            
        Returns:
            list: List of tree lines
        """
        if depth > max_depth or user in visited:
            return []
        
        visited.add(user)
        lines = []
        
        # Get people this user delegates to, sorted by priority
        delegations = delegation_map.get(user, [])
        delegations.sort(key=lambda x: x['order'])
        
        for i, delegation_info in enumerate(delegations):
            followee = delegation_info['followee']
            tags = delegation_info['tags']
            order = delegation_info['order']
            is_last_delegation = i == len(delegations) - 1
            
            # Create connector for this delegation
            connector = "└─" if is_last_delegation else "├─"
            
            # Add the tag first
            lines.append(f"{prefix}{connector} 📋 {tags} (priority: {order})")
            
            # Add the followee 
            followee_prefix = prefix + ("    " if is_last_delegation else "│   ")
            lines.append(f"{followee_prefix}└─ {self.format_username(followee, community)}")
            
            # Recursively add who the followee delegates to
            if followee in delegation_map:
                sub_visited = visited.copy()
                sub_prefix = followee_prefix + "    "
                sub_lines = self.build_tree_recursive(
                    followee, delegation_map, sub_visited, sub_prefix, depth + 1, max_depth, community
                )
                lines.extend(sub_lines)
        
        visited.remove(user)
        return lines
    
    def build_community_tree(self, community):
        """
        Build delegation tree for a community showing all delegation relationships.
        
        Args:
            community: Community object to build tree for
            
        Returns:
            dict: Tree data with text, statistics, and metadata
        """
        community_members = community.members.all()
        delegation_map, all_followers, all_followees = self.build_delegation_map(
            community_members, filter_community=community
        )
        
        if not delegation_map:
            return {
                'tree_text': "No delegation relationships found in this community.",
                'has_relationships': False,
                'stats': {'total_relationships': 0, 'unique_followers': 0, 'unique_followees': 0}
            }
        
        # Build ASCII tree
        tree_lines = []
        tree_lines.append("🌳 Hierarchical Delegation Tree")
        tree_lines.append("=" * 50)
        tree_lines.append("")
        tree_lines.append("👥 DELEGATION CHAINS (Who delegates to whom)")
        tree_lines.append("━" * 30)
        tree_lines.append("")
        
        # Show all users who delegate, sorted alphabetically
        all_shown_users = set()
        
        for user in sorted(all_followers, key=lambda u: u.username):
            if user in all_shown_users:
                continue
                
            visited = set()
            tree_lines.append(f"👤 {self.format_username(user, community)}")
            
            # Get the delegation tree for this user
            sub_lines = self.build_tree_recursive(user, delegation_map, visited, "", 0, 6, community)
            if sub_lines:  # Only show if they actually have delegations
                tree_lines.extend(sub_lines)
            tree_lines.append("")
            
            # Track users we've shown
            all_shown_users.add(user)
            all_shown_users.update(visited)
        
        # Add statistics
        tree_lines.append("📊 Network Statistics:")
        tree_lines.append(f"   • Total delegation relationships: {sum(len(dels) for dels in delegation_map.values())}")
        tree_lines.append(f"   • People being followed: {len(all_followees)}")
        tree_lines.append(f"   • People following others: {len(all_followers)}")
        tree_lines.append(f"   • Network density: {len(all_followers)}/{len(community_members)} members involved")
        
        return {
            'tree_text': '\n'.join(tree_lines),
            'has_relationships': True,
            'stats': {
                'total_relationships': sum(len(dels) for dels in delegation_map.values()),
                'unique_followers': len(all_followers),
                'unique_followees': len(all_followees)
            }
        }
    
    def build_decision_tree(self, decision):
        """
        Build delegation tree for a decision showing vote values and participation.
        
        Args:
            decision: Decision object to build tree for
            
        Returns:
            dict: Tree data with text, statistics, and vote information
        """
        from .models import Ballot
        
        # Get all ballots for this decision
        ballots = Ballot.objects.filter(decision=decision).select_related('voter').prefetch_related('votes')
        
        if not ballots.exists():
            return {
                'tree_text': "No votes cast for this decision yet.",
                'has_relationships': False,
                'stats': {'total_participants': 0, 'manual_voters': 0, 'calculated_voters': 0}
            }
        
        # Build voter data and delegation maps
        participating_voters = set(ballot.voter for ballot in ballots)
        delegation_map, all_followers, all_followees = self.build_delegation_map(
            participating_voters, filter_community=decision.community
        )
        
        # Get vote data for each participant
        voter_data = {}
        for ballot in ballots:
            voter = ballot.voter
            votes = ballot.votes.all()
            if votes:
                # Calculate average stars for this voter
                total_stars = sum(vote.stars for vote in votes)
                avg_stars = total_stars / len(votes)
                star_display = "★" * int(avg_stars) + "☆" * (5 - int(avg_stars))
            else:
                star_display = "☆☆☆☆☆"
                avg_stars = 0
            
            voter_data[voter] = {
                'ballot': ballot,
                'star_display': star_display,
                'avg_stars': avg_stars,
                'vote_type': 'Manual Vote' if not ballot.is_calculated else 'Calculated',
                'tags': ballot.tags if ballot.tags else 'no tags'
            }
        
        def format_voter_with_vote(voter):
            """Format voter with vote information and optional link"""
            data = voter_data.get(voter, {})
            stars = data.get('star_display', '☆☆☆☆☆')
            vote_type = data.get('vote_type', 'Unknown')
            tags = data.get('tags', 'no tags')
            
            # Handle anonymous voters
            if hasattr(voter, 'is_anonymous') and getattr(voter, 'is_anonymous', False):
                username = f"Anonymous Voter #{str(voter.id)[:8]}"
                return f"{username} ({vote_type}: {stars}) [Tags: {tags}]"
            
            # Format username with optional link and avatar
            username_html = self.format_username(voter, decision.community)
            return f"{username_html} ({vote_type}: {stars}) [Tags: {tags}]"
        
        # Build ASCII tree
        tree_lines = []
        tree_lines.append("🗳️ DECISION PARTICIPATION TREE")
        tree_lines.append("═" * 50)
        tree_lines.append("")
        tree_lines.append("👥 DELEGATION CHAINS (Who delegates to whom)")
        tree_lines.append("━" * 30)
        tree_lines.append("")
        
        # Show participating voters who delegate
        all_shown_users = set()
        participating_delegators = [user for user in participating_voters if user in all_followers]
        
        for user in sorted(participating_delegators, key=lambda u: u.username):
            if user in all_shown_users:
                continue
                
            visited = set()
            tree_lines.append(f"👤 {format_voter_with_vote(user)}")
            
            # Get the delegation tree for this user
            sub_lines = self.build_tree_recursive(user, delegation_map, visited, "", 0, 6, decision.community)
            if sub_lines:
                tree_lines.extend(sub_lines)
            tree_lines.append("")
            
            all_shown_users.add(user)
            all_shown_users.update(visited)
        
        # Show participating voters who don't delegate (direct voters)
        non_delegators = [user for user in participating_voters if user not in all_followers]
        if non_delegators:
            tree_lines.append("📊 DIRECT VOTERS (No delegation)")
            tree_lines.append("━" * 30)
            tree_lines.append("")
            
            for user in sorted(non_delegators, key=lambda u: u.username):
                tree_lines.append(f"👤 {format_voter_with_vote(user)}")
            tree_lines.append("")
        
        # Add statistics
        manual_count = sum(1 for ballot in ballots if not ballot.is_calculated)
        calculated_count = sum(1 for ballot in ballots if ballot.is_calculated)
        
        tree_lines.append("📊 Participation Statistics:")
        tree_lines.append(f"   • Total participants: {len(participating_voters)}")
        tree_lines.append(f"   • Manual voters: {manual_count}")
        tree_lines.append(f"   • Calculated voters: {calculated_count}")
        tree_lines.append(f"   • Delegation relationships: {sum(len(dels) for dels in delegation_map.values())}")
        
        return {
            'tree_text': '\n'.join(tree_lines),
            'has_relationships': len(delegation_map) > 0,
            'stats': {
                'total_participants': len(participating_voters),
                'manual_voters': manual_count,
                'calculated_voters': calculated_count,
                'delegation_chains': sum(len(dels) for dels in delegation_map.values())
            }
        }
