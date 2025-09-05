from django.shortcuts import render


def home(request):
    """
    Home page view displaying the CrowdVote welcome message and key features.
    """
    return render(request, 'home.html')
