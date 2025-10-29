"""
Language Preference Middleware
Sets the active language based on user's language preference
Per Requirement 2.6 - Persist language preference across sessions
"""

from django.utils import translation
from django.utils.deprecation import MiddlewareMixin


class UserLanguageMiddleware(MiddlewareMixin):
    """
    Middleware to activate user's preferred language.

    This middleware checks if the authenticated user has a language preference
    and activates it for the current request. This ensures that the user's
    language preference persists across sessions.

    Must be placed after AuthenticationMiddleware in MIDDLEWARE settings.
    """

    def process_request(self, request):
        """
        Activate user's preferred language if available.

        Args:
            request: The incoming HTTP request
        """
        # Check if user is authenticated and has a language preference
        if hasattr(request, "user") and request.user.is_authenticated:
            if hasattr(request.user, "language") and request.user.language:
                # Activate the user's preferred language
                translation.activate(request.user.language)
                # Set the language code in the request for template access
                request.LANGUAGE_CODE = request.user.language

    def process_response(self, request, response):
        """
        Deactivate language after request processing.

        Args:
            request: The HTTP request
            response: The HTTP response

        Returns:
            The HTTP response
        """
        # Deactivate to prevent language leakage between requests
        translation.deactivate()
        return response
