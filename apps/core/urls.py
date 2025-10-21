from django.urls import path

from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = "core"

urlpatterns = [
    # Basic views
    path("", views.home, name="home"),
    path("health/", views.health_check, name="health_check"),
    # Authentication endpoints
    path("api/auth/login/", views.CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/register/", views.UserRegistrationView.as_view(), name="register"),
    # User profile endpoints
    path("api/user/profile/", views.UserProfileView.as_view(), name="user_profile"),
    path("api/user/password/change/", views.PasswordChangeView.as_view(), name="password_change"),
    path("api/user/preferences/", views.UserPreferencesView.as_view(), name="user_preferences"),
    # MFA endpoints
    path("api/mfa/status/", views.MFAStatusView.as_view(), name="mfa_status"),
    path("api/mfa/enable/", views.MFAEnableView.as_view(), name="mfa_enable"),
    path("api/mfa/confirm/", views.MFAConfirmView.as_view(), name="mfa_confirm"),
    path("api/mfa/disable/", views.MFADisableView.as_view(), name="mfa_disable"),
    path("api/mfa/verify/", views.MFAVerifyView.as_view(), name="mfa_verify"),
]
