from django.shortcuts import render, redirect
from django.conf import settings
from django.urls import reverse
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
import os
import re


def get_slogans():
    """
    Parse slogans from markdown file and convert to HTML.
    """
    slogans_file = os.path.join(settings.BASE_DIR, 'slogans.md')
    slogans = []
    
    try:
        with open(slogans_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract lines that aren't headers or empty
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and line != '':
                # Convert markdown to HTML
                # **bold** -> <strong>bold</strong>
                line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', line)
                # *italic* -> <em>italic</em>
                line = re.sub(r'\*(.*?)\*', r'<em>\1</em>', line)
                # ~~strikethrough~~ -> <del>strikethrough</del>
                line = re.sub(r'~~(.*?)~~', r'<del>\1</del>', line)
                slogans.append(line)
    
    except FileNotFoundError:
        # Fallback slogans if file not found
        slogans = [
            "Think globally, follow locally!",
            "<em>Real Democracy</em> happens BETWEEN elections!",
            "Democracy ...we've been doing it <strong>wrong</strong>."
        ]
    
    return slogans


def home(request):
    """
    Home page view displaying the CrowdVote welcome message and key features.
    
    Logged-in users are redirected to their profile page instead of seeing the landing page.
    """
    # Redirect logged-in users to their profile page
    if request.user.is_authenticated:
        return redirect('accounts:member_profile', username=request.user.username)
    
    context = {
        'slogans': get_slogans(),
        'TURNSTILE_SITE_KEY': settings.TURNSTILE_SITE_KEY
    }
    return render(request, 'home.html', context)


def docs(request):
    """
    Public documentation page with CrowdVote overview, documentation, and FAQs.
    Accessible without authentication.
    """
    return render(request, 'docs.html')


def slogans(request):
    """
    Public slogans page displaying all CrowdVote slogans.
    Reads from slogans.md file to maintain single source of truth.
    Accessible without authentication.
    """
    slogans_list = get_slogans()
    
    # Define color gradients for cycling
    color_gradients = [
        'from-blue-50 to-indigo-50 dark:from-blue-900/20 dark:to-indigo-900/20 border-blue-200 dark:border-blue-700',
        'from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border-green-200 dark:border-green-700',
        'from-purple-50 to-violet-50 dark:from-purple-900/20 dark:to-violet-900/20 border-purple-200 dark:border-purple-700',
        'from-red-50 to-pink-50 dark:from-red-900/20 dark:to-pink-900/20 border-red-200 dark:border-red-700',
        'from-yellow-50 to-orange-50 dark:from-yellow-900/20 dark:to-orange-900/20 border-yellow-200 dark:border-yellow-700',
        'from-teal-50 to-cyan-50 dark:from-teal-900/20 dark:to-cyan-900/20 border-teal-200 dark:border-teal-700',
        'from-indigo-50 to-blue-50 dark:from-indigo-900/20 dark:to-blue-900/20 border-indigo-200 dark:border-indigo-700',
        'from-rose-50 to-red-50 dark:from-rose-900/20 dark:to-red-900/20 border-rose-200 dark:border-rose-700',
        'from-emerald-50 to-green-50 dark:from-emerald-900/20 dark:to-green-900/20 border-emerald-200 dark:border-emerald-700',
        'from-violet-50 to-purple-50 dark:from-violet-900/20 dark:to-purple-900/20 border-violet-200 dark:border-violet-700',
        'from-amber-50 to-yellow-50 dark:from-amber-900/20 dark:to-yellow-900/20 border-amber-200 dark:border-amber-700',
        'from-cyan-50 to-teal-50 dark:from-cyan-900/20 dark:to-teal-900/20 border-cyan-200 dark:border-cyan-700',
    ]
    
    # Pair each slogan with its color gradient
    slogans_with_colors = []
    for i, slogan in enumerate(slogans_list):
        color_class = color_gradients[i % len(color_gradients)]
        slogans_with_colors.append({
            'text': slogan,
            'color_class': color_class
        })
    
    context = {
        'slogans_with_colors': slogans_with_colors,
        'total_count': len(slogans_list)
    }
    return render(request, 'slogans.html', context)


@login_required
def global_calculation_status(request):
    """
    Return JSON status of currently processing decisions and recent activity for communities where the user is a member.
    
    Returns:
        JsonResponse: {
            'has_active_calculations': bool,
            'has_recent_activity': bool,
            'decisions': [
                {
                    'id': 'uuid',
                    'title': 'Decision Title',
                    'community_name': 'Community Name',
                    'status': 'Creating Snapshot...',
                    'status_type': 'active',  # 'active', 'completed', 'failed'
                    'timestamp': '2025-09-19T14:30:00Z',
                    'url': '/communities/uuid/decisions/uuid/results/'
                }
            ]
        }
    """
    from democracy.models import DecisionSnapshot, Decision
    
    # Get communities where the user is a member
    user_community_ids = list(request.user.memberships.values_list('community_id', flat=True))
    
    # Define active and recent activity states
    active_states = ['creating', 'ready', 'staging', 'tallying']
    recent_activity_states = ['completed', 'failed_snapshot', 'failed_staging', 'failed_tallying', 'corrupted']
    
    # Get 24 hours ago for recent activity cutoff
    twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
    
    decisions_data = []
    active_decision_ids = set()
    
    # Find most recent snapshot per decision with active processing states
    # Only include decisions from communities where the user is a member
    active_snapshots = DecisionSnapshot.objects.filter(
        calculation_status__in=active_states,
        decision__dt_close__gt=timezone.now(),
        decision__community_id__in=user_community_ids
    ).select_related('decision__community').order_by('decision_id', '-created_at').distinct('decision_id')
    
    for snapshot in active_snapshots:
        active_decision_ids.add(snapshot.decision.id)
        
        # Map calculation status to display text
        status_map = {
            'creating': 'Creating Snapshot...',
            'ready': 'Ready for Calculation',
            'staging': 'Calculating Votes...',
            'tallying': 'Tallying Results...'
        }
        
        decisions_data.append({
            'id': str(snapshot.decision.id),
            'title': snapshot.decision.title,
            'community_name': snapshot.decision.community.name,
            'status': status_map.get(snapshot.calculation_status, 'Processing...'),
            'status_type': 'active',
            'timestamp': snapshot.created_at.isoformat(),
            'url': f'/communities/{snapshot.decision.community.id}/decisions/{snapshot.decision.id}/results/'
        })
    
    # Find recent activity (last 24 hours) for decisions not already in active processing
    # Only include decisions from communities where the user is a member
    recent_snapshots = DecisionSnapshot.objects.filter(
        calculation_status__in=recent_activity_states,
        created_at__gte=twenty_four_hours_ago,
        decision__dt_close__gt=timezone.now(),
        decision__community_id__in=user_community_ids
    ).exclude(
        decision_id__in=active_decision_ids
    ).select_related('decision__community').order_by('decision_id', '-created_at').distinct('decision_id')
    
    for snapshot in recent_snapshots:
        # Determine status display based on calculation_status
        status_map = {
            'completed': '✅ Completed',
            'failed_snapshot': '❌ Snapshot Failed',
            'failed_staging': '❌ Calculation Failed',
            'failed_tallying': '❌ Tally Failed',
            'corrupted': '❌ Data Corrupted'
        }
        
        # Calculate time ago
        time_diff = timezone.now() - snapshot.created_at
        total_minutes = int(time_diff.total_seconds() / 60)
        if total_minutes < 60:  # Less than 1 hour
            time_ago = f"{max(1, total_minutes)}m ago"  # Show at least 1m ago
        else:  # 1+ hours
            hours = int(time_diff.total_seconds() / 3600)
            time_ago = f"{hours}h ago"
        
        status_display = f"{status_map.get(snapshot.calculation_status, 'Unknown')} ({time_ago})"
        
        decisions_data.append({
            'id': str(snapshot.decision.id),
            'title': snapshot.decision.title,
            'community_name': snapshot.decision.community.name,
            'status': status_display,
            'status_type': 'completed' if snapshot.calculation_status == 'completed' else 'failed',
            'timestamp': snapshot.created_at.isoformat(),
            'url': f'/communities/{snapshot.decision.community.id}/decisions/{snapshot.decision.id}/results/'
        })
    
    # Determine overall status
    has_active_calculations = len([d for d in decisions_data if d['status_type'] == 'active']) > 0
    has_recent_activity = len(decisions_data) > 0
    
    return JsonResponse({
        'has_active_calculations': has_active_calculations,
        'has_recent_activity': has_recent_activity,
        'decisions': decisions_data
    })
