"""
Views for the democracy app.

This module contains views for community management, decision making,
and voting interfaces.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db.models import Q

from .models import Community, Decision, Membership

User = get_user_model()


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
            from accounts.models import CommunityApplication
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
    
    # Get recent decisions
    recent_decisions = Decision.objects.filter(
        community=community
    ).order_by('-created')[:5]
    
    # Calculate community statistics
    total_members = community.members.count()
    voting_members = community.get_voting_members().count()
    manager_count = community.get_managers().count()
    lobbyist_count = total_members - voting_members
    
    context = {
        'community': community,
        'user_membership': user_membership,
        'user_application': user_application,
        'memberships': memberships,
        'recent_decisions': recent_decisions,
        'role_filter': role_filter,
        'search_query': search_query,
        'stats': {
            'total_members': total_members,
            'voting_members': voting_members,
            'lobbyists': lobbyist_count,
            'managers': manager_count,
        }
    }
    
    return render(request, 'democracy/community_detail.html', context)
