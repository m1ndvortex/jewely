# Django Settings Configuration

This directory contains environment-specific Django settings for the Jewelry Shop SaaS platform.

## Settings Structure

```
config/settings/
├── __init__.py          # Package initialization
├── base.py              # Common settings for all environments
├── development.py       # Development-specific settings
├── staging.py           # Staging-specific settings
├── production.py        # Production-specific settings
└── README.md            # This file
```

## Environment Selection

The active settings module is determined by the `DJANGO_SETTINGS_MODULE` environment variable:

- **Development**: `config.settings.development` (default for manage.py)
- **Staging**: `config.settings.staging`
- **Production**: `config.settings.production` (default for wsgi.py/asgi.py)

## Usage

### Local Development

```bash
# Use default development settings
python manage.py runserver

# Or explicitly set the environment
export DJANGO_SETTINGS_MODULE=config.settings.development
python manage.py runserver
```

### Docker Development

```bash
# Development uses default settings from manage.py
docker compose up

# Or override in docker-compose.yml
environment:
  - DJANGO_SETTINGS_MODULE=config.settings.development
```

### Staging Deployment

```bash
# Set environment variable
export DJANGO_SETTINGS_MODULE=config.settings.staging

# Or in docker-compose
docker compose -f docker-compose.prod.yml up
```

### Production Deployment

```bash
# Production settings are default for WSGI/ASGI
# Ensure .env file has correct values
docker compose -f docker-compose.prod.yml up
```

## Environment Variables

Each environment requires specific environment variables. See the example files:

- `.env.development.example` - Development configuration
- `.env.staging.example` - Staging configuration
- `.env.production.example` - Production configuration

### Required Variables (All Environments)

```bash
DJANGO_SECRET_KEY=<strong-secret-key>
POSTGRES_DB=<database-name>
POSTGRES_USER=<database-user>
POSTGRES_PASSWORD=<database-password>
POSTGRES_HOST=<database-host>
REDIS_HOST=<redis-host>
```

### Production-Only Required Variables

```bash
DJANGO_ALLOWED_HOSTS=<comma-separated-hosts>
SITE_URL=<https://your-domain.com>
BACKUP_ENCRYPTION_KEY=<32-byte-encryption-key>
R2_ACCESS_KEY_ID=<cloudflare-r2-key>
R2_SECRET_ACCESS_KEY=<cloudflare-r2-secret>
B2_ACCESS_KEY_ID=<backblaze-b2-key>
B2_SECRET_ACCESS_KEY=<backblaze-b2-secret>
FIELD_ENCRYPTION_KEY=<field-encryption-key>
DEFAULT_FROM_EMAIL=<email-address>
SENTRY_DSN=<sentry-dsn>
```

## Settings Validation

Each environment-specific settings file includes validation:

### Development
- Relaxed validation
- Warnings for missing optional variables
- Uses default values where safe

### Staging
- Strict validation for critical variables
- Production-like security settings
- Requires most production variables

### Production
- Strictest validation
- All security settings enforced
- Fails fast on missing required variables
- Validates secret key strength
- Validates encryption keys

## Key Differences by Environment

### Development
- `DEBUG = True`
- Console email backend
- Verbose logging
- All Silk profiling enabled
- Relaxed security settings
- Auto-create Waffle flags
- No HTTPS required

### Staging
- `DEBUG = False` (configurable)
- Real email backend
- JSON logging
- Limited Silk profiling (10%)
- Production-like security
- HTTPS required
- Sentry enabled

### Production
- `DEBUG = False` (enforced)
- Real email backend (required)
- JSON logging only
- Silk disabled
- Maximum security settings
- HTTPS required (enforced)
- Sentry required
- PgBouncer recommended
- Asset compression enabled

## Security Features

### All Environments
- Argon2 password hashing
- CSRF protection
- XSS protection
- Clickjacking protection
- Content type sniffing protection

### Staging & Production Only
- Secure cookies (HTTPS only)
- HSTS headers
- SSL redirect
- Strict rate limiting
- Brute force protection

## Adding New Settings

When adding new settings:

1. Add common settings to `base.py`
2. Add environment-specific overrides to respective files
3. Update `.env.*.example` files
4. Update this README
5. Add validation if required

## Troubleshooting

### "Missing required environment variables" Error

Ensure your `.env` file contains all required variables for your environment.
Copy from the appropriate `.env.*.example` file.

### "DJANGO_SECRET_KEY must be changed" Error

In production, you must use a strong, unique secret key.
Generate one with:

```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

### Settings Not Loading

Check that `DJANGO_SETTINGS_MODULE` is set correctly:

```bash
echo $DJANGO_SETTINGS_MODULE
```

### Import Errors

Ensure you're importing from the correct module:

```python
# Correct
from django.conf import settings

# Incorrect
from config.settings import base
```

## Best Practices

1. **Never commit `.env` files** - They contain secrets
2. **Use strong secrets in production** - At least 50 characters
3. **Rotate secrets regularly** - Especially encryption keys
4. **Test in staging first** - Before deploying to production
5. **Monitor Sentry** - For production errors
6. **Use PgBouncer in production** - For connection pooling
7. **Enable all security features** - In production
8. **Keep settings DRY** - Common settings in base.py

## References

- [Django Settings Documentation](https://docs.djangoproject.com/en/4.2/topics/settings/)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/)
- [12-Factor App Configuration](https://12factor.net/config)
