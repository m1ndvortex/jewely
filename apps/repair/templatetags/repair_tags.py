"""
Template tags and filters for repair app.
"""

from django import template

register = template.Library()


@register.filter
def abs_value(value):
    """Return the absolute value of a number."""
    try:
        return abs(int(value))
    except (ValueError, TypeError):
        return 0


@register.filter
def multiply(value, arg):
    """Multiply value by arg."""
    try:
        return int(value) * int(arg)
    except (ValueError, TypeError):
        return 0
