# Jewelry Shop SaaS Platform

Enterprise-grade, multi-tenant B2B SaaS platform for gold and jewelry shop management.

## Features

- Multi-tenant architecture with PostgreSQL Row-Level Security (RLS)
- Comprehensive inventory management
- Point of Sale (POS) system with offline mode
- Customer Relationship Management (CRM)
- Double-entry accounting
- Repair and custom order tracking
- Multi-branch management
- Advanced reporting and analytics
- Enterprise backup and disaster recovery
- Dual-language support (English/Persian)
- Dual-theme support (Light/Dark)

## Technology Stack

- **Backend**: Django 4.2+, PostgreSQL 15+, Redis 7+, Celery
- **Frontend**: Django Templates, HTMX, Alpine.js, Tailwind CSS
- **Infrastructure**: Docker, Kubernetes, Nginx
- **Storage**: Cloudflare R2, Backblaze B2

## Prerequisites

- Docker and Docker Compose
- Git

## Quick Start

1. Clone the repository:
```bash
git clone <repository-url>
cd jewelry-shop
```

2. Copy environment variables:
```bash
cp .env.example .env
```

3. Start all services:
```bash
docker-compose up -d
```

4. Run migrations:
```bash
docker-compose exec web python manage.py migrate
```

5. Create a superuser:
```bash
docker-compose exec web python manage.py createsuperuser
```

6. Access the application:
- Application: http://localhost:8000
- Admin Panel: http://localhost:8000/admin
- Health Check: http://localhost:8000/health/

## Development

### Running Commands

All commands must be run inside Docker containers:

```bash
# Django management commands
docker-compose exec web python manage.py <command>

# Run tests
docker-compose exec web pytest

# Run tests with coverage
docker-compose exec web pytest --cov=. --cov-report=html

# Access Django shell
docker-compose exec web python manage.py shell

# Access database
docker-compose exec db psql -U postgres -d jewelry_shop

# Access Redis CLI
docker-compose exec redis redis-cli

# View logs
docker-compose logs -f web
docker-compose logs -f celery_worker
```

### Code Quality

Pre-commit hooks are configured for code quality:

```bash
# Install pre-commit hooks (run once inside container)
docker-compose exec web pre-commit install

# Run pre-commit manually
docker-compose exec web pre-commit run --all-files

# Run black formatter
docker-compose exec web black .

# Run isort
docker-compose exec web isort .

# Run flake8
docker-compose exec web flake8 .

# Run mypy
docker-compose exec web mypy .
```

### Testing

```bash
# Run all tests
docker-compose exec web pytest

# Run specific test file
docker-compose exec web pytest tests/test_core.py

# Run with coverage
docker-compose exec web pytest --cov=apps --cov=config --cov-report=html

# Run only unit tests
docker-compose exec web pytest -m unit

# Run only integration tests
docker-compose exec web pytest -m integration

# Run tests in parallel
docker-compose exec web pytest -n auto
```

### Database Operations

```bash
# Create migrations
docker-compose exec web python manage.py makemigrations

# Apply migrations
docker-compose exec web python manage.py migrate

# Create a superuser
docker-compose exec web python manage.py createsuperuser

# Access database shell
docker-compose exec db psql -U postgres -d jewelry_shop
```

### Celery Tasks

```bash
# View Celery worker logs
docker-compose logs -f celery_worker

# View Celery beat logs
docker-compose logs -f celery_beat

# Restart Celery worker
docker-compose restart celery_worker

# Test Celery task
docker-compose exec web python manage.py shell
>>> from config.celery import debug_task
>>> debug_task.delay()
```

## Project Structure

```
jewelry-shop/
├── apps/                   # Django applications
│   ├── core/              # Core functionality
│   └── ...                # Other apps
├── config/                # Django configuration
│   ├── settings.py        # Settings
│   ├── urls.py           # URL configuration
│   ├── wsgi.py           # WSGI configuration
│   ├── asgi.py           # ASGI configuration
│   └── celery.py         # Celery configuration
├── tests/                 # Test files
├── static/               # Static files
├── media/                # Media files
├── templates/            # Django templates
├── logs/                 # Application logs
├── docker-compose.yml    # Docker Compose configuration
├── Dockerfile            # Docker image definition
├── requirements.txt      # Python dependencies
├── .env                  # Environment variables
├── manage.py            # Django management script
└── README.md            # This file
```

## Environment Variables

Key environment variables (see `.env.example` for full list):

- `DJANGO_SECRET_KEY`: Django secret key (change in production)
- `DJANGO_DEBUG`: Debug mode (True/False)
- `POSTGRES_DB`: Database name
- `POSTGRES_USER`: Database user
- `POSTGRES_PASSWORD`: Database password
- `REDIS_HOST`: Redis host
- `CELERY_BROKER_URL`: Celery broker URL

## Docker Services

- `web`: Django application server
- `db`: PostgreSQL database
- `redis`: Redis cache and message broker
- `celery_worker`: Celery worker for background tasks
- `celery_beat`: Celery beat for scheduled tasks

## Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

## Troubleshooting

### Database Connection Issues

```bash
# Check if database is running
docker-compose ps db

# View database logs
docker-compose logs db

# Restart database
docker-compose restart db
```

### Redis Connection Issues

```bash
# Check if Redis is running
docker-compose ps redis

# Test Redis connection
docker-compose exec redis redis-cli ping
```

### Application Errors

```bash
# View application logs
docker-compose logs -f web

# Restart application
docker-compose restart web
```

## Documentation

- [Requirements](.kiro/specs/jewelry-saas-platform/requirements.md)
- [Design](.kiro/specs/jewelry-saas-platform/design.md)
- [Tasks](.kiro/specs/jewelry-saas-platform/tasks.md)

## License

Proprietary - All rights reserved
