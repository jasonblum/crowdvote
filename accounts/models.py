"""
User account models for the CrowdVote application.

This module contains models related to user accounts, authentication, and the
following/delegation system that enables CrowdVote's delegative democracy features.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string
import uuid

from shared.models import BaseModel


class CustomUser(AbstractUser):
    """
    Custom user model extending Django's AbstractUser.
    
    This model extends Django's built-in AbstractUser to provide CrowdVote-specific
    functionality including member profiles, social links, and delegation-related
    preferences. Starting with a custom user model is a Django best practice that 
    prevents migration headaches later.
    
    Profile fields enable rich member profiles for better delegation decisions:
    - Bio and location for member context
    - Social media links for verification and transparency
    - Privacy controls for profile field visibility
    
    Inherits all standard Django user fields:
    - username, email, first_name, last_name
    - password, is_active, is_staff, is_superuser
    - date_joined, last_login
    - groups and user_permissions
    """
    
    # Profile fields for rich member profiles
    bio = models.TextField(
        max_length=1000,
        blank=True,
        help_text="Brief biography to help other members understand your background and expertise"
    )
    location = models.CharField(
        max_length=100,
        blank=True,
        help_text="Your city, state/province, country (e.g., 'San Francisco, CA, USA')"
    )
    website_url = models.URLField(
        max_length=200,
        blank=True,
        help_text="Your personal website, blog, or professional page"
    )
    twitter_url = models.URLField(
        max_length=200,
        blank=True,
        help_text="Your Twitter/X profile URL"
    )
    linkedin_url = models.URLField(
        max_length=200,
        blank=True,
        help_text="Your LinkedIn profile URL"
    )
    
    # Privacy controls for profile visibility
    bio_public = models.BooleanField(
        default=True,
        help_text="Whether your biography is visible to other community members"
    )
    location_public = models.BooleanField(
        default=True,
        help_text="Whether your location is visible to other community members"
    )
    social_links_public = models.BooleanField(
        default=True,
        help_text="Whether your social media links are visible to other community members"
    )
    
    class Meta:
        ordering = ["username"]
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        """Return string representation of the user."""
        return self.username

    def get_display_name(self):
        """
        Return the user's preferred display name.
        
        Returns:
            str: Full name if available, otherwise username
        """
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        else:
            return self.username
    
    def get_avatar_html(self, size=32):
        """
        Generate Jdenticon avatar HTML for this user.
        
        Uses the user's ID as the seed value for consistent avatar generation.
        The avatar will be the same every time for the same user.
        
        Args:
            size (int): Size in pixels for the square avatar (default: 32)
            
        Returns:
            str: HTML for SVG avatar element with Jdenticon data attributes
        """
        return f'<svg data-jdenticon-value="{self.id}" width="{size}" height="{size}" class="rounded-full bg-gray-100 dark:bg-gray-700"></svg>'
    
    def get_avatar_value(self):
        """
        Get the value used for Jdenticon avatar generation.
        
        Returns:
            str: Consistent value for avatar generation (user ID)
        """
        return str(self.id)

    def get_tag_usage_frequency(self):
        """
        Calculate frequency of tags used by this member in their manual votes.
        
        Returns:
            list: List of tuples (tag, count) sorted by frequency (most used first)
        """
        from collections import Counter
        from democracy.models import Ballot
        
        # Get all manual ballots by this member (not calculated/inherited)
        manual_ballots = Ballot.objects.filter(
            voter=self, 
            is_calculated=False
        ).exclude(tags='')
        
        # Count tag usage frequency
        tag_counter = Counter()
        for ballot in manual_ballots:
            if ballot.tags:
                tags = [tag.strip() for tag in ballot.tags.split(',')]
                for tag in tags:
                    if tag:  # Skip empty tags
                        tag_counter[tag] += 1
        
        # Return sorted by frequency (most used first)
        return tag_counter.most_common()

    def get_delegation_network(self):
        """
        Get delegation network information for this user.
        
        Returns:
            dict: Dictionary with 'following' and 'followers' lists
        """
        following = self.followings.select_related('followee').all()
        followers = self.followers.select_related('follower').all()
        
        return {
            'following': [
                {
                    'user': f.followee,
                    'tags': f.tags.split(',') if f.tags else ['all topics'],
                    'order': f.order
                }
                for f in following
            ],
            'followers': [
                {
                    'user': f.follower,
                    'tags': f.tags.split(',') if f.tags else ['all topics'],
                    'order': f.order
                }
                for f in followers
            ]
        }

    def get_full_name_or_username(self):
        """
        Return the user's full name if available, otherwise username.
        
        Returns:
            str: Full name (first + last) if both are available, otherwise username
        """
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.username


class Following(BaseModel):
    """
    Represents a user following another user for vote delegation.
    
    This model enables CrowdVote's delegative democracy system where users can
    delegate their voting power to other users they trust. The delegation can
    be topic-specific (when tagging is implemented) or general.
    
    Key concepts:
    - Follower: The user who is delegating their vote
    - Followee: The user who receives the delegated voting power
    - Tags: Topics/categories for which the delegation applies (TODO: implement)
    
    The following relationship creates a delegation chain where:
    1. If a follower doesn't vote directly, their vote is calculated based on
       their followees' votes
    2. Multiple levels of delegation are supported (A follows B, B follows C)
    3. Circular references are prevented in the calculation algorithm
    4. Users can always override delegation by voting directly
    
    Attributes:
        follower (ForeignKey): User who is following/delegating
        followee (ForeignKey): User who is being followed
        tags (TaggableManager): Topics this following applies to (TODO: re-implement)
    """
    follower = models.ForeignKey(
        CustomUser,
        related_name="followings",
        on_delete=models.PROTECT,
        help_text="The user doing the following (delegating their vote)."
    )
    followee = models.ForeignKey(
        CustomUser,
        related_name="followers",
        on_delete=models.PROTECT,
        help_text="The user being followed (receiving delegated voting power)."
    )
    tags = models.CharField(
        max_length=500,
        blank=True,
        help_text="Comma-separated tags to follow this user on (e.g., 'environmental,fiscal'). Empty = follow on all tags."
    )
    order = models.PositiveIntegerField(
        default=1,
        help_text="Priority order for tie-breaking (lower numbers = higher priority)"
    )

    class Meta:
        ordering = [
            "follower__username",
            "order",
            "followee__username",
        ]
        verbose_name = "Following Relationship"
        verbose_name_plural = "Following Relationships"
        # TODO: Add unique constraint when tags are implemented to prevent
        # duplicate following relationships for the same tags

    def __str__(self):
        """Return string representation of the following relationship."""
        return f"{self.follower.username} follows {self.followee.username}"

    def clean(self):
        """
        Validate the following relationship.
        
        Raises:
            ValidationError: If user tries to follow themselves
        """
        from django.core.exceptions import ValidationError
        
        if self.follower == self.followee:
            raise ValidationError("Users cannot follow themselves.")

    def save(self, *args, **kwargs):
        """Override save to run validation."""
        self.clean()
        super().save(*args, **kwargs)


class CommunityApplication(BaseModel):
    """
    Represents a user's application to join a community.
    
    This model enables the community membership approval workflow where users
    can apply to join communities and community managers can review and approve
    or reject applications. This prevents spam and allows communities to maintain
    control over their membership.
    
    Key features:
    - Application tracking with status (pending, approved, rejected)
    - Optional application message from the user
    - Review tracking (who reviewed and when)
    - Email notifications to community managers
    - Automatic approval for public communities (future feature)
    
    Attributes:
        user (ForeignKey): The user applying for membership
        community (ForeignKey): The community being applied to
        status (CharField): Current status of the application
        application_message (TextField): Optional message from the applicant
        reviewed_by (ForeignKey): Manager who reviewed the application
        reviewed_at (DateTimeField): When the application was reviewed
        reviewer_notes (TextField): Optional notes from the reviewer
    """
    
    STATUS_CHOICES = [
        ('pending', 'Pending Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('withdrawn', 'Withdrawn by User'),
    ]
    
    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='community_applications',
        help_text="The user applying for community membership"
    )
    
    # Import Community here to avoid circular imports
    community = models.ForeignKey(
        'democracy.Community',
        on_delete=models.CASCADE,
        related_name='membership_applications',
        help_text="The community the user wants to join"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text="Current status of the membership application"
    )
    
    application_message = models.TextField(
        blank=True,
        help_text="Optional message from the user explaining why they want to join"
    )
    
    reviewed_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_applications',
        help_text="Community manager who reviewed this application"
    )
    
    reviewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the application was reviewed"
    )
    
    reviewer_notes = models.TextField(
        blank=True,
        help_text="Optional notes from the reviewer about their decision"
    )

    class Meta:
        ordering = ['-created']
        verbose_name = "Community Application"
        verbose_name_plural = "Community Applications"
        # Prevent duplicate applications
        unique_together = ['user', 'community']

    def __str__(self):
        """Return string representation of the application."""
        return f"{self.user.username} → {self.community.name} ({self.status})"
    
    @property
    def is_pending(self):
        """Check if application is still pending review."""
        return self.status == 'pending'
    
    @property
    def is_approved(self):
        """Check if application has been approved."""
        return self.status == 'approved'
    
    @property
    def can_be_reviewed(self):
        """Check if application can still be reviewed."""
        return self.status == 'pending'
    
    def approve(self, reviewer, notes=''):
        """
        Approve the application and create community membership.
        
        Args:
            reviewer (CustomUser): The manager approving the application
            notes (str): Optional notes about the approval
            
        Returns:
            Membership: The created membership object
        """
        from django.utils import timezone
        from democracy.models import Membership
        
        if not self.can_be_reviewed:
            raise ValueError(f"Cannot approve application with status: {self.status}")
        
        # Update application status
        self.status = 'approved'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.reviewer_notes = notes
        self.save()
        
        # Create community membership
        membership, created = Membership.objects.get_or_create(
            community=self.community,
            member=self.user,
            defaults={
                'is_voting_community_member': True,
                'is_community_manager': False,
                'is_anonymous_by_default': False,
            }
        )
        
        return membership
    
    def reject(self, reviewer, notes=''):
        """
        Reject the application with optional notes.
        
        Args:
            reviewer (CustomUser): The manager rejecting the application
            notes (str): Optional notes about the rejection
        """
        from django.utils import timezone
        
        if not self.can_be_reviewed:
            raise ValueError(f"Cannot reject application with status: {self.status}")
        
        self.status = 'rejected'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.reviewer_notes = notes
        self.save()
    
    def withdraw(self):
        """Allow user to withdraw their application."""
        if not self.can_be_reviewed:
            raise ValueError(f"Cannot withdraw application with status: {self.status}")
        
        self.status = 'withdrawn'
        self.save()


class MagicLink(BaseModel):
    """
    Represents a magic link token for passwordless authentication.
    
    Magic links allow users to log in by clicking a link sent to their email,
    without needing to remember passwords or enter codes. This model stores
    secure tokens that can be used once and expire after a short time.
    
    Features:
    - Works for both new and existing users
    - Secure random tokens that can't be guessed
    - Automatic expiration after 15 minutes
    - One-time use (consumed after successful login)
    - Email tracking for audit purposes
    
    Attributes:
        email (EmailField): Email address this magic link was sent to
        token (CharField): Secure random token for the magic link
        expires_at (DateTimeField): When this magic link expires
        used_at (DateTimeField): When this magic link was used (null if unused)
        created_user (ForeignKey): User created if this was for a new user
    """
    
    email = models.EmailField(
        help_text="Email address this magic link was sent to"
    )
    
    token = models.CharField(
        max_length=64,
        unique=True,
        help_text="Secure random token for the magic link URL"
    )
    
    expires_at = models.DateTimeField(
        help_text="When this magic link expires and becomes invalid"
    )
    
    used_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this magic link was successfully used (null if unused)"
    )
    
    created_user = models.ForeignKey(
        CustomUser,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        help_text="User account that was created using this magic link"
    )

    class Meta:
        ordering = ['-created']
        verbose_name = "Magic Link"
        verbose_name_plural = "Magic Links"

    def __str__(self):
        """Return string representation of the magic link."""
        status = "used" if self.used_at else ("expired" if self.is_expired else "active")
        return f"Magic link for {self.email} ({status})"

    @classmethod
    def create_for_email(cls, email):
        """
        Create a new magic link for the given email address.
        
        Args:
            email (str): Email address to create magic link for
            
        Returns:
            MagicLink: New magic link instance
        """
        # Generate secure random token
        token = get_random_string(48, 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
        
        # Set expiration to 15 minutes from now
        expires_at = timezone.now() + timezone.timedelta(minutes=15)
        
        return cls.objects.create(
            email=email,
            token=token,
            expires_at=expires_at
        )

    @property
    def is_expired(self):
        """Check if this magic link has expired."""
        return timezone.now() > self.expires_at

    @property
    def is_used(self):
        """Check if this magic link has been used."""
        return self.used_at is not None

    @property
    def is_valid(self):
        """Check if this magic link is still valid (not expired and not used)."""
        return not self.is_expired and not self.is_used

    def use(self):
        """
        Mark this magic link as used.
        
        Returns:
            bool: True if successfully marked as used, False if already used/expired
        """
        if not self.is_valid:
            return False
        
        self.used_at = timezone.now()
        self.save()
        return True

    def get_login_url(self, request=None):
        """
        Generate the complete magic link URL.
        
        Args:
            request: Django request object for building absolute URL
            
        Returns:
            str: Complete magic link URL
        """
        from django.urls import reverse
        from django.contrib.sites.models import Site
        
        path = reverse('accounts:magic_link_login', kwargs={'token': self.token})
        
        if request:
            return request.build_absolute_uri(path)
        else:
            # Fallback to site domain
            site = Site.objects.get_current()
            protocol = 'https' if site.domain != 'localhost:8000' else 'http'
            return f"{protocol}://{site.domain}{path}"
