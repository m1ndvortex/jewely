# PgBouncer Authentication Fix

## Problem Identified

PgBouncer was failing with authentication errors:
```
ERROR: cannot do SCRAM authentication: wrong password type
WARNING: pooler error: server login failed: wrong password type
```

## Root Cause

1. **User Mismatch**: PgBouncer was configured to use `jewelry_app` user, but PostgreSQL only had `app_user`
2. **SCRAM-SHA-256 Authentication**: PostgreSQL uses SCRAM-SHA-256 password encryption, which requires special handling in PgBouncer
3. **Missing Userlist**: PgBouncer needs a userlist.txt file with the SCRAM password hash for authentication

## Solution Implemented

### 1. Updated docker-compose.yml

**Changed DATABASE_URL to use correct user:**
```yaml
# Before:
DATABASE_URL: "postgres://${DB_USER:-jewelry_app}:..."

# After:
DATABASE_URL: "postgres://app_user:..."
```

**Added AUTH_TYPE and userlist volume:**
```yaml
environment:
  AUTH_TYPE: scram-sha-256
volumes:
  - ./pgbouncer/userlist.txt:/etc/pgbouncer/userlist.txt:ro
```

**Updated healthcheck to use correct user:**
```yaml
# Before:
psql -h localhost -U ${DB_USER:-jewelry_app} ...

# After:
psql -h localhost -U app_user ...
```

### 2. Created pgbouncer/userlist.txt

Created userlist file with SCRAM-SHA-256 password hash:
```
"app_user" "SCRAM-SHA-256$4096:zBbtu4eo9/cSlPPRRlwWqg==$RfjciXkpv8KAFFqdRhXxLqVJVEi+8OTMaWFVlnnAFsc=:N8RNkFBeqEHKnOp5cIjSwsVShcrz/hJP0oj62wMkCPU="
```

This hash was extracted from PostgreSQL using:
```sql
SELECT concat('"', rolname, '" "', rolpassword, '"') 
FROM pg_authid 
WHERE rolname = 'app_user';
```

## Verification

### 1. PgBouncer Health Status
```bash
$ docker compose ps pgbouncer
STATUS: Up (healthy)
```

### 2. Direct Connection Test
```bash
$ echo "password" | docker compose exec -T pgbouncer psql -h localhost -U app_user -d jewelry_shop -c "SELECT 'PgBouncer works' as status"
     status      
-----------------
 PgBouncer works
```

### 3. Django Application Test
```bash
$ docker compose exec web python manage.py check --database default
System check identified no issues (0 silenced).

$ docker compose exec web python -c "from django.db import connection; ..."
Database connection successful
PostgreSQL version: PostgreSQL 15.14
```

### 4. PgBouncer Logs
No more authentication errors. All connections successful:
```
LOG C-0x...: jewelry_shop/app_user@127.0.0.1:... login attempt: db=jewelry_shop user=app_user tls=no
LOG C-0x...: jewelry_shop/app_user@127.0.0.1:... closing because: client close request
```

## Files Modified

1. **docker-compose.yml**
   - Updated DATABASE_URL to use `app_user`
   - Added `AUTH_TYPE: scram-sha-256`
   - Added volume mount for userlist.txt
   - Updated healthcheck to use `app_user`

2. **pgbouncer/userlist.txt** (new file)
   - Contains SCRAM-SHA-256 password hash for app_user

## Benefits

1. ✅ **Connection Pooling**: PgBouncer now properly pools database connections
2. ✅ **Performance**: Reduced connection overhead for Django application
3. ✅ **Scalability**: Can handle more concurrent connections efficiently
4. ✅ **Health Checks**: PgBouncer health checks now pass
5. ✅ **No Errors**: Clean logs with no authentication failures

## Configuration Details

### PgBouncer Settings
- **Pool Mode**: transaction (optimal for Django)
- **Max Client Connections**: 1000
- **Default Pool Size**: 25
- **Max DB Connections**: 100
- **Server Idle Timeout**: 600s
- **Server Lifetime**: 3600s

### Authentication
- **Method**: SCRAM-SHA-256
- **User**: app_user
- **Database**: jewelry_shop
- **Port**: 6432 (external), 5432 (internal)

## Testing Checklist

- [x] PgBouncer container starts successfully
- [x] PgBouncer health check passes
- [x] Direct connection through PgBouncer works
- [x] Django can connect through PgBouncer
- [x] Django check command passes
- [x] Database queries execute successfully
- [x] No authentication errors in logs
- [x] Web service starts with all dependencies healthy

## Status

✅ **FIXED AND VERIFIED**

PgBouncer is now working perfectly with SCRAM-SHA-256 authentication!
