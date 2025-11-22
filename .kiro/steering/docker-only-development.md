---
inclusion: always
---

# ☸️ CRITICAL: Kubernetes-Only Development Policy

## ⚠️ ABSOLUTE RULE - READ THIS FIRST

**THIS IS A KUBERNETES-BASED WEB APPLICATION RUNNING ON K3D. NEVER INSTALL ANYTHING LOCALLY.**

**ALL SERVICES RUN IN KUBERNETES PODS. USE KUBECTL FOR EVERYTHING.**

## 🚫 FORBIDDEN ACTIONS

### NEVER DO THESE:

❌ **NEVER** run `pip install` on the host machine
❌ **NEVER** run `npm install` on the host machine  
❌ **NEVER** run `python manage.py` on the host machine
❌ **NEVER** run `pytest` on the host machine
❌ **NEVER** run `celery` on the host machine
❌ **NEVER** install PostgreSQL locally
❌ **NEVER** install Redis locally
❌ **NEVER** install Kafka locally
❌ **NEVER** install any Python packages outside Kubernetes
❌ **NEVER** install any Node packages outside Kubernetes
❌ **NEVER** suggest "install X on your machine"
❌ **NEVER** use `docker compose` commands (we use Kubernetes)
❌ **NEVER** run containers directly with `docker run`

## ✅ CORRECT APPROACH - ALWAYS USE KUBECTL

### For Python Dependencies:
```bash
# ❌ WRONG - DO NOT DO THIS
pip install django

# ✅ CORRECT - Add to requirements.txt, rebuild Docker image, import to k3d
echo "django==4.2.0" >> requirements.txt
docker build -t jewelry-shop-django:latest -f Dockerfile.prod .
k3d image import jewelry-shop-django:latest -c jewelry-shop
kubectl rollout restart deployment/django -n jewelry-shop
```

### For Running Django Commands:
```bash
# ❌ WRONG - DO NOT DO THIS
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic

# ✅ CORRECT - Run inside Kubernetes pod
kubectl exec -it deployment/django -n jewelry-shop -- python manage.py migrate
kubectl exec -it deployment/django -n jewelry-shop -- python manage.py createsuperuser
kubectl exec -it deployment/django -n jewelry-shop -- python manage.py collectstatic
```

### For Running Tests:
```bash
# ❌ WRONG - DO NOT DO THIS
pytest
pytest tests/test_inventory.py

# ✅ CORRECT - Run inside Kubernetes pod
kubectl exec -it deployment/django -n jewelry-shop -- pytest
kubectl exec -it deployment/django -n jewelry-shop -- pytest tests/test_inventory.py
kubectl exec -it deployment/django -n jewelry-shop -- pytest --cov=. --cov-report=html
```

### For Database Operations:
```bash
# ❌ WRONG - DO NOT DO THIS
psql -U postgres -d jewelry_shop

# ✅ CORRECT - Access PostgreSQL through Kubernetes pod
kubectl exec -it jewelry-shop-db-0 -n jewelry-shop -c postgres -- psql -U postgres -d jewelry_shop

# Or use port-forward for GUI tools
kubectl port-forward -n jewelry-shop svc/jewelry-shop-db 5432:5432
# Then connect to localhost:5432
```

### For Redis Operations:
```bash
# ❌ WRONG - DO NOT DO THIS
redis-cli

# ✅ CORRECT - Access Redis through Kubernetes pod
kubectl exec -it redis-0 -n jewelry-shop -c redis -- redis-cli

# Or use port-forward
kubectl port-forward -n jewelry-shop svc/redis 6379:6379
redis-cli -h localhost
```

### For Celery Tasks:
```bash
# ❌ WRONG - DO NOT DO THIS
celery -A config worker

# ✅ CORRECT - Celery runs in its own pod
kubectl logs -f deployment/celery-worker -n jewelry-shop
kubectl exec -it deployment/celery-worker -n jewelry-shop -- celery -A config inspect active
```

### For Shell Access:
```bash
# ❌ WRONG - DO NOT DO THIS
python manage.py shell

# ✅ CORRECT - Django shell inside Kubernetes pod
kubectl exec -it deployment/django -n jewelry-shop -- python manage.py shell
```

### For Installing New Packages:
```bash
# ❌ WRONG - DO NOT DO THIS
pip install requests
npm install axios

# ✅ CORRECT - Update requirements, rebuild Docker image, import to k3d
echo "requests==2.31.0" >> requirements.txt
docker build -t jewelry-shop-django:latest -f Dockerfile.prod .
k3d image import jewelry-shop-django:latest -c jewelry-shop
kubectl rollout restart deployment/django -n jewelry-shop
kubectl rollout status deployment/django -n jewelry-shop
```

