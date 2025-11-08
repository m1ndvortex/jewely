"""
Development-specific Django settings.
"""

import os

# Load environment variables from .env file
from dotenv import load_dotenv

from .base import *  # noqa: F403,F405

load_dotenv()

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key-change-in-production")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,web,0.0.0.0").split(",")

# Site URL for email templates and notifications
SITE_URL = os.getenv("SITE_URL", "http://localhost:8000")

# Database with Prometheus monitoring
DATABASES = {
    "default": {
        "ENGINE": "django_prometheus.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "jewelry_shop"),
        "USER": os.getenv("POSTGRES_USER", "postgres"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "postgres"),
        "HOST": os.getenv("POSTGRES_HOST", "db"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "ATOMIC_REQUESTS": True,
        "CONN_MAX_AGE": 600,
    }
}

# Redis Cache Configuration - Development
CACHES = {
    "default": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}/0",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "RETRY_ON_TIMEOUT": True,
            "MAX_CONNECTIONS": 50,
        },
        "KEY_PREFIX": "jewelry_shop_dev",
        "TIMEOUT": 300,
    },
    "query": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}/1",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "jewelry_shop_dev_query",
        "TIMEOUT": 900,
    },
    "template": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}/2",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "jewelry_shop_dev_template",
        "TIMEOUT": 600,
    },
    "api": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}/3",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "jewelry_shop_dev_api",
        "TIMEOUT": 180,
    },
}

# Celery Configuration - Development
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")

# Email Configuration - Development (Console backend)
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "noreply@jewelryshop.local")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# Logging Configuration - Development (Verbose console output)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
        "file": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "django_dev.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "DEBUG",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console", "file"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# Security Settings - Development (Relaxed)
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
LANGUAGE_COOKIE_SECURE = False
WAFFLE_SECURE = False

# Django Compressor - Disabled in development
COMPRESS_ENABLED = False
COMPRESS_OFFLINE = False

# Django Silk - Enabled in development
SILKY_PYTHON_PROFILER = True
SILKY_PYTHON_PROFILER_BINARY = True
SILKY_AUTHENTICATION = True
SILKY_AUTHORISATION = True
SILKY_MAX_RECORDED_REQUESTS = 10000
SILKY_INTERCEPT_PERCENT = 100  # Profile all requests
SILKY_META = True
SILKY_ANALYZE_QUERIES = True

# Waffle - Create missing flags automatically in development
WAFFLE_CREATE_MISSING_FLAGS = True
WAFFLE_OVERRIDE = True

# Social Account Providers - Development
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online", "prompt": "select_account"},
        "APP": {
            "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID", ""),
            "secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", ""),
            "key": "",
        },
    },
    "github": {
        "SCOPE": ["user", "user:email"],
        "APP": {
            "client_id": os.getenv("GITHUB_OAUTH_CLIENT_ID", ""),
            "secret": os.getenv("GITHUB_OAUTH_CLIENT_SECRET", ""),
            "key": "",
        },
    },
}

# Backup System Configuration - Development
BACKUP_ENCRYPTION_KEY = os.getenv("BACKUP_ENCRYPTION_KEY", "dev-backup-key-for-testing-only")
BACKUP_LOCAL_PATH = os.getenv("BACKUP_LOCAL_PATH", str(BASE_DIR / "backups"))

# Cloud Storage - Development (Optional)
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "")
R2_ENDPOINT = (
    f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com" if R2_ACCOUNT_ID else ""
)
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")

B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME", "")
B2_BUCKET_ID = os.getenv("B2_BUCKET_ID", "")
B2_REGION = os.getenv("B2_REGION", "us-east-005")
B2_ENDPOINT = f"https://s3.{B2_REGION}.backblazeb2.com"
B2_ACCESS_KEY_ID = os.getenv("B2_ACCESS_KEY_ID", "")
B2_SECRET_ACCESS_KEY = os.getenv("B2_SECRET_ACCESS_KEY", "")

# API Keys - Development
GOLDAPI_KEY = os.getenv("GOLDAPI_KEY", None)
METALS_API_KEY = os.getenv("METALS_API_KEY", None)
FIELD_ENCRYPTION_KEY = os.getenv(
    "FIELD_ENCRYPTION_KEY", "ZmDfcTF7_60GrrY167zsiPd67pEvs0aGOv2oasOM1Pg="
)

# Twilio SMS - Development
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "")

# Stripe - Development (Test mode)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_LIVE_MODE = False

# Rate Limiting - Relaxed in development
RATELIMIT_ENABLE = os.getenv("RATELIMIT_ENABLE", "False") == "True"
RATELIMIT_DEFAULT_RATE = "1000/h"
RATELIMIT_STRICT_RATE = "100/m"

# Sentry - Disabled in development
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
SENTRY_ENVIRONMENT = "development"

# PgBouncer - Not used in development
USE_PGBOUNCER = False

# Validate required environment variables (relaxed for development)
# Only validate critical database settings
critical_vars = ["POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "REDIS_HOST"]
missing = [var for var in critical_vars if not os.getenv(var)]
if missing:
    print(f"WARNING: Missing environment variables: {', '.join(missing)}")
    print("Using default values for development. Set these in .env for production.")
