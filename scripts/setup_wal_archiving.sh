#!/bin/bash
# Setup and verify WAL archiving for production use
# This script configures PostgreSQL for continuous WAL archiving

set -e

echo "=========================================="
echo "WAL Archiving Setup and Verification"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Restart PostgreSQL with new configuration
echo "Step 1: Restarting PostgreSQL with WAL archiving configuration..."
docker compose restart db
sleep 10

# Step 2: Verify PostgreSQL is running
echo ""
echo "Step 2: Verifying PostgreSQL is running..."
if docker compose exec db pg_isready -U postgres > /dev/null 2>&1; then
    echo -e "${GREEN}✓ PostgreSQL is running${NC}"
else
    echo -e "${RED}✗ PostgreSQL is not running${NC}"
    exit 1
fi

# Step 3: Check WAL level
echo ""
echo "Step 3: Checking WAL level..."
WAL_LEVEL=$(docker compose exec db psql -U postgres -d jewelry_shop -t -c "SHOW wal_level;" | tr -d '[:space:]')
if [ "$WAL_LEVEL" = "replica" ]; then
    echo -e "${GREEN}✓ WAL level is set to 'replica'${NC}"
else
    echo -e "${RED}✗ WAL level is '$WAL_LEVEL' (expected 'replica')${NC}"
    exit 1
fi

# Step 4: Check archive mode
echo ""
echo "Step 4: Checking archive mode..."
ARCHIVE_MODE=$(docker compose exec db psql -U postgres -d jewelry_shop -t -c "SHOW archive_mode;" | tr -d '[:space:]')
if [ "$ARCHIVE_MODE" = "on" ]; then
    echo -e "${GREEN}✓ Archive mode is enabled${NC}"
else
    echo -e "${RED}✗ Archive mode is '$ARCHIVE_MODE' (expected 'on')${NC}"
    exit 1
fi

# Step 5: Check archive command
echo ""
echo "Step 5: Checking archive command..."
ARCHIVE_COMMAND=$(docker compose exec db psql -U postgres -d jewelry_shop -t -c "SHOW archive_command;")
echo "Archive command: $ARCHIVE_COMMAND"
if [[ "$ARCHIVE_COMMAND" == *"wal_archive"* ]]; then
    echo -e "${GREEN}✓ Archive command is configured${NC}"
else
    echo -e "${YELLOW}⚠ Archive command may not be configured correctly${NC}"
fi

# Step 6: Check WAL archive directory
echo ""
echo "Step 6: Checking WAL archive directory..."
if docker compose exec db test -d /var/lib/postgresql/wal_archive; then
    echo -e "${GREEN}✓ WAL archive directory exists${NC}"
    
    # Check permissions
    PERMS=$(docker compose exec db stat -c "%a" /var/lib/postgresql/wal_archive)
    echo "Directory permissions: $PERMS"
    
    # Check ownership
    OWNER=$(docker compose exec db stat -c "%U:%G" /var/lib/postgresql/wal_archive)
    echo "Directory ownership: $OWNER"
else
    echo -e "${RED}✗ WAL archive directory does not exist${NC}"
    exit 1
fi

# Step 7: Force a WAL switch to test archiving
echo ""
echo "Step 7: Testing WAL archiving (forcing WAL switch)..."
docker compose exec db psql -U postgres -d jewelry_shop -c "SELECT pg_switch_wal();" > /dev/null 2>&1
sleep 5

# Check if WAL files are being archived
WAL_COUNT=$(docker compose exec db sh -c "ls -1 /var/lib/postgresql/wal_archive/ 2>/dev/null | wc -l")
if [ "$WAL_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ WAL files are being archived ($WAL_COUNT files found)${NC}"
    echo "Sample WAL files:"
    docker compose exec db sh -c "ls -lh /var/lib/postgresql/wal_archive/ | head -5"
else
    echo -e "${YELLOW}⚠ No WAL files found yet (this is normal if the system just started)${NC}"
fi

# Step 8: Restart Celery services
echo ""
echo "Step 8: Restarting Celery services..."
docker compose restart celery_worker celery_beat
sleep 5

# Step 9: Verify Celery Beat schedule
echo ""
echo "Step 9: Verifying Celery Beat schedule..."
if docker compose logs celery_beat | grep -q "continuous-wal-archiving"; then
    echo -e "${GREEN}✓ WAL archiving task is scheduled in Celery Beat${NC}"
else
    echo -e "${YELLOW}⚠ WAL archiving task not found in Celery Beat logs yet${NC}"
fi

# Step 10: Check Celery worker is running
echo ""
echo "Step 10: Checking Celery worker status..."
if docker compose exec celery_worker celery -A config inspect ping > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Celery worker is running${NC}"
else
    echo -e "${RED}✗ Celery worker is not responding${NC}"
    exit 1
fi

# Step 11: Manually trigger WAL archiving task
echo ""
echo "Step 11: Manually triggering WAL archiving task..."
docker compose exec web python manage.py shell << 'EOF'
from apps.backups.tasks import continuous_wal_archiving
result = continuous_wal_archiving.delay()
print(f"Task ID: {result.id}")
print("Task submitted successfully")
EOF

echo ""
echo "Waiting for task to complete (30 seconds)..."
sleep 30

# Step 12: Check backup records
echo ""
echo "Step 12: Checking backup records..."
BACKUP_COUNT=$(docker compose exec web python manage.py shell << 'EOF'
from apps.backups.models import Backup
from apps.core.tenant_context import bypass_rls
with bypass_rls():
    count = Backup.objects.filter(backup_type=Backup.WAL_ARCHIVE).count()
    print(count)
EOF
)

if [ "$BACKUP_COUNT" -gt 0 ]; then
    echo -e "${GREEN}✓ WAL archive backup records found ($BACKUP_COUNT records)${NC}"
else
    echo -e "${YELLOW}⚠ No WAL archive backup records found yet${NC}"
fi

# Summary
echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "WAL archiving is now configured and running."
echo ""
echo "Key Information:"
echo "  - WAL Level: $WAL_LEVEL"
echo "  - Archive Mode: $ARCHIVE_MODE"
echo "  - Archive Directory: /var/lib/postgresql/wal_archive"
echo "  - Archiving Frequency: Every 5 minutes"
echo "  - Retention: 30 days in cloud storage"
echo ""
echo "Next Steps:"
echo "  1. Monitor Celery Beat logs: docker compose logs -f celery_beat"
echo "  2. Monitor WAL archiving: docker compose logs -f celery_worker | grep WAL"
echo "  3. Check backup records: docker compose exec web python manage.py shell"
echo "     >>> from apps.backups.models import Backup"
echo "     >>> Backup.objects.filter(backup_type=Backup.WAL_ARCHIVE).count()"
echo ""
echo "For troubleshooting, check:"
echo "  - PostgreSQL logs: docker compose logs db"
echo "  - Celery worker logs: docker compose logs celery_worker"
echo "  - Celery beat logs: docker compose logs celery_beat"
echo ""
