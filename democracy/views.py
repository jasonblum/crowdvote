"""
Views for the democracy app.

This module contains views for community management, decision making,
and voting interfaces.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from collections import defaultdict
import threading
import logging

from .models import Community, Decision, Membership, Ballot, Choice, Vote
from democracy.models import Following
from .signals import recalculate_community_decisions_async
from .utils import generate_username_hash

User = get_user_model()
logger = logging.getLogger(__name__)


def build_network_data(community):
    """
    Build network visualization data for D3.js showing delegation relationships.
    
    Creates a network graph showing how members follow each other for vote delegation.
    Anonymous members will display as "Anonymous" in the visualization to preserve privacy.
    Public members will display with their username and Jdenticon avatar.
    
    Returns a dictionary with:
    - nodes: List of node objects (memberships) with id, username, display_name, is_anonymous, user_id
    - links: List of link objects (following relationships) with source, target, tags
    - follower_counts: Dict mapping membership IDs to follower counts (for node colors)
    
    Args:
        community: Community object to build network data for
    
    Returns:
        dict: Network data structure for D3.js visualization with JSON-serialized values
    """
    import json
    from collections import defaultdict
    
    # Get all memberships for this community
    all_memberships = Membership.objects.filter(
        community=community
    ).select_related('member')
    
    # Get all following relationships in this community
    followings = Following.objects.filter(
        follower__community=community,
        followee__community=community
    ).select_related('follower__member', 'followee__member')
    
    # Build nodes array
    nodes = []
    for membership in all_memberships:
        display_name = membership.member.get_full_name() or membership.member.username
        nodes.append({
            'id': str(membership.id),
            'username': membership.member.username if not membership.is_anonymous else 'Anonymous',
            'display_name': display_name if not membership.is_anonymous else 'Anonymous',
            'is_anonymous': membership.is_anonymous,
            'user_id': str(membership.member.id),  # For Jdenticon avatar generation
        })
    
    # Build links array
    links = []
    for following in followings:
        # Parse tags - tags field is a comma-separated string
        tags = []
        if following.tags:
            tags = [tag.strip() for tag in following.tags.split(',') if tag.strip()]
        
        links.append({
            'source': str(following.follower.id),
            'target': str(following.followee.id),
            'tags': tags,
        })
    
    # Calculate follower counts for each membership
    follower_counts = defaultdict(int)
    for link in links:
        follower_counts[link['target']] += 1
    
    # Convert defaultdict to regular dict for JSON serialization
    follower_counts = dict(follower_counts)
    
    # Convert to JSON for safe template rendering
    return {
        'nodes': json.dumps(nodes),
        'links': json.dumps(links),
        'follower_counts': json.dumps(follower_counts),
    }


def build_decision_delegation_tree(decision, include_links=True):
    """
    Build delegation tree for a specific decision (legacy function).
    
    This function is maintained for backward compatibility.
    New code should use DelegationTreeService.build_decision_tree().
    """
    from .tree_service import DelegationTreeService
    
    tree_service = DelegationTreeService(include_links=include_links)
    return tree_service.build_decision_tree(decision)


def build_decision_delegation_tree_old(decision, include_links=True):
    """
    Build an ASCII delegation tree for a specific decision showing vote inheritance.
    
    Shows delegation flow: Follower → Tag → Followee with vote values and stars
    Only includes members who voted or whose votes were calculated for this decision.
    
    Args:
        decision: Decision object to build tree for
        include_links: Whether to include HTML links to member profiles (default True)
    
    Returns a dictionary with:
    - 'tree_text': ASCII representation of the decision delegation tree
    - 'has_relationships': Boolean indicating if there are any relationships to show
    - 'stats': Dictionary with counts of relationships and participation
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
    
    # Build maps of voters and their delegation relationships
    participating_voters = set(ballot.voter for ballot in ballots)
    delegation_map = defaultdict(list)
    all_followers = set()
    all_followees = set()
    
    # Get following relationships only for participating voters
    followings = Following.objects.filter(
        follower__in=participating_voters,
        followee__in=participating_voters
    ).select_related('follower', 'followee')
    
    for following in followings:
        tags_display = following.tags if following.tags else "all topics"
        delegation_map[following.follower].append({
            'followee': following.followee,
            'tags': tags_display,
            'order': following.order
        })
        all_followers.add(following.follower)
        all_followees.add(following.followee)
    
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
        
        # Format username with optional link
        if include_links:
            from django.urls import reverse
            try:
                profile_url = reverse('accounts:member_profile', args=[voter.username])
                username_html = f'<a href="{profile_url}" class="text-blue-600 hover:text-blue-800 underline">{voter.username}</a>'
            except:
                username_html = voter.username
        else:
            username_html = voter.username
            
        return f"{username_html} ({vote_type}: {stars}) [Tags: {tags}]"
    
    def build_decision_tree_recursive(user, visited, prefix="", depth=0, max_depth=6):
        """Recursively build decision delegation tree structure"""
        if depth > max_depth or user in visited or user not in participating_voters:
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
            
            # Add the followee with vote information
            followee_prefix = prefix + ("    " if is_last_delegation else "│   ")
            lines.append(f"{followee_prefix}└─ {format_voter_with_vote(followee)}")
            
            # Recursively add who the followee delegates to
            if followee in delegation_map and followee in participating_voters:
                sub_visited = visited.copy()
                sub_prefix = followee_prefix + "    "
                sub_lines = build_decision_tree_recursive(followee, sub_visited, sub_prefix, depth + 1, max_depth)
                lines.extend(sub_lines)
        
        visited.remove(user)
        return lines
    
    # Build ASCII tree
    tree_lines = []
    tree_lines.append("🗳️ DECISION PARTICIPATION TREE")
    tree_lines.append("═" * 50)
    tree_lines.append("")
    tree_lines.append("👥 DELEGATION CHAINS (Who delegates to whom)")
    tree_lines.append("━" * 30)
    tree_lines.append("")
    
    # Show all participating voters who delegate, sorted alphabetically
    all_shown_users = set()
    participating_delegators = [user for user in participating_voters if user in all_followers]
    
    for user in sorted(participating_delegators, key=lambda u: u.username):
        if user in all_shown_users:
            continue
            
        visited = set()
        tree_lines.append(f"👤 {format_voter_with_vote(user)}")
        
        # Get the delegation tree for this user
        sub_lines = build_decision_tree_recursive(user, visited, "", 0)
        if sub_lines:  # Only show if they actually have delegations
            tree_lines.extend(sub_lines)
        tree_lines.append("")
        
        # Track users we've shown
        all_shown_users.add(user)
        all_shown_users.update(visited)
    
    # Show participating voters who don't delegate (manual voters only)
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
    tree_lines.append(f"   • Delegation relationships: {len(followings)}")
    
    return {
        'tree_text': '\n'.join(tree_lines),
        'has_relationships': len(followings) > 0,
        'stats': {
            'total_participants': len(participating_voters),
            'manual_voters': manual_count,
            'calculated_voters': calculated_count,
            'delegation_chains': len(followings)
        }
    }


