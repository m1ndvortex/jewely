"""
Django settings for jewelry shop SaaS platform.
"""

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key-change-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,web").split(",")

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

# Site URL for email templates and notifications
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")

MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",  # Must be first
    "django.middleware.security.SecurityMiddleware",
    # Multi-portal session middleware - replaces default SessionMiddleware
    "apps.core.session_middleware.MultiPortalSessionMiddleware",
    # LocaleMiddleware must be after SessionMiddleware and before CommonMiddleware
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # User language middleware - must be after AuthenticationMiddleware and LocaleMiddleware
    "apps.core.language_middleware.UserLanguageMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Allauth middleware - must be after AuthenticationMiddleware
    "allauth.account.middleware.AccountMiddleware",
    # Hijack middleware - must be after AuthenticationMiddleware
    "hijack.middleware.HijackUserMiddleware",
    # Tenant context middleware - must be after AuthenticationMiddleware
    "apps.core.middleware.TenantContextMiddleware",
    # Role-based access control - must be after TenantContextMiddleware
    "apps.core.role_middleware.RoleBasedAccessMiddleware",
    # Audit logging middleware - must be after TenantContextMiddleware
    "apps.core.audit_middleware.AuditLoggingMiddleware",
    # Silk profiling middleware - should be near the end
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
                # i18n context processor for language support
                "django.template.context_processors.i18n",
                # User preferences (language and theme)
                "apps.core.context_processors.user_preferences",
                "apps.core.context_processors.waffle_flags",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database with Prometheus monitoring
DATABASES = {
    "default": {
        "ENGINE": "django_prometheus.db.backends.postgresql",  # Prometheus-wrapped PostgreSQL
        "NAME": os.getenv("POSTGRES_DB", "jewelry_shop"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.getenv("POSTGRES_HOST", "localhost"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "ATOMIC_REQUESTS": True,
        "CONN_MAX_AGE": 600,
    }
}

# Custom User Model
AUTH_USER_MODEL = "core.User"

# Django Allauth Configuration
AUTHENTICATION_BACKENDS = [
    # Needed to login by username in Django admin, regardless of `allauth`
    "django.contrib.auth.backends.ModelBackend",
    # `allauth` specific authentication methods, such as login by e-mail
    "allauth.account.auth_backends.AuthenticationBackend",
    # django-guardian for object-level permissions
    "guardian.backends.ObjectPermissionBackend",
]

# Allauth settings
ACCOUNT_AUTHENTICATION_METHOD = "username_email"  # Allow login with username or email
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_USERNAME_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = True
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE = True
ACCOUNT_USERNAME_MIN_LENGTH = 3
ACCOUNT_ADAPTER = "apps.core.adapters.AccountAdapter"
ACCOUNT_ALLOW_REGISTRATION = True  # Allow new user registration via OAuth
SOCIALACCOUNT_ADAPTER = (
    "apps.core.adapters.SocialAccountAdapter"  # OAuth adapter with tenant creation
)

# Rate limiting for allauth (replaces deprecated LOGIN_ATTEMPTS settings)
ACCOUNT_RATE_LIMITS = {
    "login_failed": "5/5m",  # 5 attempts per 5 minutes
}

# Login/Logout URLs
LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/dashboard/"  # Tenant dashboard after login
LOGOUT_REDIRECT_URL = "/accounts/login/"

# Social Account Providers Configuration
# Per Task 23.4 - OAuth2 support for tenant login
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": [
            "profile",
            "email",
        ],
        "AUTH_PARAMS": {
            "access_type": "online",
            "prompt": "select_account",  # Force account selection on every login
        },
        "APP": {
            "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
            "secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            "key": "",
        },
    },
    "github": {
        "SCOPE": [
            "user",
            "user:email",
        ],
        "APP": {
            "client_id": os.getenv("GITHUB_OAUTH_CLIENT_ID", ""),
            "secret": os.getenv("GITHUB_OAUTH_CLIENT_SECRET", ""),
            "key": "",
        },
    },
    "facebook": {
        "METHOD": "oauth2",
        "SCOPE": ["email", "public_profile"],
        "AUTH_PARAMS": {"auth_type": "reauthenticate"},
        "INIT_PARAMS": {"cookie": True},
        "FIELDS": [
            "id",
            "email",
            "name",
            "first_name",
            "last_name",
            "verified",
        ],
        "EXCHANGE_TOKEN": True,
        "VERIFIED_EMAIL": False,
        "VERSION": "v13.0",
        "APP": {
            "client_id": os.getenv("FACEBOOK_OAUTH_CLIENT_ID", ""),
            "secret": os.getenv("FACEBOOK_OAUTH_CLIENT_SECRET", ""),
            "key": "",
        },
    },
}

