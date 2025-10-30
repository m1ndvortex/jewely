"""
Custom adapters for django-allauth.
"""

from django.conf import settings

from allauth.account.adapter import DefaultAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    """
    Custom account adapter for django-allauth.

    Provides custom behavior for account management including
    tenant-aware user creation and validation.
    """

    def is_open_for_signup(self, request):
        """
        Control whether new signups are allowed.

        For this platform, signups are typically handled by platform admins
        creating tenant accounts, not through public registration.
        """
        # Allow signup only if explicitly enabled in settings
        return getattr(settings, "ACCOUNT_ALLOW_REGISTRATION", False)

    def save_user(self, request, user, form, commit=True):
        """
        Save a new user instance.

        This method is called when a new user is created through allauth.
        We can customize it to set tenant-specific fields.
        """
        user = super().save_user(request, user, form, commit=False)

        # Set default role for new users
        if not user.role:
            user.role = user.TENANT_EMPLOYEE

        if commit:
            user.save()

        return user

    def get_login_redirect_url(self, request):
        """
        Customize login redirect based on user role.
        
        Platform admins go to: /platform/dashboard/
        Tenant users go to: /dashboard/
        """
        user = request.user

        if user.is_authenticated:
            if user.is_platform_admin():
                return "/platform/dashboard/"
            elif user.has_tenant_access():
                return "/dashboard/"

        return super().get_login_redirect_url(request)

    def get_email_confirmation_url(self, request, emailconfirmation):
        """
        Customize email confirmation URL.
        """
        url = super().get_email_confirmation_url(request, emailconfirmation)
        return url
