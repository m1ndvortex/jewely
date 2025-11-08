# Settings Migration Guide

This guide explains the migration from monolithic `config/settings.py` to environment-specific settings modules.

## What Changed

### Before (Task 32.2)
```
config/
├── settings.py          # Single file for all environments
├── wsgi.py
├── asgi.py
└── celery.py
```

### After (Task 32.3)
```
config/
├── settings/
│   ├── __init__.py
│   ├── base.py          # Common settings
│   ├── development.py   # Dev-specific
│   ├── staging.py       # Staging-specific
│   ├── production.py    # Production-specific
│   └── README.md
├── settings.py.backup   # Backup of old file
├── wsgi.py              # Updated
├── asgi.py              # Updated
└── celery.py            # Updated
```

## Migration Steps

### 1. Update Environment Variables

Add `DJANGO_SETTINGS_MODULE` to your environment:

**Development:**
```bash
export DJANGO_SETTINGS_MODULE=config.settings.development
```

**Staging:**
```bash
export DJANGO_SETTINGS_MODULE=config.settings.staging
```

**Production:**
```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
```

### 2. Update .env File

Copy the appropriate example file:

```bash
# For development
cp .env.development.example .env

# For staging
cp .env.staging.example .env

# For production
cp .env.production.example .env
```

Then edit `.env` with your actual values.

### 3. Rebuild Docker Containers

The new settings files need to be included in the Docker image:

```bash
# Development
docker compose build
docker compose up -d

# Production
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
```

### 4. Verify Settings

Test that settings load correctly:

```bash
# Development
docker compose exec web python manage.py check

# Production
docker compose -f docker-compose.prod.yml exec web python manage.py check
```

## Key Differences

### Development Settings
- `DEBUG = True`
- Console email backend
- Verbose logging
- Relaxed security
- No HTTPS required

### Staging Settings
- `DEBUG = False` (configurable)
- Real email backend
- JSON logging
- Production-like security
- HTTPS required

### Production Settings
- `DEBUG = False` (enforced)
- Real email backend (required)
- JSON logging only
- Maximum security
- HTTPS required
- Strict validation

## Troubleshooting

### "No module named 'config.settings.development'"

**Cause:** Docker container doesn't have the new settings files.

**Solution:** Rebuild the Docker image:
```bash
docker compose build
docker compose up -d
```

### "Missing required environment variables"

**Cause:** Your `.env` file doesn't have all required variables.

**Solution:** Copy from the appropriate `.env.*.example` file and fill in values.

### Settings not loading

**Cause:** `DJANGO_SETTINGS_MODULE` not set correctly.

**Solution:** Check the environment variable:
```bash
echo $DJANGO_SETTINGS_MODULE
```

Should be one of:
- `config.settings.development`
- `config.settings.staging`
- `config.settings.production`

### Import errors in code

**Cause:** Code trying to import settings directly.

**Solution:** Always use Django's settings:
```python
# Correct
from django.conf import settings

# Incorrect
from config.settings import base
from config.settings.production import SECRET_KEY
```

## Rollback Instructions

If you need to rollback to the old settings:

1. Restore the backup:
```bash
mv config/settings.py.backup config/settings.py
```

2. Update manage.py:
```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
```

3. Update wsgi.py and asgi.py:
```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
```

4. Update celery.py:
```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
```

5. Update docker-compose.prod.yml:
```yaml
environment:
  - DJANGO_SETTINGS_MODULE=config.settings
```

6. Rebuild containers:
```bash
docker compose build
docker compose up -d
```

## Benefits of New Structure

1. **Clear separation** - Each environment has its own file
2. **Better validation** - Environment-specific validation
3. **Easier maintenance** - Common settings in base.py
4. **Safer deployments** - Production settings enforced
5. **Better documentation** - Each file documents its purpose
6. **Industry standard** - Follows Django best practices

## Next Steps

After migration:

1. ✅ Test in development environment
2. ✅ Test in staging environment
3. ✅ Deploy to production
4. ✅ Monitor for issues
5. ✅ Remove `config/settings.py.backup` after confirming everything works

## Support

For issues or questions:
- Check `config/settings/README.md`
- Review `.env.*.example` files
- Check Django logs: `docker compose logs web`
