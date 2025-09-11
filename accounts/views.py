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


def member_profile_community(request, community_id, member_id):
    """
    Display a member's profile within a specific community context.
    
    Shows member information, delegation relationships, and community-specific
    participation details for better delegation decision making.
    """
    from django.shortcuts import get_object_or_404
    from democracy.models import Community
    
    community = get_object_or_404(Community, id=community_id)
    member = get_object_or_404(User, id=member_id)
    
    # Check if member is actually in this community
    try:
        membership = community.memberships.get(member=member)
    except:
        from django.http import Http404
        raise Http404("Member not found in this community")
    
    # Get tag usage frequency for this member
    tag_usage = member.get_tag_usage_frequency()
    
    # Get delegation network information
    delegation_network = member.get_delegation_network()
    
    # Get member's communities (only show those visible to current user)
    member_communities = []
    if request.user.is_authenticated:
        # Show communities where both users are members
        user_community_ids = set(
            request.user.memberships.values_list('community_id', flat=True)
        )
        member_memberships = member.memberships.select_related('community').filter(
            community_id__in=user_community_ids
        )
        member_communities = [m.community for m in member_memberships]
    
    # Check privacy settings
    can_view_bio = member.bio_public or request.user == member
    can_view_location = member.location_public or request.user == member
    can_view_social_links = member.social_links_public or request.user == member
    
    context = {
        'member': member,
        'community': community,
        'membership': membership,
        'tag_usage': tag_usage,
        'delegation_network': delegation_network,
        'member_communities': member_communities,
        'can_view_bio': can_view_bio,
        'can_view_location': can_view_location,
        'can_view_social_links': can_view_social_links,
        'is_own_profile': request.user == member,
    }
    
    return render(request, 'accounts/member_profile_community.html', context)


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