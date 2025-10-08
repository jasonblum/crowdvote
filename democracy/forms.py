"""
Forms for the democracy app.

This module contains forms for decision creation, voting, and community management.
All forms include proper validation, security measures, and user-friendly interfaces.
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from .models import Decision, Choice, Ballot, Vote


class DecisionForm(forms.ModelForm):
    """
    Form for creating and editing community decisions.
    
    Allows community managers to create decisions with title, description,
    and voting deadline. Choices are handled separately via formsets.
    """
    
    class Meta:
        model = Decision
        fields = ['title', 'description', 'dt_close']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Enter a clear, descriptive title for this decision'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'rows': 4,
                'placeholder': 'Provide detailed context about what is being decided, why it matters, and any relevant background information...'
            }),
            'dt_close': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set minimum datetime to 1 hour from now
        min_datetime = timezone.now() + timedelta(hours=1)
        self.fields['dt_close'].widget.attrs['min'] = min_datetime.strftime('%Y-%m-%dT%H:%M')
        
        # Set default to 7 days from now if creating new decision
        if not self.instance.pk:
            default_datetime = timezone.now() + timedelta(days=7)
            self.fields['dt_close'].initial = default_datetime
    
    def clean_title(self):
        """Validate decision title."""
        title = self.cleaned_data.get('title', '').strip()
        
        if len(title) < 10:
            raise ValidationError("Title must be at least 10 characters long.")
        
        if len(title) > 200:
            raise ValidationError("Title must be no more than 200 characters.")
        
        return title
    
    def clean_description(self):
        """Validate decision description."""
        description = self.cleaned_data.get('description', '').strip()
        
        if len(description) < 50:
            raise ValidationError("Description must be at least 50 characters to provide adequate context.")
        
        return description
    
    def clean_dt_close(self):
        """Validate voting deadline."""
        dt_close = self.cleaned_data.get('dt_close')
        
        if not dt_close:
            raise ValidationError("Voting deadline is required.")
        
        # Must be at least 1 hour in the future
        min_datetime = timezone.now() + timedelta(hours=1)
        if dt_close <= min_datetime:
            raise ValidationError("Voting deadline must be at least 1 hour in the future.")
        
        # Cannot be more than 1 year in the future
        max_datetime = timezone.now() + timedelta(days=365)
        if dt_close > max_datetime:
            raise ValidationError("Voting deadline cannot be more than 1 year in the future.")
        
        return dt_close
    
    def clean(self):
        """
        Perform final validation on the form.
        
        Note: Choice validation is handled in the view using formsets
        since choices are created separately from the decision.
        """
        cleaned_data = super().clean()
        return cleaned_data


class ChoiceForm(forms.ModelForm):
    """
    Form for individual choices within a decision.
    
    Used in formsets to allow managers to add multiple choices
    to their decisions with proper validation.
    """
    
    class Meta:
        model = Choice
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'placeholder': 'Choice name (e.g., "Cathedral Gray")'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent',
                'rows': 2,
                'placeholder': 'Brief description of this choice (optional)'
            }),
        }
    
    def clean_description(self):
        """Validate choice description length."""
        description = self.cleaned_data.get('description', '').strip()
        
        if len(description) > 1000:
            raise ValidationError("Description must be no more than 1000 characters.")
        
        return description
    
    def clean_title(self):
        """Validate choice title."""
        title = self.cleaned_data.get('title', '').strip()
        
        if not title:
            raise ValidationError("Choice title is required.")
        
        if len(title) < 2:
            raise ValidationError("Choice title must be at least 2 characters.")
        
        if len(title) > 100:
            raise ValidationError("Choice title must be no more than 100 characters.")
        
        return title


# Create formset for managing multiple choices
ChoiceFormSet = forms.inlineformset_factory(
    Decision,
    Choice,
    form=ChoiceForm,
    extra=0,  # No extra forms beyond min_num
    min_num=2,  # Require at least 2 choices (will show 2 forms)
    max_num=10,  # Allow maximum 10 choices
    validate_min=True,
    validate_max=True,
    can_delete=True
)


class VoteForm(forms.Form):
    """
    Form for casting votes on a decision using STAR voting.
    
    Dynamically generates star rating fields for each choice in the decision
    and includes tag input for delegation purposes.
    
    Note: Anonymity is now controlled at the Membership level, not per-ballot.
    Users set their anonymity preference for the entire community, not per vote.
    """
    
    tags = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Add tags like "budget, environment, maintenance" (optional)'
        }),
        help_text="Tags help others follow your expertise on specific topics"
    )
    
    def __init__(self, decision, user=None, *args, **kwargs):
        """
        Initialize form with dynamic star rating fields for each choice.
        
        Args:
            decision: Decision instance to create vote form for
            user: User instance for setting default anonymity preference
        """
        super().__init__(*args, **kwargs)
        
        self.decision = decision
        self.user = user
        
        # Create star rating field for each choice
        for choice in decision.choices.all():
            field_name = f'choice_{choice.id}'
            self.fields[field_name] = forms.IntegerField(
                min_value=0,
                max_value=5,
                initial=0,
                widget=forms.HiddenInput(),  # Hidden - controlled by JavaScript stars
                label=choice.title,
                help_text=choice.description
            )
    
    def clean_tags(self):
        """Validate and clean tags input."""
        tags = self.cleaned_data.get('tags', '').strip()
        
        if not tags:
            return ''
        
        # Split by comma, clean each tag, remove duplicates
        tag_list = []
        for tag in tags.split(','):
            clean_tag = tag.strip().lower()
            if clean_tag and len(clean_tag) >= 2 and clean_tag not in tag_list:
                if len(clean_tag) <= 30:  # Max tag length
                    tag_list.append(clean_tag)
        
        # Limit to 10 tags maximum
        if len(tag_list) > 10:
            raise ValidationError("Maximum 10 tags allowed.")
        
        return ', '.join(tag_list)
    
    def clean(self):
        """Validate that all choices have been rated."""
        cleaned_data = super().clean()
        
        # Check that at least one choice has a non-zero rating
        has_rating = False
        for field_name, value in cleaned_data.items():
            if field_name.startswith('choice_') and value and value > 0:
                has_rating = True
                break
        
        if not has_rating:
            raise ValidationError("You must rate at least one choice with 1 or more stars.")
        
        return cleaned_data
    
    def get_choice_ratings(self):
        """
        Extract choice ratings from cleaned form data.
        
        Returns:
            dict: Mapping of choice_id to star rating
        """
        ratings = {}
        for field_name, value in self.cleaned_data.items():
            if field_name.startswith('choice_'):
                choice_id = field_name.replace('choice_', '')
                # Keep choice_id as string since we're using UUIDs
                ratings[choice_id] = value or 0
        return ratings


class DecisionSearchForm(forms.Form):
    """
    Form for searching and filtering decisions.
    
    Allows users to search decisions by title, filter by status,
    and sort by various criteria.
    """
    
    STATUS_CHOICES = [
        ('', 'All Decisions'),
        ('active', 'Active (Voting Open)'),
        ('upcoming', 'Upcoming'),
        ('closed', 'Closed'),
        ('draft', 'Drafts (Managers Only)'),
    ]
    
    SORT_CHOICES = [
        ('-dt_close', 'Deadline (Soonest First)'),
        ('dt_close', 'Deadline (Latest First)'),
        ('-created', 'Created (Newest First)'),
        ('created', 'Created (Oldest First)'),
        ('title', 'Title (A-Z)'),
        ('-title', 'Title (Z-A)'),
    ]
    
    search = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent',
            'placeholder': 'Search decisions by title or description...'
        })
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
    
    sort = forms.ChoiceField(
        choices=SORT_CHOICES,
        required=False,
        initial='-dt_close',
        widget=forms.Select(attrs={
            'class': 'px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent'
        })
    )
