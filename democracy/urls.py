"""
URL configuration for the democracy app.
"""

from django.urls import path
from . import views

app_name = 'democracy'

urlpatterns = [
    # Community detail pages
    path('communities/<uuid:community_id>/', views.community_detail, name='community_detail'),
]
