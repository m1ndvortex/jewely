"""
Production-specific Django settings.
Maximum security and performance optimizations.
"""

import os

# Load environment variables from .env file
from dotenv import load_dotenv

from .base import *  # noqa: F403,F405

load_dotenv()

# SECURITY WARNING: Use a strong secret key in production
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY must be set in production environment!")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",")
if not ALLOWED_HOSTS or ALLOWED_HOSTS == [""]:
    raise ValueError("DJANGO_ALLOWED_HOSTS must be set in production environment!")

# Site URL
SITE_URL = os.getenv("SITE_URL")
if not SITE_URL:
    raise ValueError("SITE_URL must be set in production environment!")

# Database with Prometheus monitoring
DATABASES = {
    "default": {
        "ENGINE": "django_prometheus.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB"),
        "USER": os.getenv("POSTGRES_USER") or os.getenv("DB_USER"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD") or os.getenv("APP_DB_PASSWORD"),
        "HOST": os.getenv("POSTGRES_HOST"),
        "PORT": os.getenv("POSTGRES_PORT", "5432"),
        "ATOMIC_REQUESTS": True,
        "CONN_MAX_AGE": 600,
        "OPTIONS": {
            "connect_timeout": 10,
            "options": "-c statement_timeout=30000",  # 30 second query timeout
            "sslmode": os.getenv("DB_SSLMODE", "prefer"),  # SSL mode for PostgreSQL
        },
    }
}

# PgBouncer Configuration - Recommended for production
USE_PGBOUNCER = os.getenv("USE_PGBOUNCER", "True") == "True"
if USE_PGBOUNCER:
    DATABASES["default"]["HOST"] = os.getenv("PGBOUNCER_HOST", "pgbouncer")
    DATABASES["default"]["PORT"] = os.getenv("PGBOUNCER_PORT", "6432")
    DATABASES["default"]["CONN_MAX_AGE"] = 0
    DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

# Redis Cache Configuration - Production
redis_host = os.getenv("REDIS_HOST")
redis_port = os.getenv("REDIS_PORT", "6379")
redis_password = os.getenv("REDIS_PASSWORD", "")

redis_url_base = (
    f"redis://:{redis_password}@{redis_host}:{redis_port}"
    if redis_password
    else f"redis://{redis_host}:{redis_port}"
)

CACHES = {
    "default": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": f"{redis_url_base}/0",
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "RETRY_ON_TIMEOUT": True,
            "MAX_CONNECTIONS": 100,
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 100,
                "retry_on_timeout": True,
            },
        },
        "KEY_PREFIX": "jewelry_shop_prod",
        "TIMEOUT": 300,
    },
    "query": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": f"{redis_url_base}/1",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient", "MAX_CONNECTIONS": 100},
        "KEY_PREFIX": "jewelry_shop_prod_query",
        "TIMEOUT": 900,
    },
    "template": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": f"{redis_url_base}/2",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient", "MAX_CONNECTIONS": 100},
        "KEY_PREFIX": "jewelry_shop_prod_template",
        "TIMEOUT": 600,
    },
    "api": {
        "BACKEND": "django_prometheus.cache.backends.redis.RedisCache",
        "LOCATION": f"{redis_url_base}/3",
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient", "MAX_CONNECTIONS": 100},
        "KEY_PREFIX": "jewelry_shop_prod_api",
        "TIMEOUT": 180,
    },
}

# Celery Configuration - Production
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", f"{redis_url_base}/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", f"{redis_url_base}/0")
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = (
    os.getenv("CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP", "true").lower() == "true"
)

# Email Configuration - Production
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)

if not DEFAULT_FROM_EMAIL:
    raise ValueError("DEFAULT_FROM_EMAIL must be set in production environment!")

# Configure email provider
if "anymail" in EMAIL_BACKEND.lower():
    INSTALLED_APPS.append("anymail")

    email_provider = os.getenv("EMAIL_PROVIDER")
    if not email_provider:
        raise ValueError("EMAIL_PROVIDER must be set when using anymail!")

    if email_provider == "sendgrid":
        ANYMAIL = {
            "SENDGRID_API_KEY": os.getenv("SENDGRID_API_KEY"),
            "SENDGRID_GENERATE_MESSAGE_ID": True,
            "SENDGRID_MERGE_FIELD_FORMAT": "-{}-",
            "SENDGRID_API_URL": "https://api.sendgrid.com/v3/",
        }
        EMAIL_BACKEND = "anymail.backends.sendgrid.EmailBackend"
    elif email_provider == "mailgun":
        ANYMAIL = {
            "MAILGUN_API_KEY": os.getenv("MAILGUN_API_KEY"),
            "MAILGUN_SENDER_DOMAIN": os.getenv("MAILGUN_SENDER_DOMAIN"),
            "MAILGUN_API_URL": "https://api.mailgun.net/v3",
        }
        EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
    elif email_provider == "ses":
        ANYMAIL = {
            "AMAZON_SES_REGION": os.getenv("AWS_SES_REGION", "us-east-1"),
            "AMAZON_SES_ACCESS_KEY_ID": os.getenv("AWS_ACCESS_KEY_ID"),
            "AMAZON_SES_SECRET_ACCESS_KEY": os.getenv("AWS_SECRET_ACCESS_KEY"),
        }
        EMAIL_BACKEND = "anymail.backends.amazon_ses.EmailBackend"

