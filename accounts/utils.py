"""
Utility functions for the accounts app.

This module contains helper functions for user account management, including
safe username generation and validation utilities.
"""

from wonderwords import RandomWord
from django.contrib.auth import get_user_model

User = get_user_model()


def generate_safe_username():
    """
    Generate a safe, family-friendly username using adjective + noun combinations.
    
    Uses the wonderwords library to create memorable usernames like "WiseElephant"
    or "QuietGardener". Handles collisions by appending numbers (e.g., "WiseElephant2").
    
    The wonderwords library filters out offensive content and generates appropriate
    combinations suitable for all ages.
    
    Returns:
        str: A unique, family-friendly username
        
    Examples:
        - "WiseElephant"
        - "QuietGardener" 
        - "BrightMountain"
        - "CreativeRiver42" (if collision occurred)
    """
    rw = RandomWord()
    
    # Try up to 100 different base combinations before giving up
    for attempt in range(100):
        try:
            # Generate adjective + noun combination
            adjective = rw.word(
                word_min_length=4, 
                word_max_length=8, 
                include_parts_of_speech=["adjective"]
            )
            noun = rw.word(
                word_min_length=4, 
                word_max_length=8,
                include_parts_of_speech=["noun"]
            )
            
            # Create title-cased username
            base_username = f"{adjective.title()}{noun.title()}"
            
            # Check if base username is available
            if not User.objects.filter(username__iexact=base_username).exists():
                return base_username
            
            # Try with number suffixes if base is taken
            for suffix in range(2, 1000):
                numbered_username = f"{base_username}{suffix}"
                if not User.objects.filter(username__iexact=numbered_username).exists():
                    return numbered_username
                    
        except Exception:
            # If wonderwords fails, continue to next attempt
            continue
    
    # Fallback if all attempts fail (very unlikely)
    import uuid
    fallback = f"User{str(uuid.uuid4())[:8].title()}"
    return fallback


def is_username_available(username):
    """
    Check if a username is available (not taken by another user).
    
    Performs case-insensitive check to prevent confusing similar usernames.
    
    Args:
        username (str): The username to check
        
    Returns:
        bool: True if username is available, False if taken
    """
    if not username or len(username.strip()) == 0:
        return False
        
    return not User.objects.filter(username__iexact=username.strip()).exists()


def validate_username(username):
    """
    Validate a username according to CrowdVote rules.
    
    Args:
        username (str): The username to validate
        
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
        
    Examples:
        >>> validate_username("WiseElephant")
        (True, None)
        
        >>> validate_username("ab")
        (False, "Username must be between 3 and 30 characters")
        
        >>> validate_username("User@Name")
        (False, "Username can only contain letters and numbers")
    """
    if not username:
        return False, "Username is required"
    
    username = username.strip()
    
    # Length check
    if len(username) < 3:
        return False, "Username must be at least 3 characters"
    if len(username) > 30:
        return False, "Username must be no more than 30 characters"
    
    # Character check - only letters and numbers
    if not username.isalnum():
        return False, "Username can only contain letters and numbers"
    
    # Availability check
    if not is_username_available(username):
        return False, "Username is already taken"
    
    return True, None
