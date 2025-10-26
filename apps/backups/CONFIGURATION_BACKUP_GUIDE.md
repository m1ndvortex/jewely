# Configuration Backup Quick Reference Guide

## Overview

The configuration backup system automatically backs up all critical configuration files to ensure quick disaster recovery.

## What Gets Backed Up

### Docker Configuration
- `docker-compose.yml` (all variants)
- `Dockerfile`
- `.dockerignore`
- All files in `docker/` directory

### Environment Files
- `.env.example`
- `.env` (sanitized with redacted sensitive values)

### Nginx Configuration
- All `.conf` files in nginx directories
- System nginx configs (if accessible)

### SSL Certificates
- `.pem`, `.crt`, `.key`, `.cert` files
- Let's Encrypt certificates (if accessible)

### Kubernetes Manifests
- All `.yaml` and `.yml` files in k8s directories

### PostgreSQL Configuration
- `postgresql.conf`
- `init-db.sh`
- `init-wal-archive.sh`
- All files in `docker/postgres/` directory

### Other Important Files
- `requirements.txt`
- `pyproject.toml`
- `setup.cfg`
- `pytest.ini`
- `.pre-commit-config.yaml`
- `Makefile`
- Django settings files

## Automated Backup

### Schedule
Runs automatically at **4:00 AM daily** via Celery Beat.

### Setup
Add to `config/celery.py`:

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    'configuration-backup-daily': {
        'task': 'apps.backups.tasks.configuration_backup',
        'schedule': crontab(hour=4, minute=0),
        'options': {
            'priority': 8,
        }
    },
}
```

## Manual Backup

### Via Django Shell

```python
from apps.backups.tasks import configuration_backup

# Trigger backup
result = configuration_backup.delay(initiated_by_user_id=1)

# Wait for completion and get backup ID
backup_id = result.get()
print(f"Backup created: {backup_id}")
```

### Via Django Admin (Future)
Will be available through the backup management interface (Task 18.10).

## Verify Backup

```python
from apps.backups.models import Backup

# Get the backup
backup = Backup.objects.get(id=backup_id)

# Check status
print(f"Status: {backup.status}")  # Should be 'VERIFIED'
print(f"Size: {backup.get_size_mb()} MB")
print(f"Created: {backup.created_at}")

# Check storage locations
print(f"Local: {backup.local_path}")
print(f"R2: {backup.r2_path}")
print(f"B2: {backup.b2_path}")

# Check metadata
print(f"Files collected: {backup.metadata['files_collected']}")
print(f"Categories: {backup.metadata['file_categories']}")
```

## Restore Configuration

### 1. Download Backup

```python
from apps.backups.storage import get_storage_backend
from apps.backups.encryption import decrypt_and_decompress_file
import tempfile

# Get backup
backup = Backup.objects.get(id=backup_id)

# Download from R2 (or B2 as fallback)
storage = get_storage_backend('r2')
with tempfile.NamedTemporaryFile(delete=False) as temp_file:
    temp_path = temp_file.name

storage.download(backup.r2_path, temp_path)
```

### 2. Decrypt and Extract

```python
import tarfile

# Decrypt and decompress
decrypted_path = decrypt_and_decompress_file(temp_path)

# Extract tar archive
with tarfile.open(decrypted_path, 'r:gz') as tar:
    tar.extractall('/path/to/restore/location')
```

### 3. Review and Apply

Manually review the extracted files and copy them to their original locations as needed.

## Monitoring

### Check Recent Backups

```python
from apps.backups.models import Backup
from datetime import timedelta
from django.utils import timezone

# Get backups from last 7 days
recent_backups = Backup.objects.filter(
    backup_type=Backup.CONFIGURATION,
    created_at__gte=timezone.now() - timedelta(days=7)
).order_by('-created_at')

for backup in recent_backups:
    print(f"{backup.created_at}: {backup.status} - {backup.get_size_mb()} MB")
```

### Check for Failures

```python
from apps.backups.models import BackupAlert

# Get recent alerts
alerts = BackupAlert.objects.filter(
    alert_type=BackupAlert.BACKUP_FAILURE,
    status=BackupAlert.ACTIVE
).order_by('-created_at')[:10]

for alert in alerts:
    print(f"{alert.created_at}: {alert.severity} - {alert.message}")
```

## Troubleshooting

### Backup Failed

1. Check the backup record:
   ```python
   backup = Backup.objects.filter(
       backup_type=Backup.CONFIGURATION,
       status=Backup.FAILED
   ).order_by('-created_at').first()
   
   print(backup.notes)  # Error message
   ```

2. Check alerts:
   ```python
   alerts = BackupAlert.objects.filter(backup=backup)
   for alert in alerts:
       print(alert.message)
       print(alert.details)
   ```

3. Check Celery logs:
   ```bash
   docker compose logs celery_worker | grep configuration_backup
   ```

### No Files Collected

This usually means the project structure is different than expected. Check:
- Project root directory is correctly set in Django settings
- Configuration files exist in expected locations
- File permissions allow reading

### Upload Failed

Check storage backend credentials:
- Local storage: Check `BACKUP_LOCAL_PATH` setting
- R2: Check `R2_ACCESS_KEY_ID` and `R2_SECRET_ACCESS_KEY`
- B2: Check `B2_ACCESS_KEY_ID` and `B2_SECRET_ACCESS_KEY`

### Verification Failed

This means the backup was uploaded but checksums don't match. This could indicate:
- Network corruption during upload
- Storage backend issues
- Encryption key mismatch

Check the verification details in the alert.

## Best Practices

1. **Test Restores:** Periodically test restoring configuration backups to ensure they work
2. **Monitor Alerts:** Set up notifications for backup failures
3. **Review Logs:** Regularly check backup logs for warnings
4. **Verify Storage:** Ensure all three storage locations are working
5. **Update Schedule:** Adjust backup schedule based on configuration change frequency

## Security Notes

1. **Sensitive Data:** The `.env` file is automatically sanitized with redacted values
2. **Encryption:** All backups are encrypted with AES-256
3. **Access Control:** Only platform administrators should have access to backups
4. **Key Management:** Protect the `BACKUP_ENCRYPTION_KEY` setting
5. **Storage Security:** Ensure storage backend credentials are secure

## Performance

### Typical Metrics
- **Collection Time:** 1-5 seconds
- **Archive Creation:** 1-3 seconds
- **Encryption:** 1-2 seconds
- **Upload Time:** 5-30 seconds
- **Total Duration:** 10-60 seconds

### Archive Sizes
- **Uncompressed:** 5-20 MB
- **Compressed:** 1-5 MB
- **Encrypted:** 1-5 MB

## Support

For issues or questions:
1. Check this guide
2. Review the completion report: `TASK_18.7_COMPLETION_REPORT.md`
3. Check Celery logs
4. Review backup alerts in the database
