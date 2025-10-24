"""
Custom template filters for the notifications app.
"""

from django import template

register = template.Library()


@register.filter
def lookup(dictionary, key):
    """
    Template filter to look up a key in a dictionary.
    Usage: {{ dict|lookup:key }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def get_item(dictionary, key):
    """
    Alternative template filter for dictionary lookup.
    Usage: {{ dict|get_item:key }}
    """
    return dictionary.get(key) if dictionary else None
