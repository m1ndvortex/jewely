"""
Core views for the jewelry shop SaaS platform.
"""

from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext as _
from django.views import View
from django.views.decorators.http import require_http_methods

from django_otp import user_has_device
from django_otp.plugins.otp_totp.models import TOTPDevice
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
    CustomTokenObtainPairSerializer,
    PasswordChangeSerializer,
    UserPreferencesSerializer,
    UserRegistrationSerializer,
    UserSerializer,
)

User = get_user_model()


@require_http_methods(["GET"])
def health_check(request):
    """
    Health check endpoint for Docker and Kubernetes.
    Returns 200 OK if the application is running.
    """
    return JsonResponse({"status": "healthy", "service": "jewelry-shop-saas"})


@require_http_methods(["GET"])
def home(request):
    """
    Home page view - redirects to appropriate dashboard based on user role.
    """
    if request.user.is_authenticated:
        if request.user.is_platform_admin():
            return redirect("core:admin_dashboard")
        elif request.user.has_tenant_access():
            return redirect("core:tenant_dashboard")
        else:
            # User has no proper role/tenant - logout
            return redirect("account_logout")

    # Unauthenticated users see login page
    return redirect("account_login")


# Authentication Views


class AdminLoginView(View):
    """
    Custom admin login view for platform administrators.

    This view only allows username/password authentication.
    OAuth2/social login is NOT available for admin accounts.
    """

    template_name = "admin/admin_login.html"

    def get(self, request):
        """Display the admin login form."""
        # If user is already logged in and is a platform admin, redirect to admin dashboard
        if request.user.is_authenticated and request.user.is_platform_admin():
            return redirect("/platform/dashboard/")

        # If user is logged in but not admin, log them out first
        if request.user.is_authenticated:
            from django.contrib.auth import logout

            logout(request)
            messages.info(request, _("Please use your admin credentials to access this area."))

        return render(request, self.template_name)

    def post(self, request):
        """Handle admin login submission."""
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        next_url = request.POST.get("next", "/platform/dashboard/")

        # Validate input
        if not username or not password:
            messages.error(request, _("Username and password are required."))
            return render(request, self.template_name, {"form": request.POST})

        # Authenticate user
        user = authenticate(request, username=username, password=password)

        if user is not None:
            # Check if user is a platform admin
            if not user.is_platform_admin():
                messages.error(
                    request, _("Access denied. This login is for platform administrators only.")
                )
                return render(request, self.template_name, {"form": request.POST})

            # Check if account is active
            if not user.is_active:
                messages.error(request, _("This account has been disabled."))
                return render(request, self.template_name, {"form": request.POST})

            # Log the user in
            login(request, user)
            messages.success(request, _("Welcome back, {}!").format(user.username))

            # Redirect to next URL or default dashboard
            return redirect(next_url)
        else:
            # Authentication failed
            messages.error(request, _("Invalid username or password. Please try again."))
            return render(request, self.template_name, {"form": request.POST, "username": username})


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token view that includes additional user information.
    """

    serializer_class = CustomTokenObtainPairSerializer


class AdminLogoutView(View):
    """
    Custom logout view for platform administrators.
    Logs out the user and redirects to the admin login page.
    Clears the platform_sessionid cookie specifically.
    """

    def get(self, request):
        """Handle admin logout."""
        # Clear the session
        logout(request)

        # Create response with redirect
        response = redirect("core:admin_login")

        # Explicitly clear the platform session cookie
        response.delete_cookie(
            "platform_sessionid",
            path="/",
            domain=None,
            samesite="Lax",
        )

        messages.success(request, _("You have been successfully logged out."))
        return response

    def post(self, request):
        """Handle admin logout via POST."""
        # Clear the session
        logout(request)

        # Create response with redirect
        response = redirect("core:admin_login")

        # Explicitly clear the platform session cookie
        response.delete_cookie(
            "platform_sessionid",
            path="/",
            domain=None,
            samesite="Lax",
        )

        messages.success(request, _("You have been successfully logged out."))
        return response


class TenantLogoutView(View):
    """
    Custom logout view for tenant users.
    Logs out the user and redirects to the tenant login page.
    Clears the tenant_sessionid cookie and OAuth tokens.
    """

    def get(self, request):
        """Handle tenant logout."""
        # Delete social account tokens if user logged in via OAuth
        if request.user.is_authenticated:
            # Import here to avoid circular imports
            from allauth.socialaccount.models import SocialToken

            SocialToken.objects.filter(account__user=request.user).delete()

        # Clear the session
        logout(request)

        # Create response with redirect
        response = redirect("account_login")

        # Explicitly clear the tenant session cookie
        response.delete_cookie(
            "tenant_sessionid",
            path="/",
            domain=None,
            samesite="Lax",
        )

        messages.success(request, _("You have been successfully logged out."))
        return response

    def post(self, request):
        """Handle tenant logout via POST."""
        # Delete social account tokens if user logged in via OAuth
        if request.user.is_authenticated:
            # Import here to avoid circular imports
            from allauth.socialaccount.models import SocialToken

            SocialToken.objects.filter(account__user=request.user).delete()

        # Clear the session
        logout(request)

        # Create response with redirect
        response = redirect("account_login")

        # Explicitly clear the tenant session cookie
        response.delete_cookie(
            "tenant_sessionid",
            path="/",
            domain=None,
            samesite="Lax",
        )

        messages.success(request, _("You have been successfully logged out."))
        return response


class UserRegistrationView(generics.CreateAPIView):
    """
    API endpoint for user registration.

    Note: This is typically disabled in production as users are created
    by platform admins or tenant owners.
    """

    queryset = User.objects.all()
    permission_classes = [permissions.AllowAny]
    serializer_class = UserRegistrationSerializer


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    API endpoint for viewing and updating user profile.
    """

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class PasswordChangeView(APIView):
    """
    API endpoint for changing user password.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"detail": "Password changed successfully."},
                status=status.HTTP_200_OK,
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserPreferencesView(generics.UpdateAPIView):
    """
    API endpoint for updating user preferences (language, theme).
    """

    serializer_class = UserPreferencesSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class LanguageSwitchView(APIView):
    """
    API endpoint for switching user's language preference.

    Per Requirement 2 - Dual-Language Support (English and Persian)
    Task 26.5 - Create language switcher
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        Switch user's language preference.

        Expected payload:
        {
            "language": "en" or "fa"
        }
        """
        from django.utils import translation

        language = request.data.get("language")

        # Validate language choice - use simple validation
        valid_languages = ["en", "fa"]
        if language not in valid_languages:
            return Response(
                {"error": "Invalid language choice", "valid_choices": valid_languages},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Update user's language preference
            user = request.user
            user.language = language
            user.save(update_fields=["language"])

            # Activate the new language for the current session
            translation.activate(language)
            # Set language in session using Django's standard key
            request.session["django_language"] = language

            # Get language name
            language_names = {"en": "English", "fa": "Persian"}

            return Response(
                {
                    "message": "Language preference updated successfully",
                    "language": language,
                    "language_name": language_names.get(language, language),
                },
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            import traceback

            print(f"Language switch error: {e}")
            print(traceback.format_exc())
            return Response(
                {"error": f"Failed to update language: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ThemeSwitchView(APIView):
    """
    API endpoint for switching user's theme preference.

    Per Requirement 3 - Dual-Theme Support (Light and Dark Mode)
    Task 27.1 - Implement theme infrastructure
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        """
        Switch user's theme preference.

        Expected payload:
        {
            "theme": "light" or "dark"
        }
        """
        theme = request.data.get("theme")

        # Validate theme choice
        valid_themes = dict(User.THEME_CHOICES).keys()
        if theme not in valid_themes:
            return Response(
                {"error": "Invalid theme choice", "valid_choices": list(valid_themes)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update user's theme preference
        user = request.user
        user.theme = theme
        user.save(update_fields=["theme"])

        return Response(
            {
                "message": "Theme preference updated successfully",
                "theme": theme,
                "theme_name": dict(User.THEME_CHOICES)[theme],
            },
            status=status.HTTP_200_OK,
        )


class MFAStatusView(APIView):
    """
    API endpoint to check MFA status for the current user.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        has_mfa = user_has_device(user)
        return Response(
            {
                "is_mfa_enabled": user.is_mfa_enabled,
                "has_device": has_mfa,
            }
        )


class MFAEnableView(APIView):
    """
    API endpoint to enable MFA for the current user.

    Returns a QR code URL that can be scanned with an authenticator app.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user

        # Check if user already has a device
        if user_has_device(user):
            return Response(
                {"detail": "MFA is already enabled for this user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create a new TOTP device
        device = TOTPDevice.objects.create(user=user, name="default", confirmed=False)

        # Generate QR code URL
        url = device.config_url

        return Response(
            {
                "detail": "MFA device created. Scan the QR code with your authenticator app.",
                "qr_code_url": url,
                "secret": device.key,
            },
            status=status.HTTP_201_CREATED,
        )


class MFAConfirmView(APIView):
    """
    API endpoint to confirm MFA setup by verifying a token.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        token = request.data.get("token")

        if not token:
            return Response(
                {"detail": "Token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the unconfirmed device
        try:
            device = TOTPDevice.objects.get(user=user, confirmed=False)
        except TOTPDevice.DoesNotExist:
            return Response(
                {"detail": "No unconfirmed MFA device found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify the token
        if device.verify_token(token):
            device.confirmed = True
            device.save()

            # Update user's MFA status
            user.is_mfa_enabled = True
            user.save(update_fields=["is_mfa_enabled"])

            return Response(
                {"detail": "MFA enabled successfully."},
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {"detail": "Invalid token."},
                status=status.HTTP_400_BAD_REQUEST,
            )


class MFADisableView(APIView):
    """
    API endpoint to disable MFA for the current user.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        password = request.data.get("password")

        if not password:
            return Response(
                {"detail": "Password is required to disable MFA."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Verify password
        if not user.check_password(password):
            return Response(
                {"detail": "Invalid password."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Delete all TOTP devices
        TOTPDevice.objects.filter(user=user).delete()

        # Update user's MFA status
        user.is_mfa_enabled = False
        user.save(update_fields=["is_mfa_enabled"])

        return Response(
            {"detail": "MFA disabled successfully."},
            status=status.HTTP_200_OK,
        )


class MFAVerifyView(APIView):
    """
    API endpoint to verify MFA token during login.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        token = request.data.get("token")

        if not token:
            return Response(
                {"detail": "Token is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get the confirmed device
        try:
            device = TOTPDevice.objects.get(user=user, confirmed=True)
        except TOTPDevice.DoesNotExist:
            return Response(
                {"detail": "MFA is not enabled for this user."},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Verify the token
        if device.verify_token(token):
            return Response(
                {"detail": "Token verified successfully."},
                status=status.HTTP_200_OK,
            )
        else:
            return Response(
                {"detail": "Invalid token."},
                status=status.HTTP_400_BAD_REQUEST,
            )
