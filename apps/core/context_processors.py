"""
Context processors for core app.
Provides template context variables for waffle feature flags and other global data.
"""

from waffle import flag_is_active, sample_is_active, switch_is_active
from waffle.models import Flag, Sample, Switch


def waffle_flags(request):
    """
    Add waffle flag checking functions to template context.

    This allows templates to check feature flags using:
    - flag_is_active
    - switch_is_active
    - sample_is_active

    Also provides all flags, switches, and samples for iteration.
    """
    return {
        "flag_is_active": flag_is_active,
        "switch_is_active": switch_is_active,
        "sample_is_active": sample_is_active,
        "waffle_flags": Flag.objects.all(),
        "waffle_switches": Switch.objects.all(),
        "waffle_samples": Sample.objects.all(),
    }
