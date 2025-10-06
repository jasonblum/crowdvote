from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group
from django.contrib.sites.models import Site
from django.utils.html import format_html

from .models import CustomUser
# TODO (Change 0002): Re-enable after moving CommunityApplication to democracy app
# from .models import CommunityApplication

# Unregister built-in models to keep admin interface clean
admin.site.unregister(Group)
admin.site.unregister(Site)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    Admin interface for CustomUser model.
    """
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined']
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'date_joined']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    ordering = ['username']


# TODO (Change 0002): CommunityApplicationAdmin removed temporarily
# Will be re-added to democracy app admin after CommunityApplication is moved
