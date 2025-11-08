"""
Staging-specific Django settings.
Similar to production but with some debugging enabled.
"""

import os

# Load environment variables from .env file
from dotenv import load_dotenv

from .base import *  # noqa: F403,F405

load_dotenv()

# SECURITY WARNING: Use a strong secret key in staging
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY must be set in staging environment!")

# Limited debugging in staging
DEBUG = os.getenv("DJANGO_DEBUG", "False") == "True"

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",")
if not ALLOWED_HOSTS or ALLOWED_HOSTS == [""]:
    raise ValueError("DJANGO_ALLOWED_HOSTS must be set in staging environment!")

# Site URL
SITE_URL = os.getenv("SITE_URL")
if not SITE_URL:
    raise ValueError("SITE_URL must be set in staging environment!")

# Database with Prometheus monitoring
DATABASES = {
    "default": {
        "ENGINE": "django_prometheus.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB"),
        "USER": os.getenv("POSTGRES_USER"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD"),
        "HOST": os.getenv("POSTGRES_HOST"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "ATOMIC_REQUESTS": True,
        "CONN_MAX_AGE": 600,
    }
}

# PgBouncer Configuration
USE_PGBOUNCER = os.getenv("USE_PGBOUNCER", "False") == "True"
if USE_PGBOUNCER:
    DATABASES["default"]["HOST"] = os.getenv("PGBOUNCER_HOST", "pgbouncer")
    DATABASES["default"]["PORT"] = os.getenv("PGBOUNCER_PORT", "6432")
    DATABASES["default"]["CONN_MAX_AGE"] = 0
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

# Redis Cache Configuration - Staging
redis_host = os.getenv("REDIS_HOST")
redis_port = os.getenv("REDIS_PORT", "6379")

CACHES = {
    "default": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{redis_host}:{redis_port}/0",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "RETRY_ON_TIMEOUT": True,
            "MAX_CONNECTIONS": 50,
        },
        "KEY_PREFIX": "jewelry_shop_staging",
        "TIMEOUT": 300,
    },
    "query": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{redis_host}:{redis_port}/1",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "jewelry_shop_staging_query",
        "TIMEOUT": 900,
    },
    "template": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{redis_host}:{redis_port}/2",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "jewelry_shop_staging_template",
        "TIMEOUT": 600,
    },
    "api": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": f"redis://{redis_host}:{redis_port}/3",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        "KEY_PREFIX": "jewelry_shop_staging_api",
        "TIMEOUT": 180,
    },
}

# Celery Configuration - Staging
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", f"redis://{redis_host}:{redis_port}/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", f"redis://{redis_host}:{redis_port}/0")

# Email Configuration - Staging
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "staging@jewelryshop.com")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

# Configure email provider if specified
if "anymail" in EMAIL_BACKEND.lower():
    INSTALLED_APPS.append("anymail")

    email_provider = os.getenv("EMAIL_PROVIDER")
    if email_provider == "sendgrid":
        ANYMAIL = {
            "SENDGRID_API_KEY": os.getenv("SENDGRID_API_KEY"),
            "SENDGRID_GENERATE_MESSAGE_ID": True,
        }
        EMAIL_BACKEND = "anymail.backends.sendgrid.EmailBackend"
    elif email_provider == "mailgun":
        ANYMAIL = {
            "MAILGUN_API_KEY": os.getenv("MAILGUN_API_KEY"),
            "MAILGUN_SENDER_DOMAIN": os.getenv("MAILGUN_SENDER_DOMAIN"),
        }
        EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"

# SMTP Configuration (fallback)
if EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
    EMAIL_HOST = os.getenv("EMAIL_HOST")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

# Logging Configuration - Staging (JSON format)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
        },
        "verbose": {
            "format": "{levelname} {asctime} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "django_staging.log",
            "maxBytes": 1024 * 1024 * 10,  # 10 MB
            "backupCount": 10,
            "formatter": "json",
        },
    },
    "root": {
        "handlers": ["console", "file"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "file"],
            "level": "WARNING",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console", "file"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# Security Settings - Staging (Production-like)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
LANGUAGE_COOKIE_SECURE = True
WAFFLE_SECURE = True

# HTTPS and SSL Settings
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 3600  # 1 hour (shorter than production)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False  # Don't preload in staging

# Django Compressor - Enabled in staging
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = False
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "compressor.finders.CompressorFinder",
]

# Django Silk - Limited profiling in staging
SILKY_PYTHON_PROFILER = False
SILKY_PYTHON_PROFILER_BINARY = False
SILKY_AUTHENTICATION = True
SILKY_AUTHORISATION = True
SILKY_MAX_RECORDED_REQUESTS = 5000
SILKY_INTERCEPT_PERCENT = 10  # Profile 10% of requests
SILKY_META = False
SILKY_ANALYZE_QUERIES = True

# Waffle - Don't create missing flags in staging
WAFFLE_CREATE_MISSING_FLAGS = False
WAFFLE_OVERRIDE = False

# Social Account Providers - Staging
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
}

# Backup System Configuration - Staging
BACKUP_ENCRYPTION_KEY = os.getenv("BACKUP_ENCRYPTION_KEY")
BACKUP_LOCAL_PATH = os.getenv("BACKUP_LOCAL_PATH", "/var/backups/jewelry-shop")

# Cloud Storage - Staging
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "b7900eeee7c415345d86ea859c9dad47")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "securesyntax-staging")
R2_ENDPOINT = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")

B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME", "securesyntax-staging")
B2_BUCKET_ID = os.getenv("B2_BUCKET_ID")
B2_REGION = os.getenv("B2_REGION", "us-east-005")
B2_ENDPOINT = f"https://s3.{B2_REGION}.backblazeb2.com"
B2_ACCESS_KEY_ID = os.getenv("B2_ACCESS_KEY_ID")
B2_SECRET_ACCESS_KEY = os.getenv("B2_SECRET_ACCESS_KEY")

# API Keys - Staging
GOLDAPI_KEY = os.getenv("GOLDAPI_KEY")
METALS_API_KEY = os.getenv("METALS_API_KEY")
FIELD_ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY")

# Twilio SMS - Staging
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Stripe - Staging (Test mode)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_LIVE_MODE = False

# Rate Limiting - Enabled in staging
RATELIMIT_ENABLE = True
RATELIMIT_DEFAULT_RATE = os.getenv("RATELIMIT_DEFAULT_RATE", "100/h")
RATELIMIT_STRICT_RATE = os.getenv("RATELIMIT_STRICT_RATE", "10/m")

# Sentry - Enabled in staging
SENTRY_DSN = os.getenv("SENTRY_DSN", "")
SENTRY_ENVIRONMENT = "staging"
SENTRY_RELEASE = os.getenv("SENTRY_RELEASE")
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.5"))

if SENTRY_DSN:
    from apps.core.sentry_config import initialize_sentry

    initialize_sentry(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        release=SENTRY_RELEASE,
    )

# Validate required environment variables
validate_required_env_vars()
validate_security_settings(DEBUG)
