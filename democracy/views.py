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
from django.utils import timezone

from .models import Community, Decision, Membership, Ballot, Choice, Vote

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
        
        if form.is_valid():
            # Create decision but don't save yet
            decision = form.save(commit=False)
            decision.community = community
            
            # Handle draft vs publish
            action = request.POST.get('action')
            if action == 'save_draft':
                decision.dt_close = None  # Null means draft
            
            decision.save()
            
            # Handle choices formset
            choice_formset = ChoiceFormSet(request.POST, instance=decision)
            if choice_formset.is_valid():
                choice_formset.save()
                
                if action == 'save_draft':
                    messages.success(request, f'Decision "{decision.title}" saved as draft.')
                    return redirect('democracy:decision_edit', community_id=community_id, decision_id=decision.id)
                else:
                    messages.success(request, f'Decision "{decision.title}" published successfully!')
                    return redirect('democracy:decision_detail', community_id=community_id, decision_id=decision.id)
            else:
                # Formset errors - decision was saved but choices weren't
                messages.error(request, "Please fix the errors in the choices below.")
        else:
            # Form errors
            choice_formset = ChoiceFormSet(request.POST)
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
    try:
        user_ballot = Ballot.objects.get(decision=decision, voter=request.user)
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
    
    context = {
        'community': community,
        'user_membership': user_membership,
        'decision': decision,
        'user_ballot': user_ballot,
        'status': status,
        'can_vote': status == 'active' and user_membership.is_voting_community_member,
        'can_edit': (user_membership.is_community_manager and 
                    not decision.ballots.exists() and 
                    status in ['draft', 'active']),
        'stats': {
            'total_ballots': total_ballots,
            'voting_members': voting_members,
            'participation_rate': round(participation_rate, 1),
        },
        'current_results': current_results,
    }
    
    return render(request, 'democracy/decision_detail.html', context)


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
    
    Handles STAR voting submission with tag input and anonymity preferences.
    Creates or updates the user's ballot and individual choice votes.
    
    Args:
        request: Django request object
        community_id: UUID of the community
        decision_id: UUID of the decision
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
        ballot, created = Ballot.objects.get_or_create(
            decision=decision,
            voter=request.user,
            defaults={
                'is_calculated': False,
                'is_anonymous': form.cleaned_data.get('is_anonymous', True),
                'tags': form.cleaned_data.get('tags', ''),
            }
        )
        
        # Update ballot if it already existed
        if not created:
            ballot.is_anonymous = form.cleaned_data.get('is_anonymous', True)
            ballot.tags = form.cleaned_data.get('tags', '')
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
        
        # Process all community members to build delegation tree
        for membership in community.memberships.all():
            stage_ballots_service.get_or_calculate_ballot(
                decision=decision, voter=membership.member
            )
        
        # Get the delegation tree data for this decision
        delegation_tree_data = stage_ballots_service.delegation_tree_data.copy()
        
        # Calculate basic stats
        total_ballots = decision.ballots.count()
        manual_ballots = decision.ballots.filter(is_calculated=False).count()
        calculated_ballots = decision.ballots.filter(is_calculated=True).count()
        voting_members = community.get_voting_members().count()
        participation_rate = (total_ballots / voting_members * 100) if voting_members > 0 else 0
        
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
    
    # Get choices with basic stats
    choices = decision.choices.all()
    choice_stats = {}
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
    }
    
    return render(request, 'democracy/decision_results.html', context)
