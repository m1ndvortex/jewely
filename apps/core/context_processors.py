"""
Context processors for the core app.

Context processors add variables to the template context for all templates.
Per Requirement 2 (Language) and Requirement 3 (Theme).
"""


def user_preferences(request):
    """
    Add user preferences (language and theme) to template context.

    This makes user.language and user.theme available in all templates
    without having to pass them explicitly in every view.

    Per Requirement 2 - Dual-Language Support
    Per Requirement 3 - Dual-Theme Support
    """
    context = {}

    if request.user.is_authenticated:
        context["user_language"] = request.user.language
        context["user_theme"] = request.user.theme
    else:
        # Default values for anonymous users
        context["user_language"] = "en"
        context["user_theme"] = "light"

    return context


def impersonation_context(request):
    """
    Add impersonation status to template context.

    This makes is_impersonating and original_admin available in all templates
    for displaying the impersonation banner.

    Per Requirement 12.3 - Display visible banner during impersonation
    """
    from apps.core.services.impersonation_service import ImpersonationService

    context = {
        "is_impersonating": False,
        "original_admin": None,
        "impersonation_start_time": None,
    }

    if request.user.is_authenticated:
        service = ImpersonationService()
        if service.is_impersonating(request):
            context["is_impersonating"] = True
            context["original_admin"] = service.get_original_user(request)
            context["impersonation_start_time"] = service.get_impersonation_start_time(request)

    return context


def waffle_flags(request):
    """
    Add waffle feature flags to template context.

    This makes feature flags available in all templates for conditional rendering.
    """
    # Get all flags that are active for this request
    # This is a placeholder - waffle provides its own context processor
    # but we need this function to exist for the settings reference
    return {}
