"""
Base Django settings for jewelry shop SaaS platform.
Common settings shared across all environments.
"""

import os
from datetime import timedelta
from pathlib import Path

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Application definition
INSTALLED_APPS = [
    "django_prometheus",  # Must be first for proper metrics collection
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.humanize",  # For humanizing numbers and dates
    # Third-party apps
    "rest_framework",
    "rest_framework_simplejwt",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.github",
    "allauth.socialaccount.providers.facebook",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "guardian",
    "django_ledger",
    "django_fsm",
    "import_export",
    "hijack",
    "hijack.contrib.admin",
    "waffle",
    "rosetta",  # Translation management interface
    "widget_tweaks",  # Form widget styling
    "silk",  # Query profiling and optimization
    "compressor",  # Asset compression and minification
    "django_celery_beat",  # Celery beat scheduler
    # Local apps
    "apps.core",
    "apps.inventory",
    "apps.sales",
    "apps.crm",
    "apps.accounting",
    "apps.repair",
    "apps.procurement",
    "apps.pricing",
    "apps.reporting",
    "apps.notifications",
    "apps.backups",
]

# Site ID for django-allauth
SITE_ID = 1

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",  # Must be first
    "django.middleware.security.SecurityMiddleware",
    "apps.core.security_headers_middleware.SecurityHeadersMiddleware",
    "apps.core.rate_limit_middleware.APIRateLimitMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "apps.core.session_middleware.MultiPortalSessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.language_middleware.UserLanguageMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "hijack.middleware.HijackUserMiddleware",
    "apps.core.middleware.TenantContextMiddleware",
    "apps.core.role_middleware.RoleBasedAccessMiddleware",
    "apps.core.audit_middleware.AuditLoggingMiddleware",
    "apps.core.cache_headers_middleware.CacheHeadersMiddleware",
    "silk.middleware.SilkyMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",  # Must be last
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.csrf",
                "django.template.context_processors.i18n",
                "apps.core.context_processors.user_preferences",
                "apps.core.context_processors.waffle_flags",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Custom User Model
AUTH_USER_MODEL = "core.User"

# Django Allauth Configuration
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
    "guardian.backends.ObjectPermissionBackend",
]

# Allauth settings
ACCOUNT_AUTHENTICATION_METHOD = "username_email"
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = True
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE = True
ACCOUNT_USERNAME_MIN_LENGTH = 3
ACCOUNT_ADAPTER = "apps.core.adapters.AccountAdapter"
ACCOUNT_ALLOW_REGISTRATION = True
SOCIALACCOUNT_ADAPTER = "apps.core.adapters.SocialAccountAdapter"

# Rate limiting for allauth
ACCOUNT_RATE_LIMITS = {
    "login_failed": "5/5m",
}

# Login/Logout URLs
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# Allauth social account settings
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "optional"
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_STORE_TOKENS = True
SOCIALACCOUNT_LOGIN_ON_GET = True

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {
            "min_length": 12,
        },
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Password Hashing with Argon2
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

# Internationalization
LANGUAGE_CODE = "en"
TIME_ZONE = "UTC"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# Supported languages
LANGUAGES = [
    ("en", "English"),
    ("fa", "Persian (فارسی)"),
]

# Locale paths for translation files
LOCALE_PATHS = [
    BASE_DIR / "locale",
]

# Format localization settings
FORMAT_MODULE_PATH = [
    "config.formats",
]

# Language cookie settings
LANGUAGE_COOKIE_NAME = "django_language"
LANGUAGE_COOKIE_AGE = 31536000  # 1 year
LANGUAGE_COOKIE_DOMAIN = None
LANGUAGE_COOKIE_PATH = "/"
LANGUAGE_COOKIE_HTTPONLY = False
LANGUAGE_COOKIE_SAMESITE = "Lax"

# Static files (CSS, JavaScript, Images)
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Media files
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Session Configuration
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 86400  # 24 hours

# CSRF Configuration
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_USE_SESSIONS = False
CSRF_FAILURE_VIEW = "apps.core.views.csrf_failure"

# Browser Security Headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

# Django Guardian Configuration
ANONYMOUS_USER_NAME = None
GUARDIAN_RAISE_403 = True

# Django OTP Configuration
OTP_TOTP_ISSUER = "Jewelry Shop SaaS"

