"""
URL configuration for crowdvote project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('docs/', views.docs, name='docs'),
    path('slogans/', views.slogans, name='slogans'),
    path('docs/', views.docs, name='docs'),
    path('status/global-calculations/', views.global_calculation_status, name='global_calculation_status'),
    path(f'{settings.ADMIN_URL}/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('', include('security.urls')),
    path('', include('democracy.urls')),
    path('network-visualization/', TemplateView.as_view(template_name='network visualization.html'), name='network_visualization'),
    path('vote-inheritance/', TemplateView.as_view(template_name='vote-inheritance-tree.html'), name='vote_inheritance'),
]

# Add Debug Toolbar URLs when in DEBUG mode (but not during testing)
import sys
TESTING = 'pytest' in sys.modules or 'test' in sys.argv

if settings.DEBUG and not TESTING:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
