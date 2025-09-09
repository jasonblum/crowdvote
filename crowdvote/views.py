from django.shortcuts import render, redirect
from django.conf import settings
from django.urls import reverse
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
    In production, shows an under construction page to prevent premature access.
    
    Logged-in users are redirected to their profile page instead of seeing the landing page.
    """
    # Redirect logged-in users to their profile page
    if request.user.is_authenticated:
        return redirect('accounts:member_profile', username=request.user.username)
    
    # Show under construction page in production
    if not settings.DEBUG:
        return render(request, 'under_construction.html')
    
    context = {
        'slogans': get_slogans()
    }
    return render(request, 'home.html', context)


def docs(request):
    """
    Public documentation page with CrowdVote overview, documentation, and FAQs.
    Accessible without authentication.
    """
    return render(request, 'docs.html')
