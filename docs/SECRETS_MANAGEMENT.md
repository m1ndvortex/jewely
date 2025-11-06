# Secrets Management System

## Overview

The Jewelry SaaS Platform implements a comprehensive secrets management system to securely handle sensitive configuration data. This system provides:

- **AES-256 Encryption**: All secrets are encrypted using Fernet (AES-256 in CBC mode with HMAC-SHA256)
- **Quarterly Key Rotation**: Automated key rotation tracking with 90-day rotation schedule
- **Audit Trail**: Complete history of all key rotations and operations
- **Secure Storage**: Encrypted .env files safe to commit to version control
- **Secrets Masking**: Automatic masking of sensitive values in logs and error reports

## Architecture

### Components

1. **SecretsManager**: Core class for encryption, decryption, and key rotation
2. **SecretsKeyRotation Model**: Database tracking of key rotation history
3. **Management Commands**: CLI tools for key operations
4. **Secrets Masking**: Automatic filtering of sensitive data in logs

### Security Model

```
┌─────────────────────────────────────────────────────────────┐
│                    Master Encryption Key                     │
│         (Stored in environment/Kubernetes secret)            │
│                  NEVER in .env file                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    .env File (Plaintext)                     │
│  • DJANGO_SECRET_KEY=...                                     │
│  • DB_PASSWORD=...                                           │
│  • API_KEYS=...                                              │
│  • NOT committed to git                                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼ Encrypt
┌─────────────────────────────────────────────────────────────┐
│              .env.encrypted (Ciphertext)                     │
│  • AES-256 encrypted                                         │
│  • HMAC-SHA256 authenticated                                 │
│  • Safe to commit to git                                     │
│  • Requires master key to decrypt                            │
└─────────────────────────────────────────────────────────────┘
```

## Setup

### 1. Generate Master Key

Generate a new master encryption key:

```bash
docker compose exec web python manage.py generate_secrets_key
```

This will output a new key like:
```
gAAAAABh1234567890abcdefghijklmnopqrstuvwxyz...
```

### 2. Store Master Key Securely

**For Development:**
```bash
export SECRETS_MASTER_KEY='your-generated-key-here'
```

**For Production (Kubernetes):**
```bash
kubectl create secret generic secrets-master-key \
  --from-literal=SECRETS_MASTER_KEY='your-generated-key-here' \
  --namespace jewelry-saas
```

**For Production (Docker Compose):**
Add to a secure `.env.secrets` file (NOT committed to git):
```bash
SECRETS_MASTER_KEY=your-generated-key-here
```

### 3. Encrypt .env File

Encrypt your .env file:

```bash
docker compose exec web python manage.py encrypt_env
```

This creates `.env.encrypted` which is safe to commit to version control.

### 4. Update .gitignore

Ensure your `.gitignore` includes:
```
.env
.env.local
.env.*.local
.env.secrets
*.backup_*
```

But allows:
```
!.env.example
!.env.encrypted
```

## Usage

### Encrypting .env File

```bash
# Encrypt default .env file
docker compose exec web python manage.py encrypt_env

# Encrypt specific file
docker compose exec web python manage.py encrypt_env --env-path /path/to/.env

# Specify output path
docker compose exec web python manage.py encrypt_env --output /path/to/.env.encrypted

# Force overwrite existing encrypted file
docker compose exec web python manage.py encrypt_env --force
```

### Decrypting .env File

```bash
# Decrypt default .env.encrypted file
docker compose exec web python manage.py decrypt_env

# Decrypt specific file
docker compose exec web python manage.py decrypt_env --encrypted-path /path/to/.env.encrypted

# Specify output path
docker compose exec web python manage.py decrypt_env --output /path/to/.env

# Force overwrite existing .env file
docker compose exec web python manage.py decrypt_env --force
```

### Key Rotation

Rotate the master encryption key (required quarterly):

```bash
# Rotate with default settings
docker compose exec web python manage.py rotate_secrets_key

# Rotate with custom reason
docker compose exec web python manage.py rotate_secrets_key --reason "Security incident response"

# Rotate without backup
docker compose exec web python manage.py rotate_secrets_key --no-backup

# Force rotation (skip confirmation)
docker compose exec web python manage.py rotate_secrets_key --force
```

**Key Rotation Process:**
1. Generates new master encryption key
2. Decrypts .env with old key
3. Re-encrypts .env with new key
4. Creates backup of old encrypted file
5. Verifies new encryption works
6. Records rotation in database
7. Outputs new key for secure storage

