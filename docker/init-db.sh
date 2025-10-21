#!/bin/bash
set -e

# This script initializes the PostgreSQL database for the jewelry shop SaaS platform
# It creates a non-superuser role for the application to use with RLS

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
-- Create application user (non-superuser) for RLS to work properly
-- Superusers bypass RLS even with FORCE ROW LEVEL SECURITY
DO \$\$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user WITH LOGIN PASSWORD '${APP_DB_PASSWORD:-app_password_change_in_production}';
    END IF;
END
\$\$;

-- Grant necessary privileges
GRANT ALL PRIVILEGES ON DATABASE ${POSTGRES_DB} TO app_user;
GRANT ALL PRIVILEGES ON SCHEMA public TO app_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO app_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO app_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO app_user;

-- Set default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO app_user;

-- Ensure app_user does not bypass RLS
ALTER ROLE app_user NOBYPASSRLS;
EOSQL

echo "Database initialization complete. Application user 'app_user' created."