# Allauth social account settings
SOCIALACCOUNT_AUTO_SIGNUP = True  # Automatically create account on OAuth login
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_EMAIL_VERIFICATION = "optional"  # Less strict for OAuth
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_STORE_TOKENS = True  # Store OAuth tokens for API access
SOCIALACCOUNT_LOGIN_ON_GET = True  # Skip the intermediate "Sign in via Google" page

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
# Per Requirement 2 - Dual-Language Support (English and Persian)
LANGUAGE_CODE = "en"  # Default language
TIME_ZONE = "UTC"
USE_I18N = True  # Enable internationalization
USE_L10N = True  # Enable localized formatting
USE_TZ = True  # Use timezone-aware datetimes

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
# Use locale-specific formats for dates, numbers, etc.
FORMAT_MODULE_PATH = [
    "config.formats",
]

# Language cookie settings
LANGUAGE_COOKIE_NAME = "django_language"
LANGUAGE_COOKIE_AGE = 31536000  # 1 year
LANGUAGE_COOKIE_DOMAIN = None
LANGUAGE_COOKIE_PATH = "/"
LANGUAGE_COOKIE_SECURE = not DEBUG  # Secure in production
LANGUAGE_COOKIE_HTTPONLY = False  # Allow JavaScript access for language switcher
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

# Redis Cache Configuration with Prometheus monitoring
# Multiple cache backends for different use cases
CACHES = {
    "default": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",  # Prometheus-wrapped Redis
        "LOCATION": f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}/{os.getenv('REDIS_DB', '0')}",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "RETRY_ON_TIMEOUT": True,
            "MAX_CONNECTIONS": 50,
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 50,
                "retry_on_timeout": True,
            },
        },
        "KEY_PREFIX": "jewelry_shop",
        "TIMEOUT": 300,  # 5 minutes default
    },
    # Query result caching - longer timeout for expensive queries
    "query": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}/1",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "RETRY_ON_TIMEOUT": True,
            "MAX_CONNECTIONS": 50,
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 50,
                "retry_on_timeout": True,
            },
        },
        "KEY_PREFIX": "jewelry_shop_query",
        "TIMEOUT": 900,  # 15 minutes for query results
    },
    # Template fragment caching - medium timeout
    "template": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}/2",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "RETRY_ON_TIMEOUT": True,
            "MAX_CONNECTIONS": 50,
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 50,
                "retry_on_timeout": True,
            },
        },
        "KEY_PREFIX": "jewelry_shop_template",
        "TIMEOUT": 600,  # 10 minutes for templates
    },
    # API response caching - short timeout for frequently changing data
    "api": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{os.getenv('REDIS_HOST', 'localhost')}:{os.getenv('REDIS_PORT', '6379')}/3",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "RETRY_ON_TIMEOUT": True,
            "MAX_CONNECTIONS": 50,
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 50,
                "retry_on_timeout": True,
            },
        },
        "KEY_PREFIX": "jewelry_shop_api",
        "TIMEOUT": 180,  # 3 minutes for API responses
    },
}

# Session Configuration
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# Celery Configuration
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes
CELERY_WORKER_PREFETCH_MULTIPLIER = 4
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000


# Logging Configuration with JSON formatting
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
        },
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "filters": {
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose" if DEBUG else "json",
        },
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "django.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 10,
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": os.getenv("LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": os.getenv("LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "file"],
            "level": "ERROR",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Create logs directory if it doesn't exist
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Email Configuration
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@jewelryshop.com")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# Django Anymail Configuration (for production email providers)
if "anymail" in EMAIL_BACKEND.lower():
    INSTALLED_APPS.append("anymail")

    # Example configuration for different providers
    # Uncomment and configure based on your email provider

    # For SendGrid
    if os.getenv("EMAIL_PROVIDER") == "sendgrid":
        ANYMAIL = {
            "SENDGRID_API_KEY": os.getenv("SENDGRID_API_KEY"),
            "SENDGRID_GENERATE_MESSAGE_ID": True,
            "SENDGRID_MERGE_FIELD_FORMAT": "-{}-",
            "SENDGRID_API_URL": "https://api.sendgrid.com/v3/",
        }
        EMAIL_BACKEND = "anymail.backends.sendgrid.EmailBackend"

    # For Mailgun
    elif os.getenv("EMAIL_PROVIDER") == "mailgun":
        ANYMAIL = {
            "MAILGUN_API_KEY": os.getenv("MAILGUN_API_KEY"),
            "MAILGUN_SENDER_DOMAIN": os.getenv("MAILGUN_SENDER_DOMAIN"),
            "MAILGUN_API_URL": "https://api.mailgun.net/v3",
        }
        EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"

    # For Amazon SES
    elif os.getenv("EMAIL_PROVIDER") == "ses":
        ANYMAIL = {
            "AMAZON_SES_REGION": os.getenv("AWS_SES_REGION", "us-east-1"),
            "AMAZON_SES_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
            "AMAZON_SES_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY"),
        }
        EMAIL_BACKEND = "anymail.backends.amazon_ses.EmailBackend"

    # For Postmark
    elif os.getenv("EMAIL_PROVIDER") == "postmark":
        ANYMAIL = {
            "POSTMARK_SERVER_TOKEN": os.getenv("POSTMARK_SERVER_TOKEN"),
            "POSTMARK_API_URL": "https://api.postmarkapp.com/",
        }
        EMAIL_BACKEND = "anymail.backends.postmark.EmailBackend"