**After Rotation:**
You MUST update the `SECRETS_MASTER_KEY` environment variable with the new key:

```bash
# Update environment variable
export SECRETS_MASTER_KEY='new-key-here'

# Or update Kubernetes secret
kubectl create secret generic secrets-master-key \
  --from-literal=SECRETS_MASTER_KEY='new-key-here' \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart application pods to use new key
kubectl rollout restart deployment/jewelry-saas-web
```

## Quarterly Rotation Schedule

Key rotation is required every 90 days for security compliance.

### Automated Rotation Tracking

The system tracks:
- Last rotation date
- Next rotation due date
- Rotation status (initiated, in progress, completed, failed)
- Key fingerprints (SHA-256 hashes, not actual keys)
- Files re-encrypted
- Verification results

### Checking Rotation Status

```python
from apps.core.models import SecretsKeyRotation

# Get last rotation
last_rotation = SecretsKeyRotation.objects.filter(
    status=SecretsKeyRotation.COMPLETED
).first()

if last_rotation:
    print(f"Last rotation: {last_rotation.rotation_date}")
    print(f"Next due: {last_rotation.next_rotation_due}")
    print(f"Overdue: {last_rotation.is_overdue()}")
```

### Rotation Reminders

Set up a Celery task to check for overdue rotations:

```python
from celery import shared_task
from django.utils import timezone
from apps.core.models import SecretsKeyRotation

@shared_task
def check_key_rotation_due():
    """Check if key rotation is overdue and send alerts."""
    last_rotation = SecretsKeyRotation.objects.filter(
        status=SecretsKeyRotation.COMPLETED
    ).first()
    
    if last_rotation and last_rotation.is_overdue():
        # Send alert to admins
        send_admin_alert(
            "Key Rotation Overdue",
            f"Master encryption key rotation is overdue. "
            f"Last rotation: {last_rotation.rotation_date}"
        )
```

## Secrets Masking

### Automatic Masking in Logs

Sensitive values are automatically masked in logs:

```python
from apps.core.secrets_management import SecretsManager

# Mask individual value
masked = SecretsManager.mask_sensitive_value(
    "DJANGO_SECRET_KEY", 
    "my-secret-key-12345"
)
# Output: "my-s...2345"

# Mask dictionary
env_dict = {
    "DJANGO_SECRET_KEY": "my-secret-key-12345",
    "DEBUG": "True",
}
masked_dict = SecretsManager.mask_env_dict(env_dict)
# Output: {"DJANGO_SECRET_KEY": "my-s...2345", "DEBUG": "True"}
```

### Sensitive Keys

The following keys are automatically masked:
- `DJANGO_SECRET_KEY`
- `DB_SUPERUSER_PASSWORD`
- `APP_DB_PASSWORD`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_ACCOUNT_SID`
- `GOLDAPI_KEY`
- `METALS_API_KEY`
- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `BACKUP_ENCRYPTION_KEY`
- `SECRETS_MASTER_KEY`
- `GRAFANA_ADMIN_PASSWORD`
- `AWS_SECRET_ACCESS_KEY`
- `CLOUDFLARE_R2_SECRET_KEY`
- `BACKBLAZE_B2_APPLICATION_KEY`

## Best Practices

### 1. Master Key Security

✅ **DO:**
- Store master key in environment variables or Kubernetes secrets
- Keep secure backup of master key in password manager
- Rotate master key quarterly (every 90 days)
- Use different keys for development, staging, and production
- Restrict access to master key to authorized personnel only

❌ **DON'T:**
- Commit master key to version control
- Store master key in .env file
- Share master key via email or chat
- Use the same key across environments
- Store master key in application code

### 2. .env File Management

✅ **DO:**
- Commit `.env.encrypted` to version control
- Keep `.env` in `.gitignore`
- Use `.env.example` for documentation
- Encrypt .env before committing changes
- Verify encryption before pushing to git

❌ **DON'T:**
- Commit plaintext `.env` file
- Store secrets in application code
- Use hardcoded secrets
- Share .env files via insecure channels

### 3. Key Rotation

✅ **DO:**
- Rotate keys every 90 days
- Document rotation in change log
- Verify new key works before deleting old key
- Keep backup of old encrypted files
- Update all environments after rotation
- Test decryption after rotation

❌ **DON'T:**
- Skip quarterly rotations
- Delete old backups immediately
- Rotate without verification
- Forget to update production environment
- Rotate during peak traffic hours

### 4. Deployment

✅ **DO:**
- Use Kubernetes secrets for production
- Automate secret injection in CI/CD
- Use separate secrets per environment
- Implement secret rotation in deployment pipeline
- Monitor secret access and usage

❌ **DON'T:**
- Hardcode secrets in Dockerfiles
- Store secrets in container images
- Use same secrets across environments
- Expose secrets in logs or error messages

## Troubleshooting

### "SECRETS_MASTER_KEY not found"

**Problem:** Master key not set in environment.

**Solution:**
```bash
export SECRETS_MASTER_KEY='your-key-here'
# Or set in Kubernetes secret
```

### "Invalid encryption key or corrupted file"

**Problem:** Wrong master key or corrupted encrypted file.

**Solutions:**
1. Verify you're using the correct master key
2. Check if encrypted file is corrupted
3. Restore from backup if available
4. Re-encrypt from plaintext .env if available

### "Checksum mismatch"

**Problem:** Encrypted file was modified or corrupted.

**Solutions:**
1. Restore from backup
2. Re-encrypt from plaintext .env
3. Check file permissions and storage integrity

### Key Rotation Failed

**Problem:** Key rotation process failed.

**Solutions:**
1. Check rotation logs in database
2. Verify old key is still valid
3. Ensure sufficient disk space
4. Check file permissions
5. Restore from backup if needed

## API Reference

### SecretsManager

```python
from apps.core.secrets_management import SecretsManager

