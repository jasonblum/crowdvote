"""
Views for the democracy app.

This module contains views for community management, decision making,
and voting interfaces.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_http_methods, require_POST
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
    from accounts.models import CommunityApplication
    
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
    from accounts.models import CommunityApplication
    
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
