"""
URL configuration for the accounts app.
"""

from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Magic link authentication
    path('request-magic-link/', views.request_magic_link, name='request_magic_link'),
    path('magic-login/<str:token>/', views.magic_link_login, name='magic_link_login'),
    
    # User dashboard and profile
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/setup/', views.profile_setup, name='profile_setup'),
    path('check-username/', views.check_username_availability, name='check_username'),
    path('generate-username/', views.generate_new_username, name='generate_username'),
    
    # Community features
    path('communities/', views.community_discovery, name='community_discovery'),
    path('apply/<uuid:community_id>/', views.apply_to_community, name='apply_to_community'),
    path('leave/<uuid:community_id>/', views.leave_community, name='leave_community'),
    
    # Member profiles
    path('member/<str:username>/', views.member_profile, name='member_profile'),
    path('communities/<uuid:community_id>/members/<int:member_id>/', views.member_profile_community, name='member_profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
]