# Initialize
manager = SecretsManager()

# Encrypt .env file
encrypted_path = manager.encrypt_env_file('.env')

# Decrypt .env file
decrypted_path = manager.decrypt_env_file('.env.encrypted')

# Rotate master key
new_encrypted, backup = manager.rotate_master_key(
    new_key=b'new-key-bytes',
    env_path='.env',
    backup=True
)

# Generate new key
new_key = SecretsManager.generate_new_key()

# Mask sensitive value
masked = SecretsManager.mask_sensitive_value('API_KEY', 'secret-value')

# Parse .env file
env_dict = SecretsManager.parse_env_file('.env')

# Check if rotation is due
should_rotate = manager.should_rotate_key(last_rotation_date)

# Get next rotation date
next_date = manager.get_next_rotation_date(last_rotation_date)
```

### SecretsKeyRotation Model

```python
from apps.core.models import SecretsKeyRotation

# Create rotation record
rotation = SecretsKeyRotation.objects.create(
    status=SecretsKeyRotation.INITIATED,
    old_key_fingerprint='old_hash',
    new_key_fingerprint='new_hash',
    rotation_reason='Quarterly rotation'
)

# Check if overdue
if rotation.is_overdue():
    print("Rotation is overdue!")

# Get duration
duration = rotation.duration_seconds()
```

## Security Considerations

### Encryption Algorithm

- **Algorithm**: AES-256 in CBC mode
- **Authentication**: HMAC-SHA256
- **Library**: Fernet (cryptography package)
- **Key Size**: 256 bits
- **Compliance**: FIPS 140-2 compliant

### Key Storage

- Master key stored in environment variables or Kubernetes secrets
- Never stored in application code or database
- Separate keys for each environment
- Regular rotation (90 days)

### Audit Trail

All key operations are logged:
- Key rotations (with fingerprints, not actual keys)
- Encryption/decryption operations
- Verification results
- Failure reasons

### Access Control

- Only platform administrators can rotate keys
- Key rotation requires authentication
- All operations are logged in audit trail
- Failed operations trigger alerts

## Compliance

This secrets management system helps meet:

- **GDPR**: Encryption of personal data at rest
- **PCI DSS**: Encryption of cardholder data
- **SOC 2**: Encryption and key management controls
- **ISO 27001**: Information security management
- **HIPAA**: Encryption of protected health information (if applicable)

## Support

For issues or questions:
1. Check troubleshooting section above
2. Review audit logs in database
3. Contact platform administrators
4. Refer to security team for key recovery

## References

- [Cryptography Library Documentation](https://cryptography.io/)
- [Fernet Specification](https://github.com/fernet/spec/)
- [NIST Key Management Guidelines](https://csrc.nist.gov/publications/detail/sp/800-57-part-1/rev-5/final)
- [OWASP Cryptographic Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cryptographic_Storage_Cheat_Sheet.html)