# SMTP Configuration (fallback)
if EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
    EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
    EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False") == "True"
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

# Email webhook configuration for tracking
EMAIL_WEBHOOK_SECRET = os.getenv("EMAIL_WEBHOOK_SECRET", "")

# Email rate limiting
EMAIL_RATE_LIMIT = {
    "TRANSACTIONAL": int(os.getenv("EMAIL_RATE_LIMIT_TRANSACTIONAL", "1000")),  # per hour
    "MARKETING": int(os.getenv("EMAIL_RATE_LIMIT_MARKETING", "500")),  # per hour
    "SYSTEM": int(os.getenv("EMAIL_RATE_LIMIT_SYSTEM", "100")),  # per hour
}

# Twilio SMS Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

# SMS webhook configuration for tracking
SMS_WEBHOOK_SECRET = os.getenv("SMS_WEBHOOK_SECRET", "")

# SMS rate limiting
SMS_RATE_LIMIT = {
    "TRANSACTIONAL": int(os.getenv("SMS_RATE_LIMIT_TRANSACTIONAL", "100")),  # per hour
    "MARKETING": int(os.getenv("SMS_RATE_LIMIT_MARKETING", "50")),  # per hour
    "SYSTEM": int(os.getenv("SMS_RATE_LIMIT_SYSTEM", "20")),  # per hour
    "ALERT": int(os.getenv("SMS_RATE_LIMIT_ALERT", "200")),  # per hour
}

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
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),  # 15 minutes
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),  # 7 days
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": "rest_framework_simplejwt.authentication.default_user_authentication_rule",
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "JTI_CLAIM": "jti",
    "SLIDING_TOKEN_REFRESH_EXP_CLAIM": "refresh_exp",
    "SLIDING_TOKEN_LIFETIME": timedelta(minutes=15),
    "SLIDING_TOKEN_REFRESH_LIFETIME": timedelta(days=7),
}

# Django OTP Configuration
OTP_TOTP_ISSUER = "Jewelry Shop SaaS"

# Security Settings
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Django Guardian Configuration
# Object-level permissions
ANONYMOUS_USER_NAME = None  # Disable anonymous user
GUARDIAN_RAISE_403 = True  # Raise PermissionDenied exception for DRF compatibility

# Backup System Configuration
BACKUP_ENCRYPTION_KEY = os.getenv("BACKUP_ENCRYPTION_KEY", "")
BACKUP_LOCAL_PATH = os.getenv("BACKUP_LOCAL_PATH", "/var/backups/jewelry-shop")

# Cloudflare R2 Configuration
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "b7900eeee7c415345d86ea859c9dad47")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "securesyntax")
R2_ENDPOINT = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")

# Backblaze B2 Configuration
B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME", "securesyntax")
B2_BUCKET_ID = os.getenv("B2_BUCKET_ID", "2a0cfb4aa9f8f8f29c820b18")
B2_REGION = os.getenv("B2_REGION", "us-east-005")
B2_ENDPOINT = f"https://s3.{B2_REGION}.backblazeb2.com"
B2_ACCESS_KEY_ID = os.getenv("B2_ACCESS_KEY_ID", "")
B2_SECRET_ACCESS_KEY = os.getenv("B2_SECRET_ACCESS_KEY", "")

# Gold Rate API Configuration
# Get API keys from environment variables
# GoldAPI: https://www.goldapi.io/ (requires API key)
# Metals-API: https://metals-api.com/ (free tier available)
GOLDAPI_KEY = os.getenv("GOLDAPI_KEY", None)
METALS_API_KEY = os.getenv("METALS_API_KEY", None)

# Field Encryption Settings
# For encrypting sensitive integration credentials
FIELD_ENCRYPTION_KEY = os.getenv(
    "FIELD_ENCRYPTION_KEY",
    "ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg=",  # Default key for development only
)