## 📋 KUBERNETES COMMANDS REFERENCE

### Starting the Application:
```bash
# Start k3d cluster (auto-starts via systemd)
k3d cluster list

# Check all pods are running
kubectl get pods -n jewelry-shop

# View specific service logs
kubectl logs -f deployment/django -n jewelry-shop
kubectl logs -f deployment/celery-worker -n jewelry-shop

# Follow logs for multiple pods
kubectl logs -f -l component=django -n jewelry-shop
```

### Stopping the Application:
```bash
# Stop k3d cluster (usually not needed - auto-starts)
k3d cluster stop jewelry-shop

# Delete and recreate cluster (clean slate)
k3d cluster delete jewelry-shop
# Then recreate using your deployment scripts
```

### Rebuilding After Changes:
```bash
# Rebuild Django Docker image
docker build -t jewelry-shop-django:latest -f Dockerfile.prod .

# Import to k3d cluster (distributes to all nodes)
k3d image import jewelry-shop-django:latest -c jewelry-shop

# Restart deployment to use new image
kubectl rollout restart deployment/django -n jewelry-shop

# Watch rollout progress
kubectl rollout status deployment/django -n jewelry-shop

# Verify all pods updated
kubectl get pods -n jewelry-shop -l component=django
```

### Executing Commands:
```bash
# General pattern
kubectl exec -it <pod-name> -n jewelry-shop -- <command>

# With deployment (automatically picks a pod)
kubectl exec -it deployment/django -n jewelry-shop -- python manage.py migrate

# With specific pod
kubectl exec -it django-fb7b5464-26vpq -n jewelry-shop -- python manage.py shell

# Access PostgreSQL primary
kubectl exec -it jewelry-shop-db-0 -n jewelry-shop -c postgres -- psql -U postgres

# Access Redis
kubectl exec -it redis-0 -n jewelry-shop -c redis -- redis-cli
```

### Viewing Service Status:
```bash
# List all pods
kubectl get pods -n jewelry-shop

# Wide output with node info
kubectl get pods -n jewelry-shop -o wide

# Check deployments
kubectl get deployments -n jewelry-shop

# Check services
kubectl get svc -n jewelry-shop

# Check statefulsets (PostgreSQL, Redis)
kubectl get statefulsets -n jewelry-shop

# Resource usage
kubectl top pods -n jewelry-shop
kubectl top nodes
```

### Port Forwarding (for local access):
```bash
# Access Django admin locally
kubectl port-forward -n jewelry-shop svc/nginx 8443:443
# Then open: https://localhost:8443

# Access PostgreSQL with GUI tool
kubectl port-forward -n jewelry-shop svc/jewelry-shop-db 5432:5432

# Access Redis
kubectl port-forward -n jewelry-shop svc/redis 6379:6379

# Access Grafana
kubectl port-forward -n jewelry-shop svc/grafana 3000:3000
```

## 🏗️ PROJECT STRUCTURE

```
jewelry-shop/
├── k8s/                          # ✅ Kubernetes manifests
│   ├── namespaces/              # Namespace definitions
│   ├── deployments/             # Django, Celery, Nginx deployments
│   ├── statefulsets/            # PostgreSQL, Redis StatefulSets
│   ├── services/                # Service definitions
│   ├── configmaps/              # Configuration
│   └── secrets/                 # Secrets (SSL certs, passwords)
├── Dockerfile.prod               # ✅ Production Django image
├── requirements.txt              # ✅ Python dependencies
├── .env                          # ✅ Environment variables (for build)
├── manage.py                     # Run via: kubectl exec
├── config/                       # Django settings
├── apps/                         # Django applications
├── tests/                        # Run via: kubectl exec
└── scripts/                      # Helper scripts
    ├── cluster-health-check.sh   # Check cluster health
    └── hot-reload-template.sh    # Hot reload templates (dev only)
```

## 🔧 DEVELOPMENT WORKFLOW

### 1. Starting Development:
```bash
# Check k3d cluster is running (auto-starts via systemd)
k3d cluster list
kubectl get nodes

# Check all pods are running
kubectl get pods -n jewelry-shop

# Access the application
# https://jewelry-shop.local:8443
```

