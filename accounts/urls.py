"""
URL configuration for the accounts app.
"""

from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('profile/setup/', views.profile_setup, name='profile_setup'),
    path('check-username/', views.check_username_availability, name='check_username'),
    path('generate-username/', views.generate_new_username, name='generate_username'),
    path('communities/', views.community_discovery, name='community_discovery'),
    path('apply/<uuid:community_id>/', views.apply_to_community, name='apply_to_community'),
]