def build_influence_tree(community, include_links=True):
    """
    Build delegation tree for a community (legacy function).
    
    This function is maintained for backward compatibility.
    New code should use DelegationTreeService.build_community_tree().
    """
    from .tree_service import DelegationTreeService
    
    tree_service = DelegationTreeService(include_links=include_links)
    return tree_service.build_community_tree(community)


def build_influence_tree_old(community, include_links=True):
    """
    Build an ASCII delegation tree showing hierarchical delegation chains.
    
    Shows delegation flow: Follower → Tag → Followee (who they delegate to)
    
    Args:
        community: Community object to build tree for
        include_links: Whether to include HTML links to member profiles (default True)
    
    Returns a dictionary with:
    - 'tree_text': ASCII representation of the hierarchical delegation tree
    - 'has_relationships': Boolean indicating if there are any relationships to show
    - 'stats': Dictionary with counts of relationships
    """
    # Get all following relationships for community members
    community_members = community.members.all()
    
    # Get all following relationships where both users are in the community
    followings = Following.objects.filter(
        follower__in=community_members,
        followee__in=community_members
    ).select_related('follower', 'followee').order_by('follower__username', 'order')
    
    if not followings.exists():
        return {
            'tree_text': "No delegation relationships found in this community.",
            'has_relationships': False,
            'stats': {'total_relationships': 0, 'unique_followers': 0, 'unique_followees': 0}
        }
    
    # Build delegation map: user -> list of people they follow (delegate to)
    delegation_map = defaultdict(list)
    all_followers = set()
    all_followees = set()
    
    for following in followings:
        tags_display = following.tags if following.tags else "all topics"
        delegation_map[following.follower].append({
            'followee': following.followee,
            'tags': tags_display,
            'order': following.order
        })
        all_followers.add(following.follower)
        all_followees.add(following.followee)
    
    # Find root delegates (people who delegate to others, starting with those who delegate most)
    # These are the "leaf voters" - people who start delegation chains
    root_candidates = sorted([user for user in all_followers], 
                            key=lambda u: len(delegation_map.get(u, [])), 
                            reverse=True)[:5]  # Top 5 most active delegators
    
    def format_username(user):
        """Format username with optional link to profile"""
        if include_links:
            from django.urls import reverse
            try:
                profile_url = reverse('accounts:member_profile', args=[user.username])
                return f'<a href="{profile_url}" class="text-blue-600 hover:text-blue-800 underline">{user.username}</a>'
            except:
                return user.username
        else:
            return user.username
    
    def build_delegation_tree_recursive(user, visited, prefix="", depth=0, max_depth=6):
        """Recursively build delegation tree structure for a user"""
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
            lines.append(f"{followee_prefix}└─ {format_username(followee)}")
            
            # Recursively add who the followee delegates to, but only if they have delegations
            if followee in delegation_map:
                sub_visited = visited.copy()
                # For sub-delegations, continue the tree structure
                sub_prefix = followee_prefix + "    "
                sub_lines = build_delegation_tree_recursive(followee, sub_visited, sub_prefix, depth + 1, max_depth)
                lines.extend(sub_lines)
        
        visited.remove(user)
        return lines
    
    # Build ASCII tree
    tree_lines = []
    tree_lines.append("🌳 Hierarchical Delegation Tree")
    tree_lines.append("=" * 50)
    tree_lines.append("")
    tree_lines.append("👥 DELEGATION CHAINS (Who delegates to whom)")
    tree_lines.append("━" * 30)
    tree_lines.append("")
    
    # Build tree for all users who delegate to others, sorted alphabetically for consistency
    all_shown_users = set()
    
    # Show all users who have delegations, sorted alphabetically
    for user in sorted(all_followers, key=lambda u: u.username):
        if user in all_shown_users:
            continue
            
        visited = set()
        tree_lines.append(f"👤 {format_username(user)}")
        
        # Get the delegation tree for this user (start with empty prefix)
        sub_lines = build_delegation_tree_recursive(user, visited, "", 0)
        if sub_lines:  # Only show if they actually have delegations
            tree_lines.extend(sub_lines)
        tree_lines.append("")
        
        # Track users we've shown
        all_shown_users.add(user)
        all_shown_users.update(visited)
    
    # Add statistics
    tree_lines.append("📊 Network Statistics:")
    tree_lines.append(f"   • Total delegation relationships: {len(followings)}")
    tree_lines.append(f"   • People being followed: {len(all_followees)}")
    tree_lines.append(f"   • People following others: {len(all_followers)}")
    tree_lines.append(f"   • Maximum observed depth: {len(root_candidates)} root nodes")
    tree_lines.append(f"   • Network density: {len(followings)}/{len(community_members)} members involved")
    
    return {
        'tree_text': '\n'.join(tree_lines),
        'has_relationships': True,
        'stats': {
            'total_relationships': len(followings),
            'unique_followers': len(all_followers),
            'unique_followees': len(all_followees)
        }
    }


def community_detail(request, community_id):
    """
    Community detail page showing members, decisions, and community information.
    
    This page displays:
    - Community description and statistics
    - Complete member list with roles (filterable)
    - Recent decisions and their outcomes
    - Application status for current user
    - Join/Leave community actions
    
    Args:
        request: Django request object
        community_id: UUID of the community to display
    """
    community = get_object_or_404(Community, id=community_id)
    
    # Get user's relationship to this community
    user_membership = None
    user_application = None
    
    if request.user.is_authenticated:
        try:
            user_membership = Membership.objects.get(
                community=community,
                member=request.user
            )
        except Membership.DoesNotExist:
            pass
        
        # Check for pending applications
        if not user_membership:
            from security.models import CommunityApplication
            user_application = CommunityApplication.objects.filter(
                user=request.user,
                community=community
            ).first()
    
    # Get member filter from query params
    role_filter = request.GET.get('role', 'all')
    search_query = request.GET.get('search', '').strip()
    
    # Get all memberships for this community
    memberships = Membership.objects.filter(community=community).select_related('member')
    
    # Apply role filter
    if role_filter == 'managers':
        memberships = memberships.filter(is_community_manager=True)
    elif role_filter == 'voters':
        memberships = memberships.filter(is_voting_community_member=True)
    elif role_filter == 'lobbyists':
        memberships = memberships.filter(is_voting_community_member=False)
    
    # Apply search filter
    if search_query:
        memberships = memberships.filter(
            Q(member__username__icontains=search_query) |
            Q(member__first_name__icontains=search_query) |
            Q(member__last_name__icontains=search_query)
        )
    
    # Order by role (managers first, then by username)
    memberships = memberships.order_by(
        '-is_community_manager',
        '-is_voting_community_member', 
        'member__username'
    )
    
    # Get all decisions for this community (if user is a member)
    decisions = []
    if user_membership:
        from django.db.models import Count
        decisions = Decision.objects.filter(community=community).select_related('community')
        
        # Filter based on user role - regular members can't see drafts
        if not user_membership.is_community_manager:
            decisions = decisions.exclude(dt_close__isnull=True)
        
        # Annotate with vote counts
        decisions = decisions.annotate(
            total_votes=Count('ballots', distinct=True),
            total_choices=Count('choices', distinct=True)
        )
        
        # Order by close date (active first, then most recent)
        decisions = decisions.order_by('-dt_close')
        
        # Add status information
        now = timezone.now()
        for decision in decisions:
            if decision.dt_close is None:
                decision.status = 'draft'
            elif decision.dt_close > now:
                decision.status = 'active'
            else:
                decision.status = 'closed'
    
    # Calculate community statistics
    total_members = community.members.count()
    voting_members = community.get_voting_members().count()
    manager_count = community.get_managers().count()
    lobbyist_count = total_members - voting_members
    
    # Build network visualization data
    network_data = build_network_data(community)
    
    # Get current timestamp for network visualization
    from django.utils.formats import date_format
    network_timestamp = date_format(timezone.now(), 'F j, Y @ g:i A T')
    
    # Get follow status for current user (for follow buttons)
    following_status = {}
    if request.user.is_authenticated and user_membership:
        from democracy.models import Following
        user_followings = Following.objects.filter(
            follower=user_membership,
            followee__in=memberships
        ).select_related('followee')
        following_status = {f.followee.id: f for f in user_followings}
    
    context = {
        'community': community,
        'user_membership': user_membership,
        'user_application': user_application,
        'memberships': memberships,
        'decisions': decisions,
        'role_filter': role_filter,
        'search_query': search_query,
        'following_status': following_status,
        'network_data': network_data,
        'network_timestamp': network_timestamp,
        'stats': {
            'total_members': total_members,
            'voting_members': voting_members,
            'lobbyists': lobbyist_count,
            'managers': manager_count,
        }
    }
    
    return render(request, 'democracy/community_detail.html', context)