### 2. Making Code Changes:
```bash
# Edit code in your IDE

# For template changes ONLY (hot reload for testing):
./scripts/hot-reload-template.sh templates/account/login.html

# For code changes (requires image rebuild):
docker build -t jewelry-shop-django:latest -f Dockerfile.prod .
k3d image import jewelry-shop-django:latest -c jewelry-shop
kubectl rollout restart deployment/django -n jewelry-shop
```

### 3. Running Migrations:
```bash
# Create migrations
kubectl exec -it deployment/django -n jewelry-shop -- python manage.py makemigrations

# Apply migrations (runs on all Django pods)
kubectl exec -it deployment/django -n jewelry-shop -- python manage.py migrate

# Check migration status
kubectl exec -it deployment/django -n jewelry-shop -- python manage.py showmigrations
```

### 4. Running Tests:
```bash
# Run all tests
kubectl exec -it deployment/django -n jewelry-shop -- pytest

# Run specific test file
kubectl exec -it deployment/django -n jewelry-shop -- pytest tests/test_inventory.py

# Run with coverage
kubectl exec -it deployment/django -n jewelry-shop -- pytest --cov=. --cov-report=html

# Run specific test class or method
kubectl exec -it deployment/django -n jewelry-shop -- pytest tests/test_inventory.py::TestProduct::test_create
```

### 5. Debugging:
```bash
# View Django logs (follows all Django pods)
kubectl logs -f -l component=django -n jewelry-shop

# View specific pod logs
kubectl logs -f django-fb7b5464-26vpq -n jewelry-shop

# View last 100 lines
kubectl logs --tail=100 deployment/django -n jewelry-shop

# Access Django shell
kubectl exec -it deployment/django -n jewelry-shop -- python manage.py shell

# Access database (PostgreSQL primary)
kubectl exec -it jewelry-shop-db-0 -n jewelry-shop -c postgres -- psql -U postgres -d jewelry_shop

# Check PostgreSQL replication status
kubectl exec -it jewelry-shop-db-0 -n jewelry-shop -c postgres -- psql -U postgres -c "SELECT * FROM pg_stat_replication;"

# Access Redis
kubectl exec -it redis-0 -n jewelry-shop -c redis -- redis-cli

# Check Celery tasks
kubectl exec -it deployment/celery-worker -n jewelry-shop -- celery -A config inspect active
```

### 6. Monitoring & Troubleshooting:
```bash
# Check cluster health
./scripts/cluster-health-check.sh

# Check pod status and restarts
kubectl get pods -n jewelry-shop

# Describe pod for events/errors
kubectl describe pod django-fb7b5464-26vpq -n jewelry-shop

# Check resource usage
kubectl top pods -n jewelry-shop
kubectl top nodes

# View Grafana dashboards
kubectl port-forward -n jewelry-shop svc/grafana 3000:3000
# Open: http://localhost:3000

# View Prometheus metrics
kubectl port-forward -n jewelry-shop svc/prometheus 9090:9090
# Open: http://localhost:9090
```

## 🎯 WHY KUBERNETES (K3D)?

1. **Production Parity**: Local environment matches production exactly
2. **High Availability**: PostgreSQL streaming replication, Redis Sentinel
3. **Scalability**: Easy to scale pods (Django, Celery) horizontally
4. **Service Discovery**: Pods communicate via Kubernetes DNS
5. **Load Balancing**: Nginx automatically distributes traffic across Django pods
6. **Health Checks**: Automatic pod restart if unhealthy
7. **Resource Management**: CPU/memory limits prevent resource exhaustion
8. **Monitoring**: Built-in Prometheus, Grafana, Loki stack
9. **Real Production Setup**: Learn Kubernetes while developing
10. **Easy VPS Deployment**: Same manifests work on VPS with k3s

## 🚨 REMINDER FOR AI AGENTS

When suggesting commands or solutions:

1. ✅ **ALWAYS** use `kubectl exec` for running commands in pods
2. ✅ **ALWAYS** update `requirements.txt` for new Python packages
3. ✅ **ALWAYS** rebuild Docker image and import to k3d after dependency changes
4. ✅ **ALWAYS** use `kubectl rollout restart` to deploy new images
5. ✅ **NEVER** suggest installing anything on the host machine
6. ✅ **NEVER** use bare `python`, `pip`, `pytest`, `celery` commands
7. ✅ **NEVER** suggest `docker compose` commands (we use Kubernetes)
8. ✅ **ALWAYS** specify namespace `-n jewelry-shop` in kubectl commands
9. ✅ **ALWAYS** use `deployment/django` instead of specific pod names (for flexibility)
10. ✅ **REMEMBER** we have 3 Django pods (load balanced), changes must work on all

