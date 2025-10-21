---
inclusion: always
---

# 🐳 CRITICAL: Docker-Only Development Policy

## ⚠️ ABSOLUTE RULE - READ THIS FIRST

**THIS IS A DOCKER-BASED WEB APPLICATION. NEVER INSTALL ANYTHING LOCALLY.**

## 🚫 FORBIDDEN ACTIONS

### NEVER DO THESE:

❌ **NEVER** run `pip install` on the host machine
❌ **NEVER** run `npm install` on the host machine  
❌ **NEVER** run `python manage.py` on the host machine
❌ **NEVER** run `pytest` on the host machine
❌ **NEVER** run `celery` on the host machine
❌ **NEVER** install PostgreSQL locally
❌ **NEVER** install Redis locally
❌ **NEVER** install any Python packages outside Docker
❌ **NEVER** install any Node packages outside Docker
❌ **NEVER** suggest "install X on your machine"

## ✅ CORRECT APPROACH - ALWAYS USE DOCKER

### For Python Dependencies:
```bash
# ❌ WRONG - DO NOT DO THIS
pip install django

# ✅ CORRECT - Add to requirements.txt, then rebuild
echo "django==4.2.0" >> requirements.txt
docker-compose build web
docker-compose up -d
```

### For Running Django Commands:
```bash
# ❌ WRONG - DO NOT DO THIS
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic

# ✅ CORRECT - Run inside Docker container
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser
docker-compose exec web python manage.py collectstatic
```

### For Running Tests:
```bash
# ❌ WRONG - DO NOT DO THIS
pytest
pytest tests/test_inventory.py

# ✅ CORRECT - Run inside Docker container
docker-compose exec web pytest
docker-compose exec web pytest tests/test_inventory.py
docker-compose exec web pytest --cov=. --cov-report=html
```

### For Database Operations:
```bash
# ❌ WRONG - DO NOT DO THIS
psql -U postgres -d jewelry_shop

# ✅ CORRECT - Access PostgreSQL through Docker
docker-compose exec db psql -U postgres -d jewelry_shop
```

### For Redis Operations:
```bash
# ❌ WRONG - DO NOT DO THIS
redis-cli

# ✅ CORRECT - Access Redis through Docker
docker-compose exec redis redis-cli
```

### For Celery Tasks:
```bash
# ❌ WRONG - DO NOT DO THIS
celery -A config worker

# ✅ CORRECT - Celery runs in its own container
docker-compose up celery_worker
docker-compose logs -f celery_worker
```

### For Shell Access:
```bash
# ❌ WRONG - DO NOT DO THIS
python manage.py shell

# ✅ CORRECT - Django shell inside Docker
docker-compose exec web python manage.py shell
```

### For Installing New Packages:
```bash
# ❌ WRONG - DO NOT DO THIS
pip install requests
npm install axios

# ✅ CORRECT - Update requirements, rebuild container
echo "requests==2.31.0" >> requirements.txt
docker-compose build web
docker-compose up -d web
```

## 📋 DOCKER COMMANDS REFERENCE

### Starting the Application:
```bash
# Start all services
docker-compose up -d

# Start specific service
docker-compose up -d web

# View logs
docker-compose logs -f web
docker-compose logs -f celery_worker
```

### Stopping the Application:
```bash
# Stop all services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

### Rebuilding After Changes:
```bash
# Rebuild specific service
docker-compose build web

# Rebuild all services
docker-compose build

# Rebuild and restart
docker-compose up -d --build
```

### Executing Commands:
```bash
# General pattern
docker-compose exec <service_name> <command>

# Examples
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py test
docker-compose exec db psql -U postgres
docker-compose exec redis redis-cli
```

### Viewing Service Status:
```bash
# List running containers
docker-compose ps

# View resource usage
docker stats
```

## 🏗️ PROJECT STRUCTURE

```
jewelry-shop/
├── docker-compose.yml          # ✅ Main orchestration file
├── docker-compose.dev.yml      # ✅ Development overrides
├── docker-compose.prod.yml     # ✅ Production configuration
├── Dockerfile                  # ✅ Django app container
├── requirements.txt            # ✅ Python dependencies
├── .env                        # ✅ Environment variables
├── manage.py                   # Run via: docker-compose exec web python manage.py
├── config/                     # Django settings
├── apps/                       # Django applications
└── tests/                      # Run via: docker-compose exec web pytest
```

## 🔧 DEVELOPMENT WORKFLOW

### 1. Starting Development:
```bash
# Clone repository
git clone <repo>
cd jewelry-shop