@login_required
def community_manage(request, community_id):
    """
    Community management dashboard for community managers.
    
    Allows community managers to:
    - Edit community description and settings
    - Review and approve/reject membership applications
    - Manage member roles and permissions
    - View community analytics and statistics
    
    Args:
        request: Django request object
        community_id: UUID of the community to manage
    """
    from security.models import CommunityApplication
    
    community = get_object_or_404(Community, id=community_id)
    
    # Check if user is a manager of this community
    try:
        user_membership = Membership.objects.get(
            community=community,
            member=request.user
        )
        if not user_membership.is_community_manager:
            messages.error(request, "You don't have permission to manage this community.")
            return redirect('democracy:community_detail', community_id=community_id)
    except Membership.DoesNotExist:
        messages.error(request, "You are not a member of this community.")
        return redirect('democracy:community_detail', community_id=community_id)
    
    # Handle form submissions
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'update_description':
            new_description = request.POST.get('description', '').strip()
            if new_description:
                community.description = new_description
                community.save()
                messages.success(request, "Community description updated successfully!")
            else:
                messages.error(request, "Description cannot be empty.")
        
        elif action == 'toggle_auto_approve':
            community.auto_approve_applications = not community.auto_approve_applications
            community.save()
            status = "enabled" if community.auto_approve_applications else "disabled"
            messages.success(request, f"Auto-approval has been {status}.")
        
        return redirect('democracy:community_manage', community_id=community_id)
    
    # Get pending applications
    pending_applications = CommunityApplication.objects.filter(
        community=community,
        status='pending'
    ).select_related('user').order_by('-created')
    
    # Get recent applications (approved/rejected)
    recent_applications = CommunityApplication.objects.filter(
        community=community,
        status__in=['approved', 'rejected']
    ).select_related('user', 'reviewed_by').order_by('-reviewed_at')[:10]
    
    # Get community statistics
    total_members = community.members.count()
    voting_members = community.get_voting_members().count()
    managers = community.get_managers().count()
    lobbyists = total_members - voting_members
    
    context = {
        'community': community,
        'user_membership': user_membership,
        'pending_applications': pending_applications,
        'recent_applications': recent_applications,
        'stats': {
            'total_members': total_members,
            'voting_members': voting_members,
            'lobbyists': lobbyists,
            'managers': managers,
            'pending_applications': pending_applications.count(),
        }
    }
    
    return render(request, 'democracy/community_manage.html', context)


@login_required
@require_POST
def manage_application(request, community_id, application_id):
    """
    Approve or reject a community membership application.
    
    Only community managers can approve/reject applications.
    """
    from security.models import CommunityApplication
    
    community = get_object_or_404(Community, id=community_id)
    application = get_object_or_404(CommunityApplication, id=application_id, community=community)
    
    # Check if user is a manager
    try:
        user_membership = Membership.objects.get(
            community=community,
            member=request.user
        )
        if not user_membership.is_community_manager:
            return HttpResponseForbidden("You don't have permission to manage applications.")
    except Membership.DoesNotExist:
        return HttpResponseForbidden("You are not a member of this community.")
    
    action = request.POST.get('action')
    notes = request.POST.get('notes', '').strip()
    
    if action == 'approve':
        try:
            membership = application.approve(reviewer=request.user, notes=notes)
            messages.success(
                request, 
                f"Approved {application.user.get_full_name_or_username()}'s application to join {community.name}!"
            )
        except Exception as e:
            messages.error(request, f"Error approving application: {str(e)}")
    
    elif action == 'reject':
        try:
            application.reject(reviewer=request.user, notes=notes)
            messages.success(
                request, 
                f"Rejected {application.user.get_full_name_or_username()}'s application to join {community.name}."
            )
        except Exception as e:
            messages.error(request, f"Error rejecting application: {str(e)}")
    
    return redirect('democracy:community_manage', community_id=community_id)


