# Requirements Document

## Introduction

This document specifies the requirements for enhancing the existing Tenant Management System in the Jewelry Shop SaaS Platform. The enhancements expand the current tenant creation form, implement the Activity tab, and add enterprise-grade features for comprehensive tenant administration within the Tenants tab only. This builds upon the existing models (`Tenant`, `TenantSettings`, `User`, `Branch`, `AuditLog`, `LoginAttempt`) and views (`TenantListView`, `TenantDetailView`, `TenantCreateView`, `TenantUpdateView`) in `apps/core/`.

**Important:** This system uses PostgreSQL Row-Level Security (RLS) for tenant data isolation. All features must maintain strict tenant boundaries.

Note: Subscription management is handled separately and is not part of this spec.

## Glossary

- **Tenant**: A jewelry shop business that subscribes to the platform (existing model: `apps.core.models.Tenant`)
- **TenantSettings**: Business configuration for a tenant (existing model: `apps.core.models.TenantSettings`)
- **TenantDomain**: Domain configuration for tenant access (new model to be created)
- **Platform Administrator**: A user with PLATFORM_ADMIN role who manages all tenants (no tenant association)
- **Tenant Owner**: The primary administrator of a tenant account (role: TENANT_OWNER)
- **Tenant Manager**: A user who can manage tenant operations (role: TENANT_MANAGER)
- **Tenant Employee**: A regular user within a tenant (role: TENANT_EMPLOYEE)
- **AuditLog**: Existing audit logging model for tracking actions (existing model: `apps.core.audit_models.AuditLog`)
- **LoginAttempt**: Existing model for tracking login attempts (existing model: `apps.core.audit_models.LoginAttempt`)
- **Custom Domain**: A tenant-owned domain configured to access their shop (e.g., shop.example.com)
- **Subdomain**: A platform-provided subdomain for tenant access (e.g., tenant-slug.jewelry-shop.local)
- **RLS**: Row-Level Security - PostgreSQL feature for tenant data isolation
- **TemporaryPassword**: A time-limited password for user account recovery (new model to be created)

## Requirements

### Requirement 1: Enhanced Tenant Creation Form

**User Story:** As a platform administrator, I want to create new tenants with comprehensive configuration options in a single workflow, so that tenants are fully configured from the start.

#### Acceptance Criteria

1. WHEN a platform administrator accesses the tenant creation page THEN the system SHALL display a multi-section form with collapsible sections for Basic Info, Business Settings, Domain Configuration, and Initial Admin User
2. WHEN creating a tenant THEN the system SHALL require company name, business email, and initial admin user credentials (username, email, password)
3. WHEN creating a tenant THEN the system SHALL allow optional configuration of business name, registration number, tax ID, address, phone, fax, and website
4. WHEN creating a tenant THEN the system SHALL allow setting timezone, currency, and date format preferences from TenantSettings model choices
5. WHEN creating a tenant THEN the system SHALL allow configuring subdomain (auto-generated from slug) and optional custom domain
6. WHEN creating a tenant THEN the system SHALL automatically create TenantSettings with the provided business configuration in a single atomic transaction
7. WHEN creating a tenant THEN the system SHALL create an initial tenant owner user with the specified credentials and associate with the new tenant
8. WHEN creating a tenant THEN the system SHALL validate all inputs including email format, password strength (min 8 chars, 1 uppercase, 1 number, 1 special char), and unique username
9. WHEN a tenant is successfully created THEN the system SHALL display the tenant detail page with a one-time password display modal containing copy button
10. WHEN creating a tenant THEN the system SHALL send a welcome email to the tenant owner with login credentials and verification link
11. WHEN creating a tenant THEN the system SHALL log the creation action in AuditLog with category ADMIN and action TENANT_CREATE

### Requirement 2: Enhanced Tenant Edit Form

**User Story:** As a platform administrator, I want to edit all aspects of a tenant's configuration from the edit page, so that I can modify any tenant setting after creation.

#### Acceptance Criteria

1. WHEN editing a tenant THEN the system SHALL display all configurable fields organized in collapsible sections (Basic Info, Business Settings, Domain, Security)
2. WHEN editing a tenant THEN the system SHALL allow modification of company name, slug, and status
3. WHEN editing a tenant THEN the system SHALL allow modification of all TenantSettings fields including business_name, business_registration_number, tax_identification_number, address fields, contact fields, and localization settings
4. WHEN editing a tenant THEN the system SHALL allow modification of subdomain and custom domain settings via TenantDomain model
5. WHEN editing a tenant THEN the system SHALL display the last modification timestamp (updated_at) and modifier username
6. WHEN saving tenant changes THEN the system SHALL validate all inputs and display specific error messages for invalid data
7. WHEN saving tenant changes THEN the system SHALL log the modification in AuditLog with old_values and new_values JSON fields populated

### Requirement 3: Enhanced Users Tab with Employee Management

**User Story:** As a platform administrator, I want comprehensive user management within the tenant detail Users tab, so that I can fully administer tenant users including creating new employees.

#### Acceptance Criteria

