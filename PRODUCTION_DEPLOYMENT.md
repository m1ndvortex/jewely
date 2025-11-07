# Production Deployment Guide

This guide covers deploying the Jewelry Management SaaS Platform to production using Docker Compose.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Architecture Overview](#architecture-overview)
- [Initial Setup](#initial-setup)
- [Configuration](#configuration)
- [Deployment](#deployment)
- [SSL/TLS Setup](#ssltls-setup)
- [Monitoring](#monitoring)
- [Backup & Recovery](#backup--recovery)
- [Scaling](#scaling)
- [Maintenance](#maintenance)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Operating System**: Ubuntu 20.04 LTS or later (recommended)
- **CPU**: Minimum 4 cores, recommended 8+ cores
- **RAM**: Minimum 8GB, recommended 16GB+
- **Disk**: Minimum 100GB SSD, recommended 500GB+ SSD
- **Network**: Static IP address and domain name

### Software Requirements

```bash
# Docker Engine 20.10+
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Docker Compose V2
sudo apt-get update
sudo apt-get install docker-compose-plugin

# Verify installations
docker --version
docker compose version
```

## Architecture Overview

### Network Architecture

```
Internet
    │
    ├─── Port 80/443 ──> Nginx (Reverse Proxy)
    │                      │
    │                      ├─── frontend network ──> Django Web (Port 8000)
    │                                                   │
    │                                                   └─── backend network
    │                                                          │
    └─── Monitoring ──> Prometheus/Grafana                    ├─── PostgreSQL (Port 5432)
                                                               ├─── PgBouncer (Connection Pool)
                                                               ├─── Redis (Cache/Broker)
                                                               ├─── Celery Worker
                                                               └─── Celery Beat
```

### Service Isolation

- **Frontend Network**: Nginx ↔ Django (public-facing)
- **Backend Network**: Django ↔ Database/Redis/Celery (internal only)

### Data Persistence

All data is stored in named Docker volumes:

- `postgres_data`: Database files
- `postgres_wal_archive`: WAL files for PITR
- `redis_data`: Redis persistence
- `media_files`: User-uploaded files
- `static_files`: Static assets
- `backups`: Backup files
- `prometheus_data`: Metrics data
- `grafana_data`: Dashboard data

## Initial Setup

### 1. Clone Repository

```bash
git clone https://github.com/your-org/jewelry-shop.git
cd jewelry-shop
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit with production values
nano .env
```

### 3. Required Environment Variables

```bash
# Django Settings
SECRET_KEY=your-very-long-random-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
DJANGO_SETTINGS_MODULE=config.settings

# Database
POSTGRES_DB=jewelry_shop
DB_SUPERUSER=postgres
DB_SUPERUSER_PASSWORD=strong-postgres-password
APP_DB_PASSWORD=strong-app-password

# Redis
REDIS_URL=redis://redis:6379/0

# Celery
CELERY_BROKER_URL=redis://redis:6379/0

# Email
EMAIL_HOST=smtp.your-provider.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@domain.com
EMAIL_HOST_PASSWORD=your-email-password
EMAIL_USE_TLS=True

# SMS (Twilio)
TWILIO_ACCOUNT_SID=your-twilio-sid
TWILIO_AUTH_TOKEN=your-twilio-token
TWILIO_PHONE_NUMBER=+1234567890

# Backup Encryption
BACKUP_ENCRYPTION_KEY=your-backup-encryption-key

# Cloudflare R2
R2_ACCESS_KEY_ID=your-r2-access-key
R2_SECRET_ACCESS_KEY=your-r2-secret-key
R2_BUCKET_NAME=securesyntax
R2_ENDPOINT_URL=https://b7900eeee7c415345d86ea859c9dad47.r2.cloudflarestorage.com

# Backblaze B2
B2_APPLICATION_KEY_ID=your-b2-key-id
B2_APPLICATION_KEY=your-b2-key
B2_BUCKET_NAME=securesyntax
B2_ENDPOINT_URL=https://s3.us-east-005.backblazeb2.com

# Monitoring
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=strong-grafana-password
GRAFANA_ROOT_URL=https://grafana.your-domain.com

# Sentry (Error Tracking)
SENTRY_DSN=your-sentry-dsn

# Version
VERSION=1.0.0
```

### 4. Generate Secrets

```bash
# Generate Django secret key
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"

# Generate backup encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Configuration

### 1. Database Configuration

The PostgreSQL configuration is in `docker/postgresql.conf`. Key settings:

```conf
max_connections = 200
shared_buffers = 2GB
effective_cache_size = 6GB
maintenance_work_mem = 512MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 10485kB
min_wal_size = 1GB
max_wal_size = 4GB
```

### 2. Nginx Configuration

Update `docker/nginx/conf.d/jewelry-shop.conf`:

```nginx
# Replace server_name with your domain
server_name your-domain.com www.your-domain.com;

# Uncomment HTTPS server block
# Update SSL certificate paths
```

### 3. PgBouncer Configuration

Create `pgbouncer/userlist.txt`:

```bash
# Generate password hash
echo -n "passwordapp_user" | md5sum

# Add to userlist.txt
"app_user" "md5<hash>"
```

## Deployment

### 1. Build Images

```bash
# Build production images
docker compose -f docker-compose.prod.yml build

# Tag with version
docker tag jewelry-shop:latest jewelry-shop:1.0.0
```

### 2. Start Services

```bash
# Start all services
docker compose -f docker-compose.prod.yml up -d

# Check status
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f
```

### 3. Initialize Database

```bash
# Run migrations
docker compose -f docker-compose.prod.yml exec web python manage.py migrate

# Create superuser
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser

# Collect static files
docker compose -f docker-compose.prod.yml exec web python manage.py collectstatic --noinput

# Load initial data (optional)
docker compose -f docker-compose.prod.yml exec web python manage.py loaddata initial_data.json
```

### 4. Verify Deployment

```bash
# Check health endpoints
curl http://localhost/health/
curl http://localhost:9090/-/healthy  # Prometheus
curl http://localhost:3000/api/health  # Grafana

# Check service status
docker compose -f docker-compose.prod.yml ps
```

## SSL/TLS Setup

### 1. Obtain SSL Certificate

```bash
# Run setup script
./docker/nginx/setup-ssl.sh your-domain.com

# Or manually with certbot
docker compose -f docker-compose.prod.yml run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  --email your-email@domain.com \
  --agree-tos \
  --no-eff-email \
  -d your-domain.com \
  -d www.your-domain.com
```

### 2. Update Nginx Configuration

```bash
# Edit nginx config
nano docker/nginx/conf.d/jewelry-shop.conf

# Uncomment HTTPS server block
# Update certificate paths
# Comment out HTTP location / block

# Reload nginx
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

### 3. Test SSL Configuration

```bash
# Test SSL
curl -I https://your-domain.com

# Check SSL rating
# Visit: https://www.ssllabs.com/ssltest/
```

## Monitoring

### Prometheus

Access: `http://your-domain:9090`

Key metrics:
- `django_http_requests_total`
- `django_http_request_duration_seconds`
- `postgresql_up`
- `redis_up`
- `celery_tasks_total`

### Grafana

Access: `http://your-domain:3000`

Default credentials:
- Username: `admin`
- Password: Set in `.env`

Pre-configured dashboards:
- System Overview
- Application Performance
- Database Performance
- Celery Monitoring

### Logs

```bash
# View all logs
docker compose -f docker-compose.prod.yml logs -f

# View specific service
docker compose -f docker-compose.prod.yml logs -f web
docker compose -f docker-compose.prod.yml logs -f celery_worker

# View last 100 lines
docker compose -f docker-compose.prod.yml logs --tail=100 web
```

## Backup & Recovery

### Automated Backups

Backups run automatically via Celery:
- Full database backup: Daily at 2:00 AM
- Tenant backups: Weekly on Sunday at 3:00 AM
- WAL archiving: Every 5 minutes
- Configuration backup: Daily at 4:00 AM

### Manual Backup

```bash
# Trigger manual backup via Django admin
# Or use management command
docker compose -f docker-compose.prod.yml exec web python manage.py backup_database
```

### Restore from Backup

```bash
# List available backups
docker compose -f docker-compose.prod.yml exec web python manage.py list_backups

# Restore specific backup
docker compose -f docker-compose.prod.yml exec web python manage.py restore_backup <backup_id>

# Point-in-time recovery
docker compose -f docker-compose.prod.yml exec web python manage.py pitr_restore "2024-01-15 14:30:00"
```

### Backup Verification

```bash
# Test restore (monthly automated)
docker compose -f docker-compose.prod.yml exec web python manage.py test_restore
```

## Scaling

### Horizontal Scaling

```bash
# Scale web servers
docker compose -f docker-compose.prod.yml up -d --scale web=3

# Scale celery workers
docker compose -f docker-compose.prod.yml up -d --scale celery_worker=2

# Verify scaling
docker compose -f docker-compose.prod.yml ps
```

### Load Balancing

Nginx automatically load balances across multiple web containers using least connections algorithm.

### Resource Limits

Adjust in `docker-compose.prod.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
    reservations:
      cpus: '1.0'
      memory: 1G
```

## Maintenance

### Updates

```bash
# Pull latest images
docker compose -f docker-compose.prod.yml pull

# Rebuild and restart
docker compose -f docker-compose.prod.yml up -d --build

# Run migrations
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
```

### Database Maintenance

```bash
# Vacuum database
docker compose -f docker-compose.prod.yml exec db psql -U postgres -d jewelry_shop -c "VACUUM ANALYZE;"

# Reindex
docker compose -f docker-compose.prod.yml exec db psql -U postgres -d jewelry_shop -c "REINDEX DATABASE jewelry_shop;"

# Check database size
docker compose -f docker-compose.prod.yml exec db psql -U postgres -d jewelry_shop -c "SELECT pg_size_pretty(pg_database_size('jewelry_shop'));"
```

### Log Rotation

Logs are automatically rotated by Docker:
- Max size: 10MB per file
- Max files: 3-5 depending on service

### Certificate Renewal

Certbot automatically renews certificates every 12 hours. Manual renewal:

```bash
docker compose -f docker-compose.prod.yml exec certbot certbot renew
docker compose -f docker-compose.prod.yml exec nginx nginx -s reload
```

## Troubleshooting

### Service Won't Start

```bash
# Check logs
docker compose -f docker-compose.prod.yml logs [service_name]

# Check health status
docker compose -f docker-compose.prod.yml ps

# Restart service
docker compose -f docker-compose.prod.yml restart [service_name]
```

### Database Connection Issues

```bash
# Check database is running
docker compose -f docker-compose.prod.yml exec db pg_isready -U postgres

# Check PgBouncer
docker compose -f docker-compose.prod.yml exec pgbouncer psql -h localhost -U app_user -d jewelry_shop -c "SELECT 1;"

# Check connections
docker compose -f docker-compose.prod.yml exec db psql -U postgres -d jewelry_shop -c "SELECT count(*) FROM pg_stat_activity;"
```

### High Memory Usage

```bash
# Check resource usage
docker stats

# Restart services
docker compose -f docker-compose.prod.yml restart

# Adjust resource limits in docker-compose.prod.yml
```

### Slow Performance

```bash
# Check database queries
docker compose -f docker-compose.prod.yml exec db psql -U postgres -d jewelry_shop -c "SELECT * FROM pg_stat_statements ORDER BY total_time DESC LIMIT 10;"

# Check Redis
docker compose -f docker-compose.prod.yml exec redis redis-cli INFO stats

# Check Celery queue
docker compose -f docker-compose.prod.yml exec web python manage.py celery inspect active
```

### Disk Space Issues

```bash
# Check disk usage
df -h

# Check Docker volumes
docker system df -v

# Clean up old images
docker image prune -a

# Clean up old logs
docker compose -f docker-compose.prod.yml exec nginx sh -c "find /var/log/nginx -name '*.log' -mtime +7 -delete"
```

## Security Checklist

- [ ] All passwords are strong and unique
- [ ] `.env` file has restricted permissions (600)
- [ ] SSL/TLS certificates are valid
- [ ] Firewall is configured (only ports 80, 443, 22 open)
- [ ] Database backups are encrypted
- [ ] Monitoring alerts are configured
- [ ] Security headers are enabled in Nginx
- [ ] Rate limiting is configured
- [ ] Regular security updates are applied
- [ ] Audit logs are enabled and monitored

## Performance Checklist

- [ ] Database indexes are optimized
- [ ] Redis caching is configured
- [ ] Static files are served by Nginx
- [ ] Gzip compression is enabled
- [ ] CDN is configured (optional)
- [ ] Database connection pooling is active
- [ ] Celery workers are scaled appropriately
- [ ] Monitoring dashboards are reviewed regularly

## Support

For issues and questions:
- GitHub Issues: https://github.com/your-org/jewelry-shop/issues
- Documentation: https://docs.your-domain.com
- Email: support@your-domain.com

## License

Copyright © 2024 Your Company. All rights reserved.
