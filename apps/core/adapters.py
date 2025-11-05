"""
Custom adapters for django-allauth.
"""

from django.conf import settings
from django.db import transaction

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


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
        For OAuth signups, automatically creates a tenant for the user.
        """
        from apps.core.models import Tenant

        user = super().save_user(request, user, form, commit=False)

        # For OAuth signups without a tenant, create one automatically
        if not user.role:
            # Check if this is an OAuth signup (no tenant assigned)
            if not user.tenant_id:
                # Create tenant for OAuth user
                with transaction.atomic():
                    # Create tenant with user's name or email
                    shop_name = f"{user.get_full_name() or user.username}'s Jewelry Shop"
                    tenant = Tenant.objects.create(
                        company_name=shop_name,
                        slug=f"shop-{user.username}".lower().replace(" ", "-"),
                        status=Tenant.ACTIVE,
                    )
                    user.tenant = tenant
                    user.role = user.TENANT_OWNER
            else:
                user.role = user.TENANT_EMPLOYEE

        if commit:
            user.save()

        return user


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Custom social account adapter for OAuth signups.

    Handles automatic tenant creation for OAuth signups.
    """

    def pre_social_login(self, request, sociallogin):
        """
        Called just after social login is confirmed.

        We use this to create a tenant for OAuth signups before the user is saved.
        """
        from apps.core.models import Tenant

        # Only process for new users (not existing users connecting accounts)
        if sociallogin.is_existing:
            return

        user = sociallogin.user

        # Create tenant for OAuth user if they don't have one
        if not user.tenant_id:
            with transaction.atomic():
                # Create tenant with user's name or email
                shop_name = f"{user.get_full_name() or user.username}'s Jewelry Shop"
                tenant = Tenant.objects.create(
                    company_name=shop_name,
                    slug=f"shop-{user.username}".lower().replace(" ", "-"),
                    status=Tenant.ACTIVE,
                )
                user.tenant = tenant
                user.role = user.TENANT_OWNER

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
