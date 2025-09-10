"""
Shared models for the CrowdVote application.

This module contains abstract base models and common utilities that are shared
across all CrowdVote Django apps to ensure consistency and reduce code duplication.
"""

import uuid
from django.db import models


class BaseModel(models.Model):
    """
    Abstract base model that provides common fields for all CrowdVote models.
    
    This model provides:
    - UUID primary key for enhanced security and scalability
    - Automatic timestamp tracking for created and modified dates
    - Consistent field naming and behavior across all models
    
    All CrowdVote models should inherit from this base class to ensure
    consistent data structure and behavior throughout the application.
    
    Attributes:
        id (UUIDField): Primary key using UUID4 for security and uniqueness
        created (DateTimeField): Timestamp when the record was created
        modified (DateTimeField): Timestamp when the record was last modified
    """
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False,
        help_text="Unique identifier for this record"
    )
    created = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when this record was created"
    )
    modified = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when this record was last modified"
    )
    
    class Meta:
        abstract = True