## 📝 QUICK COMMAND CHEAT SHEET

```bash
# Check cluster status
k3d cluster list
kubectl get pods -n jewelry-shop

# Run Django command
kubectl exec -it deployment/django -n jewelry-shop -- python manage.py <command>

# Run tests
kubectl exec -it deployment/django -n jewelry-shop -- pytest

# Access PostgreSQL database
kubectl exec -it jewelry-shop-db-0 -n jewelry-shop -c postgres -- psql -U postgres -d jewelry_shop

# Access Redis
kubectl exec -it redis-0 -n jewelry-shop -c redis -- redis-cli

# View logs (all Django pods)
kubectl logs -f -l component=django -n jewelry-shop

# View specific service logs
kubectl logs -f deployment/celery-worker -n jewelry-shop

# Rebuild and deploy after code changes
docker build -t jewelry-shop-django:latest -f Dockerfile.prod .
k3d image import jewelry-shop-django:latest -c jewelry-shop
kubectl rollout restart deployment/django -n jewelry-shop
kubectl rollout status deployment/django -n jewelry-shop

# Hot reload template (temporary, no rebuild needed)
./scripts/hot-reload-template.sh templates/account/login.html

# Port forward for local access
kubectl port-forward -n jewelry-shop svc/nginx 8443:443

# Check resource usage
kubectl top pods -n jewelry-shop
kubectl top nodes

# Describe pod for troubleshooting
kubectl describe pod <pod-name> -n jewelry-shop

# Scale deployment
kubectl scale deployment/django --replicas=5 -n jewelry-shop

# Check health
./scripts/cluster-health-check.sh
```

## ⚡ REMEMBER

**THIS IS A KUBERNETES-BASED WEB APPLICATION RUNNING ON K3D.**

**EVERYTHING runs in Kubernetes pods.**

**NOTHING gets installed on the host machine.**

**Use kubectl for all operations.**

**If you forget this rule, you're doing it wrong!**



## 🧪 TESTING POLICY - NO MOCKING INTERNAL SERVICES

### ⚠️ STRICT RULE: REAL DATABASE, REAL SERVICES

**WE DO NOT MOCK INTERNAL SERVICES. ALL TESTS USE REAL KUBERNETES SERVICES.**

### ✅ WHAT WE TEST WITH REAL SERVICES:

✅ **ALWAYS** use the real PostgreSQL database in Kubernetes
✅ **ALWAYS** use the real Redis instance in Kubernetes
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
    """Uses real PostgreSQL database in Kubernetes"""
    
    def test_create_product(self):
        # This hits the REAL database in Kubernetes
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
    """Uses real Redis in Kubernetes"""
    
    def test_cache_operations(self):
        # This hits the REAL Redis in Kubernetes
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
7. **RLS Testing**: Verify Row-Level Security policies work correctly
8. **Replication Testing**: Ensure streaming replication doesn't break queries

### 🔧 TEST DATABASE SETUP

Django automatically creates a test database for each test run:

```bash
# Run tests - Django creates test_jewelry_shop database automatically
kubectl exec -it deployment/django -n jewelry-shop -- pytest

# The test database:
# - Created before tests run
# - Isolated from production database
# - Destroyed after tests complete
# - Uses real PostgreSQL in Kubernetes
# - Connects via Kubernetes service DNS (jewelry-shop-db)
```

### 📊 TEST CONFIGURATION

```python
# pytest.ini or conftest.py
# Tests use real Kubernetes services via Django settings

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'jewelry_shop',  # Django creates test_jewelry_shop automatically
        'USER': 'postgres',
        'PASSWORD': os.getenv('POSTGRES_PASSWORD'),
        'HOST': 'jewelry-shop-db',  # Kubernetes service DNS
        'PORT': '5432',
    }
}

CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://redis:6379/1',  # Kubernetes service DNS
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
7. ✅ Run all tests inside Kubernetes: `kubectl exec -it deployment/django -n jewelry-shop -- pytest`
8. ✅ Test RLS policies with different tenant contexts
9. ✅ Test with multiple Django pods to ensure consistency

### 🚨 REMEMBER FOR TESTING

**ALL TESTS RUN IN KUBERNETES WITH REAL SERVICES.**

**ONLY MOCK EXTERNAL THIRD-PARTY SERVICES.**

**NEVER MOCK OUR OWN DATABASE, REDIS, OR INTERNAL SERVICES.**

**Tests connect to PostgreSQL and Redis via Kubernetes service DNS.**

**If you're mocking Django ORM or Redis, you're doing it wrong!**