# SMTP Configuration (fallback)
if EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend":
    EMAIL_HOST = os.getenv("EMAIL_HOST")
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
    EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False") == "True"
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

    if not EMAIL_HOST or not EMAIL_HOST_USER or not EMAIL_HOST_PASSWORD:
        raise ValueError(
            "EMAIL_HOST, EMAIL_HOST_USER, and EMAIL_HOST_PASSWORD must be set for SMTP!"
        )

# Logging Configuration - Production (JSON format for log aggregation)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "%(asctime)s %(name)s %(levelname)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "json",
        },
        "file": {
            "level": "WARNING",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "django_production.log",
            "maxBytes": 1024 * 1024 * 50,  # 50 MB
            "backupCount": 20,
            "formatter": "json",
        },
        "error_file": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": BASE_DIR / "logs" / "django_errors.log",
            "maxBytes": 1024 * 1024 * 50,  # 50 MB
            "backupCount": 20,
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
            "handlers": ["console", "error_file"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console", "error_file"],
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

# Security Settings - Production (Maximum security)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
LANGUAGE_COOKIE_SECURE = True
WAFFLE_SECURE = True

# HTTPS and SSL Settings
# SSL is terminated at the proxy (Traefik/Nginx), not at Django
# Django needs to trust the X-Forwarded-Proto header from the proxy
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Allow disabling SSL redirect for local testing (default: True for production)
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True") == "True"
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Django Compressor - Enabled with offline compression in production
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True  # Pre-compress assets during deployment
COMPRESS_CSS_FILTERS = [
    "compressor.filters.css_default.CssAbsoluteFilter",
    "compressor.filters.cssmin.rCSSMinFilter",
]
COMPRESS_JS_FILTERS = [
    "compressor.filters.jsmin.JSMinFilter",
]
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "compressor.finders.CompressorFinder",
]

# Django Silk - Disabled in production (use APM tools instead)
SILKY_PYTHON_PROFILER = False
SILKY_PYTHON_PROFILER_BINARY = False
SILKY_AUTHENTICATION = True
SILKY_AUTHORISATION = True
SILKY_MAX_RECORDED_REQUESTS = 1000
SILKY_INTERCEPT_PERCENT = 0  # Disabled in production
SILKY_META = False
SILKY_ANALYZE_QUERIES = False

# Waffle - Strict mode in production
WAFFLE_CREATE_MISSING_FLAGS = False
WAFFLE_OVERRIDE = False

# Social Account Providers - Production
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online", "prompt": "select_account"},
        "APP": {
            "client_id": os.getenv("GOOGLE_OAUTH_CLIENT_ID"),
            "secret": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET"),
            "key": "",
        },
    },
    "github": {
        "SCOPE": ["user", "user:email"],
        "APP": {
            "client_id": os.getenv("GITHUB_OAUTH_CLIENT_ID"),
            "secret": os.getenv("GITHUB_OAUTH_CLIENT_SECRET"),
            "key": "",
        },
    },
    "facebook": {
        "METHOD": "oauth2",
        "SCOPE": ["email", "public_profile"],
        "AUTH_PARAMS": {"auth_type": "reauthenticate"},
        "FIELDS": ["id", "email", "name", "first_name", "last_name", "verified"],
        "EXCHANGE_TOKEN": True,
        "VERSION": "v13.0",
        "APP": {
            "client_id": os.getenv("FACEBOOK_OAUTH_CLIENT_ID"),
            "secret": os.getenv("FACEBOOK_OAUTH_CLIENT_SECRET"),
            "key": "",
        },
    },
}

# Backup System Configuration - Production
BACKUP_ENCRYPTION_KEY = os.getenv("BACKUP_ENCRYPTION_KEY")
if not BACKUP_ENCRYPTION_KEY:
    raise ValueError("BACKUP_ENCRYPTION_KEY must be set in production!")

