"""
Utility functions for the democracy app.

This module contains helper functions for anonymity, hash generation,
and other democracy-related utilities.
"""

import hashlib
from django.conf import settings


def generate_username_hash(username):
    """
    Generate a one-way hash of the username for anonymity verification.
    
    Uses SHA-256 with a secret salt to create a hash that can verify
    vote authenticity without revealing the voter's identity. The hash
    is deterministic for the same username+salt combination but cannot
    be reversed without knowing the salt.
    
    Args:
        username (str): The username to hash
        
    Returns:
        str: 64-character SHA-256 hash in hexadecimal format
        
    Example:
        >>> generate_username_hash("alice")
        "a1b2c3d4e5f6..."  # 64-character hash
    """
    salt = getattr(settings, 'ANONYMITY_SALT', 'development-salt-change-in-production')
    return hashlib.sha256(f"{username}{salt}".encode()).hexdigest()


def verify_username_hash(username, hash_to_check):
    """
    Verify that a hash corresponds to a given username.
    
    This function allows verification that an anonymous vote belongs
    to a specific user without revealing their identity in the database.
    Useful for audit trails and vote verification.
    
    Args:
        username (str): The username to verify
        hash_to_check (str): The hash to verify against
        
    Returns:
        bool: True if hash matches username, False otherwise
        
    Example:
        >>> hash_val = generate_username_hash("alice")
        >>> verify_username_hash("alice", hash_val)
        True
        >>> verify_username_hash("bob", hash_val)
        False
    """
    return generate_username_hash(username) == hash_to_check
