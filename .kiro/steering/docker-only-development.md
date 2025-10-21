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