@login_required
def decision_list(request, community_id):
    """
    List all decisions for a community with filtering and search.
    
    Shows different views based on user role:
    - Community members: Active and closed decisions
    - Community managers: All decisions including drafts
    
    Args:
        request: Django request object
        community_id: UUID of the community
    """
    from django.db.models import Q, Count
    from .forms import DecisionSearchForm
    
    community = get_object_or_404(Community, id=community_id)
    
    # Check if user is a member
    try:
        user_membership = Membership.objects.get(
            community=community,
            member=request.user
        )
    except Membership.DoesNotExist:
        messages.error(request, "You must be a member of this community to view decisions.")
        return redirect('democracy:community_detail', community_id=community_id)
    
    # Get base queryset
    decisions = Decision.objects.filter(community=community).select_related('community')
    
    # Filter based on user role
    if not user_membership.is_community_manager:
        # Regular members can't see draft decisions
        decisions = decisions.exclude(dt_close__isnull=True)
    
    # Handle search and filtering - simplified approach
    search = request.GET.get('search', '').strip()
    status = request.GET.get('status', '').strip()
    sort = request.GET.get('sort', '-dt_close').strip()
    
    # Create form for display
    form = DecisionSearchForm(request.GET)
    
    if search:
        decisions = decisions.filter(
            Q(title__icontains=search) | Q(description__icontains=search)
        )
    
    if status:
        now = timezone.now()
        if status == 'active':
            decisions = decisions.filter(dt_close__gt=now)
        elif status == 'closed':
            decisions = decisions.filter(dt_close__lte=now)
        elif status == 'draft':
            if user_membership.is_community_manager:
                decisions = decisions.filter(dt_close__isnull=True)
            else:
                decisions = decisions.none()  # No drafts for non-managers
    
    # Apply sorting - ensure sort is valid and not empty
    valid_sort_fields = ['-dt_close', 'dt_close', '-created', 'created', 'title', '-title']
    if sort and sort in valid_sort_fields:
        decisions = decisions.order_by(sort)
    else:
        decisions = decisions.order_by('-dt_close')
    
    # Annotate with vote counts
    decisions = decisions.annotate(
        total_votes=Count('ballots', distinct=True),
        total_choices=Count('choices', distinct=True)
    )
    
    # Add status information
    now = timezone.now()
    for decision in decisions:
        if decision.dt_close is None:
            decision.status = 'draft'
        elif decision.dt_close > now:
            decision.status = 'active'
        else:
            decision.status = 'closed'
    
    context = {
        'community': community,
        'user_membership': user_membership,
        'decisions': decisions,
        'search_form': form,
        'can_create': user_membership.is_community_manager,
    }
    
    return render(request, 'democracy/decision_list.html', context)


@login_required
def decision_create(request, community_id):
    """
    Create a new decision for the community.
    
    Only community managers can create decisions. Supports both
    draft saving and immediate publishing.
    
    Args:
        request: Django request object
        community_id: UUID of the community
    """
    from .forms import DecisionForm, ChoiceFormSet
    
    community = get_object_or_404(Community, id=community_id)
    
    # Check if user is a manager
    try:
        user_membership = Membership.objects.get(
            community=community,
            member=request.user
        )
        if not user_membership.is_community_manager:
            messages.error(request, "Only community managers can create decisions.")
            return redirect('democracy:community_detail', community_id=community_id)
    except Membership.DoesNotExist:
        messages.error(request, "You must be a member of this community.")
        return redirect('democracy:community_detail', community_id=community_id)
    
    if request.method == 'POST':
        form = DecisionForm(request.POST)
        choice_formset = ChoiceFormSet(request.POST)
        
        if form.is_valid() and choice_formset.is_valid():
            # Use database transaction to ensure atomicity
            with transaction.atomic():
                # Create decision but don't save yet
                decision = form.save(commit=False)
                decision.community = community
                
                # Handle draft vs publish
                action = request.POST.get('action')
                if action == 'save_draft':
                    decision.dt_close = None  # Null means draft
                
                decision.save()
                
                # Save choices - this will only happen if both forms are valid
                choice_formset.instance = decision
                choices = choice_formset.save()
                
                # Validate that at least one choice was created (unless it's a draft)
                if action != 'save_draft' and len(choices) == 0:
                    raise ValidationError("A published decision must have at least one choice.")
                
                if action == 'save_draft':
                    messages.success(request, f'Decision "{decision.title}" saved as draft.')
                    return redirect('democracy:decision_edit', community_id=community_id, decision_id=decision.id)
                else:
                    messages.success(request, f'Decision "{decision.title}" published successfully!')
                    return redirect('democracy:decision_detail', community_id=community_id, decision_id=decision.id)
        else:
            # Form or formset errors - nothing gets saved
            if not form.is_valid():
                messages.error(request, "Please fix the errors in the decision form.")
            if not choice_formset.is_valid():
                messages.error(request, "Please fix the errors in the choices below.")
    else:
        form = DecisionForm()
        choice_formset = ChoiceFormSet()
    
    context = {
        'community': community,
        'user_membership': user_membership,
        'form': form,
        'choice_formset': choice_formset,
        'is_editing': False,
    }
    
    return render(request, 'democracy/decision_create.html', context)


@login_required
def decision_detail(request, community_id, decision_id):
    """
    View decision details and voting interface.
    
    Shows decision information, current results (if available),
    and voting interface for active decisions.
    
    Args:
        request: Django request object
        community_id: UUID of the community
        decision_id: UUID of the decision
    """
    community = get_object_or_404(Community, id=community_id)
    decision = get_object_or_404(Decision, id=decision_id, community=community)
    
    # Check if user is a member
    try:
        user_membership = Membership.objects.get(
            community=community,
            member=request.user
        )
    except Membership.DoesNotExist:
        messages.error(request, "You must be a member of this community to view decisions.")
        return redirect('democracy:community_detail', community_id=community_id)
    
    # Check if decision is published (not draft)
    if decision.dt_close is None and not user_membership.is_community_manager:
        messages.error(request, "This decision is not yet published.")
        return redirect('democracy:decision_list', community_id=community_id)
    
    # Get user's existing ballot if any
    user_ballot = None
    user_ballot_tags = []
    try:
        user_ballot = Ballot.objects.get(decision=decision, voter=request.user)
        # Split tags for template (Django templates can't call .split(','))
        if user_ballot.tags:
            user_ballot_tags = [tag.strip() for tag in user_ballot.tags.split(',') if tag.strip()]
    except Ballot.DoesNotExist:
        pass
    
    # Determine decision status
    now = timezone.now()
    if decision.dt_close is None:
        status = 'draft'
    elif decision.dt_close > now:
        status = 'active'
    else:
        status = 'closed'
    
    # Get voting statistics
    total_ballots = decision.ballots.count()
    voting_members = community.get_voting_members().count()
    participation_rate = (total_ballots / voting_members * 100) if voting_members > 0 else 0
    
    # Get current results if decision is closed or has votes
    current_results = None
    if status == 'closed' or total_ballots > 0:
        # Get the latest result
        current_results = decision.results.first()
    
    # Get all snapshots for this decision (for historical results table - Plan #8)
    snapshots = decision.snapshots.all().order_by('-created')
    
    context = {
        'community': community,
        'user_membership': user_membership,
        'decision': decision,
        'user_ballot': user_ballot,
        'user_ballot_tags': user_ballot_tags,
        'status': status,
        'can_vote': status == 'active' and user_membership.is_voting_community_member,
        'can_manage': user_membership.is_community_manager,
        'can_edit': (user_membership.is_community_manager and 
                    not decision.ballots.exists() and 
                    status in ['draft', 'active']),
        'stats': {
            'total_ballots': total_ballots,
            'voting_members': voting_members,
            'participation_rate': round(participation_rate, 1),
        },
        'current_results': current_results,
        'snapshots': snapshots,  # Historical snapshots for Plan #8
    }
    
    return render(request, 'democracy/decision_detail.html', context)


