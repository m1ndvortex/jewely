"""
Core views for the jewelry shop SaaS platform.
"""

from django.contrib.auth import get_user_model
from django.http import JsonResponse
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
    Home page view.
    """
    return JsonResponse({"message": "Welcome to Jewelry Shop SaaS Platform", "version": "1.0.0"})


# Authentication Views


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token view that includes additional user information.
    """

    serializer_class = CustomTokenObtainPairSerializer


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
        language = request.data.get("language")

        # Validate language choice
        valid_languages = dict(User.LANGUAGE_CHOICES).keys()
        if language not in valid_languages:
            return Response(
                {"error": "Invalid language choice", "valid_choices": list(valid_languages)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Update user's language preference
        user = request.user
        user.language = language
        user.save(update_fields=["language"])

        # Activate the new language for the current request
        from django.utils import translation

        translation.activate(language)

        return Response(
            {
                "message": "Language preference updated successfully",
                "language": language,
                "language_name": dict(User.LANGUAGE_CHOICES)[language],
            },
            status=status.HTTP_200_OK,
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
