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
]
