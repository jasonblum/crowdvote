from django.shortcuts import render
from django.conf import settings


def home(request):
    """
    Home page view displaying the CrowdVote welcome message and key features.
    In production, shows an under construction page to prevent premature access.
    """
    # Show under construction page in production
    if not settings.DEBUG:
        return render(request, 'under_construction.html')
    return render(request, 'home.html')


def docs(request):
    """
    Public documentation page with CrowdVote overview, documentation, and FAQs.
    Accessible without authentication.
    """
    return render(request, 'docs.html')
