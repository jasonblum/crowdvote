"""
URL configuration for the democracy app.
"""

from django.urls import path
from . import views

app_name = 'democracy'

urlpatterns = [
    # Community detail pages
    path('communities/<uuid:community_id>/', views.community_detail, name='community_detail'),
    
    # Community management
    path('communities/<uuid:community_id>/manage/', views.community_manage, name='community_manage'),
    path('communities/<uuid:community_id>/applications/<uuid:application_id>/', views.manage_application, name='manage_application'),
    
    # Decision management
    path('communities/<uuid:community_id>/decisions/', views.decision_list, name='decision_list'),
    path('communities/<uuid:community_id>/decisions/create/', views.decision_create, name='decision_create'),
    path('communities/<uuid:community_id>/decisions/<uuid:decision_id>/', views.decision_detail, name='decision_detail'),
    path('communities/<uuid:community_id>/decisions/<uuid:decision_id>/edit/', views.decision_edit, name='decision_edit'),
    path('communities/<uuid:community_id>/decisions/<uuid:decision_id>/vote/', views.vote_submit, name='vote_submit'),
    path('communities/<uuid:community_id>/decisions/<uuid:decision_id>/recalculate/', views.manual_recalculation, name='manual_recalculation'),
    path('communities/<uuid:community_id>/decisions/<uuid:decision_id>/status/', views.calculation_status, name='calculation_status'),
    # Plan #8: Snapshot detail page (Phase 7)
    path('communities/<uuid:community_id>/decisions/<uuid:decision_id>/snapshots/<uuid:snapshot_id>/', views.snapshot_detail, name='snapshot_detail'),
    
    # Follow/Unfollow
    path('communities/<uuid:community_id>/follow/<uuid:member_id>/', views.follow_modal, name='follow_modal'),
    path('communities/<uuid:community_id>/follow/<uuid:member_id>/save/', views.follow_member, name='follow_member'),
    path('communities/<uuid:community_id>/unfollow/<uuid:member_id>/', views.unfollow_member, name='unfollow_member'),
    
    # Membership Settings (Anonymity Toggle)
    path('communities/<uuid:community_id>/membership-settings/', views.membership_settings_modal, name='membership_settings_modal'),
    path('communities/<uuid:community_id>/membership-settings/save/', views.membership_settings_save, name='membership_settings_save'),
    
    # Network Visualization Refresh
    path('communities/<uuid:community_id>/network/refresh/', views.refresh_network, name='refresh_network'),
]
