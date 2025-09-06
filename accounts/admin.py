from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from .models import CustomUser, Following, CommunityApplication


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
    list_display = ['follower', 'followee', 'tags_display', 'order', 'created']
    list_filter = ['order', 'created', 'modified']
    search_fields = ['follower__username', 'followee__username', 'tags']
    raw_id_fields = ['follower', 'followee']
    
    def tags_display(self, obj):
        """Display tags as a comma-separated list."""
        return obj.tags if obj.tags else "(all tags)"
    tags_display.short_description = 'Tags'


@admin.register(CommunityApplication)
class CommunityApplicationAdmin(admin.ModelAdmin):
    """Admin interface for community membership applications."""
    list_display = [
        'user', 'community', 'status', 'created', 
        'reviewed_by', 'reviewed_at', 'application_preview'
    ]
    list_filter = ['status', 'created', 'reviewed_at', 'community']
    search_fields = [
        'user__username', 'user__email', 'community__name', 
        'application_message', 'reviewer_notes'
    ]
    ordering = ['-created']
    readonly_fields = ['created', 'modified']
    
    fieldsets = (
        ('Application Details', {
            'fields': ('user', 'community', 'status', 'application_message')
        }),
        ('Review Information', {
            'fields': ('reviewed_by', 'reviewed_at', 'reviewer_notes'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created', 'modified'),
            'classes': ('collapse',)
        })
    )
    
    def application_preview(self, obj):
        """Show preview of application message."""
        if obj.application_message:
            preview = obj.application_message[:50]
            if len(obj.application_message) > 50:
                preview += "..."
            return preview
        return "(no message)"
    application_preview.short_description = "Application Message"
    
    def get_queryset(self, request):
        """Optimize queryset with select_related."""
        return super().get_queryset(request).select_related(
            'user', 'community', 'reviewed_by'
        )
    
    actions = ['approve_applications', 'reject_applications']
    
    def approve_applications(self, request, queryset):
        """Bulk approve selected applications."""
        approved_count = 0
        for application in queryset.filter(status='pending'):
            try:
                application.approve(request.user, 'Bulk approved via admin')
                approved_count += 1
            except ValueError:
                pass  # Skip applications that can't be approved
        
        self.message_user(
            request, 
            f"Successfully approved {approved_count} applications."
        )
    approve_applications.short_description = "Approve selected applications"
    
    def reject_applications(self, request, queryset):
        """Bulk reject selected applications."""
        rejected_count = 0
        for application in queryset.filter(status='pending'):
            try:
                application.reject(request.user, 'Bulk rejected via admin')
                rejected_count += 1
            except ValueError:
                pass  # Skip applications that can't be rejected
        
        self.message_user(
            request, 
            f"Successfully rejected {rejected_count} applications."
        )
    reject_applications.short_description = "Reject selected applications"
