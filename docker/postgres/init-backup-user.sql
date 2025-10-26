-- Initialize PostgreSQL for backup operations
-- This script grants the necessary privileges for pg_dump to work with RLS

-- Grant BYPASSRLS privilege to postgres user
-- This allows pg_dump to export all data without being affected by RLS policies
ALTER USER postgres WITH BYPASSRLS;

-- Verify the privilege was granted
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles 
        WHERE rolname = 'postgres' AND rolbypassrls = true
    ) THEN
        RAISE EXCEPTION 'Failed to grant BYPASSRLS privilege to postgres user';
    END IF;
    
    RAISE NOTICE 'BYPASSRLS privilege granted to postgres user successfully';
END $$;
