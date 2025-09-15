"""
Views for the accounts app.

This module contains views for user account management, including
profile setup, username validation, and onboarding flows.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model, login
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.contrib import messages
from django.core.mail import send_mail
import logging
from django.template.loader import render_to_string
from django.conf import settings
from .utils import generate_safe_username, validate_username
from .models import MagicLink, Following
from .forms import FollowForm

User = get_user_model()
logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    """
    User dashboard showing communities, applications, and recent activity.
    
    This is the main landing page for authenticated users, providing:
    - My Communities section with joined communities
    - Pending applications status
    - Recent decisions and activity
    - Quick navigation to key features
    """
    from democracy.models import Community
    from .models import CommunityApplication
    
    # Get user's communities with membership details
    user_memberships = request.user.memberships.select_related('community').order_by('-dt_joined')
    
    # Get pending applications
    pending_applications = CommunityApplication.objects.filter(
        user=request.user,
        status='pending'
    ).select_related('community').order_by('-created')
    
    # Get recent applications (approved/rejected)
    recent_applications = CommunityApplication.objects.filter(
        user=request.user,
        status__in=['approved', 'rejected']
    ).select_related('community').order_by('-reviewed_at')[:5]
    
    # Get available communities to join (not a member, no pending application)
    user_community_ids = set(user_memberships.values_list('community_id', flat=True))
    pending_community_ids = set(pending_applications.values_list('community_id', flat=True))
    excluded_ids = user_community_ids.union(pending_community_ids)
    
    available_communities = Community.objects.exclude(
        id__in=excluded_ids
    ).order_by('name')[:3]  # Show top 3 suggestions
    
    context = {
        'user_memberships': user_memberships,
        'pending_applications': pending_applications,
        'recent_applications': recent_applications,
        'available_communities': available_communities,
        'total_communities': user_memberships.count(),
        'total_pending': pending_applications.count(),
    }
    
    return render(request, 'accounts/dashboard.html', context)


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
        return redirect('accounts:dashboard')
    
    # Generate a suggested username
    suggested_username = generate_safe_username()
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        
        # Validate username (exclude current user to allow keeping same username)
        is_valid, error_message = validate_username(username, exclude_user=request.user)
        
        if is_valid and first_name:
            # Update user profile
            request.user.username = username
            request.user.first_name = first_name
            request.user.last_name = last_name
            request.user.save()
            
            messages.success(request, f"Welcome to CrowdVote, {first_name}! 🎉")
            return redirect('accounts:dashboard')
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
    
    Returns HTML response with availability status and helpful messages.
    Used for live validation as users type their desired username.
    """
    username = request.POST.get('username', '').strip()
    
    if not username:
        return HttpResponse('<span class="text-gray-500"></span>')
    
    # Exclude current user from availability check if they're logged in
    exclude_user = request.user if request.user.is_authenticated else None
    is_valid, error_message = validate_username(username, exclude_user=exclude_user)
    
    if is_valid:
        return HttpResponse(f'<span class="text-green-600">✅ "{username}" is available!</span>')
    else:
        return HttpResponse(f'<span class="text-red-600">❌ {error_message}</span>')


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
            # Return JSON for non-HTMX requests (make community serializable)
            json_context = {
                'success': success,
                'message': message,
                'status': status,
                'community': {
                    'id': str(community.id),
                    'name': community.name,
                    'description': community.description
                }
            }
            return JsonResponse(json_context)
    
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
        elif existing_app.status == 'approved':
            # Check if membership actually exists
            from democracy.models import Membership
            membership = Membership.objects.filter(
                community=community,
                member=request.user
            ).first()
            
            if membership:
                return return_response(
                    success=False,
                    message='You are already a member of this community',
                    status='approved'
                )
            else:
                # Approved application but no membership - create it now (fix data inconsistency)
                membership = Membership.objects.create(
                    community=community,
                    member=request.user,
                    is_voting_community_member=True,
                    is_community_manager=False,
                    is_anonymous_by_default=False,
                )
                return return_response(
                    success=True,
                    message=f'Welcome to {community.name}! Your membership has been activated.',
                    status='approved'
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
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Community application error: {str(e)}", exc_info=True)
        print(f"DEBUG: Community application error: {str(e)}")  # Also print to console
        return return_response(
            success=False,
            message=f'An error occurred while submitting your application: {str(e)}',
            status='error'
        )


@login_required
@require_POST
def leave_community(request, community_id):
    """
    Allow users to leave a community they belong to.
    
    Removes the user's membership from the community. Users cannot leave
    if they are the only manager of the community.
    """
    from democracy.models import Community, Membership
    from django.shortcuts import get_object_or_404
    
    community = get_object_or_404(Community, id=community_id)
    
    try:
        membership = Membership.objects.get(
            member=request.user,
            community=community
        )
    except Membership.DoesNotExist:
        messages.error(request, "You are not a member of this community.")
        return redirect('accounts:dashboard')
    
    # Check if user is the only manager
    if membership.is_community_manager:
        manager_count = community.get_managers().count()
        if manager_count <= 1:
            messages.error(
                request, 
                f"You cannot leave {community.name} because you are the only manager. "
                "Please promote another member to manager first."
            )
            return redirect('accounts:dashboard')
    
    # Remove membership
    community_name = community.name
    membership.delete()
    
    messages.success(
        request, 
        f"You have successfully left {community_name}. You can reapply anytime if you change your mind."
    )
    
    return redirect('accounts:dashboard')


@login_required
def member_profile(request, username):
    """
    Display a member's public profile for delegation decisions.
    
    Shows basic member information, communities they belong to,
    and their role in each community to help other users make
    delegation decisions.
    """
    from django.shortcuts import get_object_or_404
    
    member = get_object_or_404(User, username=username)
    
    # Get member's communities that the current user can see
    # (only communities where current user is also a member)
    user_community_ids = set()
    if request.user.is_authenticated:
        user_community_ids = set(
            request.user.memberships.values_list('community_id', flat=True)
        )
    
    # Get member's memberships in communities the current user can see
    visible_memberships = member.memberships.filter(
        community_id__in=user_community_ids
    ).select_related('community').order_by('community__name')
    
    # Get member's following relationships (who they follow)
    following = member.followings.select_related('followee').order_by('followee__username')
    
    # Get member's followers (who follows them)
    followers = member.followers.select_related('follower').order_by('follower__username')
    
    # Check if current user is following this member
    current_following = None
    is_following = False
    if request.user.is_authenticated and request.user != member:
        try:
            current_following = Following.objects.get(
                follower=request.user,
                followee=member
            )
            is_following = True
        except Following.DoesNotExist:
            pass
    
    context = {
        'member': member,
        'visible_memberships': visible_memberships,
        'following_count': following.count(),
        'followers_count': followers.count(),
        'following': following[:10],  # Show first 10
        'followers': followers[:10],  # Show first 10
        'is_own_profile': request.user == member,
        'can_view_details': bool(visible_memberships.exists()),
        'is_following': is_following,
        'current_following': current_following,
    }
    
    return render(request, 'accounts/member_profile.html', context)


@login_required
def edit_profile(request):
    """
    Allow users to edit their own profile information.
    
    Handles updating profile fields, social links, and privacy settings.
    """
    from .forms import ProfileEditForm
    
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully!")
            return redirect('accounts:dashboard')
    else:
        form = ProfileEditForm(instance=request.user)
    
    context = {
        'form': form,
        'user': request.user,
    }
    
    return render(request, 'accounts/edit_profile.html', context)


@require_POST
def request_magic_link(request):
    """
    Handle magic link requests for any email address with rate limiting.
    
    This view:
    1. Checks rate limits (3 per hour per IP and per email, 15min minimum interval)
    2. Creates a magic link token
    3. Sends an email with a clickable link (not a code)
    4. Works for both new and existing users
    5. Returns a success message regardless of user existence (security)
    """
    try:
        email = request.POST.get('email', '').strip().lower()
        logger.info(f"Magic link requested for email: {email}")
        
        if not email:
            messages.error(request, "Please enter a valid email address")
            return redirect('home')
        
        # Get client IP address
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR')
        
        # Rate limiting checks
        rate_limit_error = _check_magic_link_rate_limits(ip, email)
        if rate_limit_error:
            messages.error(request, rate_limit_error)
            return redirect('home')
        
        # Create magic link for any email
        logger.info(f"Creating magic link for: {email}")
        magic_link = MagicLink.create_for_email(email)
        logger.info(f"Magic link created with token: {magic_link.token[:8]}...")
        
        # Generate the clickable URL
        login_url = magic_link.get_login_url(request)
        logger.info(f"Generated login URL for: {email}")
    except Exception as e:
        logger.error(f"Error in magic link setup for {email}: {e}", exc_info=True)
        messages.error(request, "An error occurred. Please try again or contact support.")
        return redirect('home')
    
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

Questions? Contact support@crowdvote.com
"""
    
    try:
        # Send the magic link email
        logger.info(f"Attempting to send email to: {email}")
        logger.info(f"Using from_email: {settings.DEFAULT_FROM_EMAIL}")
        logger.info(f"Email backend: {getattr(settings, 'EMAIL_BACKEND', 'default')}")
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
        
        logger.info(f"Email sent successfully to: {email}")
        messages.success(
            request, 
            f"✨ Magic link sent to {email}! Check your email and click the link to sign in. (Limit: 3 requests per hour)"
        )
        
        # Update rate limit counters after successful email send
        _update_magic_link_rate_limits(ip, email)
        
    except Exception as e:
        # Log the specific error for debugging
        logger.error(f"Magic link email failed for {email}: {e}")
        
        # Check if this might be a rate limiting issue
        error_str = str(e).lower()
        if 'rate limit' in error_str or '429' in error_str or 'quota' in error_str:
            from django.utils.safestring import mark_safe
            messages.error(
                request,
                mark_safe('⚠️ We\'ve reached our daily email limit. Please try again tomorrow or contact <a href="mailto:support@crowdvote.com" class="text-red-600 hover:text-red-800 underline">support@crowdvote.com</a> for immediate assistance.'),
                extra_tags='safe'
            )
        elif 'authentication' in error_str or '401' in error_str:
            from django.utils.safestring import mark_safe
            messages.error(
                request,
                mark_safe('⚠️ Email service temporarily unavailable. Please contact <a href="mailto:support@crowdvote.com" class="text-red-600 hover:text-red-800 underline">support@crowdvote.com</a> for assistance.'),
                extra_tags='safe'
            )
        else:
            from django.utils.safestring import mark_safe
            messages.error(
                request,
                mark_safe('📧 We couldn\'t send your magic link right now. Please try again in a few minutes or contact <a href="mailto:support@crowdvote.com" class="text-red-600 hover:text-red-800 underline">support@crowdvote.com</a> if the problem persists.'),
                extra_tags='safe'
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
            return redirect('accounts:dashboard')
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


@login_required
@require_http_methods(["GET", "POST"])
def follow_user(request, user_id):
    """
    Handle following a user with tag specification.
    
    GET: Returns follow modal for tag specification
    POST: Creates or updates following relationship
    """
    followee = get_object_or_404(User, id=user_id)
    
    # Prevent self-following
    if request.user == followee:
        messages.error(request, "You cannot follow yourself.")
        return redirect('accounts:member_profile', username=followee.username)
    
    if request.method == "GET":
        # Return follow modal for tag specification
        form = FollowForm(initial={'followee': followee}, followee=followee)
        return render(request, 'accounts/components/follow_modal.html', {
            'form': form,
            'followee': followee
        })
    
    if request.method == "POST":
        form = FollowForm(request.POST, followee=followee)
        if form.is_valid():
            # Create or update following relationship
            following, created = Following.objects.update_or_create(
                follower=request.user,
                followee=followee,
                defaults={
                    'tags': form.cleaned_data['tags'],
                    'order': form.cleaned_data['order']
                }
            )
            
            if request.htmx:
                # Return updated follow button
                return render(request, 'accounts/components/follow_button.html', {
                    'user': followee,
                    'is_following': True,
                    'following': following
                })
            
            action = "Updated" if not created else "Now"
            messages.success(request, f"{action} following {followee.get_display_name()}")
            return redirect('accounts:member_profile', username=followee.username)
        
        # Form invalid - return modal with errors
        if request.htmx:
            return render(request, 'accounts/components/follow_modal.html', {
                'form': form,
                'followee': followee
            })
        
        messages.error(request, "Please correct the errors below.")
        return redirect('accounts:member_profile', username=followee.username)


@login_required
@require_POST
def unfollow_user(request, user_id):
    """Handle unfollowing a user."""
    followee = get_object_or_404(User, id=user_id)
    
    try:
        following = Following.objects.get(
            follower=request.user,
            followee=followee
        )
        following.delete()
        
        if request.htmx:
            # Return updated follow button
            return render(request, 'accounts/components/follow_button.html', {
                'user': followee,
                'is_following': False,
                'following': None
            })
        
        messages.success(request, f"Stopped following {followee.get_display_name()}")
        
    except Following.DoesNotExist:
        messages.error(request, "You are not following this user")
    
    return redirect('accounts:member_profile', username=followee.username)


@login_required
def edit_follow(request, user_id):
    """Handle editing an existing following relationship."""
    followee = get_object_or_404(User, id=user_id)
    
    try:
        following = Following.objects.get(
            follower=request.user,
            followee=followee
        )
    except Following.DoesNotExist:
        messages.error(request, "You are not following this user")
        return redirect('accounts:member_profile', username=followee.username)
    
    if request.method == "GET":
        # Return edit modal with current values
        form = FollowForm(
            initial={
                'followee': followee,
                'tags': following.tags,
                'order': following.order
            },
            followee=followee
        )
        return render(request, 'accounts/components/follow_modal.html', {
            'form': form,
            'followee': followee,
            'editing': True
        })
    
    # This view only handles GET - POST goes to follow_user
    return redirect('accounts:follow_user', user_id=user_id)


def _check_magic_link_rate_limits(ip, email):
    """
    Check rate limits for magic link requests.
    
    Returns error message if rate limit exceeded, None if allowed.
    
    Args:
        ip (str): Client IP address
        email (str): Email address requesting magic link
        
    Returns:
        str or None: Error message if rate limited, None if allowed
    """
    from django.core.cache import cache
    from django.conf import settings
    from django.utils import timezone
    import math
    
    rate_limit_per_hour = getattr(settings, 'MAGIC_LINK_RATE_LIMIT_PER_HOUR', 3)
    min_interval_minutes = getattr(settings, 'MAGIC_LINK_MIN_INTERVAL_MINUTES', 15)
    
    # Check IP rate limit
    ip_key = f'magic_link_ip:{ip}'
    ip_data = cache.get(ip_key, {'count': 0, 'last_request': 0})
    
    current_time = timezone.now().timestamp()
    
    # Check minimum interval for IP
    if ip_data['last_request'] > 0:
        time_since_last = current_time - ip_data['last_request']
        min_interval_seconds = min_interval_minutes * 60
        
        if time_since_last < min_interval_seconds:
            minutes_remaining = math.ceil((min_interval_seconds - time_since_last) / 60)
            return f"Too many requests from your location. Please wait {minutes_remaining} minutes before requesting another magic link. (Limit: {rate_limit_per_hour} per hour)"
    
    # Check hourly limit for IP
    if ip_data['count'] >= rate_limit_per_hour:
        return f"Too many requests from your location. Please wait up to 60 minutes before requesting another magic link. (Limit: {rate_limit_per_hour} per hour)"
    
    # Check email rate limit
    email_key = f'magic_link_email:{email}'
    email_data = cache.get(email_key, {'count': 0, 'last_request': 0})
    
    # Check minimum interval for email
    if email_data['last_request'] > 0:
        time_since_last = current_time - email_data['last_request']
        
        if time_since_last < min_interval_seconds:
            minutes_remaining = math.ceil((min_interval_seconds - time_since_last) / 60)
            return f"Too many magic links requested for {email}. Please wait {minutes_remaining} minutes before requesting another. (Limit: {rate_limit_per_hour} per hour)"
    
    # Check hourly limit for email
    if email_data['count'] >= rate_limit_per_hour:
        return f"Too many magic links requested for {email}. Please wait up to 60 minutes before requesting another. (Limit: {rate_limit_per_hour} per hour)"
    
    return None


def _update_magic_link_rate_limits(ip, email):
    """
    Update rate limit counters after successful magic link request.
    
    Args:
        ip (str): Client IP address
        email (str): Email address that received magic link
    """
    from django.core.cache import cache
    from django.utils import timezone
    
    current_time = timezone.now().timestamp()
    timeout = 3600  # 1 hour
    
    # Update IP counter
    ip_key = f'magic_link_ip:{ip}'
    ip_data = cache.get(ip_key, {'count': 0, 'last_request': 0})
    ip_data['count'] += 1
    ip_data['last_request'] = current_time
    cache.set(ip_key, ip_data, timeout)
    
    # Update email counter
    email_key = f'magic_link_email:{email}'
    email_data = cache.get(email_key, {'count': 0, 'last_request': 0})
    email_data['count'] += 1
    email_data['last_request'] = current_time
    cache.set(email_key, email_data, timeout)