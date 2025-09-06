from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, Following


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    """
    Admin interface for CustomUser model.
    """
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined']
    list_filter = ['is_staff', 'is_superuser', 'is_active', 'date_joined']
    search_fields = ['username', 'first_name', 'last_name', 'email']
    ordering = ['username']


@admin.register(Following)
class FollowingAdmin(admin.ModelAdmin):
    """
    Admin interface for Following relationships.
    """
    list_display = ['follower', 'followee', 'created']
    list_filter = ['created', 'modified']
    search_fields = ['follower__username', 'followee__username']
    raw_id_fields = ['follower', 'followee']
    
    # TODO: Re-enable when tagging is implemented
    # def tag_list(self, obj):
    #     """Display tags as a comma-separated list."""
    #     return ", ".join(o.name for o in obj.tags.all())
    # tag_list.short_description = 'Tags'
