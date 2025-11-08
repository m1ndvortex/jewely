# Production Deployment Checklist

This checklist ensures all requirements are met before deploying to production.

## Pre-Deployment Checklist

### 1. Environment Configuration ✓

- [ ] Copy `.env.production.example` to `.env`
- [ ] Generate strong secrets using `python scripts/generate_secrets.py`
- [ ] Set all required environment variables
- [ ] Validate configuration: `python scripts/validate_env.py --env production`
- [ ] Verify `DJANGO_SETTINGS_MODULE=config.settings.production`
- [ ] Verify `DEBUG=False`
- [ ] Set `DJANGO_ALLOWED_HOSTS` to actual domain names
- [ ] Set `SITE_URL` to actual production URL (https://)

### 2. Secrets and Keys ✓

- [ ] `DJANGO_SECRET_KEY` - At least 50 characters, cryptographically secure
- [ ] `BACKUP_ENCRYPTION_KEY` - 32-byte Fernet key (base64 encoded)
- [ ] `FIELD_ENCRYPTION_KEY` - 32-byte Fernet key (base64 encoded)
- [ ] `POSTGRES_PASSWORD` - Strong database password
- [ ] `APP_DB_PASSWORD` - Strong app user password
- [ ] `REDIS_PASSWORD` - Strong Redis password
- [ ] All secrets stored securely (password manager, secrets vault)
- [ ] Secrets different from staging/development

### 3. Database Configuration ✓

- [ ] PostgreSQL 15+ installed and running
- [ ] Database created with correct name
- [ ] App user created with correct permissions
- [ ] Row-Level Security (RLS) policies applied
- [ ] Database backups configured
- [ ] PgBouncer configured for connection pooling
- [ ] `USE_PGBOUNCER=True` in production

### 4. Redis Configuration ✓

- [ ] Redis 7+ installed and running
- [ ] Redis password set
- [ ] Redis persistence enabled (RDB + AOF)
- [ ] Redis Sentinel configured for failover (optional but recommended)
- [ ] Redis maxmemory policy set

### 5. Email Configuration ✓

- [ ] Email provider selected (SendGrid, Mailgun, SES, or SMTP)
- [ ] `EMAIL_PROVIDER` set correctly
- [ ] API keys or SMTP credentials configured
- [ ] `DEFAULT_FROM_EMAIL` set to valid email
- [ ] Test email sending works
- [ ] SPF, DKIM, DMARC records configured

### 6. Cloud Storage Configuration ✓

- [ ] Cloudflare R2 bucket created
- [ ] R2 access keys generated and set
- [ ] Backblaze B2 bucket created (backup storage)
- [ ] B2 access keys generated and set
- [ ] Test upload/download works
- [ ] Bucket permissions configured correctly

### 7. External Services ✓

- [ ] Twilio account created (for SMS)
- [ ] Twilio credentials configured
- [ ] Stripe account created (for payments)
- [ ] Stripe live mode keys configured
- [ ] Stripe webhook endpoint configured
- [ ] Gold API key obtained (optional)
- [ ] Metals API key obtained (optional)

### 8. Monitoring and Logging ✓

- [ ] Sentry project created
- [ ] `SENTRY_DSN` configured
- [ ] `SENTRY_ENVIRONMENT=production`
- [ ] Prometheus configured
- [ ] Grafana dashboards imported
- [ ] Alert rules configured
- [ ] Log aggregation configured (Loki)

### 9. SSL/TLS Configuration ✓

- [ ] Domain name registered and DNS configured
- [ ] SSL certificate obtained (Let's Encrypt via Certbot)
- [ ] Nginx configured for HTTPS
- [ ] HTTP to HTTPS redirect enabled
- [ ] HSTS headers configured
- [ ] Certificate auto-renewal configured

### 10. Security Hardening ✓

- [ ] Firewall rules configured (only necessary ports open)
- [ ] SSH key-based authentication only
- [ ] Fail2ban installed and configured
- [ ] Security headers configured in Nginx
- [ ] Rate limiting enabled
- [ ] Brute force protection enabled
- [ ] CSRF protection enabled
- [ ] XSS protection enabled

### 11. Docker Configuration ✓

- [ ] Docker and Docker Compose installed
- [ ] Production Dockerfile reviewed
- [ ] Non-root user configured (appuser:appgroup)
- [ ] Health checks configured for all services
- [ ] Resource limits set
- [ ] Restart policies configured
- [ ] Volumes for persistent data configured
- [ ] Networks for service isolation configured

### 12. Application Configuration ✓

- [ ] Static files collected: `docker compose exec web python manage.py collectstatic`
- [ ] Translations compiled: `docker compose exec web python manage.py compilemessages`
- [ ] Database migrations applied: `docker compose exec web python manage.py migrate`
- [ ] Superuser created: `docker compose exec web python manage.py createsuperuser`
- [ ] Initial data loaded (if any)

### 13. Backup Configuration ✓

- [ ] Backup encryption key set
- [ ] Backup schedule configured
- [ ] Backup retention policy set
- [ ] Backup storage locations configured (local + cloud)
- [ ] Backup restoration tested
- [ ] WAL archiving configured
- [ ] Point-in-time recovery tested

### 14. Performance Optimization ✓

- [ ] Redis caching enabled
- [ ] Query optimization reviewed
- [ ] Database indexes created
- [ ] Static file compression enabled
- [ ] CDN configured (optional)
- [ ] Asset minification enabled
- [ ] Gzip compression enabled

### 15. Testing ✓

- [ ] All unit tests pass: `docker compose exec web pytest`
- [ ] Integration tests pass
- [ ] Load testing performed
- [ ] Security scanning completed
- [ ] Penetration testing completed (if required)
- [ ] Backup restoration tested
- [ ] Disaster recovery plan tested

## Deployment Steps

### 1. Build Docker Images

```bash
# Build production images
docker compose -f docker-compose.prod.yml build

# Tag with version
docker tag jewelry-shop:latest jewelry-shop:v1.0.0
```

### 2. Push to Registry (if using)

```bash
# Tag for registry
docker tag jewelry-shop:latest registry.example.com/jewelry-shop:v1.0.0

# Push to registry
docker push registry.example.com/jewelry-shop:v1.0.0
```

### 3. Deploy to Production

```bash
# Pull latest images (if using registry)
docker compose -f docker-compose.prod.yml pull

# Start services
docker compose -f docker-compose.prod.yml up -d

# Check service health
docker compose -f docker-compose.prod.yml ps

# View logs
docker compose -f docker-compose.prod.yml logs -f
```

### 4. Run Migrations

```bash
# Apply database migrations
docker compose -f docker-compose.prod.yml exec web python manage.py migrate

# Create superuser (if first deployment)
docker compose -f docker-compose.prod.yml exec web python manage.py createsuperuser
```

### 5. Verify Deployment

```bash
# Check Django
docker compose -f docker-compose.prod.yml exec web python manage.py check

# Check health endpoint
curl https://your-domain.com/health/

# Check admin panel
curl https://your-domain.com/admin/

# Check Prometheus metrics
curl https://your-domain.com/metrics
```

### 6. Monitor

```bash
# Watch logs
docker compose -f docker-compose.prod.yml logs -f web

# Check Sentry for errors
# Check Grafana dashboards
# Check Prometheus alerts
```

## Post-Deployment Checklist

- [ ] All services running and healthy
- [ ] Health checks passing
- [ ] Application accessible via domain
- [ ] Admin panel accessible
- [ ] Login/authentication working
- [ ] Database queries working
- [ ] Redis caching working
- [ ] Celery tasks running
- [ ] Email sending working
- [ ] File uploads working
- [ ] Backups running
- [ ] Monitoring working
- [ ] Alerts configured
- [ ] SSL certificate valid
- [ ] Performance acceptable
- [ ] No errors in Sentry
- [ ] Documentation updated

## Rollback Plan

If deployment fails:

```bash
# Stop new version
docker compose -f docker-compose.prod.yml down

# Restore previous version
docker compose -f docker-compose.prod.yml up -d jewelry-shop:v1.0.0-previous

# Restore database backup (if needed)
docker compose -f docker-compose.prod.yml exec web python manage.py restore_backup --backup-id=<id>

# Verify rollback
curl https://your-domain.com/health/
```

## Maintenance

### Regular Tasks

- **Daily**: Check logs, monitor Sentry, verify backups
- **Weekly**: Review performance metrics, check disk space
- **Monthly**: Update dependencies, rotate secrets, review security
- **Quarterly**: Load testing, disaster recovery drill, security audit

### Updates

```bash
# Update dependencies
pip-compile requirements.in
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# Update Django
# Test in staging first!
docker compose -f docker-compose.prod.yml exec web python manage.py migrate
```

## Emergency Contacts

- **DevOps Lead**: [contact]
- **Database Admin**: [contact]
- **Security Team**: [contact]
- **On-Call Engineer**: [contact]

## Documentation

- Architecture: `docs/architecture.md`
- API Documentation: `https://your-domain.com/api/docs/`
- Admin Guide: `docs/admin-guide.md`
- Runbooks: `docs/runbooks/`

---

**Last Updated**: 2025-11-08
**Version**: 1.0.0
**Reviewed By**: [Name]