1. WHEN viewing the Users tab THEN the system SHALL display a paginated list with username, email, role, branch (from Branch model), status (is_active), last_login, is_mfa_enabled, and date_joined
2. WHEN viewing the Users tab THEN the system SHALL provide search by username or email and filter by role (TENANT_OWNER, TENANT_MANAGER, TENANT_EMPLOYEE), status (active/inactive), and branch
3. WHEN managing tenant users THEN the system SHALL allow creating new users directly from the Users tab with full form (username, email, password, role, branch FK, phone, language, theme)
4. WHEN creating a new user THEN the system SHALL display a one-time password modal with copy button and warning that password will not be shown again
5. WHEN managing tenant users THEN the system SHALL allow editing user details (email, role, branch, phone, language, theme) inline or via modal
6. WHEN managing tenant users THEN the system SHALL display user login history from LoginAttempt model showing last 10 attempts with ip_address, timestamp, and result
7. WHEN managing tenant users THEN the system SHALL show is_mfa_enabled status and allow forcing MFA enrollment by setting require_mfa flag
8. WHEN managing tenant users THEN the system SHALL prevent deactivation or role change of the last active user with TENANT_OWNER role
9. WHEN managing tenant users THEN the system SHALL allow generating a temporary password via TemporaryPassword model with configurable expiry (1h, 24h, 7d)
10. WHEN managing tenant users THEN the system SHALL allow sending password reset email to any user via Django's password reset mechanism
11. WHEN creating or modifying users THEN the system SHALL log the action in AuditLog with action USER_CREATE or USER_UPDATE

### Requirement 4: Implement Activity Tab with Audit Logs

**User Story:** As a platform administrator, I want to view tenant activity logs in the Activity tab, so that I can audit operations and troubleshoot issues.

#### Acceptance Criteria