@login_required
def snapshot_detail(request, community_id, decision_id, snapshot_id):
    """
    Display detailed view of a calculation snapshot (Plan #8 Phase 7).
    
    Shows complete delegation tree, ballot calculations, and STAR voting tally
    results for a specific point-in-time snapshot.
    
    Args:
        request: Django request object
        community_id: UUID of the community
        decision_id: UUID of the decision
        snapshot_id: UUID of the snapshot
    """
    community = get_object_or_404(Community, id=community_id)
    decision = get_object_or_404(Decision, id=decision_id, community=community)
    snapshot = get_object_or_404(DecisionSnapshot, id=snapshot_id, decision=decision)
    
    # Check if user is a member
    try:
        user_membership = Membership.objects.get(
            community=community,
            member=request.user
        )
    except Membership.DoesNotExist:
        messages.error(request, "You must be a member of this community to view snapshots.")
        return redirect('democracy:decision_detail', community_id=community_id, decision_id=decision_id)
    
    # Extract data from snapshot
    snapshot_data = snapshot.snapshot_data
    
    # Get statistics from snapshot data
    stats = snapshot_data.get('statistics', {
        'total_members': 0,
        'manual_ballots': 0,
        'calculated_ballots': 0,
        'no_ballot': 0,
        'circular_prevented': 0,
        'max_delegation_depth': 0
    })
    
    # Get delegation tree data (if available)
    delegation_tree = snapshot_data.get('delegation_tree', {
        'nodes': [],
        'edges': [],
        'inheritance_chains': []
    })
    
    # Build a user lookup dict for displaying names
    from security.models import CustomUser
    user_ids = list(set(
        [node['voter_id'] for node in delegation_tree.get('nodes', [])]
    ))
    users = CustomUser.objects.filter(id__in=user_ids)
    user_lookup = {str(u.id): u for u in users}
    
    # Organize nodes by type
    manual_nodes = [n for n in delegation_tree.get('nodes', []) if n.get('vote_type') == 'manual']
    calculated_nodes = [n for n in delegation_tree.get('nodes', []) if n.get('vote_type') == 'calculated']
    
    # Calculate influence counts (how many people inherited from each voter)
    influence_counts = {}
    for edge in delegation_tree.get('edges', []):
        followee_id = edge.get('followee')
        if followee_id:
            influence_counts[followee_id] = influence_counts.get(followee_id, 0) + 1
    
    max_influence = max(influence_counts.values()) if influence_counts else 0
    
    context = {
        'community': community,
        'decision': decision,
        'snapshot': snapshot,
        'stats': stats,
        'delegation_tree': delegation_tree,
        'manual_nodes': manual_nodes,
        'calculated_nodes': calculated_nodes,
        'user_lookup': user_lookup,
        'influence_counts': influence_counts,
        'max_influence': max_influence,
        'can_manage': user_membership.is_community_manager,
    }
    
    return render(request, 'democracy/snapshot_detail.html', context)


@login_required
def decision_edit(request, community_id, decision_id):
    """
    Edit an existing decision.
    
    Only managers can edit decisions, and only before any votes are cast.
    Draft decisions can be published from this view.
    
    Args:
        request: Django request object
        community_id: UUID of the community
        decision_id: UUID of the decision to edit
    """
    from .forms import DecisionForm, ChoiceFormSet
    
    community = get_object_or_404(Community, id=community_id)
    decision = get_object_or_404(Decision, id=decision_id, community=community)
    
    # Check if user is a manager
    try:
        user_membership = Membership.objects.get(
            community=community,
            member=request.user
        )
        if not user_membership.is_community_manager:
            messages.error(request, "Only community managers can edit decisions.")
            return redirect('democracy:decision_detail', community_id=community_id, decision_id=decision_id)
    except Membership.DoesNotExist:
        messages.error(request, "You must be a member of this community.")
        return redirect('democracy:community_detail', community_id=community_id)
    
    # Check if decision can be edited (no votes cast yet)
    if decision.ballots.exists():
        messages.error(request, "Cannot edit decision after votes have been cast.")
        return redirect('democracy:decision_detail', community_id=community_id, decision_id=decision_id)
    
    if request.method == 'POST':
        form = DecisionForm(request.POST, instance=decision)
        choice_formset = ChoiceFormSet(request.POST, instance=decision)
        
        if form.is_valid() and choice_formset.is_valid():
            # Handle draft vs publish
            action = request.POST.get('action')
            
            decision = form.save(commit=False)
            if action == 'save_draft':
                decision.dt_close = None  # Keep as draft
            elif action == 'publish' and decision.dt_close is None:
                # Publishing a draft - ensure dt_close is set
                if not form.cleaned_data.get('dt_close'):
                    messages.error(request, "Please set a voting deadline to publish this decision.")
                    return render(request, 'democracy/decision_create.html', {
                        'community': community,
                        'user_membership': user_membership,
                        'form': form,
                        'choice_formset': choice_formset,
                        'decision': decision,
                        'is_editing': True,
                    })
            
            decision.save()
            choice_formset.save()
            
            if action == 'save_draft':
                messages.success(request, f'Decision "{decision.title}" updated and saved as draft.')
            elif action == 'publish':
                messages.success(request, f'Decision "{decision.title}" published successfully!')
                return redirect('democracy:decision_detail', community_id=community_id, decision_id=decision_id)
            else:
                messages.success(request, f'Decision "{decision.title}" updated successfully!')
                return redirect('democracy:decision_detail', community_id=community_id, decision_id=decision_id)
        
    else:
        form = DecisionForm(instance=decision)
        choice_formset = ChoiceFormSet(instance=decision)
    
    context = {
        'community': community,
        'user_membership': user_membership,
        'form': form,
        'choice_formset': choice_formset,
        'decision': decision,
        'is_editing': True,
        'is_draft': decision.dt_close is None,
    }
    
    return render(request, 'democracy/decision_create.html', context)


