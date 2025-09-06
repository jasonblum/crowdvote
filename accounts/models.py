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
