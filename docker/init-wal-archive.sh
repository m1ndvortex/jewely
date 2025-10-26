#!/bin/bash
# Initialize WAL archive directory for PostgreSQL
# This script runs as part of PostgreSQL container initialization

set -e

# Create WAL archive directory if it doesn't exist
WAL_ARCHIVE_DIR="/var/lib/postgresql/wal_archive"

if [ ! -d "$WAL_ARCHIVE_DIR" ]; then
    echo "Creating WAL archive directory: $WAL_ARCHIVE_DIR"
    mkdir -p "$WAL_ARCHIVE_DIR"
fi

# Set proper ownership and permissions
# PostgreSQL runs as user 'postgres' (UID 70 in Alpine)
chown -R postgres:postgres "$WAL_ARCHIVE_DIR"
chmod 700 "$WAL_ARCHIVE_DIR"

echo "WAL archive directory initialized successfully"
echo "Directory: $WAL_ARCHIVE_DIR"
echo "Permissions: $(ls -ld $WAL_ARCHIVE_DIR)"
