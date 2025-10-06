"""
Forms for the accounts app.

This module contains forms for user profile management, authentication,
and account-related functionality in CrowdVote.
"""

from django import forms
from django.contrib.auth import get_user_model
from .utils import verify_turnstile_token, get_client_ip

User = get_user_model()


class ProfileEditForm(forms.ModelForm):
    """
    Form for editing user profile information.
    
    Allows users to update their biography, location, social media links,
    and privacy settings for profile visibility.
    """
    
    class Meta:
        model = User
        fields = [
            'first_name', 'last_name', 'bio', 'location',
            'website_url', 'twitter_url', 'linkedin_url',
            'bio_public', 'location_public', 'social_links_public'
        ]
        
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200',
                'placeholder': 'Your first name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200',
                'placeholder': 'Your last name'
            }),
            'bio': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200',
                'rows': 4,
                'placeholder': 'Tell other community members about your background, expertise, and interests...'
            }),
            'location': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200',
                'placeholder': 'e.g., San Francisco, CA, USA'
            }),
            'website_url': forms.URLInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200',
                'placeholder': 'https://yourwebsite.com'
            }),
            'twitter_url': forms.URLInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200',
                'placeholder': 'https://twitter.com/yourusername'
            }),
            'linkedin_url': forms.URLInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-white placeholder-gray-500 dark:placeholder-gray-400 focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all duration-200',
                'placeholder': 'https://linkedin.com/in/yourprofile'
            }),
            'bio_public': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'location_public': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'social_links_public': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded'
            }),
        }
        
        help_texts = {
            'first_name': 'Your first name (visible to community members)',
            'last_name': 'Your last name (visible to community members)',
            'bio': 'Share your background and expertise to help others make delegation decisions',
            'location': 'Your general location helps build trust in the community',
            'website_url': 'Link to your personal website, blog, or professional page',
            'twitter_url': 'Your Twitter/X profile for transparency and verification',
            'linkedin_url': 'Your LinkedIn profile for professional context',
            'bio_public': 'Allow other community members to see your biography',
            'location_public': 'Allow other community members to see your location',
            'social_links_public': 'Allow other community members to see your social media links',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add labels
        self.fields['first_name'].label = 'First Name'
        self.fields['last_name'].label = 'Last Name'
        self.fields['bio'].label = 'Biography'
        self.fields['location'].label = 'Location'
        self.fields['website_url'].label = 'Website'
        self.fields['twitter_url'].label = 'Twitter/X URL'
        self.fields['linkedin_url'].label = 'LinkedIn URL'
        self.fields['bio_public'].label = 'Make biography public'
        self.fields['location_public'].label = 'Make location public'
        self.fields['social_links_public'].label = 'Make social links public'

    def clean_twitter_url(self):
        """Validate Twitter URL format."""
        url = self.cleaned_data.get('twitter_url')
        if url:
            # Check for exact domain matches, not just substring
            import re
            if not re.search(r'https?://(www\.)?(twitter\.com|x\.com)/', url):
                raise forms.ValidationError('Please enter a valid Twitter/X URL.')
        return url

    def clean_linkedin_url(self):
        """Validate LinkedIn URL format.""" 
        url = self.cleaned_data.get('linkedin_url')
        if url:
            # Check for exact domain match, not just substring
            import re
            if not re.search(r'https?://(www\.)?linkedin\.com/', url):
                raise forms.ValidationError('Please enter a valid LinkedIn URL.')
        return url


class CaptchaProtectedMagicLinkForm(forms.Form):
    """
    Form for requesting magic links with Turnstile CAPTCHA protection.
    
    Protects against automated bot signups while maintaining excellent
    user experience for legitimate users.
    """
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-lg',
            'placeholder': 'Enter your email address',
            'autocomplete': 'email'
        }),
        help_text="We'll send you a magic link to sign in instantly"
    )
    
    captcha_token = forms.CharField(
        widget=forms.HiddenInput(),
        required=False  # Will be populated by JavaScript
    )
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
    
    def clean_captcha_token(self):
        """Verify the Turnstile CAPTCHA token."""
        token = self.cleaned_data.get('captcha_token')
        
        if not self.request:
            raise forms.ValidationError("Request context required for CAPTCHA verification.")
        
        user_ip = get_client_ip(self.request)
        
        if not verify_turnstile_token(token, user_ip):
            raise forms.ValidationError(
                "CAPTCHA verification failed. Please try again. "
                "Having trouble? Email support@crowdvote.com"
            )
        
        return token
