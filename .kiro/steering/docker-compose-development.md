---
inclusion: always
priority: high
---

# Docker Compose Development Environment

## ⚠️ CRITICAL: This project uses Docker Compose, NOT Kubernetes

**ALL development and testing runs via Docker Compose. Do NOT use kubectl or Kubernetes commands.**

## Docker Container Names

| Service | Container Name |
|---------|---------------|
| Django Web | `jewelry_shop_web` |
| PostgreSQL | `jewelry_shop_db` |
| Redis | `jewelry_shop_redis` |
| Celery Worker | `jewelry_shop_celery_worker` |
| Nginx | `jewelry_shop_nginx` |
| PgBouncer | `jewelry_shop_pgbouncer` |
| Prometheus | `jewelry_shop_prometheus` |
| Grafana | `jewelry_shop_grafana` |

## ✅ CORRECT Commands

### Running Django Commands
```bash
# Run migrations
docker exec jewelry_shop_web python manage.py migrate

# Make migrations
docker exec jewelry_shop_web python manage.py makemigrations

# Run tests
docker exec jewelry_shop_web pytest

# Django shell
docker exec -it jewelry_shop_web python manage.py shell

# Create superuser
docker exec -it jewelry_shop_web python manage.py createsuperuser
```

### Database Access
```bash
# PostgreSQL shell
docker exec -it jewelry_shop_db psql -U postgres -d jewelry_shop

# Check tables
docker exec jewelry_shop_db psql -U postgres -d jewelry_shop -c "\dt"
```

### Redis Access
```bash
docker exec -it jewelry_shop_redis redis-cli
```

### View Logs
```bash
# Django logs
docker logs -f jewelry_shop_web

# All services
docker compose logs -f

# Specific service
docker compose logs -f web
```

### Container Management
```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# Restart a service
docker compose restart web

# Rebuild and restart
docker compose up -d --build web
```

## 🚫 DO NOT USE

- ❌ `kubectl` commands
- ❌ `k3d` commands
- ❌ Any Kubernetes-related commands
- ❌ Pod names or Kubernetes service names

## Testing Policy

- Use real PostgreSQL database in Docker (`jewelry_shop_db`)
- Use real Redis in Docker (`jewelry_shop_redis`)
- Only mock external third-party services (Twilio, Stripe, etc.)
- Never mock internal database or cache operations
