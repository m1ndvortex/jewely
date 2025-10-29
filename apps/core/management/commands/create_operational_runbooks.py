"""
Management command to create operational runbooks for platform operations.

This command creates comprehensive runbooks for:
- Incident response procedures
- Maintenance runbooks
- Disaster recovery procedures
- Admin notes and tips

Per Requirement 34 - Knowledge Base and Documentation
"""

from datetime import timedelta

from django.core.management.base import BaseCommand

from apps.core.documentation_models import AdminNote, Runbook


class Command(BaseCommand):
    help = "Create operational runbooks for platform operations"

    def handle(self, *args, **options):
        self.stdout.write("Creating operational runbooks...")

        # Create incident response runbooks
        self.create_incident_response_runbooks()

        # Create maintenance runbooks
        self.create_maintenance_runbooks()

        # Create disaster recovery runbooks
        self.create_disaster_recovery_runbooks()

        # Create deployment runbooks
        self.create_deployment_runbooks()

        # Create troubleshooting runbooks
        self.create_troubleshooting_runbooks()

        # Create backup & restore runbooks
        self.create_backup_restore_runbooks()

        # Create admin notes and tips
        self.create_admin_notes()

        self.stdout.write(self.style.SUCCESS("Successfully created operational runbooks"))

    def create_incident_response_runbooks(self):
        """Create incident response runbooks."""
        self.stdout.write("Creating incident response runbooks...")

        # Database outage incident response
        runbook, created = Runbook.objects.update_or_create(
            slug="incident-database-outage",
            defaults={
                "title": "Database Outage Incident Response",
                "description": "Procedures for responding to PostgreSQL database outages",
                "runbook_type": Runbook.INCIDENT_RESPONSE,
                "priority": Runbook.CRITICAL,
                "prerequisites": "- Access to Kubernetes cluster\n- Database admin credentials\n- Monitoring dashboard access",
                "steps": [
                    {
                        "title": "Assess the Situation",
                        "description": "Determine the scope and impact of the database outage",
                        "commands": [
                            "kubectl get pods -n production | grep postgres",
                            "kubectl logs -n production postgres-0 --tail=100",
                            "docker-compose exec db pg_isready -U postgres",
                        ],
                        "expected_output": "Check if database pods are running and responsive",
                    },
                    {
                        "title": "Check Database Logs",
                        "description": "Review PostgreSQL logs for error messages",
                        "commands": [
                            "kubectl logs -n production postgres-0 --tail=500",
                            "docker-compose logs db --tail=500",
                        ],
                        "expected_output": "Look for connection errors, disk space issues, or corruption messages",
                    },
                    {
                        "title": "Verify Patroni Status",
                        "description": "Check Patroni cluster health and failover status",
                        "commands": [
                            "kubectl exec -n production postgres-0 -- patronictl list",
                        ],
                        "expected_output": "Verify primary and replica status",
                    },
                    {
                        "title": "Check Disk Space",
                        "description": "Ensure database has sufficient disk space",
                        "commands": [
                            "kubectl exec -n production postgres-0 -- df -h",
                            "docker-compose exec db df -h",
                        ],
                        "expected_output": "Disk usage should be below 90%",
                    },
                    {
                        "title": "Attempt Automatic Recovery",
                        "description": "Restart database pod if necessary",
                        "commands": [
                            "kubectl delete pod -n production postgres-0",
                            "docker-compose restart db",
                        ],
                        "expected_output": "Pod should restart and become ready",
                    },
                    {
                        "title": "Trigger Failover (if needed)",
                        "description": "If primary is unrecoverable, trigger Patroni failover",
                        "commands": [
                            "kubectl exec -n production postgres-1 -- patronictl failover --force",
                        ],
                        "expected_output": "Replica should be promoted to primary",
                    },
                    {
                        "title": "Restore from Backup (last resort)",
                        "description": "If database is corrupted, restore from latest backup",
                        "commands": [
                            "# See disaster-recovery-database-restore runbook",
                        ],
                        "expected_output": "Database restored to last known good state",
                    },
                    {
                        "title": "Notify Stakeholders",
                        "description": "Update status page and notify affected tenants",
                        "commands": [
                            "# Update status page",
                            "# Send notification via admin panel",
                        ],
                        "expected_output": "Stakeholders informed of incident and resolution",
                    },
                ],
                "expected_duration": timedelta(minutes=30),
                "rto": timedelta(hours=1),
                "verification_steps": [
                    {
                        "title": "Verify Database Connectivity",
                        "description": "Test database connections from application",
                        "commands": [
                            "docker-compose exec web python manage.py dbshell",
                        ],
                    },
                    {
                        "title": "Check Application Health",
                        "description": "Verify application can query database",
                        "commands": [
                            "curl https://api.example.com/health",
                        ],
                    },
                    {
                        "title": "Monitor Error Rates",
                        "description": "Check Grafana for database error rates",
                        "commands": [],
                    },
                ],
                "rollback_steps": [],
                "tags": ["database", "incident", "critical", "postgres"],
                "status": Runbook.ACTIVE,
            },
        )
        if created:
            self.stdout.write(f"  Created: {runbook.title}")

        # Application crash incident response
        runbook, created = Runbook.objects.update_or_create(
            slug="incident-application-crash",
            defaults={
                "title": "Application Crash Incident Response",
                "description": "Procedures for responding to Django application crashes or high error rates",
                "runbook_type": Runbook.INCIDENT_RESPONSE,
                "priority": Runbook.CRITICAL,
                "prerequisites": "- Access to Kubernetes cluster\n- Sentry access\n- Grafana dashboard access",
                "steps": [
                    {
                        "title": "Check Application Pods",
                        "description": "Verify pod status and restart counts",
                        "commands": [
                            "kubectl get pods -n production | grep web",
                            "kubectl describe pod -n production web-0",
                            "docker-compose ps",
                        ],
                        "expected_output": "Check for CrashLoopBackOff or high restart counts",
                    },
                    {
                        "title": "Review Application Logs",
                        "description": "Check Django logs for errors and exceptions",
                        "commands": [
                            "kubectl logs -n production web-0 --tail=200",
                            "docker-compose logs web --tail=200",
                        ],
                        "expected_output": "Identify error messages, stack traces, or exceptions",
                    },
                    {
                        "title": "Check Sentry for Errors",
                        "description": "Review recent errors in Sentry dashboard",
                        "commands": [],
                        "expected_output": "Identify error patterns and affected endpoints",
                    },
                    {
                        "title": "Check Resource Usage",
                        "description": "Verify CPU and memory usage",
                        "commands": [
                            "kubectl top pods -n production",
                            "docker stats",
                        ],
                        "expected_output": "Check for resource exhaustion",
                    },
                    {
                        "title": "Check Database Connections",
                        "description": "Verify database connectivity and connection pool",
                        "commands": [
                            "docker-compose exec web python manage.py dbshell",
                        ],
                        "expected_output": "Database should be accessible",
                    },
                    {
                        "title": "Check Redis Connectivity",
                        "description": "Verify Redis cache and Celery broker",
                        "commands": [
                            "docker-compose exec redis redis-cli ping",
                        ],
                        "expected_output": "Should return PONG",
                    },
                    {
                        "title": "Rollback Recent Deployment (if applicable)",
                        "description": "If crash started after deployment, rollback",
                        "commands": [
                            "kubectl rollout undo deployment/web -n production",
                        ],
                        "expected_output": "Application rolled back to previous version",
                    },
                    {
                        "title": "Scale Up Replicas (if needed)",
                        "description": "Increase pod count to handle load",
                        "commands": [
                            "kubectl scale deployment/web --replicas=5 -n production",
                        ],
                        "expected_output": "Additional pods started",
                    },
                    {
                        "title": "Clear Cache (if needed)",
                        "description": "Clear Redis cache if corrupted data suspected",
                        "commands": [
                            "docker-compose exec redis redis-cli FLUSHDB",
                        ],
                        "expected_output": "Cache cleared",
                    },
                ],
                "expected_duration": timedelta(minutes=20),
                "rto": timedelta(minutes=30),
                "verification_steps": [
                    {
                        "title": "Check Application Health",
                        "description": "Verify health endpoint responds",
                        "commands": [
                            "curl https://api.example.com/health",
                        ],
                    },
                    {
                        "title": "Monitor Error Rates",
                        "description": "Check Grafana for error rate trends",
                        "commands": [],
                    },
                    {
                        "title": "Test Critical Endpoints",
                        "description": "Manually test key API endpoints",
                        "commands": [
                            "curl https://api.example.com/api/v1/inventory/",
                        ],
                    },
                ],
                "rollback_steps": [
                    {
                        "title": "Rollback Deployment",
                        "description": "Revert to previous stable version",
                        "commands": [
                            "kubectl rollout undo deployment/web -n production",
                        ],
                    },
                ],
                "tags": ["application", "incident", "critical", "django"],
                "status": Runbook.ACTIVE,
            },
        )
        if created:
            self.stdout.write(f"  Created: {runbook.title}")

        # Security breach incident response
        runbook, created = Runbook.objects.update_or_create(
            slug="incident-security-breach",
            defaults={
                "title": "Security Breach Incident Response",
                "description": "Procedures for responding to suspected security breaches or unauthorized access",
                "runbook_type": Runbook.INCIDENT_RESPONSE,
                "priority": Runbook.CRITICAL,
                "prerequisites": "- Access to audit logs\n- Database admin access\n- Security team contact info",
                "steps": [
                    {
                        "title": "Contain the Breach",
                        "description": "Immediately isolate affected systems",
                        "commands": [
                            "# Disable affected user accounts",
                            "# Block suspicious IP addresses",
                            "# Revoke compromised API keys",
                        ],
                        "expected_output": "Threat contained and isolated",
                    },
                    {
                        "title": "Review Audit Logs",
                        "description": "Examine audit logs for unauthorized access",
                        "commands": [
                            "# Check admin panel audit logs",
                            "# Review authentication logs",
                            "# Check API access logs",
                        ],
                        "expected_output": "Identify scope of breach and affected data",
                    },
                    {
                        "title": "Check for Data Exfiltration",
                        "description": "Look for unusual data exports or API calls",
                        "commands": [
                            "# Review data export logs",
                            "# Check API rate limits and unusual patterns",
                        ],
                        "expected_output": "Determine if data was stolen",
                    },
                    {
                        "title": "Force Password Resets",
                        "description": "Reset passwords for affected accounts",
                        "commands": [
                            "docker-compose exec web python manage.py force_password_reset --tenant=<tenant_id>",
                        ],
                        "expected_output": "All affected users must reset passwords",
                    },
                    {
                        "title": "Rotate Secrets and Keys",
                        "description": "Rotate all API keys, tokens, and secrets",
                        "commands": [
                            "# Rotate database passwords",
                            "# Rotate API keys",
                            "# Rotate JWT secrets",
                            "# Rotate encryption keys",
                        ],
                        "expected_output": "All secrets rotated",
                    },
                    {
                        "title": "Patch Vulnerabilities",
                        "description": "Apply security patches if vulnerability exploited",
                        "commands": [
                            "# Update dependencies",
                            "# Deploy security patches",
                        ],
                        "expected_output": "Vulnerabilities patched",
                    },
                    {
                        "title": "Notify Affected Parties",
                        "description": "Inform affected tenants and comply with breach notification laws",
                        "commands": [
                            "# Send breach notification emails",
                            "# Update status page",
                        ],
                        "expected_output": "All required parties notified",
                    },
                    {
                        "title": "Document Incident",
                        "description": "Create detailed incident report",
                        "commands": [],
                        "expected_output": "Complete incident documentation",
                    },
                ],
                "expected_duration": timedelta(hours=2),
                "rto": timedelta(hours=1),
                "verification_steps": [
                    {
                        "title": "Verify No Ongoing Unauthorized Access",
                        "description": "Monitor for continued suspicious activity",
                        "commands": [],
                    },
                    {
                        "title": "Verify All Secrets Rotated",
                        "description": "Confirm all credentials changed",
                        "commands": [],
                    },
                    {
                        "title": "Verify Patches Applied",
                        "description": "Confirm vulnerabilities fixed",
                        "commands": [],
                    },
                ],
                "rollback_steps": [],
                "tags": ["security", "incident", "critical", "breach"],
                "status": Runbook.ACTIVE,
            },
        )
        if created:
            self.stdout.write(f"  Created: {runbook.title}")

    def create_maintenance_runbooks(self):
        """Create maintenance runbooks."""
        self.stdout.write("Creating maintenance runbooks...")

        # Database maintenance
        runbook, created = Runbook.objects.update_or_create(
            slug="maintenance-database-routine",
            defaults={
                "title": "Routine Database Maintenance",
                "description": "Regular PostgreSQL maintenance tasks including VACUUM, ANALYZE, and index maintenance",
                "runbook_type": Runbook.MAINTENANCE,
                "priority": Runbook.MEDIUM,
                "prerequisites": "- Database admin credentials\n- Maintenance window scheduled\n- Backup completed",
                "steps": [
                    {
                        "title": "Verify Recent Backup",
                        "description": "Ensure a recent backup exists before maintenance",
                        "commands": [
                            "docker-compose exec web python manage.py list_backups --type=FULL_DATABASE --limit=1",
                        ],
                        "expected_output": "Backup from last 24 hours exists",
                    },
                    {
                        "title": "Check Database Size",
                        "description": "Record current database size for comparison",
                        "commands": [
                            "docker-compose exec db psql -U postgres -d jewelry_shop -c \"SELECT pg_size_pretty(pg_database_size('jewelry_shop'));\"",
                        ],
                        "expected_output": "Current database size displayed",
                    },
                    {
                        "title": "Run VACUUM ANALYZE",
                        "description": "Reclaim storage and update statistics",
                        "commands": [
                            'docker-compose exec db psql -U postgres -d jewelry_shop -c "VACUUM ANALYZE;"',
                        ],
                        "expected_output": "VACUUM completed successfully",
                    },
                    {
                        "title": "Reindex Large Tables",
                        "description": "Rebuild indexes on large tables",
                        "commands": [
                            'docker-compose exec db psql -U postgres -d jewelry_shop -c "REINDEX TABLE inventory_items;"',
                            'docker-compose exec db psql -U postgres -d jewelry_shop -c "REINDEX TABLE sales;"',
                        ],
                        "expected_output": "Indexes rebuilt",
                    },
                    {
                        "title": "Check for Bloat",
                        "description": "Identify tables with excessive bloat",
                        "commands": [
                            "docker-compose exec db psql -U postgres -d jewelry_shop -f /scripts/check_bloat.sql",
                        ],
                        "expected_output": "Bloat report generated",
                    },
                    {
                        "title": "Update Table Statistics",
                        "description": "Ensure query planner has current statistics",
                        "commands": [
                            'docker-compose exec db psql -U postgres -d jewelry_shop -c "ANALYZE;"',
                        ],
                        "expected_output": "Statistics updated",
                    },
                    {
                        "title": "Check for Missing Indexes",
                        "description": "Identify queries that could benefit from indexes",
                        "commands": [
                            "docker-compose exec db psql -U postgres -d jewelry_shop -f /scripts/missing_indexes.sql",
                        ],
                        "expected_output": "Missing index report generated",
                    },
                ],
                "expected_duration": timedelta(hours=1),
                "verification_steps": [
                    {
                        "title": "Verify Database Size",
                        "description": "Check if VACUUM reclaimed space",
                        "commands": [
                            "docker-compose exec db psql -U postgres -d jewelry_shop -c \"SELECT pg_size_pretty(pg_database_size('jewelry_shop'));\"",
                        ],
                    },
                    {
                        "title": "Check Query Performance",
                        "description": "Verify common queries are fast",
                        "commands": [
                            "docker-compose exec web python manage.py test_query_performance",
                        ],
                    },
                ],
                "rollback_steps": [],
                "tags": ["database", "maintenance", "postgres", "vacuum"],
                "status": Runbook.ACTIVE,
            },
        )
        if created:
            self.stdout.write(f"  Created: {runbook.title}")

        # Certificate renewal
        runbook, created = Runbook.objects.update_or_create(
            slug="maintenance-ssl-certificate-renewal",
            defaults={
                "title": "SSL Certificate Renewal",
                "description": "Renew SSL/TLS certificates before expiration",
                "runbook_type": Runbook.MAINTENANCE,
                "priority": Runbook.HIGH,
                "prerequisites": "- Access to certificate authority\n- DNS access\n- Nginx configuration access",
                "steps": [
                    {
                        "title": "Check Certificate Expiration",
                        "description": "Verify current certificate expiration date",
                        "commands": [
                            "echo | openssl s_client -servername example.com -connect example.com:443 2>/dev/null | openssl x509 -noout -dates",
                        ],
                        "expected_output": "Certificate expiration date displayed",
                    },
                    {
                        "title": "Request New Certificate",
                        "description": "Use Let's Encrypt or certificate provider",
                        "commands": [
                            "certbot renew --nginx",
                        ],
                        "expected_output": "New certificate issued",
                    },
                    {
                        "title": "Update Nginx Configuration",
                        "description": "Update certificate paths in Nginx config",
                        "commands": [
                            "# Update ssl_certificate and ssl_certificate_key paths",
                            "nginx -t",
                        ],
                        "expected_output": "Nginx configuration valid",
                    },
                    {
                        "title": "Reload Nginx",
                        "description": "Apply new certificate without downtime",
                        "commands": [
                            "kubectl exec -n production nginx-0 -- nginx -s reload",
                            "docker-compose exec nginx nginx -s reload",
                        ],
                        "expected_output": "Nginx reloaded successfully",
                    },
                    {
                        "title": "Update Kubernetes Secrets",
                        "description": "Update TLS secrets in Kubernetes",
                        "commands": [
                            "kubectl create secret tls tls-cert --cert=cert.pem --key=key.pem --dry-run=client -o yaml | kubectl apply -f -",
                        ],
                        "expected_output": "Kubernetes secret updated",
                    },
                ],
                "expected_duration": timedelta(minutes=30),
                "verification_steps": [
                    {
                        "title": "Verify New Certificate",
                        "description": "Check certificate is valid and not expired",
                        "commands": [
                            "echo | openssl s_client -servername example.com -connect example.com:443 2>/dev/null | openssl x509 -noout -dates",
                        ],
                    },
                    {
                        "title": "Test HTTPS Connection",
                        "description": "Verify HTTPS works correctly",
                        "commands": [
                            "curl -I https://example.com",
                        ],
                    },
                    {
                        "title": "Check SSL Labs Rating",
                        "description": "Verify SSL configuration quality",
                        "commands": [
                            "# Visit https://www.ssllabs.com/ssltest/",
                        ],
                    },
                ],
                "rollback_steps": [
                    {
                        "title": "Restore Previous Certificate",
                        "description": "Revert to previous certificate if issues",
                        "commands": [
                            "# Restore certificate files from backup",
                            "nginx -s reload",
                        ],
                    },
                ],
                "tags": ["ssl", "certificate", "maintenance", "nginx"],
                "status": Runbook.ACTIVE,
            },
        )
        if created:
            self.stdout.write(f"  Created: {runbook.title}")

        # Dependency updates
        runbook, created = Runbook.objects.update_or_create(
            slug="maintenance-dependency-updates",
            defaults={
                "title": "Dependency Updates and Security Patches",
                "description": "Update Python packages and apply security patches",
                "runbook_type": Runbook.MAINTENANCE,
                "priority": Runbook.MEDIUM,
                "prerequisites": "- Development environment\n- Test environment\n- CI/CD pipeline access",
                "steps": [
                    {
                        "title": "Check for Outdated Packages",
                        "description": "List packages with available updates",
                        "commands": [
                            "docker-compose exec web pip list --outdated",
                        ],
                        "expected_output": "List of outdated packages",
                    },
                    {
                        "title": "Check for Security Vulnerabilities",
                        "description": "Scan for known vulnerabilities",
                        "commands": [
                            "docker-compose exec web pip-audit",
                            "docker-compose exec web safety check",
                        ],
                        "expected_output": "Vulnerability report",
                    },
                    {
                        "title": "Update requirements.txt",
                        "description": "Update package versions in requirements file",
                        "commands": [
                            "# Update package versions",
                            "# Review changelog for breaking changes",
                        ],
                        "expected_output": "requirements.txt updated",
                    },
                    {
                        "title": "Rebuild Docker Images",
                        "description": "Build new images with updated dependencies",
                        "commands": [
                            "docker-compose build web",
                        ],
                        "expected_output": "Docker image built successfully",
                    },
                    {
                        "title": "Run Tests",
                        "description": "Verify all tests pass with new dependencies",
                        "commands": [
                            "docker-compose exec web pytest",
                        ],
                        "expected_output": "All tests pass",
                    },
                    {
                        "title": "Deploy to Staging",
                        "description": "Deploy updated application to staging",
                        "commands": [
                            "git push origin staging",
                        ],
                        "expected_output": "Staging deployment successful",
                    },
                    {
                        "title": "Test in Staging",
                        "description": "Perform smoke tests in staging environment",
                        "commands": [
                            "# Manual testing of critical features",
                        ],
                        "expected_output": "All features working correctly",
                    },
                    {
                        "title": "Deploy to Production",
                        "description": "Deploy to production after staging validation",
                        "commands": [
                            "git push origin main",
                        ],
                        "expected_output": "Production deployment successful",
                    },
                ],
                "expected_duration": timedelta(hours=2),
                "verification_steps": [
                    {
                        "title": "Verify No Vulnerabilities",
                        "description": "Confirm all vulnerabilities patched",
                        "commands": [
                            "docker-compose exec web pip-audit",
                        ],
                    },
                    {
                        "title": "Monitor Error Rates",
                        "description": "Check for increased errors after deployment",
                        "commands": [],
                    },
                ],
                "rollback_steps": [
                    {
                        "title": "Rollback Deployment",
                        "description": "Revert to previous version",
                        "commands": [
                            "kubectl rollout undo deployment/web -n production",
                        ],
                    },
                ],
                "tags": ["dependencies", "security", "maintenance", "updates"],
                "status": Runbook.ACTIVE,
            },
        )
        if created:
            self.stdout.write(f"  Created: {runbook.title}")

    def create_disaster_recovery_runbooks(self):
        """Create disaster recovery runbooks."""
        self.stdout.write("Creating disaster recovery runbooks...")

        # Full database restore
        runbook, created = Runbook.objects.update_or_create(
            slug="disaster-recovery-database-restore",
            defaults={
                "title": "Full Database Disaster Recovery",
                "description": "Complete database restore from backup after catastrophic failure",
                "runbook_type": Runbook.DISASTER_RECOVERY,
                "priority": Runbook.CRITICAL,
                "prerequisites": "- Backup files accessible\n- Database admin credentials\n- Maintenance mode enabled",
                "steps": [
                    {
                        "title": "Enable Maintenance Mode",
                        "description": "Put application in maintenance mode",
                        "commands": [
                            "kubectl scale deployment/web --replicas=0 -n production",
                            "docker-compose stop web",
                        ],
                        "expected_output": "Application stopped",
                    },
                    {
                        "title": "Identify Latest Backup",
                        "description": "Find the most recent valid backup",
                        "commands": [
                            "docker-compose exec web python manage.py list_backups --type=FULL_DATABASE --limit=5",
                        ],
                        "expected_output": "List of recent backups",
                    },
                    {
                        "title": "Download Backup from Cloud",
                        "description": "Download backup from Cloudflare R2 or Backblaze B2",
                        "commands": [
                            "docker-compose exec web python manage.py download_backup --backup-id=<backup_id>",
                        ],
                        "expected_output": "Backup downloaded successfully",
                    },
                    {
                        "title": "Verify Backup Integrity",
                        "description": "Check backup checksum",
                        "commands": [
                            "docker-compose exec web python manage.py verify_backup --backup-id=<backup_id>",
                        ],
                        "expected_output": "Checksum matches",
                    },
                    {
                        "title": "Decrypt Backup",
                        "description": "Decrypt the backup file",
                        "commands": [
                            "# Decryption handled automatically by restore command",
                        ],
                        "expected_output": "Backup decrypted",
                    },
                    {
                        "title": "Drop Existing Database",
                        "description": "Remove corrupted database",
                        "commands": [
                            'docker-compose exec db psql -U postgres -c "DROP DATABASE jewelry_shop;"',
                            'docker-compose exec db psql -U postgres -c "CREATE DATABASE jewelry_shop;"',
                        ],
                        "expected_output": "Database recreated",
                    },
                    {
                        "title": "Restore Database",
                        "description": "Restore from backup using pg_restore",
                        "commands": [
                            "docker-compose exec web python manage.py restore_backup --backup-id=<backup_id> --mode=FULL",
                        ],
                        "expected_output": "Database restored successfully",
                    },
                    {
                        "title": "Apply WAL Files (if PITR needed)",
                        "description": "Apply WAL files for point-in-time recovery",
                        "commands": [
                            "docker-compose exec web python manage.py apply_wal_files --until=<timestamp>",
                        ],
                        "expected_output": "WAL files applied",
                    },
                    {
                        "title": "Verify Data Integrity",
                        "description": "Check database for corruption",
                        "commands": [
                            'docker-compose exec db psql -U postgres -d jewelry_shop -c "SELECT COUNT(*) FROM tenants;"',
                            'docker-compose exec db psql -U postgres -d jewelry_shop -c "SELECT COUNT(*) FROM inventory_items;"',
                        ],
                        "expected_output": "Data counts match expectations",
                    },
                    {
                        "title": "Restart Application",
                        "description": "Bring application back online",
                        "commands": [
                            "kubectl scale deployment/web --replicas=3 -n production",
                            "docker-compose start web",
                        ],
                        "expected_output": "Application running",
                    },
                    {
                        "title": "Disable Maintenance Mode",
                        "description": "Allow user traffic",
                        "commands": [
                            "# Remove maintenance page",
                        ],
                        "expected_output": "Application accessible",
                    },
                ],
                "expected_duration": timedelta(hours=1),
                "rto": timedelta(hours=1),
                "rpo": timedelta(minutes=15),
                "verification_steps": [
                    {
                        "title": "Test Database Connectivity",
                        "description": "Verify application can connect to database",
                        "commands": [
                            "curl https://api.example.com/health",
                        ],
                    },
                    {
                        "title": "Test Critical Queries",
                        "description": "Run sample queries to verify data",
                        "commands": [
                            "docker-compose exec web python manage.py test_database_queries",
                        ],
                    },
                    {
                        "title": "Verify Tenant Data",
                        "description": "Spot check tenant data integrity",
                        "commands": [
                            "# Login to tenant panel and verify data",
                        ],
                    },
                ],
                "rollback_steps": [
                    {
                        "title": "Try Alternative Backup",
                        "description": "If restore fails, try previous backup",
                        "commands": [
                            "# Repeat restore with different backup",
                        ],
                    },
                ],
                "tags": ["disaster-recovery", "database", "critical", "restore"],
                "status": Runbook.ACTIVE,
            },
        )
        if created:
            self.stdout.write(f"  Created: {runbook.title}")

        # Complete system recovery
        runbook, created = Runbook.objects.update_or_create(
            slug="disaster-recovery-complete-system",
            defaults={
                "title": "Complete System Disaster Recovery",
                "description": "Full system recovery from catastrophic infrastructure failure",
                "runbook_type": Runbook.DISASTER_RECOVERY,
                "priority": Runbook.CRITICAL,
                "prerequisites": "- New infrastructure provisioned\n- Backup access\n- DNS access\n- Configuration backups",
                "steps": [
                    {
                        "title": "Provision New Infrastructure",
                        "description": "Set up new Kubernetes cluster or Docker hosts",
                        "commands": [
                            "# Provision cloud resources",
                            "# Set up Kubernetes cluster",
                        ],
                        "expected_output": "Infrastructure ready",
                    },
                    {
                        "title": "Restore Configuration Files",
                        "description": "Download and restore configuration backup",
                        "commands": [
                            "# Download configuration backup from R2/B2",
                            "# Extract docker-compose.yml, .env, nginx.conf, etc.",
                        ],
                        "expected_output": "Configuration files restored",
                    },
                    {
                        "title": "Deploy Database",
                        "description": "Deploy PostgreSQL with Patroni",
                        "commands": [
                            "kubectl apply -f k8s/postgres/",
                            "docker-compose up -d db",
                        ],
                        "expected_output": "Database running",
                    },
                    {
                        "title": "Restore Database",
                        "description": "Restore database from backup",
                        "commands": [
                            "# Follow disaster-recovery-database-restore runbook",
                        ],
                        "expected_output": "Database restored",
                    },
                    {
                        "title": "Deploy Redis",
                        "description": "Deploy Redis with Sentinel",
                        "commands": [
                            "kubectl apply -f k8s/redis/",
                            "docker-compose up -d redis",
                        ],
                        "expected_output": "Redis running",
                    },
                    {
                        "title": "Deploy Application",
                        "description": "Deploy Django application",
                        "commands": [
                            "kubectl apply -f k8s/web/",
                            "docker-compose up -d web",
                        ],
                        "expected_output": "Application running",
                    },
                    {
                        "title": "Deploy Celery Workers",
                        "description": "Deploy background task workers",
                        "commands": [
                            "kubectl apply -f k8s/celery/",
                            "docker-compose up -d celery_worker celery_beat",
                        ],
                        "expected_output": "Celery workers running",
                    },
                    {
                        "title": "Deploy Nginx",
                        "description": "Deploy reverse proxy and load balancer",
                        "commands": [
                            "kubectl apply -f k8s/nginx/",
                            "docker-compose up -d nginx",
                        ],
                        "expected_output": "Nginx running",
                    },
                    {
                        "title": "Restore SSL Certificates",
                        "description": "Install SSL certificates",
                        "commands": [
                            "# Restore certificates from backup",
                            "# Or request new certificates from Let's Encrypt",
                        ],
                        "expected_output": "SSL configured",
                    },
                    {
                        "title": "Update DNS",
                        "description": "Point DNS to new infrastructure",
                        "commands": [
                            "# Update A records to new IP addresses",
                        ],
                        "expected_output": "DNS updated",
                    },
                    {
                        "title": "Deploy Monitoring",
                        "description": "Deploy Prometheus and Grafana",
                        "commands": [
                            "kubectl apply -f k8s/monitoring/",
                        ],
                        "expected_output": "Monitoring running",
                    },
                ],
                "expected_duration": timedelta(hours=4),
                "rto": timedelta(hours=4),
                "rpo": timedelta(minutes=15),
                "verification_steps": [
                    {
                        "title": "Verify All Services Running",
                        "description": "Check all pods/containers are healthy",
                        "commands": [
                            "kubectl get pods -n production",
                            "docker-compose ps",
                        ],
                    },
                    {
                        "title": "Test Application Access",
                        "description": "Verify application is accessible",
                        "commands": [
                            "curl https://example.com/health",
                        ],
                    },
                    {
                        "title": "Test Tenant Login",
                        "description": "Verify tenants can login and access data",
                        "commands": [
                            "# Manual login test",
                        ],
                    },
                    {
                        "title": "Verify Monitoring",
                        "description": "Check Grafana dashboards",
                        "commands": [
                            "# Access Grafana and verify metrics",
                        ],
                    },
                ],
                "rollback_steps": [],
                "tags": ["disaster-recovery", "critical", "infrastructure", "complete"],
                "status": Runbook.ACTIVE,
            },
        )
        if created:
            self.stdout.write(f"  Created: {runbook.title}")

    def create_deployment_runbooks(self):
        """Create deployment runbooks."""
        self.stdout.write("Creating deployment runbooks...")

        # Production deployment
        runbook, created = Runbook.objects.update_or_create(
            slug="deployment-production-release",
            defaults={
                "title": "Production Deployment",
                "description": "Deploy new application version to production with zero downtime",
                "runbook_type": Runbook.DEPLOYMENT,
                "priority": Runbook.HIGH,
                "prerequisites": "- Code merged to main branch\n- All tests passing\n- Staging validation complete\n- Change approval obtained",
                "steps": [
                    {
                        "title": "Create Release Tag",
                        "description": "Tag the release in Git",
                        "commands": [
                            "git tag -a v1.2.3 -m 'Release version 1.2.3'",
                            "git push origin v1.2.3",
                        ],
                        "expected_output": "Release tag created",
                    },
                    {
                        "title": "Build Docker Images",
                        "description": "Build and push Docker images",
                        "commands": [
                            "docker build -t registry.example.com/jewelry-shop:v1.2.3 .",
                            "docker push registry.example.com/jewelry-shop:v1.2.3",
                        ],
                        "expected_output": "Images pushed to registry",
                    },
                    {
                        "title": "Backup Database",
                        "description": "Create pre-deployment backup",
                        "commands": [
                            "docker-compose exec web python manage.py trigger_backup --type=FULL_DATABASE",
                        ],
                        "expected_output": "Backup completed",
                    },
                    {
                        "title": "Run Database Migrations",
                        "description": "Apply any pending migrations",
                        "commands": [
                            "kubectl exec -n production web-0 -- python manage.py migrate",
                            "docker-compose exec web python manage.py migrate",
                        ],
                        "expected_output": "Migrations applied",
                    },
                    {
                        "title": "Update Kubernetes Deployment",
                        "description": "Update deployment with new image",
                        "commands": [
                            "kubectl set image deployment/web web=registry.example.com/jewelry-shop:v1.2.3 -n production",
                        ],
                        "expected_output": "Deployment updated",
                    },
                    {
                        "title": "Monitor Rollout",
                        "description": "Watch rollout progress",
                        "commands": [
                            "kubectl rollout status deployment/web -n production",
                        ],
                        "expected_output": "Rollout completed successfully",
                    },
                    {
                        "title": "Run Smoke Tests",
                        "description": "Verify critical functionality",
                        "commands": [
                            "curl https://api.example.com/health",
                            "# Test critical API endpoints",
                        ],
                        "expected_output": "All smoke tests pass",
                    },
                    {
                        "title": "Monitor Error Rates",
                        "description": "Check Grafana for error spikes",
                        "commands": [],
                        "expected_output": "Error rates normal",
                    },
                    {
                        "title": "Update Release Notes",
                        "description": "Publish release notes in admin panel",
                        "commands": [
                            "# Create release notes in admin panel",
                        ],
                        "expected_output": "Release notes published",
                    },
                    {
                        "title": "Notify Team",
                        "description": "Send deployment notification",
                        "commands": [
                            "# Send Slack notification",
                        ],
                        "expected_output": "Team notified",
                    },
                ],
                "expected_duration": timedelta(minutes=30),
                "verification_steps": [
                    {
                        "title": "Verify New Version",
                        "description": "Check version endpoint",
                        "commands": [
                            "curl https://api.example.com/version",
                        ],
                    },
                    {
                        "title": "Test Critical Features",
                        "description": "Manual testing of key features",
                        "commands": [
                            "# Test POS, inventory, sales",
                        ],
                    },
                    {
                        "title": "Monitor for 30 Minutes",
                        "description": "Watch metrics and logs",
                        "commands": [],
                    },
                ],
                "rollback_steps": [
                    {
                        "title": "Rollback Deployment",
                        "description": "Revert to previous version",
                        "commands": [
                            "kubectl rollout undo deployment/web -n production",
                        ],
                    },
                    {
                        "title": "Rollback Migrations (if needed)",
                        "description": "Revert database migrations",
                        "commands": [
                            "kubectl exec -n production web-0 -- python manage.py migrate <app> <migration>",
                        ],
                    },
                ],
                "tags": ["deployment", "production", "release"],
                "status": Runbook.ACTIVE,
            },
        )
        if created:
            self.stdout.write(f"  Created: {runbook.title}")

    def create_troubleshooting_runbooks(self):
        """Create troubleshooting runbooks."""
        self.stdout.write("Creating troubleshooting runbooks...")

        # Slow query troubleshooting
        runbook, created = Runbook.objects.update_or_create(
            slug="troubleshooting-slow-queries",
            defaults={
                "title": "Troubleshooting Slow Database Queries",
                "description": "Identify and optimize slow database queries",
                "runbook_type": Runbook.TROUBLESHOOTING,
                "priority": Runbook.MEDIUM,
                "prerequisites": "- Database admin access\n- Query logs enabled",
                "steps": [
                    {
                        "title": "Enable Query Logging",
                        "description": "Enable slow query logging if not already enabled",
                        "commands": [
                            'docker-compose exec db psql -U postgres -c "ALTER SYSTEM SET log_min_duration_statement = 1000;"',
                            'docker-compose exec db psql -U postgres -c "SELECT pg_reload_conf();"',
                        ],
                        "expected_output": "Slow query logging enabled",
                    },
                    {
                        "title": "Identify Slow Queries",
                        "description": "Find queries taking longer than threshold",
                        "commands": [
                            'docker-compose exec db psql -U postgres -d jewelry_shop -c "SELECT query, mean_exec_time, calls FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;"',
                        ],
                        "expected_output": "List of slowest queries",
                    },
                    {
                        "title": "Analyze Query Plan",
                        "description": "Use EXPLAIN ANALYZE to understand query execution",
                        "commands": [
                            'docker-compose exec db psql -U postgres -d jewelry_shop -c "EXPLAIN ANALYZE <slow_query>;"',
                        ],
                        "expected_output": "Query execution plan",
                    },
                    {
                        "title": "Check for Missing Indexes",
                        "description": "Identify tables that need indexes",
                        "commands": [
                            "docker-compose exec db psql -U postgres -d jewelry_shop -f /scripts/missing_indexes.sql",
                        ],
                        "expected_output": "Missing index recommendations",
                    },
                    {
                        "title": "Create Indexes",
                        "description": "Add indexes to improve query performance",
                        "commands": [
                            'docker-compose exec db psql -U postgres -d jewelry_shop -c "CREATE INDEX CONCURRENTLY idx_name ON table_name(column_name);"',
                        ],
                        "expected_output": "Index created",
                    },
                    {
                        "title": "Update Statistics",
                        "description": "Ensure query planner has current statistics",
                        "commands": [
                            'docker-compose exec db psql -U postgres -d jewelry_shop -c "ANALYZE table_name;"',
                        ],
                        "expected_output": "Statistics updated",
                    },
                    {
                        "title": "Optimize Query",
                        "description": "Rewrite query for better performance",
                        "commands": [
                            "# Add select_related() or prefetch_related() in Django",
                            "# Avoid N+1 queries",
                            "# Use aggregation instead of Python loops",
                        ],
                        "expected_output": "Query optimized",
                    },
                ],
                "expected_duration": timedelta(hours=1),
                "verification_steps": [
                    {
                        "title": "Re-run Query",
                        "description": "Verify query is now fast",
                        "commands": [
                            'docker-compose exec db psql -U postgres -d jewelry_shop -c "EXPLAIN ANALYZE <optimized_query>;"',
                        ],
                    },
                    {
                        "title": "Monitor Query Performance",
                        "description": "Check pg_stat_statements after optimization",
                        "commands": [
                            "docker-compose exec db psql -U postgres -d jewelry_shop -c \"SELECT query, mean_exec_time FROM pg_stat_statements WHERE query LIKE '%<table>%';\"",
                        ],
                    },
                ],
                "rollback_steps": [
                    {
                        "title": "Drop Index (if causing issues)",
                        "description": "Remove index if it degrades write performance",
                        "commands": [
                            'docker-compose exec db psql -U postgres -d jewelry_shop -c "DROP INDEX CONCURRENTLY idx_name;"',
                        ],
                    },
                ],
                "tags": ["troubleshooting", "performance", "database", "queries"],
                "status": Runbook.ACTIVE,
            },
        )
        if created:
            self.stdout.write(f"  Created: {runbook.title}")

        # High memory usage
        runbook, created = Runbook.objects.update_or_create(
            slug="troubleshooting-high-memory-usage",
            defaults={
                "title": "Troubleshooting High Memory Usage",
                "description": "Diagnose and resolve high memory consumption",
                "runbook_type": Runbook.TROUBLESHOOTING,
                "priority": Runbook.HIGH,
                "prerequisites": "- Kubernetes/Docker access\n- Monitoring dashboard access",
                "steps": [
                    {
                        "title": "Check Memory Usage",
                        "description": "Identify which pods/containers are using memory",
                        "commands": [
                            "kubectl top pods -n production",
                            "docker stats",
                        ],
                        "expected_output": "Memory usage by pod/container",
                    },
                    {
                        "title": "Check for Memory Leaks",
                        "description": "Look for continuously increasing memory",
                        "commands": [
                            "# Check Grafana memory graphs over time",
                        ],
                        "expected_output": "Identify memory leak patterns",
                    },
                    {
                        "title": "Review Application Logs",
                        "description": "Check for out-of-memory errors",
                        "commands": [
                            "kubectl logs -n production web-0 --tail=500 | grep -i memory",
                            "docker-compose logs web --tail=500 | grep -i memory",
                        ],
                        "expected_output": "Memory-related errors",
                    },
                    {
                        "title": "Check Celery Queue Size",
                        "description": "Large queues can consume memory",
                        "commands": [
                            "docker-compose exec redis redis-cli LLEN celery",
                        ],
                        "expected_output": "Queue length",
                    },
                    {
                        "title": "Check Database Connection Pool",
                        "description": "Too many connections can use memory",
                        "commands": [
                            'docker-compose exec db psql -U postgres -c "SELECT count(*) FROM pg_stat_activity;"',
                        ],
                        "expected_output": "Active connection count",
                    },
                    {
                        "title": "Restart High-Memory Pods",
                        "description": "Restart pods to free memory",
                        "commands": [
                            "kubectl delete pod -n production web-0",
                            "docker-compose restart web",
                        ],
                        "expected_output": "Pod restarted, memory freed",
                    },
                    {
                        "title": "Increase Memory Limits (if needed)",
                        "description": "Adjust resource limits if legitimate usage",
                        "commands": [
                            "# Update Kubernetes resource limits",
                            "kubectl edit deployment/web -n production",
                        ],
                        "expected_output": "Memory limits increased",
                    },
                    {
                        "title": "Scale Horizontally",
                        "description": "Add more pods to distribute load",
                        "commands": [
                            "kubectl scale deployment/web --replicas=5 -n production",
                        ],
                        "expected_output": "Additional pods running",
                    },
                ],
                "expected_duration": timedelta(minutes=45),
                "verification_steps": [
                    {
                        "title": "Monitor Memory Usage",
                        "description": "Verify memory usage is stable",
                        "commands": [
                            "kubectl top pods -n production",
                        ],
                    },
                    {
                        "title": "Check for OOM Kills",
                        "description": "Verify no pods are being killed",
                        "commands": [
                            "kubectl get events -n production | grep OOM",
                        ],
                    },
                ],
                "rollback_steps": [],
                "tags": ["troubleshooting", "memory", "performance"],
                "status": Runbook.ACTIVE,
            },
        )
        if created:
            self.stdout.write(f"  Created: {runbook.title}")

    def create_backup_restore_runbooks(self):
        """Create backup and restore runbooks."""
        self.stdout.write("Creating backup & restore runbooks...")

        # Manual backup
        runbook, created = Runbook.objects.update_or_create(
            slug="backup-manual-full-backup",
            defaults={
                "title": "Manual Full Database Backup",
                "description": "Trigger a manual full database backup before major changes",
                "runbook_type": Runbook.BACKUP_RESTORE,
                "priority": Runbook.HIGH,
                "prerequisites": "- Backup system configured\n- Storage access\n- Sufficient disk space",
                "steps": [
                    {
                        "title": "Check Disk Space",
                        "description": "Ensure sufficient space for backup",
                        "commands": [
                            "df -h /backups",
                        ],
                        "expected_output": "At least 50GB free space",
                    },
                    {
                        "title": "Trigger Backup",
                        "description": "Start manual backup via admin panel or CLI",
                        "commands": [
                            "docker-compose exec web python manage.py trigger_backup --type=FULL_DATABASE --reason='Pre-deployment backup'",
                        ],
                        "expected_output": "Backup job started",
                    },
                    {
                        "title": "Monitor Backup Progress",
                        "description": "Watch backup job status",
                        "commands": [
                            "docker-compose exec web python manage.py list_backups --limit=1",
                            "docker-compose logs -f celery_worker",
                        ],
                        "expected_output": "Backup in progress",
                    },
                    {
                        "title": "Verify Backup Completion",
                        "description": "Check backup completed successfully",
                        "commands": [
                            "docker-compose exec web python manage.py list_backups --limit=1",
                        ],
                        "expected_output": "Status: COMPLETED",
                    },
                    {
                        "title": "Verify Backup Integrity",
                        "description": "Check backup checksum",
                        "commands": [
                            "docker-compose exec web python manage.py verify_backup --backup-id=<backup_id>",
                        ],
                        "expected_output": "Checksum valid",
                    },
                    {
                        "title": "Verify Cloud Upload",
                        "description": "Confirm backup uploaded to R2 and B2",
                        "commands": [
                            "# Check backup record for r2_path and b2_path",
                        ],
                        "expected_output": "Backup in all three locations",
                    },
                ],
                "expected_duration": timedelta(minutes=30),
                "verification_steps": [
                    {
                        "title": "List Recent Backups",
                        "description": "Verify backup appears in list",
                        "commands": [
                            "docker-compose exec web python manage.py list_backups --limit=5",
                        ],
                    },
                    {
                        "title": "Check Backup Size",
                        "description": "Verify backup size is reasonable",
                        "commands": [
                            "ls -lh /backups/",
                        ],
                    },
                ],
                "rollback_steps": [],
                "tags": ["backup", "database", "manual"],
                "status": Runbook.ACTIVE,
            },
        )
        if created:
            self.stdout.write(f"  Created: {runbook.title}")

        # Tenant restore
        runbook, created = Runbook.objects.update_or_create(
            slug="backup-restore-single-tenant",
            defaults={
                "title": "Restore Single Tenant Data",
                "description": "Restore data for a specific tenant from backup",
                "runbook_type": Runbook.BACKUP_RESTORE,
                "priority": Runbook.HIGH,
                "prerequisites": "- Tenant backup available\n- Tenant ID known\n- Database admin access",
                "steps": [
                    {
                        "title": "Identify Tenant Backup",
                        "description": "Find the backup for the specific tenant",
                        "commands": [
                            "docker-compose exec web python manage.py list_backups --type=TENANT_BACKUP --tenant=<tenant_id>",
                        ],
                        "expected_output": "List of tenant backups",
                    },
                    {
                        "title": "Notify Tenant",
                        "description": "Inform tenant of restore operation",
                        "commands": [
                            "# Send notification via admin panel",
                        ],
                        "expected_output": "Tenant notified",
                    },
                    {
                        "title": "Backup Current Data",
                        "description": "Create backup of current tenant data before restore",
                        "commands": [
                            "docker-compose exec web python manage.py trigger_backup --type=TENANT_BACKUP --tenant=<tenant_id>",
                        ],
                        "expected_output": "Current data backed up",
                    },
                    {
                        "title": "Choose Restore Mode",
                        "description": "Decide between FULL (replace) or MERGE (preserve)",
                        "commands": [
                            "# FULL: Deletes current data and restores from backup",
                            "# MERGE: Adds backup data without deleting current data",
                        ],
                        "expected_output": "Restore mode selected",
                    },
                    {
                        "title": "Trigger Restore",
                        "description": "Start restore operation",
                        "commands": [
                            "docker-compose exec web python manage.py restore_backup --backup-id=<backup_id> --mode=FULL --tenant=<tenant_id>",
                        ],
                        "expected_output": "Restore job started",
                    },
                    {
                        "title": "Monitor Restore Progress",
                        "description": "Watch restore job status",
                        "commands": [
                            "docker-compose logs -f celery_worker",
                        ],
                        "expected_output": "Restore in progress",
                    },
                    {
                        "title": "Verify Data Restored",
                        "description": "Check tenant data is present",
                        "commands": [
                            "docker-compose exec db psql -U postgres -d jewelry_shop -c \"SELECT COUNT(*) FROM inventory_items WHERE tenant_id='<tenant_id>';\"",
                        ],
                        "expected_output": "Data counts match backup",
                    },
                    {
                        "title": "Test Tenant Access",
                        "description": "Verify tenant can login and access data",
                        "commands": [
                            "# Manual login test",
                        ],
                        "expected_output": "Tenant can access system",
                    },
                ],
                "expected_duration": timedelta(minutes=20),
                "verification_steps": [
                    {
                        "title": "Verify Tenant Data",
                        "description": "Spot check tenant records",
                        "commands": [
                            "# Login as tenant and verify data",
                        ],
                    },
                    {
                        "title": "Check Restore Log",
                        "description": "Review restore operation log",
                        "commands": [
                            "# Check BackupRestoreLog in admin panel",
                        ],
                    },
                ],
                "rollback_steps": [
                    {
                        "title": "Restore from Pre-Restore Backup",
                        "description": "Revert to backup taken before restore",
                        "commands": [
                            "# Restore from the backup created in step 3",
                        ],
                    },
                ],
                "tags": ["backup", "restore", "tenant"],
                "status": Runbook.ACTIVE,
            },
        )
        if created:
            self.stdout.write(f"  Created: {runbook.title}")

    def create_admin_notes(self):
        """Create helpful admin notes and tips."""
        self.stdout.write("Creating admin notes and tips...")

        # Database performance tip
        note, created = AdminNote.objects.update_or_create(
            title="Database Connection Pooling Best Practices",
            defaults={
                "content": """When configuring database connection pooling with PgBouncer:

- Set pool_mode to 'transaction' for best performance
- Configure max_client_conn based on expected concurrent users
- Set default_pool_size to match your application's needs
- Monitor connection usage in Grafana dashboard
- Adjust pool sizes during high traffic periods

Recommended settings for production:
- default_pool_size: 25
- max_client_conn: 1000
- pool_mode: transaction
- server_idle_timeout: 600

Remember: More connections != better performance. Find the sweet spot for your workload.""",
                "note_type": AdminNote.BEST_PRACTICE,
                "tags": ["database", "performance", "pgbouncer", "connections"],
                "is_pinned": True,
            },
        )
        if created:
            self.stdout.write(f"  Created note: {note.title}")

        # Backup verification tip
        note, created = AdminNote.objects.update_or_create(
            title="Always Verify Backups Before Major Changes",
            defaults={
                "content": """Before performing any major operation (deployment, migration, schema change):

1. Trigger a manual backup
2. Wait for backup to complete
3. Verify backup integrity with checksum
4. Confirm backup uploaded to all three storage locations (local, R2, B2)
5. Only then proceed with the operation

Use this command:
```
docker-compose exec web python manage.py trigger_backup --type=FULL_DATABASE --reason='Pre-deployment'
```

Then verify:
```
docker-compose exec web python manage.py verify_backup --backup-id=<id>
```

A backup is only good if you can restore from it!""",
                "note_type": AdminNote.BEST_PRACTICE,
                "tags": ["backup", "safety", "deployment"],
                "is_pinned": True,
            },
        )
        if created:
            self.stdout.write(f"  Created note: {note.title}")

        # Monitoring tip
        note, created = AdminNote.objects.update_or_create(
            title="Key Metrics to Monitor Daily",
            defaults={
                "content": """Check these metrics every morning in Grafana:

**Application Health:**
- Error rate (should be < 0.1%)
- Response time p95 (should be < 500ms)
- Request rate trends

**Database:**
- Connection count (should be < 80% of max)
- Query duration p95 (should be < 100ms)
- Replication lag (should be < 1 second)

**Infrastructure:**
- CPU usage (should be < 70%)
- Memory usage (should be < 80%)
- Disk space (should be > 20% free)

**Backups:**
- Last backup time (should be < 24 hours)
- Backup success rate (should be 100%)
- Storage usage trends

Set up alerts for these metrics to catch issues early!""",
                "note_type": AdminNote.TIP,
                "tags": ["monitoring", "grafana", "metrics", "daily"],
                "is_pinned": True,
            },
        )
        if created:
            self.stdout.write(f"  Created note: {note.title}")

        # Security warning
        note, created = AdminNote.objects.update_or_create(
            title="Never Share Database Credentials",
            defaults={
                "content": """⚠️ CRITICAL SECURITY WARNING ⚠️

NEVER share database credentials via:
- Email
- Slack
- Text message
- Unencrypted files

If someone needs database access:
1. Create a dedicated user account with minimal permissions
2. Use strong, unique passwords
3. Enable SSL for connections
4. Rotate credentials quarterly
5. Revoke access when no longer needed

If credentials are compromised:
1. Immediately rotate all passwords
2. Review audit logs for unauthorized access
3. Follow the security breach incident response runbook
4. Notify security team

Remember: Database access = access to ALL tenant data!""",
                "note_type": AdminNote.WARNING,
                "tags": ["security", "database", "credentials", "critical"],
                "is_pinned": True,
            },
        )
        if created:
            self.stdout.write(f"  Created note: {note.title}")

        # Deployment tip
        note, created = AdminNote.objects.update_or_create(
            title="Deployment Checklist",
            defaults={
                "content": """Before every production deployment:

✅ All tests passing in CI/CD
✅ Code review approved
✅ Staging validation complete
✅ Database backup completed
✅ Rollback plan documented
✅ Change window scheduled
✅ Team notified
✅ Monitoring dashboard open

During deployment:
- Watch Grafana for error spikes
- Monitor Sentry for new errors
- Check application logs
- Test critical endpoints

After deployment:
- Monitor for 30 minutes
- Run smoke tests
- Update release notes
- Notify team of completion

If anything looks wrong, rollback immediately!""",
                "note_type": AdminNote.BEST_PRACTICE,
                "tags": ["deployment", "checklist", "production"],
            },
        )
        if created:
            self.stdout.write(f"  Created note: {note.title}")

        # Incident response tip
        note, created = AdminNote.objects.update_or_create(
            title="Incident Response: Stay Calm and Follow the Runbook",
            defaults={
                "content": """When an incident occurs:

1. **Don't Panic** - Take a deep breath
2. **Assess Severity** - Is it critical? High? Medium?
3. **Find the Runbook** - Search documentation for relevant runbook
4. **Follow Steps** - Execute runbook steps in order
5. **Document Everything** - Take notes as you go
6. **Communicate** - Update status page and notify stakeholders
7. **Post-Mortem** - After resolution, document lessons learned

Common incidents and their runbooks:
- Database down → incident-database-outage
- App crashing → incident-application-crash
- Security breach → incident-security-breach
- High load → troubleshooting-high-memory-usage

Remember: Runbooks are tested procedures. Trust the process!""",
                "note_type": AdminNote.TIP,
                "tags": ["incident", "response", "runbook"],
            },
        )
        if created:
            self.stdout.write(f"  Created note: {note.title}")

        # Performance tip
        note, created = AdminNote.objects.update_or_create(
            title="Optimizing Slow Queries",
            defaults={
                "content": """When you encounter slow queries:

1. **Identify the Query**
   - Check pg_stat_statements
   - Look at slow query logs
   - Use Django Debug Toolbar in dev

2. **Analyze Execution Plan**
   ```sql
   EXPLAIN ANALYZE <your_query>;
   ```

3. **Common Issues:**
   - Missing indexes → Add index
   - N+1 queries → Use select_related/prefetch_related
   - Full table scans → Add WHERE clause or index
   - Large result sets → Add pagination

4. **Quick Wins:**
   - Add indexes on foreign keys
   - Add indexes on frequently filtered columns
   - Use database-level aggregation
   - Cache expensive queries

5. **Test the Fix:**
   - Re-run EXPLAIN ANALYZE
   - Check execution time improved
   - Monitor in production

Pro tip: CREATE INDEX CONCURRENTLY to avoid locking tables!""",
                "note_type": AdminNote.TIP,
                "tags": ["performance", "database", "queries", "optimization"],
            },
        )
        if created:
            self.stdout.write(f"  Created note: {note.title}")

        # Lesson learned
        note, created = AdminNote.objects.update_or_create(
            title="Lesson Learned: Always Test Restores",
            defaults={
                "content": """**Incident Date:** 2024-01-15

**What Happened:**
We had a database corruption and needed to restore from backup. The backup file was corrupted and couldn't be restored. We lost 6 hours of data.

**Root Cause:**
We were creating backups but never testing restores. The backup process had a bug that created invalid backup files.

**What We Changed:**
1. Implemented automated monthly test restores
2. Added backup integrity verification (checksums)
3. Store backups in 3 locations (local, R2, B2)
4. Alert on backup failures immediately
5. Document restore procedures in runbooks

**Key Takeaway:**
A backup you can't restore from is worthless. Always test your backups!

**Action Items:**
- Review backup monitoring dashboard weekly
- Verify test restore reports monthly
- Practice disaster recovery procedures quarterly

Don't learn this lesson the hard way like we did!""",
                "note_type": AdminNote.LESSON_LEARNED,
                "tags": ["backup", "restore", "incident", "lesson-learned"],
            },
        )
        if created:
            self.stdout.write(f"  Created note: {note.title}")
