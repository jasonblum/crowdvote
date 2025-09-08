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
    path('communities/<uuid:community_id>/decisions/<uuid:decision_id>/results/', views.decision_results, name='decision_results'),
]
