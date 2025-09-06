"""
User account models for the CrowdVote application.

This module contains models related to user accounts, authentication, and the
following/delegation system that enables CrowdVote's delegative democracy features.
"""

from django.contrib.auth.models import AbstractUser
from django.db import models

from shared.models import BaseModel


class CustomUser(AbstractUser):
    """
    Custom user model extending Django's AbstractUser.
    
    This model extends Django's built-in AbstractUser to provide future flexibility
    for adding CrowdVote-specific user fields without requiring complex migrations.
    Starting with a custom user model is a Django best practice that prevents
    migration headaches later.
    
    Currently identical to AbstractUser but provides a foundation for future
    enhancements such as:
    - User preferences for voting and delegation
    - Community-specific settings
    - Privacy and anonymity controls
    - Reputation or influence tracking
    
    Inherits all standard Django user fields:
    - username, email, first_name, last_name
    - password, is_active, is_staff, is_superuser
    - date_joined, last_login
    - groups and user_permissions
    """
    
    class Meta:
        ordering = ["username"]
        verbose_name = "User"
        verbose_name_plural = "Users"

    def __str__(self):
        """Return string representation of the user."""
        return self.username

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