BACKUP_LOCAL_PATH = os.getenv("BACKUP_LOCAL_PATH", "/var/backups/jewelry-shop")

# Cloud Storage - Production
R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "b7900eeee7c415345d86ea859c9dad47")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "securesyntax")
R2_ENDPOINT = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")

if not R2_ACCESS_KEY_ID or not R2_SECRET_ACCESS_KEY:
    raise ValueError("R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY must be set in production!")

B2_BUCKET_NAME = os.getenv("B2_BUCKET_NAME", "securesyntax")
B2_BUCKET_ID = os.getenv("B2_BUCKET_ID", "2a0cfb4aa9f8f8f29c820b18")
B2_REGION = os.getenv("B2_REGION", "us-east-005")
B2_ENDPOINT = f"https://s3.{B2_REGION}.backblazeb2.com"
B2_ACCESS_KEY_ID = os.getenv("B2_ACCESS_KEY_ID")
B2_SECRET_ACCESS_KEY = os.getenv("B2_SECRET_ACCESS_KEY")

if not B2_ACCESS_KEY_ID or not B2_SECRET_ACCESS_KEY:
    raise ValueError("B2_ACCESS_KEY_ID and B2_SECRET_ACCESS_KEY must be set in production!")

# API Keys - Production
GOLDAPI_KEY = os.getenv("GOLDAPI_KEY")
METALS_API_KEY = os.getenv("METALS_API_KEY")
FIELD_ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY")

if not FIELD_ENCRYPTION_KEY:
    raise ValueError("FIELD_ENCRYPTION_KEY must be set in production!")

# Twilio SMS - Production
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# Alertmanager Webhook Token - Production
# This token is used to authenticate webhook requests from Alertmanager
ALERT_WEBHOOK_TOKEN = os.getenv("ALERT_WEBHOOK_TOKEN")
if not ALERT_WEBHOOK_TOKEN:
    raise ValueError("ALERT_WEBHOOK_TOKEN must be set in production!")

# Stripe - Production (Live mode)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_LIVE_MODE = os.getenv("STRIPE_LIVE_MODE", "True") == "True"

if STRIPE_LIVE_MODE and not all([STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_WEBHOOK_SECRET]):
    raise ValueError("All Stripe keys must be set when STRIPE_LIVE_MODE is True!")

# Rate Limiting - Strict in production
RATELIMIT_ENABLE = True
RATELIMIT_DEFAULT_RATE = os.getenv("RATELIMIT_DEFAULT_RATE", "100/h")
RATELIMIT_STRICT_RATE = os.getenv("RATELIMIT_STRICT_RATE", "10/m")
RATELIMIT_LENIENT_RATE = os.getenv("RATELIMIT_LENIENT_RATE", "500/h")
RATELIMIT_TENANT_RATE = os.getenv("RATELIMIT_TENANT_RATE", "1000/h")
RATELIMIT_USER_RATE = os.getenv("RATELIMIT_USER_RATE", "100/h")

# Sentry - Enabled in production
SENTRY_DSN = os.getenv("SENTRY_DSN")
SENTRY_ENVIRONMENT = "production"
SENTRY_RELEASE = os.getenv("SENTRY_RELEASE")
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1"))

if SENTRY_DSN:
    from apps.core.sentry_config import initialize_sentry

    initialize_sentry(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        traces_sample_rate=SENTRY_TRACES_SAMPLE_RATE,
        release=SENTRY_RELEASE,
    )
else:
    print("WARNING: SENTRY_DSN not set. Error tracking is disabled!")

# Validate all required environment variables
validate_required_env_vars()
validate_security_settings(DEBUG)

# Additional production-specific validations
if SECRET_KEY == "dev-secret-key-change-in-production":
    raise ValueError("SECRET_KEY must be changed from default value in production!")

if len(SECRET_KEY) < 50:
    raise ValueError("SECRET_KEY must be at least 50 characters long in production!")

print("✓ Production settings loaded successfully")
print(f"✓ Site URL: {SITE_URL}")
print(f"✓ Allowed hosts: {', '.join(ALLOWED_HOSTS)}")
print(f"✓ Database: {DATABASES['default']['NAME']} @ {DATABASES['default']['HOST']}")
print(f"✓ Redis: {redis_host}:{redis_port}")
print(f"✓ PgBouncer: {'Enabled' if USE_PGBOUNCER else 'Disabled'}")
print(f"✓ Sentry: {'Enabled' if SENTRY_DSN else 'Disabled'}")
print(f"✓ Stripe: {'Live Mode' if STRIPE_LIVE_MODE else 'Test Mode'}")