@login_required
@require_POST
def vote_submit(request, community_id, decision_id):
    """
    Submit or update a vote on a decision.
    
    Handles STAR voting submission with tag input. Creates or updates the user's
    ballot and individual choice votes. Anonymity is controlled at the membership
    level, not per-ballot, via the membership settings modal.
    
    Args:
        request: Django POST request object containing vote data
        community_id: UUID of the community
        decision_id: UUID of the decision
        
    Returns:
        Redirect to decision detail page with success/error message
        
    Raises:
        Http404: If community or decision doesn't exist
    """
    from .forms import VoteForm
    
    community = get_object_or_404(Community, id=community_id)
    decision = get_object_or_404(Decision, id=decision_id, community=community)
    
    # Check if user is a voting member
    try:
        user_membership = Membership.objects.get(
            community=community,
            member=request.user
        )
        if not user_membership.is_voting_community_member:
            messages.error(request, "Only voting members can cast ballots.")
            return redirect('democracy:decision_detail', community_id=community_id, decision_id=decision_id)
    except Membership.DoesNotExist:
        messages.error(request, "You must be a member of this community to vote.")
        return redirect('democracy:community_detail', community_id=community_id)
    
    # Check if decision is active
    now = timezone.now()
    if decision.dt_close is None:
        messages.error(request, "This decision is not yet published.")
        return redirect('democracy:decision_detail', community_id=community_id, decision_id=decision_id)
    elif decision.dt_close <= now:
        messages.error(request, "Voting has closed for this decision.")
        return redirect('democracy:decision_detail', community_id=community_id, decision_id=decision_id)
    
    # Process the vote form
    form = VoteForm(decision, request.user, request.POST)
    
    if form.is_valid():
        # Get or create ballot
        # Note: Anonymity is now controlled at the Membership level, not per-ballot
        ballot, created = Ballot.objects.get_or_create(
            decision=decision,
            voter=request.user,
            defaults={
                'is_calculated': False,
                'tags': form.cleaned_data.get('tags', ''),
                'hashed_username': generate_username_hash(request.user.username),
            }
        )
        
        # Update ballot if it already existed
        if not created:
            ballot.tags = form.cleaned_data.get('tags', '')
            ballot.hashed_username = generate_username_hash(request.user.username)
            ballot.save()
        
        # Clear existing votes and create new ones
        ballot.votes.all().delete()
        
        choice_ratings = form.get_choice_ratings()
        for choice_id, stars in choice_ratings.items():
            choice = get_object_or_404(Choice, id=choice_id, decision=decision)
            Vote.objects.create(
                choice=choice,
                stars=stars,
                ballot=ballot
            )
        
        # Mark decision results as needing update
        decision.results_need_updating = True
        decision.save()
        
        messages.success(
            request, 
            f"Your vote has been {'updated' if not created else 'submitted'} successfully! "
            f"You can change it anytime before {decision.dt_close.strftime('%B %d, %Y at %I:%M %p')}."
        )
        
        return redirect('democracy:decision_detail', community_id=community_id, decision_id=decision_id)
    
    else:
        # Form errors
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field}: {error}")
        
        return redirect('democracy:decision_detail', community_id=community_id, decision_id=decision_id)


@login_required
def decision_results(request, community_id, decision_id):
    """
    Display comprehensive decision results with delegation tree and complete analysis.
    
    Shows the complete transparency view of a decision including:
    - Decision metadata and participation statistics
    - Delegation tree visualization (Phase 2)
    - Complete vote tally with manual vs calculated indicators
    - Final STAR voting results and analysis
    
    Args:
        request: Django request object
        community_id: UUID of the community
        decision_id: UUID of the decision
    """
    community = get_object_or_404(Community, id=community_id)
    decision = get_object_or_404(Decision, id=decision_id, community=community)
    
    # Check if user is a member
    try:
        user_membership = Membership.objects.get(
            community=community,
            member=request.user
        )
    except Membership.DoesNotExist:
        messages.error(request, "You must be a member of this community to view decision results.")
        return redirect('democracy:community_detail', community_id=community_id)
    
    # Check if decision is published (not draft)
    if decision.dt_close is None and not user_membership.is_community_manager:
        messages.error(request, "This decision is not yet published.")
        return redirect('democracy:decision_list', community_id=community_id)
    
    # Get the latest snapshot (or create a basic one if none exists)
    from .models import DecisionSnapshot
    latest_snapshot = DecisionSnapshot.objects.filter(decision=decision).first()
    
    # If no snapshot exists, create a comprehensive one with delegation tree data
    if not latest_snapshot:
        # Generate delegation tree data using StageBallots service
        from .services import StageBallots
        stage_ballots_service = StageBallots()
        
        # Process ballots to get delegation tree data
        delegation_trees = {}
        
        # Reset delegation tree data for this decision
        stage_ballots_service.delegation_tree_data = {
            'nodes': [],
            'edges': [],
            'inheritance_chains': []
        }
        
        # Process only voting members to build delegation tree (exclude lobbyists)
        for membership in community.memberships.filter(is_voting_community_member=True):
            stage_ballots_service.get_or_calculate_ballot(
                decision=decision, voter=membership.member
            )
        
        # Get the delegation tree data for this decision
        delegation_tree_data = stage_ballots_service.delegation_tree_data.copy()
        
        # Calculate basic stats with debugging - ONLY count ballots from voting members
        voting_member_ids = list(community.get_voting_members().values_list('id', flat=True))
        total_ballots = decision.ballots.filter(voter_id__in=voting_member_ids).count()
        manual_ballots = decision.ballots.filter(voter_id__in=voting_member_ids, is_calculated=False).count()
        calculated_ballots = decision.ballots.filter(voter_id__in=voting_member_ids, is_calculated=True).count()
        voting_members = community.get_voting_members().count()
        participation_rate = (total_ballots / voting_members * 100) if voting_members > 0 else 0
        
        # Clean debug logging
        print(f"✅ Participation Rate Fixed: {total_ballots}/{voting_members} = {participation_rate:.1f}%")
        
        # Get tags used
        tags_used = []
        for ballot in decision.ballots.exclude(tags=''):
            if ballot.tags:
                ballot_tags = [tag.strip().lower() for tag in ballot.tags.split(',')]
                tags_used.extend(ballot_tags)
        
        # Count tag frequency
        from collections import Counter
        tag_frequency = Counter(tags_used)
        
        # Create comprehensive snapshot data with delegation tree
        snapshot_data = {
            "metadata": {
                "calculation_timestamp": timezone.now().isoformat(),
                "system_version": "1.0.0",
                "decision_status": "active" if decision.dt_close and decision.dt_close > timezone.now() else "closed"
            },
            "delegation_tree": delegation_tree_data,
            "tag_analysis": {
                "tag_frequency": dict(tag_frequency.most_common(10)),
                "total_unique_tags": len(tag_frequency)
            },
            "vote_tally": {
                "direct_votes": manual_ballots,
                "calculated_votes": calculated_ballots
            }
        }
        
        # Create snapshot
        latest_snapshot = DecisionSnapshot.objects.create(
            decision=decision,
            snapshot_data=snapshot_data,
            total_eligible_voters=voting_members,
            total_votes_cast=manual_ballots,
            total_calculated_votes=calculated_ballots,
            tags_used=list(tag_frequency.keys()),
            is_final=(decision.dt_close and decision.dt_close <= timezone.now())
        )
    
    # Determine decision status
    now = timezone.now()
    if decision.dt_close is None:
        status = 'draft'
    elif decision.dt_close > now:
        status = 'active'
    else:
        status = 'closed'
    
    # Get all ballots for display (including those with 0 votes)
    ballots_with_votes = decision.ballots.select_related('voter').prefetch_related('votes__choice').order_by('voter__username')
    
    # Get choices with basic stats and STAR voting results
    choices = decision.choices.all()
    choice_stats = {}
    star_results = None
    winner_choice_id = None
    
    # Calculate STAR voting results if there are ballots
    voting_member_ids = list(community.get_voting_members().values_list('id', flat=True))
    voting_ballots = decision.ballots.filter(voter_id__in=voting_member_ids)
    
    if voting_ballots.exists():
        from .services import StageBallots
        stage_service = StageBallots()
        
        # Run STAR voting calculation
        try:
            star_results = stage_service.automatic_runoff(voting_ballots)
            if star_results and star_results.get('winner'):
                winner_choice_id = star_results['winner'].id
        except Exception as e:
            # Fallback to basic stats if STAR calculation fails
            pass
    
    # Calculate basic stats for all choices
    for choice in choices:
        votes = Vote.objects.filter(choice=choice)
        total_votes = votes.count()
        if total_votes > 0:
            avg_stars = sum(vote.stars for vote in votes) / total_votes
            choice_stats[choice.id] = {
                'total_votes': total_votes,
                'average_stars': round(avg_stars, 2)
            }
        else:
            choice_stats[choice.id] = {'total_votes': 0, 'average_stars': 0}
    
    # Extract delegation tree data from snapshot
    delegation_tree_data = latest_snapshot.snapshot_data.get('delegation_tree', {
        'nodes': [],
        'edges': [],
        'inheritance_chains': []
    })
    
    # Generate decision-specific delegation tree
    # TODO: Temporarily disabled for new network visualization (Change 0003)
    # decision_delegation_tree = build_decision_delegation_tree(decision, include_links=True)
    decision_delegation_tree = None
    
    context = {
        'community': community,
        'user_membership': user_membership,
        'decision': decision,
        'status': status,
        'latest_snapshot': latest_snapshot,
        'ballots_with_votes': ballots_with_votes,
        'choices': choices,
        'choice_stats': choice_stats,
        'can_manage': user_membership.is_community_manager,
        'delegation_tree_data': delegation_tree_data,
        # 'decision_delegation_tree': decision_delegation_tree,  # TODO: Temporarily disabled (Change 0003)
        'star_results': star_results,
        'winner_choice_id': winner_choice_id,
    }
    
    return render(request, 'democracy/decision_results.html', context)


