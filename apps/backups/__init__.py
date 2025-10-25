"""
Backup and disaster recovery app for the jewelry shop SaaS platform.

This app provides enterprise-grade backup capabilities including:
- Triple-redundant storage (local, Cloudflare R2, Backblaze B2)
- Multiple backup types (full database, tenant-specific, WAL archives, configuration)
- Automated disaster recovery with 1-hour RTO
- Comprehensive monitoring and alerting
- Point-in-time recovery (PITR) support
"""

default_app_config = "apps.backups.apps.BackupsConfig"
