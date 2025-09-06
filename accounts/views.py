"""
Views for the accounts app.

This module contains views for user account management, including
profile setup, username validation, and onboarding flows.
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from .utils import generate_safe_username, validate_username

User = get_user_model()


@login_required
def profile_setup(request):
    """
    Profile setup page for new users after email verification.
    
    This page allows users to:
    - Set their username (generated or custom)
    - Add basic profile information
    - Choose communities to join
    
    Uses HTMX for real-time username validation.
    """
    # Check if user already has a complete profile
    if request.user.username and hasattr(request.user, 'first_name') and request.user.first_name:
        return redirect('community_discovery')
    
    # Generate a suggested username
    suggested_username = generate_safe_username()
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        
        # Validate username
        is_valid, error_message = validate_username(username)
        
        if is_valid and first_name:
            # Update user profile
            request.user.username = username
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.save()
            
            messages.success(request, f"Welcome to CrowdVote, {first_name}! 🎉")
            return redirect('community_discovery')
        else:
            if not is_valid:
                messages.error(request, error_message)
            if not first_name:
                messages.error(request, "First name is required")
    
    context = {
        'suggested_username': suggested_username,
        'user': request.user,
    }
    return render(request, 'accounts/profile_setup.html', context)


@require_http_methods(["POST"])
def check_username_availability(request):
    """
    HTMX endpoint to check username availability in real-time.
    
    Returns JSON response with availability status and helpful messages.
    Used for live validation as users type their desired username.
    """
    username = request.POST.get('username', '').strip()
    
    if not username:
        return JsonResponse({
            'available': False,
            'message': '',
            'class': ''
        })
    
    is_valid, error_message = validate_username(username)
    
    if is_valid:
        return JsonResponse({
            'available': True,
            'message': f'✅ "{username}" is available!',
            'class': 'text-green-600'
        })
    else:
        return JsonResponse({
            'available': False,
            'message': f'❌ {error_message}',
            'class': 'text-red-600'
        })


@require_http_methods(["POST"])
def generate_new_username(request):
    """
    HTMX endpoint to generate a new random username.
    
    Returns a fresh username suggestion when user clicks "Generate New".
    """
    new_username = generate_safe_username()
    
    return JsonResponse({
        'username': new_username,
        'message': f'✨ How about "{new_username}"?',
        'class': 'text-blue-600'
    })


def community_discovery(request):
    """
    Community discovery page where users can browse and apply to join communities.
    
    Shows all available communities with information about membership
    requirements and application processes.
    """
    from democracy.models import Community
    from .models import CommunityApplication
    
    # Get all communities with member counts
    communities = Community.objects.all().order_by('name')
    
    # If user is authenticated, get their application status for each community
    user_applications = {}
    user_memberships = set()
    
    if request.user.is_authenticated:
        # Get existing applications
        applications = CommunityApplication.objects.filter(
            user=request.user
        ).select_related('community')
        
        for app in applications:
            user_applications[app.community.id] = app.status
        
        # Get existing memberships
        memberships = request.user.memberships.values_list('community_id', flat=True)
        user_memberships = set(memberships)
    
    # Prepare community data with application status
    community_data = []
    for community in communities:
        member_count = community.members.count()
        voting_member_count = community.get_voting_members().count()
        
        # Determine user's status with this community
        status = 'not_member'
        if community.id in user_memberships:
            status = 'member'
        elif community.id in user_applications:
            status = user_applications[community.id]
        
        community_data.append({
            'community': community,
            'member_count': member_count,
            'voting_member_count': voting_member_count,
            'user_status': status,
        })
    
    return render(request, 'accounts/community_discovery.html', {
        'community_data': community_data,
        'is_authenticated': request.user.is_authenticated,
    })


@login_required
@require_http_methods(["POST"])
def apply_to_community(request, community_id):
    """
    HTMX endpoint to apply for community membership.
    
    Creates a new community application and returns updated status.
    """
    from democracy.models import Community
    from .models import CommunityApplication
    from django.shortcuts import get_object_or_404
    
    community = get_object_or_404(Community, id=community_id)
    application_message = request.POST.get('message', '').strip()
    
    # Check if user is already a member
    if community.members.filter(id=request.user.id).exists():
        return JsonResponse({
            'success': False,
            'message': 'You are already a member of this community',
            'status': 'member'
        })
    
    # Check for existing application
    existing_app = CommunityApplication.objects.filter(
        user=request.user, 
        community=community
    ).first()
    
    if existing_app:
        if existing_app.status == 'pending':
            return JsonResponse({
                'success': False,
                'message': 'You already have a pending application',
                'status': 'pending'
            })
        elif existing_app.status == 'rejected':
            # Allow reapplication after rejection
            existing_app.status = 'pending'
            existing_app.application_message = application_message
            existing_app.reviewed_by = None
            existing_app.reviewed_at = None
            existing_app.reviewer_notes = ''
            existing_app.save()
            
            return JsonResponse({
                'success': True,
                'message': f'Your application to {community.name} has been resubmitted!',
                'status': 'pending'
            })
    
    # Create new application
    try:
        application = CommunityApplication.objects.create(
            user=request.user,
            community=community,
            application_message=application_message
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Your application to {community.name} has been submitted!',
            'status': 'pending'
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': 'An error occurred while submitting your application',
            'status': 'error'
        })