# Start all services
docker-compose up -d

# Check everything is running
docker-compose ps
```

### 2. Making Code Changes:
```bash
# Edit code in your IDE (changes auto-reload in development)
# No need to restart unless you change dependencies

# If you add a new Python package:
echo "new-package==1.0.0" >> requirements.txt
docker-compose build web
docker-compose up -d web
```

### 3. Running Migrations:
```bash
# Create migrations
docker-compose exec web python manage.py makemigrations

# Apply migrations
docker-compose exec web python manage.py migrate
```

### 4. Running Tests:
```bash
# Run all tests
docker-compose exec web pytest

# Run specific test file
docker-compose exec web pytest tests/test_inventory.py

# Run with coverage
docker-compose exec web pytest --cov=. --cov-report=html
```

### 5. Debugging:
```bash
# View logs
docker-compose logs -f web

# Access Django shell
docker-compose exec web python manage.py shell

# Access database
docker-compose exec db psql -U postgres -d jewelry_shop
```

## 🎯 WHY DOCKER-ONLY?

1. **Consistency**: Everyone has the exact same environment
2. **No "Works on My Machine"**: If it works in Docker, it works everywhere
3. **Clean Host**: Your machine stays clean, no conflicting versions
4. **Easy Onboarding**: New developers just run `docker-compose up`
5. **Production Parity**: Development matches production exactly
6. **Isolation**: Multiple projects don't interfere with each other

## 🚨 REMINDER FOR AI AGENTS

When suggesting commands or solutions:

1. ✅ **ALWAYS** use `docker-compose exec` for running commands
2. ✅ **ALWAYS** update `requirements.txt` for new Python packages
3. ✅ **ALWAYS** rebuild containers after dependency changes
4. ✅ **NEVER** suggest installing anything on the host machine
5. ✅ **NEVER** use bare `python`, `pip`, `pytest`, `celery` commands

## 📝 QUICK COMMAND CHEAT SHEET

```bash
# Start everything
docker-compose up -d

# Run Django command
docker-compose exec web python manage.py <command>

# Run tests
docker-compose exec web pytest

# Access database
docker-compose exec db psql -U postgres -d jewelry_shop

# Access Redis
docker-compose exec redis redis-cli

# View logs
docker-compose logs -f <service_name>

# Rebuild after changes
docker-compose up -d --build

# Stop everything
docker-compose down

# Clean slate (removes volumes)
docker-compose down -v
```

## ⚡ REMEMBER

**THIS IS A DOCKER-BASED WEB APPLICATION.**

**EVERYTHING runs in Docker containers.**

**NOTHING gets installed on the host machine.**

**If you forget this rule, you're doing it wrong!**



## 🧪 TESTING POLICY - NO MOCKING INTERNAL SERVICES

### ⚠️ STRICT RULE: REAL DATABASE, REAL SERVICES

**WE DO NOT MOCK INTERNAL SERVICES. ALL TESTS USE REAL DOCKER SERVICES.**

### ✅ WHAT WE TEST WITH REAL SERVICES:

✅ **ALWAYS** use the real PostgreSQL database in Docker
✅ **ALWAYS** use the real Redis instance in Docker
✅ **ALWAYS** test with actual database transactions
✅ **ALWAYS** test with real Celery tasks (if needed)
✅ **ALWAYS** test with real Django ORM queries
✅ **ALWAYS** test with real cache operations
✅ **ALWAYS** use Django's test database (automatically created/destroyed)

### 🚫 WHAT WE MOCK (EXTERNAL SERVICES ONLY):

❌ **ONLY MOCK** external SMS services (Twilio, etc.)
❌ **ONLY MOCK** external payment gateways (Stripe, PayPal, etc.)
❌ **ONLY MOCK** external email services (SendGrid, Mailgun, etc.)
❌ **ONLY MOCK** external APIs (third-party integrations)
❌ **ONLY MOCK** external file storage (S3, CloudFlare, etc.)

### 📋 TESTING EXAMPLES

#### ✅ CORRECT - Real Database Testing:
```python
# tests/test_inventory.py
import pytest
from django.test import TestCase
from apps.inventory.models import Product

