"""
Views for the accounts app.

This module contains views for user account management, including
profile setup, username validation, and onboarding flows.
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model, login
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .utils import generate_safe_username, validate_username
from .models import MagicLink

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
            return redirect('accounts:community_discovery')
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
    Returns HTML for HTMX requests, JSON for non-HTMX requests.
    """
    from democracy.models import Community
    from .models import CommunityApplication
    from django.shortcuts import get_object_or_404
    
    community = get_object_or_404(Community, id=community_id)
    application_message = request.POST.get('message', '').strip()
    
    def return_response(success, message, status):
        """Helper to return appropriate response type"""
        context = {
            'success': success,
            'message': message,
            'status': status,
            'community': community
        }
        
        if request.htmx:
            # Return HTML for HTMX requests
            html = render_to_string('accounts/community_status.html', context, request=request)
            return HttpResponse(html)
        else:
            # Return JSON for non-HTMX requests
            return JsonResponse(context)
    
    # Check if user is already a member
    if community.members.filter(id=request.user.id).exists():
        return return_response(
            success=False,
            message='You are already a member of this community',
            status='member'
        )
    
    # Check for existing application
    existing_app = CommunityApplication.objects.filter(
        user=request.user, 
        community=community
    ).first()
    
    if existing_app:
        if existing_app.status == 'pending':
            return return_response(
                success=False,
                message='You already have a pending application',
                status='pending'
            )
        elif existing_app.status == 'rejected':
            # Allow reapplication after rejection
            existing_app.status = 'pending'
            existing_app.application_message = application_message
            existing_app.reviewed_by = None
            existing_app.reviewed_at = None
            existing_app.reviewer_notes = ''
            existing_app.save()
            
            return return_response(
                success=True,
                message=f'Your application to {community.name} has been resubmitted!',
                status='pending'
            )
    
    # Create new application
    try:
        application = CommunityApplication.objects.create(
            user=request.user,
            community=community,
            application_message=application_message
        )
        
        # Check if community has auto-approval enabled
        if community.auto_approve_applications:
            # Auto-approve the application immediately
            membership = application.approve(
                reviewer=request.user,  # Self-approval for auto-approval
                notes='Auto-approved for demo community'
            )
            
            return return_response(
                success=True,
                message=f'Welcome to {community.name}! You have been automatically approved.',
                status='approved'
            )
        else:
            # Standard manual approval process
            return return_response(
                success=True,
                message=f'Your application to {community.name} has been submitted!',
                status='pending'
            )
        
    except Exception as e:
        return return_response(
            success=False,
            message='An error occurred while submitting your application',
            status='error'
        )


@require_POST
def request_magic_link(request):
    """
    Handle magic link requests for any email address.
    
    This view:
    1. Creates a magic link token
    2. Sends an email with a clickable link (not a code)
    3. Works for both new and existing users
    4. Returns a success message regardless of user existence (security)
    """
    email = request.POST.get('email', '').strip().lower()
    
    if not email:
        messages.error(request, "Please enter a valid email address")
        return redirect('home')
    
    # Create magic link for any email
    magic_link = MagicLink.create_for_email(email)
    
    # Generate the clickable URL
    login_url = magic_link.get_login_url(request)
    
    # Prepare email content
    context = {
        'email': email,
        'login_url': login_url,
        'site_name': 'CrowdVote',
        'expires_minutes': 15,
    }
    
    # Email content
    subject = 'Your CrowdVote Magic Link 🪄'
    message = f"""
Hello!

Click the link below to sign into CrowdVote:

{login_url}

This link will expire in 15 minutes and can only be used once.

If you didn't request this, you can safely ignore this email.

Happy voting!
The CrowdVote Team
"""
    
    try:
        # Send the magic link email
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        
        messages.success(
            request, 
            f"✨ Magic link sent to {email}! Check your email and click the link to sign in."
        )
        
    except Exception as e:
        messages.error(
            request,
            "We couldn't send your magic link right now. Please try again in a few minutes."
        )
    
    return redirect('home')


def magic_link_login(request, token):
    """
    Handle magic link login for the given token.
    
    This view:
    1. Validates the magic link token
    2. For existing users: logs them in directly
    3. For new users: creates account and redirects to profile setup
    4. Marks the magic link as used
    """
    try:
        magic_link = MagicLink.objects.get(token=token)
    except MagicLink.DoesNotExist:
        messages.error(request, "Invalid magic link. Please request a new one.")
        return redirect('home')
    
    # Check if magic link is still valid
    if not magic_link.is_valid:
        if magic_link.is_expired:
            messages.error(request, "This magic link has expired. Please request a new one.")
        else:
            messages.error(request, "This magic link has already been used. Please request a new one.")
        return redirect('home')
    
    # Mark magic link as used
    magic_link.use()
    
    # Check if user already exists
    try:
        user = User.objects.get(email=magic_link.email)
        # Existing user - log them in
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        
        # Check if they have a complete profile
        if user.first_name and user.username:
            # Existing user with complete profile - redirect to dashboard
            messages.success(request, f"Welcome back, {user.first_name}! 👋")
            return redirect('accounts:community_discovery')  # Or dashboard when we build it
        else:
            # Existing user without complete profile - redirect to profile setup
            messages.success(request, "Welcome back! Please complete your profile.")
            return redirect('accounts:profile_setup')
            
    except User.DoesNotExist:
        # New user - create account
        username = generate_safe_username()  # Temporary username
        user = User.objects.create_user(
            email=magic_link.email,
            username=username,  # Temporary - user will change this
            first_name='',  # User will set this in profile setup
        )
        
        # Associate the created user with the magic link
        magic_link.created_user = user
        magic_link.save()
        
        # Log them in
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        
        messages.success(
            request, 
            "🎉 Welcome to CrowdVote! Let's set up your profile."
        )
        return redirect('accounts:profile_setup')