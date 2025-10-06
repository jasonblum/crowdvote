"""
Custom allauth adapters for CrowdVote.

This module contains customizations for django-allauth behavior, including
graceful handling of email sending failures and user-friendly error messages.
"""

from allauth.account.adapter import DefaultAccountAdapter
from django.contrib import messages
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class CrowdVoteAccountAdapter(DefaultAccountAdapter):
    """
    Custom allauth adapter that handles email sending gracefully.
    
    Provides user-friendly error messages when email sending fails,
    particularly useful during the demo phase with SendGrid's free tier
    (100 emails/day limit).
    """
    
    def send_mail(self, template_prefix, email, context):
        """
        Override send_mail to handle errors gracefully with humor.
        
        If email sending fails (e.g., daily SendGrid limit reached),
        we'll show a friendly message instead of a scary error.
        """
        try:
            # Try to send the email normally
            super().send_mail(template_prefix, email, context)
            logger.info(f"Successfully sent {template_prefix} email to {email}")
            
        except Exception as e:
            logger.error(f"Failed to send {template_prefix} email to {email}: {str(e)}")
            
            # Check if this is a SendGrid quota/limit error
            error_str = str(e).lower()
            is_quota_error = any(keyword in error_str for keyword in [
                'quota', 'limit', 'rate', 'daily', 'exceeded', '550', '421'
            ])
            
            if is_quota_error and not settings.DEBUG:
                # Humorous message for quota issues in production
                raise Exception(
                    "🤦‍♂️ Oops! Jason's being too cheap and hit the daily email limit. "
                    "Try again tomorrow or send him an angry email at jason@crowdvote.org "
                    "demanding he upgrade to a real email service! "
                    "(We're on SendGrid's free tier: 100 emails/day)"
                )
            elif not settings.DEBUG:
                # Generic production error
                raise Exception(
                    "📧 Email sending is temporarily unavailable. "
                    "Please try again in a few minutes or contact support."
                )
            else:
                # In development, show the actual error
                raise e
    
    def get_email_confirmation_url(self, request, emailconfirmation):
        """
        Customize the email confirmation URL if needed.
        Currently uses the default behavior.
        """
        return super().get_email_confirmation_url(request, emailconfirmation)
    
    def save_user(self, request, user, form, commit=True):
        """
        Save user with any CrowdVote-specific customizations.
        
        This is where we could add custom fields, generate usernames,
        or perform other user setup tasks.
        """
        user = super().save_user(request, user, form, commit=False)
        
        # TODO: Generate safe username here if not provided
        # from .utils import generate_safe_username
        # if not user.username:
        #     user.username = generate_safe_username()
        
        if commit:
            user.save()
        return user