# Django Hijack Configuration
# Secure tenant impersonation for platform administrators
HIJACK_ALLOW_GET_REQUESTS = False  # Require POST for security
HIJACK_LOGIN_REDIRECT_URL = "/dashboard/"  # Redirect to tenant dashboard after hijack
HIJACK_LOGOUT_REDIRECT_URL = "/platform/dashboard/"  # Return to admin dashboard after release
HIJACK_DISPLAY_ADMIN_BUTTON = False  # We'll add custom buttons
HIJACK_USE_BOOTSTRAP = False  # We use Tailwind CSS
HIJACK_REGISTER_ADMIN = False  # Don't auto-register in Django admin
HIJACK_PERMISSION_CHECK = "apps.core.permissions.can_hijack_user"  # Custom permission check
HIJACK_DECORATOR = "apps.core.decorators.platform_admin_required"  # Require platform admin

# Stripe Payment Gateway Configuration
# For subscription billing and payment processing per Requirement 5.7
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_LIVE_MODE = os.getenv("STRIPE_LIVE_MODE", "False") == "True"

# Prometheus Monitoring Configuration
# Per Requirements 7 and 24 - System Monitoring and Observability
PROMETHEUS_EXPORT_MIGRATIONS = True  # Export migration status
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
)  # Request latency buckets in seconds

# Use URL-based exporter only (not separate port) to avoid conflicts with Django autoreloader
# Metrics will be available at /metrics endpoint
# PROMETHEUS_METRICS_EXPORT_PORT is intentionally not set to use URL exporter only

# Django Waffle Configuration
# Per Requirement 30 - Feature Flag Management
# Allows gradual feature rollout and A/B testing

# Cache configuration for waffle flags
WAFFLE_CACHE_PREFIX = "waffle:"
WAFFLE_CACHE_NAME = "default"  # Use default Redis cache

# Flag defaults
WAFFLE_FLAG_DEFAULT = False  # Flags are disabled by default
WAFFLE_SWITCH_DEFAULT = False  # Switches are disabled by default
WAFFLE_SAMPLE_DEFAULT = False  # Samples are disabled by default

# Create flags in database automatically when referenced in code
WAFFLE_CREATE_MISSING_FLAGS = DEBUG  # Only in development

# Override flags for testing
WAFFLE_OVERRIDE = os.getenv("WAFFLE_OVERRIDE", "False") == "True"

# Flag model configuration
WAFFLE_FLAG_MODEL = "waffle.Flag"
WAFFLE_SWITCH_MODEL = "waffle.Switch"
WAFFLE_SAMPLE_MODEL = "waffle.Sample"

# Secure flag cookies
WAFFLE_SECURE = not DEBUG  # Use secure cookies in production
WAFFLE_MAX_AGE = 2592000  # 30 days cookie lifetime

# ============================================================================
# Django Silk Configuration
# Per Requirement 26 - Performance Optimization and Scaling
# ============================================================================

# Enable Silk only in development and staging
SILKY_PYTHON_PROFILER = DEBUG
SILKY_PYTHON_PROFILER_BINARY = DEBUG

# Authentication required to view silk pages
SILKY_AUTHENTICATION = True
SILKY_AUTHORISATION = True

# Maximum number of requests to store
SILKY_MAX_REQUEST_BODY_SIZE = 1024 * 1024  # 1MB
SILKY_MAX_RESPONSE_BODY_SIZE = 1024 * 1024  # 1MB
SILKY_MAX_RECORDED_REQUESTS = 10000

# Intercept percentage (100 = all requests)
SILKY_INTERCEPT_PERCENT = 100 if DEBUG else 10  # Profile all in dev, 10% in staging

# Meta profiling
SILKY_META = True

# Analyze queries
SILKY_ANALYZE_QUERIES = True

# ============================================================================
# Database Connection Pooling Configuration
# Per Requirement 26.5 - Use PgBouncer for database connection pooling
# ============================================================================

# PgBouncer will be configured in docker-compose.yml
# When using PgBouncer, update DATABASES['default']['HOST'] to 'pgbouncer'
# and PORT to 6432 (PgBouncer default port)
USE_PGBOUNCER = os.getenv("USE_PGBOUNCER", "False") == "True"

if USE_PGBOUNCER:
    DATABASES["default"]["HOST"] = os.getenv("PGBOUNCER_HOST", "pgbouncer")
    DATABASES["default"]["PORT"] = os.getenv("PGBOUNCER_PORT", "6432")
    # Disable persistent connections when using PgBouncer
    DATABASES["default"]["CONN_MAX_AGE"] = 0
    # Disable server-side cursors for PgBouncer compatibility
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True
