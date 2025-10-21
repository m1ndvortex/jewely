# Multi-Factor Authentication (MFA) Implementation

## Overview

This document describes the complete Multi-Factor Authentication (MFA) implementation for the Jewelry Shop SaaS platform, satisfying Requirements 18.7 and 25.7.

## Requirements Satisfied

### Requirement 18.7
**"THE System SHALL support multi-factor authentication for enhanced security"**

The system provides optional MFA for all users using TOTP (Time-based One-Time Password) authentication.

### Requirement 25.7
**"THE System SHALL require multi-factor authentication for admin users"**

Platform administrators are required to enable MFA for accessing sensitive operations.

## Architecture

### Components

1. **django-otp**: Core MFA library providing TOTP device management
2. **qrcode**: QR code generation for authenticator app setup
3. **Custom Login Flow**: Modified JWT authentication to support MFA verification
4. **MFA Management Views**: API endpoints for enabling, disabling, and verifying MFA
5. **Admin Enforcement**: Decorators and checks to enforce MFA for platform admins

### Database Models

#### TOTPDevice (from django-otp)
- `user`: Foreign key to User model
- `name`: Device name (default: "default")
- `key`: Secret key for TOTP generation (hex format)
- `confirmed`: Boolean indicating if device is confirmed
- `created_at`: Timestamp of device creation

#### User Model Extensions
- `is_mfa_enabled`: Boolean field indicating if MFA is active
- `requires_mfa()`: Method to check if user must have MFA enabled

## API Endpoints

### 1. Check MFA Status
```
GET /api/mfa/status/
```

**Authentication**: Required

**Response**:
```json
{
  "is_mfa_enabled": false,
  "has_device": false
}
```

### 2. Enable MFA
```
POST /api/mfa/enable/
```

**Authentication**: Required

**Response**:
```json
{
  "detail": "MFA device created. Scan the QR code with your authenticator app.",
  "qr_code_url": "otpauth://totp/Jewelry%20Shop%20SaaS:username?secret=ABCD1234&issuer=Jewelry%20Shop%20SaaS",
  "secret": "abcd1234567890abcdef"
}
```

**Notes**:
- Returns a QR code URL that can be scanned with Google Authenticator, Authy, or similar apps
- The secret key is also provided for manual entry
- Device is created in unconfirmed state

### 3. Confirm MFA Setup
```
POST /api/mfa/confirm/
```

**Authentication**: Required

**Request Body**:
```json
{
  "token": "123456"
}
```

**Response**:
```json
{
  "detail": "MFA enabled successfully."
}
```

**Notes**:
- Verifies the TOTP token from the authenticator app
- Confirms the device and sets `is_mfa_enabled=True` on the user
- Token must be valid (6-digit code from authenticator app)

### 4. Disable MFA
```
POST /api/mfa/disable/
```

**Authentication**: Required

**Request Body**:
```json
{
  "password": "user_password"
}
```

**Response**:
```json
{
  "detail": "MFA disabled successfully."
}
```

**Notes**:
- Requires password verification for security
- Deletes all TOTP devices for the user
- Sets `is_mfa_enabled=False` on the user

### 5. Verify MFA Token
```
POST /api/mfa/verify/
```

**Authentication**: Required

**Request Body**:
```json
{
  "token": "123456"
}
```

**Response**:
```json
{
  "detail": "Token verified successfully."
}
```

**Notes**:
- Used during login flow to verify MFA token
- Can also be used for re-authentication before sensitive operations

## Login Flow with MFA

### Standard Login (No MFA)

```
POST /api/auth/login/
{
  "username": "user@example.com",
  "password": "password123"
}

Response:
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "uuid",
    "username": "user",
    "is_mfa_enabled": false
  },
  "mfa_required": false
}
```

### Login with MFA Enabled (Step 1)

```
POST /api/auth/login/
{
  "username": "user@example.com",
  "password": "password123"
}

Response:
{
  "mfa_required": true,
  "user_id": "uuid",
  "message": "MFA verification required. Please provide your authentication code."
}
```

**Note**: No access or refresh tokens are returned. Client must proceed to step 2.

### Login with MFA Enabled (Step 2)

```
POST /api/auth/login/
{
  "username": "user@example.com",
  "password": "password123",
  "mfa_token": "123456"
}

Response:
{
  "access": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": "uuid",
    "username": "user",
    "is_mfa_enabled": true
  },
  "mfa_required": false
}
```

## Client Implementation Guide

### React/JavaScript Example

```javascript
async function login(username, password, mfaToken = null) {
  const response = await fetch('/api/auth/login/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username,
      password,
      ...(mfaToken && { mfa_token: mfaToken })
    })
  });
  
  const data = await response.json();
  
  if (data.mfa_required) {
    // Show MFA input form
    const token = await promptForMFAToken();
    return login(username, password, token);
  }
  
  // Store tokens and proceed
  localStorage.setItem('access_token', data.access);
  localStorage.setItem('refresh_token', data.refresh);
  return data.user;
}
```

### Python/CLI Example

