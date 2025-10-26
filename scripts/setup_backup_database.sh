#!/bin/bash
#
# Setup script for configuring database for backup operations
#
# This script grants the necessary privileges to the postgres user
# to perform backups without being affected by Row-Level Security (RLS) policies.
#
# Usage:
#   ./scripts/setup_backup_database.sh
#
# Or via Docker:
#   docker compose exec db psql -U postgres -d jewelry_shop -f /path/to/this/script.sql
#

set -e

echo "=========================================="
echo "Setting up database for backup operations"
echo "=========================================="

# Grant BYPASSRLS privilege to postgres user
echo "Granting BYPASSRLS privilege to postgres user..."
docker compose exec db psql -U postgres -d jewelry_shop -c "ALTER USER postgres WITH BYPASSRLS;"

echo "✓ BYPASSRLS privilege granted"

# Verify the privilege
echo "Verifying privilege..."
docker compose exec db psql -U postgres -d jewelry_shop -c "SELECT rolname, rolbypassrls FROM pg_roles WHERE rolname = 'postgres';"

echo ""
echo "=========================================="
echo "Database setup complete!"
echo "=========================================="
echo ""
echo "The postgres user can now perform backups without being affected by RLS policies."
echo "This is required for pg_dump to export all tenant data."