class TestProduct(TestCase):
    """Uses real PostgreSQL database in Docker"""
    
    def test_create_product(self):
        # This hits the REAL database in Docker
        product = Product.objects.create(
            name="Gold Ring",
            sku="GR-001",
            price=299.99
        )
        
        # Real database query
        assert Product.objects.count() == 1
        assert product.name == "Gold Ring"
```

#### ✅ CORRECT - Real Redis Testing:
```python
# tests/test_cache.py
from django.core.cache import cache
from django.test import TestCase

class TestCache(TestCase):
    """Uses real Redis in Docker"""
    
    def test_cache_operations(self):
        # This hits the REAL Redis in Docker
        cache.set('test_key', 'test_value', 60)
        assert cache.get('test_key') == 'test_value'
```

#### ✅ CORRECT - Mocking External SMS:
```python
# tests/test_notifications.py
from unittest.mock import patch, Mock
from django.test import TestCase
from apps.notifications.services import send_sms

class TestSMS(TestCase):
    """Mock external SMS service, use real database"""
    
    @patch('apps.notifications.services.twilio_client')
    def test_send_sms(self, mock_twilio):
        # Mock the EXTERNAL Twilio service
        mock_twilio.messages.create.return_value = Mock(sid='SM123')
        
        # But still use REAL database for logging
        result = send_sms('+1234567890', 'Test message')
        
        assert result.sid == 'SM123'
        # Verify SMS log was saved to REAL database
        assert SMSLog.objects.count() == 1
```

#### ❌ WRONG - Don't Mock Database:
```python
# ❌ DO NOT DO THIS
@patch('apps.inventory.models.Product.objects.create')
def test_create_product(mock_create):
    # This is WRONG - we don't mock our own database
    mock_create.return_value = Mock(id=1, name="Gold Ring")
```

#### ❌ WRONG - Don't Mock Redis:
```python
# ❌ DO NOT DO THIS
@patch('django.core.cache.cache.set')
def test_cache(mock_cache):
    # This is WRONG - we don't mock our own Redis
    mock_cache.return_value = True
```

### 🎯 WHY NO MOCKING INTERNAL SERVICES?

1. **Real Integration Testing**: Tests verify actual database behavior
2. **Catch Real Issues**: Find problems with queries, indexes, constraints
3. **Production Parity**: Tests run in environment identical to production
4. **Transaction Testing**: Verify rollbacks, commits, isolation levels work
5. **Performance Testing**: Identify slow queries and N+1 problems
6. **Data Integrity**: Ensure constraints, triggers, and validations work

### 🔧 TEST DATABASE SETUP

Django automatically creates a test database for each test run:

```bash
# Run tests - Django creates test_jewelry_shop database automatically
docker-compose exec web pytest

# The test database is:
# - Created before tests run
# - Isolated from development database
# - Destroyed after tests complete
# - Uses real PostgreSQL in Docker
```

### 📊 TEST CONFIGURATION

```python
# pytest.ini or conftest.py
# Tests use real Docker services via Django settings

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'jewelry_shop',  # Django creates test_jewelry_shop automatically
        'USER': 'postgres',
        'PASSWORD': 'postgres',
        'HOST': 'db',  # Real PostgreSQL container
        'PORT': '5432',
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis:6379/1',  # Real Redis container
    }
}
```

### ⚡ TESTING BEST PRACTICES

1. ✅ Use `TestCase` for tests that need database transactions
2. ✅ Use `TransactionTestCase` for tests that need to test transactions
3. ✅ Use `pytest` fixtures for common test data setup
4. ✅ Clean up test data in `tearDown()` or use Django's automatic cleanup
5. ✅ Mock only external APIs and services
6. ✅ Never mock Django ORM, database, or Redis operations
7. ✅ Run all tests inside Docker: `docker-compose exec web pytest`

### 🚨 REMEMBER FOR TESTING

**ALL TESTS RUN IN DOCKER WITH REAL SERVICES.**

**ONLY MOCK EXTERNAL THIRD-PARTY SERVICES.**

**NEVER MOCK OUR OWN DATABASE, REDIS, OR INTERNAL SERVICES.**

**If you're mocking Django ORM or Redis, you're doing it wrong!**