@login_required
def calculation_status(request, community_id, decision_id):
    """
    HTMX endpoint to get current calculation status for a decision.
    
    Returns JSON with current status information for real-time UI updates.
    """
    try:
        community = get_object_or_404(Community, id=community_id)
        decision = get_object_or_404(Decision, id=decision_id, community=community)
        
        # Check if user is a member
        membership = get_object_or_None(Membership, member=request.user, community=community)
        if not membership:
            return JsonResponse({'error': 'Not a community member'}, status=403)
        
        status_data = {
            'calculation_status': decision.get_calculation_status(),
            'is_calculating': decision.is_calculating(),
            'last_calculated': decision.last_calculated.isoformat() if decision.last_calculated else None,
            'last_calculated_display': f"{decision.last_calculated.strftime('%H:%M:%S')}" if decision.last_calculated else None,
        }
        
        return JsonResponse(status_data)
        
    except Exception as e:
        logger.error(f"Error getting calculation status: {str(e)}")
        return JsonResponse({'error': 'Server error'}, status=500)


@login_required
@require_POST
def manual_recalculation(request, community_id, decision_id):
    """
    Manual recalculation trigger for community managers.
    
    Allows community managers to manually trigger vote recalculation
    for a specific decision when needed (e.g., after system issues).
    
    Args:
        request: HTTP request object
        community_id: UUID of the community
        decision_id: UUID of the decision to recalculate
        
    Returns:
        JsonResponse: Status of the recalculation request
    """
    logger = logging.getLogger('democracy.views')
    
    # Get community and decision (let Http404 bubble up for nonexistent objects)
    community = get_object_or_404(Community, id=community_id)
    decision = get_object_or_404(Decision, id=decision_id, community=community)
    
    try:
        
        # Check if user is a community manager
        try:
            membership = Membership.objects.get(member=request.user, community=community)
            if not membership.is_community_manager:
                logger.warning(f"[MANUAL_RECALC_DENIED] [{request.user.username}] - Non-manager attempted manual recalculation for decision '{decision.title}'")
                return JsonResponse({
                    'success': False,
                    'error': 'Only community managers can trigger manual recalculation'
                }, status=403)
        except Membership.DoesNotExist:
            logger.warning(f"[MANUAL_RECALC_DENIED] [{request.user.username}] - Non-member attempted manual recalculation for decision '{decision.title}'")
            return JsonResponse({
                'success': False,
                'error': 'You must be a community member to trigger recalculation'
            }, status=403)
        
        # Check if decision is open
        if not decision.is_open:
            logger.info(f"[MANUAL_RECALC_DENIED] [{request.user.username}] - Attempted manual recalculation for closed decision '{decision.title}'")
            return JsonResponse({
                'success': False,
                'error': 'Cannot recalculate closed decisions'
            }, status=400)
        
        # Check if calculation is already in progress
        if decision.is_calculating():
            logger.info(f"[MANUAL_RECALC_DENIED] [{request.user.username}] - Calculation already in progress for decision '{decision.title}'")
            return JsonResponse({
                'success': False,
                'error': 'Calculation already in progress for this decision'
            }, status=400)
        
        # Log the manual trigger
        logger.info(f"[MANUAL_RECALC] [{request.user.username}] - Manual recalculation triggered for decision '{decision.title}'")
        
        # Start background recalculation
        thread = threading.Thread(
            target=recalculate_community_decisions_async,
            args=(community.id, f"manual_recalc_by_{request.user.username}", request.user.id),
            daemon=True
        )
        thread.start()
        
        logger.info(f"[ASYNC_RECALC_TRIGGERED] [system] - Manual background recalculation started for decision '{decision.title}'")
        
        return JsonResponse({
            'success': True,
            'message': f'Recalculation started for "{decision.title}". Results will update automatically when complete.',
            'decision_status': decision.get_calculation_status()
        })
        
    except Exception as e:
        logger.error(f"[MANUAL_RECALC_ERROR] [{request.user.username}] - Error in manual recalculation: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An error occurred while starting recalculation. Please try again.'
        }, status=500)


# ============================================================================
# FOLLOW/UNFOLLOW VIEWS
# ============================================================================

def get_member_tags_in_community(membership):
    """
    Get all unique tags a member has used in their community.
    
    Queries Ballot tags where this membership has voted.
    Returns list of unique tag names.
    """
    # Get all ballots this user has cast in this community's decisions
    ballots = Ballot.objects.filter(
        voter=membership.member,
        decision__community=membership.community
    ).exclude(tags='').exclude(tags__isnull=True).values_list('tags', flat=True)
    
    # Collect all unique tags from ballots
    tag_names = set()
    for tags_string in ballots:
        if tags_string:
            for tag in tags_string.split(','):
                tag_names.add(tag.strip())
    
    return sorted(list(tag_names))


