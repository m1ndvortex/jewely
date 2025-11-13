# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an enterprise-grade, multi-tenant B2B SaaS platform for jewelry shop management built with Django. It supports 500-10,000+ tenants with comprehensive features including inventory management, POS, CRM, double-entry accounting, repair tracking, and multi-branch management.

## Technology Stack

- **Backend**: Django 4.2+, PostgreSQL 15+ (with Row-Level Security), Redis 7+, Celery
- **Frontend**: Django Templates, HTMX, Alpine.js, Tailwind CSS
- **Infrastructure**: Docker, Docker Compose, Kubernetes, Nginx
- **Storage**: Cloudflare R2, Backblaze B2
- **Key Features**: Multi-tenant architecture with RLS, dual-language (English/Persian), dual-theme (light/dark), offline POS mode

## Essential Development Commands

All commands must be run through Docker containers:

### Service Management
```bash
make up                 # Start all services
make down               # Stop all services
make restart            # Restart all services
make clean              # Stop services and remove volumes
make logs               # View all service logs
make logs-web           # View Django logs
make logs-celery        # View Celery worker logs
```

### Django Development
```bash
# Django management commands
docker-compose exec web python manage.py <command>

# Common operations
make migrate            # Run database migrations
make makemigrations     # Create new migrations
make createsuperuser    # Create superuser account
make shell              # Access Django shell
make dbshell            # Access PostgreSQL shell
```

### Testing
```bash
make test               # Run all tests
make test-cov           # Run tests with coverage report
docker-compose exec web pytest tests/test_core.py  # Run specific test file
docker-compose exec web pytest -m unit             # Run only unit tests
docker-compose exec web pytest -m integration      # Run only integration tests
docker-compose exec web pytest -m rls              # Run Row-Level Security tests
```

### Code Quality
```bash
make format             # Format code with black and isort
make lint               # Run flake8 and mypy linters
docker-compose exec web black .                    # Format code manually
docker-compose exec web isort .                    # Sort imports manually
docker-compose exec web flake8 .                   # Run linting manually
```

## Architecture & Key Patterns

### Multi-Tenant Architecture
- Tenant isolation via PostgreSQL Row-Level Security (RLS) at database level
- Tenant context middleware: `apps.core.middleware.TenantContextMiddleware`
- All tenant-scoped models inherit from `TenantModel` base class
- Tenant context is maintained throughout request lifecycle

### Django Apps Structure
- `apps/core/`: Core functionality, authentication, tenant management, middleware
- `apps/inventory/`: Product and inventory management
- `apps/sales/`: POS and sales transactions
- `apps/crm/`: Customer relationship management
- `apps/accounting/`: Double-entry accounting with django-ledger
- `apps/repair/`: Repair and custom order tracking
- `apps/procurement/`: Purchase order management
- `apps/pricing/`: Dynamic pricing rules
- `apps/reporting/`: Analytics and reports
- `apps/notifications/`: Email/SMS notifications
- `apps/backups/`: Backup and disaster recovery

### Settings Configuration
- `config/settings/base.py`: Common settings for all environments
- `config/settings/development.py`: Local development settings (default)
- `config/settings/staging.py`: Staging environment settings
- `config/settings/production.py`: Production settings with security hardening
- Settings module selected via `DJANGO_SETTINGS_MODULE` environment variable

### Background Tasks
- Celery for asynchronous task processing
- Redis as message broker
- Celery Beat for scheduled tasks
- Task definitions in `config/celery.py` and app-specific `tasks.py` files

### Frontend Architecture
- Server-side rendering with Django templates
- HTMX for dynamic UI updates without full page reloads
- Alpine.js for reactive components
- Tailwind CSS for styling
- Dual-theme support (light/dark) via CSS variables
- RTL support for Persian language

## Database Considerations

### Row-Level Security (RLS)
- All tenant data queries automatically filtered by tenant_id
- RLS policies defined in PostgreSQL migrations
- Never bypass RLS without explicit authorization
- Test tenant isolation with dedicated RLS test markers

### Connection Pooling
- PgBouncer configured for connection pooling in production
- Connection through `pgbouncer` service on port 6432
- Database migrations run directly against PostgreSQL, not through PgBouncer

## Testing Strategy

- **Unit Tests**: Test individual functions and methods in isolation
- **Integration Tests**: Test component interactions and database operations
- **RLS Tests**: Verify tenant data isolation
- **Coverage Requirement**: Minimum 75% code coverage
- Use pytest markers to categorize tests: `@pytest.mark.unit`, `@pytest.mark.integration`, `@pytest.mark.rls`

## Deployment

### Development
- Uses `docker-compose.yml` for local development
- Hot reload enabled for Django development server
- Debug mode enabled with Django Debug Toolbar

### Production/Kubernetes
- Kubernetes manifests in `k8s/` directory
- Uses `Dockerfile.prod` for production image
- Horizontal Pod Autoscaling (HPA) for Celery workers
- ConfigMaps for environment configuration
- Secrets for sensitive data
- Health checks at `/health/` endpoint

### CI/CD Pipeline
- GitHub Actions workflow in `.github/workflows/ci.yml`
- Automated testing, linting, and security checks on all PRs
- Staging auto-deploy on merge to `develop` branch
- Production deployment requires manual approval

## Security Considerations

- Multi-factor authentication (MFA) with TOTP
- Session security with Redis-backed sessions
- Rate limiting on API endpoints
- Security headers middleware for XSS, CSRF protection
- Audit logging middleware tracks all data modifications
- Never commit secrets - use environment variables

## Internationalization

- English (en) and Persian (fa) languages supported
- Persian uses Jalali calendar and Persian numerals (۰۱۲۳۴۵۶۷۸۹)
- RTL layout automatically applied for Persian
- Translation files in `locale/` directories
- Use Django's translation utilities: `gettext_lazy`, `ngettext`

## Important Files & Locations

- Requirements: `.kiro/specs/jewelry-saas-platform/requirements.md`
- Design docs: `.kiro/specs/jewelry-saas-platform/design.md`
- Task tracking: `.kiro/specs/jewelry-saas-platform/tasks.md`
- Environment example: `.env.example`
- Pre-commit hooks: `.pre-commit-config.yaml`
- Test configuration: `pytest.ini`