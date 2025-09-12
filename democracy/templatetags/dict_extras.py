"""
Template filters for dictionary operations.
"""

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary by key.
    
    Usage: {{ mydict|get_item:mykey }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def split(value, delimiter=','):
    """
    Split a string by delimiter and return a list.
    
    Usage: {{ "apple,banana,grape"|split:"," }}
    """
    if value is None:
        return []
    return str(value).split(delimiter)


@register.filter
def trim(value):
    """
    Remove leading and trailing whitespace from a string.
    
    Usage: {{ " apple "|trim }}
    """
    if value is None:
        return ''
    return str(value).strip()
