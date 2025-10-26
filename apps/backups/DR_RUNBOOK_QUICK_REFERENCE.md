# Disaster Recovery Runbook - Quick Reference Guide

## 🚨 Emergency DR Execution

### When to Use
- Database corruption detected
- Data loss incident
- Ransomware attack
- Hardware failure
- Accidental data deletion
- System compromise

### Prerequisites
- Platform administrator access
- Valid backup available
- Authorization from management
- Documented reason for DR

## Quick Start

### Option 1: Web Interface (Recommended)

1. **Access DR Interface**
   ```
   https://your-domain.com/backups/disaster-recovery/
   ```

2. **Select Backup**
   - Use latest backup (recommended)
   - Or select specific backup from dropdown

3. **Provide Reason**
   - Document the disaster scenario
   - Include incident ticket number
   - Explain why DR is necessary

4. **Confirm and Execute**
   - Check confirmation box
   - Click "Execute Disaster Recovery"
   - Confirm in popup dialog

5. **Monitor Progress**
   - View restore logs: `/backups/restores/`
   - Check Celery logs for real-time updates
   - Monitor alerts: `/backups/alerts/`

### Option 2: Django Shell

```python
from apps.backups.services import BackupService

# Execute DR with latest backup
result = BackupService.execute_disaster_recovery(
    backup_id=None,  # Use latest
    reason="Production database corruption - Ticket #12345",
    user=None,  # Automated
)

print(f"Task ID: {result['task_id']}")
print(f"Status: {result['status']}")
```

### Option 3: Celery Task

```python
from apps.backups.tasks import execute_disaster_recovery_runbook

# Execute DR
task = execute_disaster_recovery_runbook.delay(
    backup_id=None,  # Use latest
    reason="Emergency DR - Database failure",
)

print(f"Task ID: {task.id}")
```

## DR Process Steps

The automated runbook executes these steps:

1. **Select Backup** (< 1 second)
   - Uses latest successful full database backup
   - Validates backup status

2. **Download Backup** (5-10 minutes)
   - Primary: Cloudflare R2
   - Failover: Backblaze B2
   - Last resort: Local storage

3. **Decrypt & Decompress** (2-5 minutes)
   - AES-256 decryption
   - gzip decompression

4. **Restore Database** (5-15 minutes)
   - pg_restore with 4 parallel jobs
   - Full restore (replaces all data)

5. **Restart Application** (1-2 minutes)
   - Kubernetes: `kubectl rollout restart`
   - Docker: `docker-compose restart`

6. **Verify Health** (2-5 minutes)
   - Polls health endpoint
   - Max 30 attempts (5 minutes)

7. **Reroute Traffic** (< 1 second)
   - Automatic via load balancer

**Total Time: 15-30 minutes** (Target RTO: 1 hour)

## Monitoring DR Progress

### Check Task Status

```bash
# View Celery logs
docker-compose logs -f celery_worker

# Or in Kubernetes
kubectl logs -f deployment/celery-worker
```

### Check Restore Log

```python
from apps.backups.models import BackupRestoreLog

# Get latest DR operation
dr_log = BackupRestoreLog.objects.filter(
    restore_mode='FULL'
).order_by('-started_at').first()

print(f"Status: {dr_log.status}")
print(f"Duration: {dr_log.get_duration_minutes()} minutes")
print(f"Steps: {dr_log.metadata['steps']}")
```

### Check Alerts

```python
from apps.backups.models import BackupAlert

# Get DR-related alerts
alerts = BackupAlert.objects.filter(
    restore_log__isnull=False
).order_by('-created_at')[:5]

for alert in alerts:
    print(f"{alert.severity}: {alert.message}")
```

## Troubleshooting

### DR Failed - Download Error

**Symptom**: "Failed to download backup from any storage location"

**Solution**:
1. Check R2 credentials in settings
2. Check B2 credentials in settings
3. Verify network connectivity
4. Check storage backend logs
5. Try manual download:
   ```python
   from apps.backups.storage import get_storage_backend
   
   r2 = get_storage_backend('r2')
   r2.download('path/to/backup', '/tmp/test.dump')
   ```

### DR Failed - Restore Error

**Symptom**: "Database restore failed"

**Solution**:
1. Check PostgreSQL logs
2. Verify database credentials
3. Check disk space
4. Verify backup integrity:
   ```python
   from apps.backups.encryption import verify_backup_integrity
   
   verify_backup_integrity(backup)
   ```

### DR Failed - Health Check Timeout

**Symptom**: "Health checks did not pass within timeout"

