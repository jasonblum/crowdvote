"""
Template tags for member-related functionality in CrowdVote.

This module provides template tags for rendering member profiles, usernames,
and delegation-related UI components throughout the application.
"""

from django import template
from django.urls import reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.inclusion_tag('accounts/components/username_link.html')
def username_link(user, community=None, css_class="username-link hover:text-blue-600 transition-colors"):
    """
    Render a clickable username link to member profile.
    
    Args:
        user: User object to link to
        community: Community context for profile link (optional)
        css_class: CSS classes to apply to the link
        
    Returns:
        Context dict for the username link template
    """
    # Get display name using the model method
    display_name = user.get_display_name() if hasattr(user, 'get_display_name') else user.username
    
    context = {
        'user': user,
        'community': community,
        'css_class': css_class,
        'display_name': display_name,
    }
    
    if community:
        try:
            context['profile_url'] = reverse('accounts:member_profile', args=[community.id, user.id])
        except:
            context['profile_url'] = None
    else:
        # If no community context, we can't link to profile page yet
        context['profile_url'] = None
        
    return context


@register.simple_tag
def username_text_link(username, community_id, user_id):
    """
    Generate a simple text-based username link for use in plain text contexts like delegation trees.
    
    Args:
        username: The username to display
        community_id: UUID of the community for context
        user_id: UUID of the user
        
    Returns:
        HTML anchor tag as safe string
    """
    try:
        profile_url = reverse('accounts:member_profile', args=[community_id, user_id])
        return format_html(
            '<a href="{}" class="text-blue-600 hover:text-blue-800 underline">{}</a>',
            profile_url,
            username
        )
    except:
        # If URL generation fails, just return the username
        return username


@register.simple_tag
def user_avatar(user, size=32):
    """
    Generate Jdenticon avatar for a user.
    
    Args:
        user: User object
        size: Size in pixels (default: 32)
        
    Returns:
        Safe HTML for SVG avatar
    """
    return mark_safe(user.get_avatar_html(size))