@login_required
def follow_modal(request, community_id, member_id):
    """
    Return HTMX modal for follow/unfollow with tag selection.
    
    Args:
        community_id: UUID of the community
        member_id: UUID of the membership to follow
    
    Returns:
        Rendered follow modal template with context for tag selection
    """
    community = get_object_or_404(Community, id=community_id)
    member_membership = get_object_or_404(Membership, id=member_id, community=community)
    
    # Get current user's membership in this community
    try:
        user_membership = Membership.objects.get(member=request.user, community=community)
    except Membership.DoesNotExist:
        return HttpResponse("You must be a member of this community to follow others.", status=403)
    
    # Don't allow following yourself
    if member_membership == user_membership:
        return HttpResponse("You cannot follow yourself.", status=400)
    
    # Check if already following
    try:
        existing_following = Following.objects.get(
            follower=user_membership,
            followee=member_membership
        )
        current_tags = [tag.strip() for tag in existing_following.tags.split(',')] if existing_following.tags else []
    except Following.DoesNotExist:
        existing_following = None
        current_tags = []
    
    # Get tags this member has used in this community
    member_tags = get_member_tags_in_community(member_membership)
    
    context = {
        'community': community,
        'member_membership': member_membership,
        'user_membership': user_membership,
        'existing_following': existing_following,
        'member_tags': member_tags,
        'current_tags': current_tags,
    }
    
    return render(request, 'democracy/components/follow_modal.html', context)


@login_required
@require_POST
def follow_member(request, community_id, member_id):
    """
    Create or update Following relationship with tag selection.
    
    POST data:
        - tags: JSON string of array of tag names, or ["ALL"] for all tags
    
    Returns:
        Partial template with updated Following and Actions columns (HTMX out-of-band swaps)
    """
    import json
    
    community = get_object_or_404(Community, id=community_id)
    member_membership = get_object_or_404(Membership, id=member_id, community=community)
    
    # Get current user's membership
    try:
        user_membership = Membership.objects.get(member=request.user, community=community)
    except Membership.DoesNotExist:
        return HttpResponse("You must be a member of this community.", status=403)
    
    # Parse tags from POST data
    tags_json = request.POST.get('tags', '[]')
    try:
        tags_list = json.loads(tags_json)
    except json.JSONDecodeError:
        return HttpResponse("Invalid tags format.", status=400)
    
    # Convert tags list to comma-separated string
    # Empty string means "ALL tags"
    if tags_list == ['ALL'] or not tags_list:
        tags_string = ''
    else:
        tags_string = ','.join(tags_list)
    
    # Get or create Following object
    following, created = Following.objects.get_or_create(
        follower=user_membership,
        followee=member_membership,
        defaults={'tags': tags_string}
    )
    
    if not created:
        # Update existing following
        following.tags = tags_string
        following.save()
    
    logger.info(f"[FOLLOWING_UPDATED] [{request.user.username}] - Now following {member_membership.member.username} in {community.name} on tags: {tags_string or 'ALL'}")
    
    # Prepare tags list for template
    tags_display = tags_string.split(',') if tags_string else None
    
    context = {
        'membership': member_membership,
        'following': following,
        'tags_list': tags_display,
        'community': community,
    }
    
    return render(request, 'democracy/components/following_update.html', context)


@login_required
@require_POST
def unfollow_member(request, community_id, member_id):
    """
    Delete Following relationship.
    
    Returns:
        Partial template with updated Following and Actions columns (HTMX out-of-band swaps)
    """
    community = get_object_or_404(Community, id=community_id)
    member_membership = get_object_or_404(Membership, id=member_id, community=community)
    
    # Get current user's membership
    try:
        user_membership = Membership.objects.get(member=request.user, community=community)
    except Membership.DoesNotExist:
        return HttpResponse("You must be a member of this community.", status=403)
    
    # Delete the following relationship
    deleted_count, _ = Following.objects.filter(
        follower=user_membership,
        followee=member_membership
    ).delete()
    
    if deleted_count > 0:
        logger.info(f"[FOLLOWING_REMOVED] [{request.user.username}] - Unfollowed {member_membership.member.username} in {community.name}")
    
    context = {
        'membership': member_membership,
        'following': None,
        'community': community,
    }
    
    return render(request, 'democracy/components/following_update.html', context)


@login_required
def membership_settings_modal(request, community_id):
    """
    Display membership settings modal for the current user in a community.
    
    This HTMX view loads a modal that allows members to toggle their anonymity
    setting for the specific community. Lobbyists will see a disabled checkbox
    with an explanation that they cannot be anonymous.
    
    Args:
        request: HTTP request object
        community_id: UUID of the community
        
    Returns:
        Rendered modal template with membership settings form
        
    Raises:
        Http404: If community doesn't exist
        HttpResponse 403: If user is not a member of the community
    """
    community = get_object_or_404(Community, id=community_id)
    
    # Get current user's membership in this community
    try:
        membership = Membership.objects.get(member=request.user, community=community)
    except Membership.DoesNotExist:
        return HttpResponse("You must be a member of this community to access settings.", status=403)
    
    context = {
        'community': community,
        'membership': membership,
    }
    
    return render(request, 'democracy/components/membership_settings_modal.html', context)


@login_required
@require_http_methods(["POST"])
def membership_settings_save(request, community_id):
    """
    Save membership settings (anonymity toggle) for the current user.
    
    This HTMX view processes the anonymity toggle form. It validates that
    lobbyists cannot be made anonymous (enforced by database constraint and
    view logic). Upon successful save, logs the change and returns an empty
    response to close the modal with HTMX redirect.
    
    Args:
        request: HTTP POST request with is_anonymous checkbox value
        community_id: UUID of the community
        
    Returns:
        Empty response with HX-Redirect header to reload page
        Or error response if validation fails
        
    Raises:
        Http404: If community doesn't exist
        HttpResponse 403: If user is not a member or trying invalid operation
    """
    community = get_object_or_404(Community, id=community_id)
    
    # Get current user's membership
    try:
        membership = Membership.objects.get(member=request.user, community=community)
    except Membership.DoesNotExist:
        return HttpResponse("You must be a member of this community.", status=403)
    
    # Get the new anonymity preference from checkbox
    # Checkbox checked = True (anonymous), unchecked/missing = False (public)
    new_is_anonymous = request.POST.get('is_anonymous') == 'on'
    
    # Validate: Lobbyists cannot be anonymous
    if not membership.is_voting_community_member and new_is_anonymous:
        return HttpResponse(
            "Lobbyists cannot vote anonymously. Only voting members can choose to be anonymous.",
            status=403
        )
    
    # Update the membership
    old_is_anonymous = membership.is_anonymous
    membership.is_anonymous = new_is_anonymous
    membership.save()
    
    # Log the change if it actually changed
    if old_is_anonymous != new_is_anonymous:
        anonymity_status = "anonymous" if new_is_anonymous else "public"
        logger.info(
            f"[ANONYMITY_CHANGED] [{request.user.username}] - "
            f"Changed anonymity to {anonymity_status} in {community.name}"
        )
    
    # Return empty response with redirect to reload the page
    # This will close the modal and refresh to show the updated table
    response = HttpResponse("")
    response['HX-Redirect'] = request.META.get('HTTP_REFERER', f'/communities/{community_id}/')
    return response