1. WHEN viewing the Activity tab THEN the system SHALL display a chronological list of AuditLog entries filtered by tenant FK to the current tenant
2. WHEN viewing the Activity tab THEN the system SHALL show action, user (actor username), timestamp, ip_address, user_agent, and description for each entry
3. WHEN viewing the Activity tab THEN the system SHALL allow filtering by date range (last 24h, 7d, 30d, 90d, custom date picker)
4. WHEN viewing the Activity tab THEN the system SHALL allow filtering by category (ADMIN, USER, DATA, API, SECURITY, SYSTEM from AuditLog.CATEGORY_CHOICES)
5. WHEN viewing the Activity tab THEN the system SHALL allow filtering by actor (specific user from tenant's users or all users)
6. WHEN viewing the Activity tab THEN the system SHALL allow exporting filtered logs to CSV format with all columns including old_values and new_values
7. WHEN viewing the Activity tab THEN the system SHALL paginate results with 50 entries per page and support both pagination and infinite scroll
8. WHEN clicking on an activity entry THEN the system SHALL display a detail modal with full JSON payload of old_values, new_values, and metadata fields

### Requirement 5: Add Settings Tab

**User Story:** As a platform administrator, I want to view and edit tenant settings from a dedicated Settings tab, so that I can manage business configuration separately from basic info.

#### Acceptance Criteria

1. WHEN viewing the Settings tab THEN the system SHALL display all TenantSettings fields organized in sections (Business Info, Contact, Localization, Security, Branding)
2. WHEN viewing the Settings tab THEN the system SHALL allow inline editing of settings with save button per section
3. WHEN editing security settings THEN the system SHALL allow configuring require_mfa_for_managers and password_expiry_days fields
4. WHEN editing localization settings THEN the system SHALL allow setting timezone (with searchable dropdown of pytz timezones), currency (from CURRENCY_CHOICES), and date_format (from DATE_FORMAT_CHOICES)
5. WHEN editing branding settings THEN the system SHALL allow uploading logo (ImageField) and setting primary_color/secondary_color with color picker (hex format validation)
6. WHEN saving settings THEN the system SHALL validate inputs and display success/error toast messages
7. WHEN saving settings THEN the system SHALL log changes in AuditLog with changed fields in old_values and new_values

### Requirement 6: Enhanced Information Tab with Statistics

**User Story:** As a platform administrator, I want to see detailed statistics in the Information tab, so that I can understand tenant usage at a glance.

#### Acceptance Criteria

1. WHEN viewing the Information tab THEN the system SHALL display user statistics (total count, active count where is_active=True, inactive count, breakdown by role)
2. WHEN viewing the Information tab THEN the system SHALL display branch count from Branch model and list of branch names with links to branch detail
3. WHEN viewing the Information tab THEN the system SHALL display storage usage with percentage and visual progress bar (calculated from media files)
4. WHEN viewing the Information tab THEN the system SHALL display last activity timestamp from most recent AuditLog entry and last active user
5. WHEN viewing the Information tab THEN the system SHALL display tenant access URLs (subdomain and custom domain from TenantDomain model) with copy buttons
6. WHEN viewing the Information tab THEN the system SHALL display tenant owner info (username, email, last_login, email verification status)

### Requirement 7: Tenant Credentials and Access Management

**User Story:** As a platform administrator, I want to view tenant admin credentials and connection info, so that I can assist with onboarding and support.

#### Acceptance Criteria

1. WHEN viewing tenant details THEN the system SHALL display the tenant owner username, email, and last_login timestamp
2. WHEN viewing tenant details THEN the system SHALL display the tenant access URLs (subdomain and custom domain from TenantDomain) with copy buttons
3. WHEN a new tenant is created THEN the system SHALL display the initial password in a modal (one-time display with copy button and security warning)
4. WHEN managing tenant users THEN the system SHALL allow generating a temporary password via TemporaryPassword model with expiry (displays in modal with copy button)
5. WHEN generating temporary password THEN the system SHALL log the action in AuditLog with action USER_UPDATE and metadata containing expiry time
6. WHEN viewing tenant details THEN the system SHALL display email verification status for tenant owner (verified/unverified with verification date if verified)

### Requirement 8: Enhanced Tenant List View

**User Story:** As a platform administrator, I want an enhanced tenant list with more columns and actions, so that I can efficiently manage many tenants.

#### Acceptance Criteria

1. WHEN viewing the tenant list THEN the system SHALL display columns for company_name, slug, status, user count (from User model), storage used, created_at, and last activity (from AuditLog)
2. WHEN viewing the tenant list THEN the system SHALL allow sorting by any column (ascending/descending) with visual sort indicators
3. WHEN viewing the tenant list THEN the system SHALL allow bulk selection with checkboxes and select all functionality
4. WHEN tenants are selected THEN the system SHALL allow bulk status change (activate, suspend) with confirmation modal showing affected tenant count
5. WHEN viewing the tenant list THEN the system SHALL display quick action buttons (view detail, edit, impersonate owner, copy access URL)
6. WHEN viewing the tenant list THEN the system SHALL allow exporting filtered list to CSV with all displayed columns

### Requirement 9: Domain Management

**User Story:** As a platform administrator, I want to manage tenant domains and subdomains, so that tenants can access their shops via custom URLs.

#### Acceptance Criteria

1. WHEN creating or editing a tenant THEN the system SHALL auto-generate subdomain from slug in format {slug}.{BASE_DOMAIN} and store in TenantDomain model
2. WHEN creating or editing a tenant THEN the system SHALL allow configuring a custom domain with DNS verification instructions displayed
3. WHEN a custom domain is configured THEN the system SHALL display verification_status (PENDING, VERIFIED, FAILED) from TenantDomain model
4. WHEN a custom domain is configured THEN the system SHALL display required DNS records (CNAME pointing to platform domain, TXT record with verification_token)
5. WHEN viewing tenant details THEN the system SHALL display all configured domains from TenantDomain model with is_primary flag and verification_status

### Requirement 10: Security Monitoring

**User Story:** As a platform administrator, I want to monitor security events for tenants, so that I can identify and respond to suspicious activity.

#### Acceptance Criteria

1. WHEN viewing the Activity tab THEN the system SHALL highlight security events (AuditLog entries with category=SECURITY or action in LOGIN_FAILED, PASSWORD_CHANGE, MFA_ENABLE, MFA_DISABLE)
2. WHEN viewing the Users tab THEN the system SHALL display failed login count in last 24h for each user from LoginAttempt model where result != SUCCESS
3. WHEN a user has more than 5 failed logins in 24h THEN the system SHALL display a warning badge with count
4. WHEN viewing tenant details THEN the system SHALL display security summary (count of users with is_mfa_enabled=True, count of security events in last 7 days)
5. WHEN viewing the Activity tab THEN the system SHALL allow filtering by security events only (category=SECURITY filter preset)

### Requirement 11: Data Isolation and RLS Compliance

**User Story:** As a platform administrator, I want all tenant management operations to maintain strict data isolation, so that tenant data is never exposed to unauthorized parties.

#### Acceptance Criteria

1. WHEN querying tenant users THEN the system SHALL filter by tenant FK to ensure only users belonging to the selected tenant are returned
2. WHEN querying audit logs THEN the system SHALL filter by tenant FK to ensure only logs belonging to the selected tenant are displayed
3. WHEN creating users for a tenant THEN the system SHALL automatically set the tenant FK to the selected tenant
4. WHEN displaying tenant statistics THEN the system SHALL calculate counts using tenant-filtered queries only
5. WHEN performing bulk operations THEN the system SHALL verify each affected record belongs to the expected tenant before modification
6. WHEN exporting data THEN the system SHALL include only data belonging to the selected tenant in the export

### Requirement 12: Impersonation Feature

**User Story:** As a platform administrator, I want to impersonate tenant users for support purposes, so that I can troubleshoot issues from the user's perspective.

#### Acceptance Criteria

1. WHEN viewing tenant users THEN the system SHALL display an impersonate button for each user (except platform admins)
2. WHEN impersonating a user THEN the system SHALL log the action in AuditLog with action IMPERSONATION_START and metadata containing target user
3. WHEN impersonating a user THEN the system SHALL display a visible banner indicating impersonation mode with "End Impersonation" button
4. WHEN ending impersonation THEN the system SHALL log the action in AuditLog with action IMPERSONATION_END
5. WHEN impersonating THEN the system SHALL maintain the original admin session for restoration after impersonation ends