# Django Hijack Configuration
HIJACK_ALLOW_GET_REQUESTS = False
HIJACK_LOGIN_REDIRECT_URL = "/dashboard/"
HIJACK_LOGOUT_REDIRECT_URL = "/platform/dashboard/"
HIJACK_DISPLAY_ADMIN_BUTTON = False
HIJACK_USE_BOOTSTRAP = False
HIJACK_REGISTER_ADMIN = False
HIJACK_PERMISSION_CHECK = "apps.core.permissions.can_hijack_user"
HIJACK_DECORATOR = "apps.core.decorators.platform_admin_required"

# Django Waffle Configuration
WAFFLE_CACHE_PREFIX = "waffle:"
WAFFLE_CACHE_NAME = "default"
WAFFLE_FLAG_DEFAULT = False
WAFFLE_SWITCH_DEFAULT = False
WAFFLE_SAMPLE_DEFAULT = False
WAFFLE_FLAG_MODEL = "waffle.Flag"
WAFFLE_SWITCH_MODEL = "waffle.Switch"
WAFFLE_SAMPLE_MODEL = "waffle.Sample"
WAFFLE_MAX_AGE = 2592000  # 30 days

# Django REST Framework Configuration
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
}

# JWT Configuration
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
}

# Celery Configuration
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes
CELERY_WORKER_PREFETCH_MULTIPLIER = 4
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000

# Prometheus Monitoring Configuration
PROMETHEUS_EXPORT_MIGRATIONS = True
PROMETHEUS_LATENCY_BUCKETS = (
    0.01,
    0.025,
    0.05,
    0.075,
    0.1,
    0.25,
    0.5,
    0.75,
    1.0,
    2.5,
    5.0,
    7.5,
    10.0,
    25.0,
    50.0,
    75.0,
    float("inf"),
)

# GZip Compression Configuration
GZIP_MIN_LENGTH = 200

# Brute force protection settings
BRUTE_FORCE_MAX_ATTEMPTS = 5
BRUTE_FORCE_LOCKOUT_MINUTES = 15
BRUTE_FORCE_WINDOW_MINUTES = 5

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def validate_required_env_vars():
    """
    Validate that all required environment variables are set.
    This function should be called at the end of each environment-specific settings file.
    """
    required_vars = {
        "DJANGO_SECRET_KEY": "Django secret key for cryptographic signing",
        "POSTGRES_DB": "PostgreSQL database name",
        "POSTGRES_USER": "PostgreSQL username",
        "POSTGRES_PASSWORD": "PostgreSQL password",
        "POSTGRES_HOST": "PostgreSQL host",
    }

    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"{var} ({description})")

    redis_use_sentinel = os.getenv("REDIS_USE_SENTINEL", "False").lower() == "true"
    if redis_use_sentinel:
        sentinel_hosts = os.getenv("REDIS_SENTINEL_HOSTS", "").strip()
        if not sentinel_hosts:
            missing_vars.append(
                "REDIS_SENTINEL_HOSTS (Comma-separated host:port list for Redis Sentinel)"
            )
    else:
        if not os.getenv("REDIS_HOST"):
            missing_vars.append("REDIS_HOST (Redis host)")

    if missing_vars:
        error_msg = (
            "Missing required environment variables:\n"
            + "\n".join(f"  - {var}" for var in missing_vars)
            + "\n\nPlease set these variables in your .env file or environment."
        )
        raise ValueError(error_msg)


def validate_security_settings(debug_mode):
    """
    Validate security-critical settings based on environment.
    """
    # Skip validation during static file collection
    if os.getenv("COLLECTSTATIC_ONLY") == "1":
        return

    if not debug_mode:
        # Production security checks
        secret_key = os.getenv("DJANGO_SECRET_KEY", "")
        if secret_key == "dev-secret-key-change-in-production":
            raise ValueError("DJANGO_SECRET_KEY must be changed from default value in production!")

        if len(secret_key) < 50:
            raise ValueError("DJANGO_SECRET_KEY must be at least 50 characters long in production!")

        # Check backup encryption key
        backup_key = os.getenv("BACKUP_ENCRYPTION_KEY", "")
        if not backup_key:
            raise ValueError("BACKUP_ENCRYPTION_KEY must be set in production for secure backups!")