```python
import requests

def login(username, password):
    response = requests.post('http://localhost:8000/api/auth/login/', json={
        'username': username,
        'password': password
    })
    data = response.json()
    
    if data.get('mfa_required'):
        mfa_token = input('Enter MFA code: ')
        response = requests.post('http://localhost:8000/api/auth/login/', json={
            'username': username,
            'password': password,
            'mfa_token': mfa_token
        })
        data = response.json()
    
    return data['access'], data['refresh']
```

## Admin MFA Enforcement

### Requirement

Per Requirement 25.7, all platform administrators MUST enable MFA.

### Implementation

1. **User Model Method**: `requires_mfa()` returns `True` for platform admins
2. **Decorators**: `@mfa_required` and `@mfa_required_for_class_view` enforce MFA
3. **Management Command**: `check_admin_mfa` reports admins without MFA

### Usage Example

```python
from apps.core.decorators import mfa_required_for_class_view
from rest_framework.views import APIView

class SensitiveAdminView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformAdmin]
    
    @mfa_required_for_class_view
    def post(self, request):
        # This endpoint requires MFA for platform admins
        # Regular users can access without MFA
        return Response({"status": "success"})
```

### Checking Admin MFA Compliance

```bash
# Run inside Docker container
docker compose exec web python manage.py check_admin_mfa

# Output:
Total Platform Administrators: 5
Admins with MFA enabled: 3
Admins without MFA: 2

⚠️  WARNING: The following platform administrators do not have MFA enabled:
  - admin1 (admin1@example.com)
  - admin2 (admin2@example.com)

⚠️  Security Requirement: All platform administrators MUST enable MFA.
   Admins without MFA will have restricted access to sensitive operations.
```

## Security Considerations

### TOTP Algorithm
- Uses HMAC-SHA1 algorithm (RFC 6238)
- 30-second time step
- 6-digit codes
- Tolerates ±1 time step for clock drift

### Secret Key Storage
- Keys stored in hex format in database
- Converted to base32 for QR code generation
- Keys are cryptographically random (generated by django-otp)

### Token Verification
- Tokens are single-use within the time window
- django-otp handles replay attack prevention
- Failed attempts are logged

### Password Protection
- MFA disable requires password verification
- Prevents unauthorized MFA removal if session is compromised

## Testing

### Running MFA Tests

```bash
# Run all authentication tests
docker compose exec web pytest tests/test_authentication.py -v

# Run only MFA tests
docker compose exec web pytest tests/test_authentication.py::TestMultiFactorAuthentication -v

# Run admin MFA enforcement tests
docker compose exec web pytest tests/test_authentication.py::TestAdminMFAEnforcement -v
```

### Test Coverage

The implementation includes comprehensive tests for:
- MFA status checking
- MFA device creation and QR code generation
- MFA confirmation with valid/invalid tokens
- MFA disable with password verification
- Login flow without MFA
- Login flow with MFA (two-step process)
- Login with invalid MFA token
- Admin MFA requirement checking
- Admin login with and without MFA

All 34 authentication tests pass successfully.

## Troubleshooting

### Issue: QR Code Not Scanning

**Solution**: Ensure the QR code URL is properly formatted. The URL should be:
```
otpauth://totp/Jewelry%20Shop%20SaaS:username?secret=SECRET&issuer=Jewelry%20Shop%20SaaS
```

### Issue: Token Always Invalid

**Possible Causes**:
1. Server time is incorrect (TOTP is time-based)
2. User's device time is incorrect
3. Secret key mismatch

**Solution**:
```bash
# Check server time
docker compose exec web date

# Verify time synchronization
docker compose exec web ntpdate -q pool.ntp.org
```

### Issue: MFA Required But No Device Found

**Solution**: User needs to re-enable MFA:
1. Admin can reset MFA for the user
2. User can contact support
3. Use backup codes (if implemented)

## Future Enhancements

### Planned Features
1. **Backup Codes**: Generate one-time backup codes for account recovery
2. **SMS MFA**: Alternative to TOTP using SMS codes
3. **WebAuthn/FIDO2**: Hardware security key support
4. **Remember Device**: Option to skip MFA for trusted devices (30 days)
5. **MFA Recovery**: Self-service MFA reset with email verification

### Configuration Options
```python
# config/settings.py

# MFA Settings
MFA_REQUIRED_FOR_ADMINS = True  # Enforce MFA for platform admins
MFA_TOKEN_VALIDITY = 30  # TOTP time step in seconds
MFA_ISSUER_NAME = "Jewelry Shop SaaS"  # Displayed in authenticator apps
MFA_REMEMBER_DEVICE_DAYS = 30  # Days to remember trusted devices
```

## References

- [RFC 6238 - TOTP Algorithm](https://tools.ietf.org/html/rfc6238)
- [django-otp Documentation](https://django-otp-official.readthedocs.io/)
- [OWASP MFA Guidelines](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html)
- [NIST SP 800-63B - Digital Identity Guidelines](https://pages.nist.gov/800-63-3/sp800-63b.html)