**Solution**:
1. Check application logs
2. Verify health endpoint: `curl http://localhost:8000/health/`
3. Check database connectivity
4. Restart application manually:
   ```bash
   # Kubernetes
   kubectl rollout restart deployment/django-app
   
   # Docker Compose
   docker-compose restart web
   ```

### Application Not Restarting

**Symptom**: "Could not automatically restart application"

**Solution**:
1. Manual restart required
2. Kubernetes:
   ```bash
   kubectl rollout restart deployment/django-app
   kubectl rollout status deployment/django-app
   ```
3. Docker Compose:
   ```bash
   docker-compose restart web
   docker-compose ps
   ```

## Post-DR Verification

### 1. Verify Database

```sql
-- Check tenant count
SELECT COUNT(*) FROM tenants;

-- Check latest data
SELECT created_at FROM sales ORDER BY created_at DESC LIMIT 1;

-- Verify RLS is enabled
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public' 
AND rowsecurity = true;
```

### 2. Verify Application

```bash
# Check health endpoint
curl http://localhost:8000/health/

# Check admin panel
curl -I http://localhost:8000/admin/

# Check tenant panel
curl -I http://localhost:8000/dashboard/
```

### 3. Verify Services

```bash
# Check all services
docker-compose ps

# Or in Kubernetes
kubectl get pods
kubectl get services
```

### 4. Test Critical Functions

- [ ] User login
- [ ] Tenant dashboard loads
- [ ] Inventory list loads
- [ ] POS interface works
- [ ] Reports generate
- [ ] Backups continue

## RTO/RPO Metrics

### Recovery Time Objective (RTO)
- **Target**: 1 hour (3600 seconds)
- **Typical**: 15-30 minutes
- **Maximum**: 60 minutes

### Recovery Point Objective (RPO)
- **Target**: 15 minutes
- **Achieved via**: WAL archiving every 5 minutes
- **Full backups**: Daily at 2:00 AM

### Data Loss
- **Maximum**: 15 minutes of transactions
- **Typical**: 5-10 minutes
- **Best case**: 0 minutes (if WAL archives available)

## Security Checklist

- [ ] DR initiated by authorized personnel
- [ ] Reason documented in restore log
- [ ] Incident ticket created
- [ ] Management notified
- [ ] Post-DR security audit scheduled
- [ ] Access logs reviewed
- [ ] Passwords rotated (if compromise suspected)

## Communication Template

### Internal Notification

```
Subject: URGENT - Disaster Recovery Initiated

Team,

A disaster recovery operation has been initiated at [TIME].

Reason: [REASON]
Initiated by: [USER]
Expected completion: [TIME + 1 hour]
Restore log ID: [UUID]

Current status: [IN_PROGRESS/COMPLETED/FAILED]

The system will be unavailable during the recovery process.
All users will be logged out and data will be restored to [BACKUP_TIME].

Updates will be provided every 15 minutes.

- Operations Team
```

### Customer Notification

```
Subject: Scheduled Maintenance - Service Restoration

Dear Customers,

We are currently performing emergency maintenance to restore service.

Expected completion: [TIME]
Estimated downtime: 30-60 minutes

We apologize for any inconvenience and appreciate your patience.

Status updates: https://status.yourcompany.com

- Support Team
```

## Emergency Contacts

- **Platform Admin**: [PHONE]
- **Database Admin**: [PHONE]
- **DevOps Lead**: [PHONE]
- **CTO**: [PHONE]
- **On-Call Engineer**: [PHONE]

## Related Documentation

- Full DR Implementation: `TASK_18.9_DR_RUNBOOK_COMPLETION.md`
- Backup System: `README.md`
- WAL Archiving: `WAL_ARCHIVING_PRODUCTION_GUIDE.md`
- Configuration Backup: `CONFIGURATION_BACKUP_GUIDE.md`

## Automated DR Testing

Schedule monthly DR tests:

```python
from celery.schedules import crontab
from config.celery import app

# Add to celerybeat schedule
app.conf.beat_schedule['monthly-dr-test'] = {
    'task': 'apps.backups.tasks.execute_disaster_recovery_runbook',
    'schedule': crontab(day_of_month='1', hour='3', minute='0'),
    'kwargs': {
        'backup_id': None,
        'reason': 'Monthly automated DR test',
    },
}
```

## Remember

- ⚠️ DR is **DESTRUCTIVE** - all current data will be replaced
- 📝 Always document the reason for DR
- 👥 Notify team before executing DR
- 📊 Monitor progress throughout execution
- ✅ Verify system after DR completes
- 📋 Conduct post-DR review

---

**Last Updated**: January 26, 2025
**Version**: 1.0
**Status**: Production Ready
