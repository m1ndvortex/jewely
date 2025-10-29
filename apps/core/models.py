"""
Core models for the jewelry shop SaaS platform.
"""

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.text import slugify

# Import alert models to register them with Django
from apps.core.alert_models import AlertDeliveryLog, AlertRule, MonitoringAlert  # noqa: F401

# Import audit models to register them with Django
from apps.core.audit_models import (  # noqa: F401
    APIRequestLog,
    AuditLog,
    DataChangeLog,
    LoginAttempt,
)

# Import documentation models to register them with Django
from apps.core.documentation_models import (  # noqa: F401
    AdminNote,
    DocumentationPage,
    Runbook,
    RunbookExecution,
)

# Import feature flag models to register them with Django
from apps.core.feature_flags import (  # noqa: F401
    ABTestVariant,
    EmergencyKillSwitch,
    FeatureFlagHistory,
    FeatureFlagMetric,
    TenantFeatureFlag,
)

# Import integration models to register them with Django
from apps.core.integration_models import (  # noqa: F401
    ExternalService,
    IntegrationHealthCheck,
    IntegrationLog,
    OAuth2Token,
)

# Import job monitoring models to register them with Django
from apps.core.job_models import JobExecution, JobStatistics  # noqa: F401

# Import webhook models to register them with Django
from apps.core.webhook_models import Webhook, WebhookDelivery  # noqa: F401


class Tenant(models.Model):
    """
    Core tenant model for multi-tenancy.

    Each tenant represents a jewelry shop business that subscribes to the platform.
    Data isolation is enforced at the database level using PostgreSQL Row-Level Security (RLS).
    """

    # Status choices
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    PENDING_DELETION = "PENDING_DELETION"

    STATUS_CHOICES = [
        (ACTIVE, "Active"),
        (SUSPENDED, "Suspended"),
        (PENDING_DELETION, "Pending Deletion"),
    ]

    # Primary key as UUID for security and scalability
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the tenant",
    )

    # Company information
    company_name = models.CharField(max_length=255, help_text="Name of the jewelry shop business")

    slug = models.SlugField(
        unique=True, max_length=255, help_text="URL-friendly identifier for the tenant"
    )

    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=ACTIVE,
        help_text="Current operational status of the tenant",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Timestamp when the tenant was created"
    )

    updated_at = models.DateTimeField(
        auto_now=True, help_text="Timestamp when the tenant was last updated"
    )

    # Status management fields
    suspended_at = models.DateTimeField(
        null=True, blank=True, help_text="Timestamp when the tenant was suspended"
    )

    scheduled_deletion_at = models.DateTimeField(
        null=True, blank=True, help_text="Timestamp when the tenant is scheduled for deletion"
    )

    deletion_grace_period_days = models.IntegerField(
        default=30, help_text="Number of days before permanent deletion after scheduling"
    )

    class Meta:
        db_table = "tenants"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="tenant_status_idx"),
            models.Index(fields=["slug"], name="tenant_slug_idx"),
        ]
        verbose_name = "Tenant"
        verbose_name_plural = "Tenants"

    def __str__(self):
        return f"{self.company_name} ({self.status})"

    def save(self, *args, **kwargs):
        """
        Override save to auto-generate slug from company_name if not provided.
        """
        if not self.slug:
            self.slug = slugify(self.company_name)
            # Ensure uniqueness by appending UUID if slug already exists
            if Tenant.objects.filter(slug=self.slug).exists():
                self.slug = f"{self.slug}-{str(uuid.uuid4())[:8]}"
        super().save(*args, **kwargs)

    def is_active(self):
        """Check if tenant is in active status."""
        return self.status == self.ACTIVE

    def is_suspended(self):
        """Check if tenant is suspended."""
        return self.status == self.SUSPENDED

    def is_pending_deletion(self):
        """Check if tenant is pending deletion."""
        return self.status == self.PENDING_DELETION

    def suspend(self, reason=None):
        """
        Suspend the tenant account.

        This disables access for all tenant users while retaining all data.
        The tenant can be reactivated later.

        Args:
            reason: Optional reason for suspension (for audit logging)
        """
        from django.utils import timezone

        self.status = self.SUSPENDED
        self.suspended_at = timezone.now()
        self.save(update_fields=["status", "suspended_at", "updated_at"])

    def activate(self):
        """
        Activate the tenant account.

        This reactivates a suspended or pending deletion tenant,
        restoring full access.
        """
        self.status = self.ACTIVE
        self.suspended_at = None
        self.scheduled_deletion_at = None
        self.save(update_fields=["status", "suspended_at", "scheduled_deletion_at", "updated_at"])

    def schedule_for_deletion(self, grace_period_days=None):
        """
        Schedule the tenant for deletion with a grace period.

        During the grace period, the tenant is suspended but data is retained.
        After the grace period expires, the tenant can be permanently deleted.

        Args:
            grace_period_days: Number of days before deletion (default: 30)
        """
        from datetime import timedelta

        from django.utils import timezone

        if grace_period_days is not None:
            self.deletion_grace_period_days = grace_period_days

        self.status = self.PENDING_DELETION
        self.scheduled_deletion_at = timezone.now() + timedelta(
            days=self.deletion_grace_period_days
        )
        self.save(
            update_fields=[
                "status",
                "scheduled_deletion_at",
                "deletion_grace_period_days",
                "updated_at",
            ]
        )

    def cancel_deletion(self):
        """
        Cancel scheduled deletion and reactivate the tenant.

        This is an alias for activate() for clarity.
        """
        self.activate()

    def get_deletion_date(self):
        """Get the date when the tenant will be permanently deleted."""
        return self.scheduled_deletion_at

    def days_until_deletion(self):
        """Get the number of days remaining until permanent deletion."""
        if not self.scheduled_deletion_at:
            return None

        from django.utils import timezone

        delta = self.scheduled_deletion_at - timezone.now()
        return max(0, delta.days)

    def mark_for_deletion(self):
        """Mark tenant for deletion."""
        self.status = self.PENDING_DELETION
        self.save(update_fields=["status", "updated_at"])


class Branch(models.Model):
    """
    Branch model for multi-branch jewelry shops.

    Each tenant can have multiple branches/locations.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the branch",
    )

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="branches",
        help_text="Tenant that owns this branch",
    )

    name = models.CharField(max_length=255, help_text="Branch name")

    address = models.TextField(blank=True, help_text="Branch address")

    phone = models.CharField(max_length=20, blank=True, help_text="Branch phone number")

    manager = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="managed_branches",
        help_text="Branch manager (must be a user from the same tenant)",
    )

    opening_hours = models.JSONField(
        default=dict,
        blank=True,
        help_text="Branch opening hours (e.g., {'monday': '9:00-18:00', 'tuesday': '9:00-18:00', ...})",
    )

    is_active = models.BooleanField(default=True, help_text="Whether the branch is active")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "branches"
        ordering = ["name"]
        verbose_name = "Branch"
        verbose_name_plural = "Branches"
        unique_together = [["tenant", "name"]]
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="branch_tenant_active_idx"),
        ]

    def __str__(self):
        return f"{self.name} ({self.tenant.company_name})"


class User(AbstractUser):
    """
    Extended user model with tenant association and additional fields.

    Supports multi-tenancy with role-based access control.
    """

    # Role choices
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    TENANT_OWNER = "TENANT_OWNER"
    TENANT_MANAGER = "TENANT_MANAGER"
    TENANT_EMPLOYEE = "TENANT_EMPLOYEE"

    ROLE_CHOICES = [
        (PLATFORM_ADMIN, "Platform Administrator"),
        (TENANT_OWNER, "Shop Owner"),
        (TENANT_MANAGER, "Shop Manager"),
        (TENANT_EMPLOYEE, "Shop Employee"),
    ]

    # Language choices
    LANGUAGE_ENGLISH = "en"
    LANGUAGE_PERSIAN = "fa"

    LANGUAGE_CHOICES = [
        (LANGUAGE_ENGLISH, "English"),
        (LANGUAGE_PERSIAN, "Persian"),
    ]

    # Theme choices
    THEME_LIGHT = "light"
    THEME_DARK = "dark"

    THEME_CHOICES = [
        (THEME_LIGHT, "Light"),
        (THEME_DARK, "Dark"),
    ]

    # Tenant association
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users",
        help_text="Tenant that this user belongs to (null for platform admins)",
    )

    # Role
    role = models.CharField(
        max_length=50,
        choices=ROLE_CHOICES,
        default=TENANT_EMPLOYEE,
        help_text="User's role in the system",
    )

    # Branch assignment
    branch = models.ForeignKey(
        Branch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users",
        help_text="Branch that this user is assigned to",
    )

    # Preferences
    language = models.CharField(
        max_length=10,
        choices=LANGUAGE_CHOICES,
        default=LANGUAGE_ENGLISH,
        help_text="User's preferred language",
    )

    theme = models.CharField(
        max_length=10,
        choices=THEME_CHOICES,
        default=THEME_LIGHT,
        help_text="User's preferred theme",
    )

    # Contact information
    phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="User's phone number",
    )

    # Security
    is_mfa_enabled = models.BooleanField(
        default=False,
        help_text="Whether multi-factor authentication is enabled for this user",
    )

    class Meta:
        db_table = "users"
        ordering = ["username"]
        verbose_name = "User"
        verbose_name_plural = "Users"
        indexes = [
            models.Index(fields=["tenant", "role"], name="user_tenant_role_idx"),
            models.Index(fields=["tenant", "branch"], name="user_tenant_branch_idx"),
        ]

    def __str__(self):
        if self.tenant:
            return f"{self.username} ({self.get_role_display()} - {self.tenant.company_name})"
        return f"{self.username} ({self.get_role_display()})"

    def is_platform_admin(self):
        """Check if user is a platform administrator."""
        return self.role == self.PLATFORM_ADMIN

    def is_tenant_owner(self):
        """Check if user is a tenant owner."""
        return self.role == self.TENANT_OWNER

    def is_tenant_manager(self):
        """Check if user is a tenant manager."""
        return self.role == self.TENANT_MANAGER

    def is_tenant_employee(self):
        """Check if user is a tenant employee."""
        return self.role == self.TENANT_EMPLOYEE

    def has_tenant_access(self):
        """Check if user has access to tenant features."""
        return self.tenant is not None and self.role in [
            self.TENANT_OWNER,
            self.TENANT_MANAGER,
            self.TENANT_EMPLOYEE,
        ]

    def can_manage_users(self):
        """Check if user can manage other users."""
        return self.role in [self.PLATFORM_ADMIN, self.TENANT_OWNER, self.TENANT_MANAGER]

    def can_manage_inventory(self):
        """Check if user can manage inventory."""
        return self.role in [self.TENANT_OWNER, self.TENANT_MANAGER]

    def can_process_sales(self):
        """Check if user can process sales."""
        return self.has_tenant_access()

    def requires_mfa(self):
        """
        Check if user is required to have MFA enabled.
        Platform admins must have MFA enabled per security requirements.
        """
        return self.role == self.PLATFORM_ADMIN

    def save(self, *args, **kwargs):
        """
        Override save to ensure data consistency.
        """
        # Platform admins should not have a tenant
        if self.role == self.PLATFORM_ADMIN:
            self.tenant = None
            self.branch = None

        # Tenant users must have a tenant
        if self.role in [self.TENANT_OWNER, self.TENANT_MANAGER, self.TENANT_EMPLOYEE]:
            if not self.tenant_id:
                raise ValueError(f"Users with role {self.role} must have a tenant assigned")

        # Branch must belong to the same tenant
        if self.branch_id and self.tenant_id:
            # Use _id fields to avoid triggering database queries
            if hasattr(self.branch, "tenant_id"):
                branch_tenant_id = self.branch.tenant_id
            else:
                # If branch is not loaded, fetch just the tenant_id
                branch_tenant_id = (
                    Branch.objects.filter(id=self.branch_id)
                    .values_list("tenant_id", flat=True)
                    .first()
                )

            if branch_tenant_id != self.tenant_id:
                raise ValueError("Branch must belong to the same tenant as the user")

        super().save(*args, **kwargs)


class PermissionAuditLog(models.Model):
    """
    Audit log for permission and role changes.

    Tracks all changes to user permissions, roles, and group assignments
    for security and compliance purposes per Requirement 18.9.
    """

    # Action types
    ROLE_CHANGED = "ROLE_CHANGED"
    PERMISSION_GRANTED = "PERMISSION_GRANTED"
    PERMISSION_REVOKED = "PERMISSION_REVOKED"
    GROUP_ADDED = "GROUP_ADDED"
    GROUP_REMOVED = "GROUP_REMOVED"
    BRANCH_ASSIGNED = "BRANCH_ASSIGNED"
    BRANCH_UNASSIGNED = "BRANCH_UNASSIGNED"

    ACTION_CHOICES = [
        (ROLE_CHANGED, "Role Changed"),
        (PERMISSION_GRANTED, "Permission Granted"),
        (PERMISSION_REVOKED, "Permission Revoked"),
        (GROUP_ADDED, "Group Added"),
        (GROUP_REMOVED, "Group Removed"),
        (BRANCH_ASSIGNED, "Branch Assigned"),
        (BRANCH_UNASSIGNED, "Branch Unassigned"),
    ]

    # Who performed the action
    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="permission_actions_performed",
        help_text="User who performed the action",
    )

    # Who was affected
    target_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="permission_changes",
        help_text="User whose permissions were changed",
    )

    # What happened
    action = models.CharField(
        max_length=50,
        choices=ACTION_CHOICES,
        help_text="Type of permission change",
    )

    # Details
    old_value = models.TextField(
        blank=True,
        help_text="Previous value (JSON format)",
    )

    new_value = models.TextField(
        blank=True,
        help_text="New value (JSON format)",
    )

    description = models.TextField(
        help_text="Human-readable description of the change",
    )

    # Metadata
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the actor",
    )

    user_agent = models.TextField(
        blank=True,
        help_text="User agent string of the actor",
    )

    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the change occurred",
    )

    class Meta:
        db_table = "permission_audit_logs"
        ordering = ["-timestamp"]
        verbose_name = "Permission Audit Log"
        verbose_name_plural = "Permission Audit Logs"
        indexes = [
            models.Index(fields=["target_user", "-timestamp"], name="audit_user_time_idx"),
            models.Index(fields=["actor", "-timestamp"], name="audit_actor_time_idx"),
            models.Index(fields=["action", "-timestamp"], name="audit_action_time_idx"),
        ]

    def __str__(self):
        actor_name = self.actor.username if self.actor else "System"
        return f"{self.action} - {self.target_user.username} by {actor_name} at {self.timestamp}"


class TenantSettings(models.Model):
    """
    Tenant-specific business settings and configuration.

    Stores business information, branding, operating hours, and holiday calendar
    per Requirement 20.1, 20.6, and 20.7.
    """

    # Currency choices
    CURRENCY_USD = "USD"
    CURRENCY_EUR = "EUR"
    CURRENCY_GBP = "GBP"
    CURRENCY_IRR = "IRR"  # Iranian Rial
    CURRENCY_AED = "AED"  # UAE Dirham

    CURRENCY_CHOICES = [
        (CURRENCY_USD, "US Dollar ($)"),
        (CURRENCY_EUR, "Euro (€)"),
        (CURRENCY_GBP, "British Pound (£)"),
        (CURRENCY_IRR, "Iranian Rial (﷼)"),
        (CURRENCY_AED, "UAE Dirham (د.إ)"),
    ]

    # Date format choices
    DATE_FORMAT_MDY = "MM/DD/YYYY"
    DATE_FORMAT_DMY = "DD/MM/YYYY"
    DATE_FORMAT_YMD = "YYYY-MM-DD"
    DATE_FORMAT_JALALI = "YYYY/MM/DD"  # Persian calendar

    DATE_FORMAT_CHOICES = [
        (DATE_FORMAT_MDY, "MM/DD/YYYY (US)"),
        (DATE_FORMAT_DMY, "DD/MM/YYYY (European)"),
        (DATE_FORMAT_YMD, "YYYY-MM-DD (ISO)"),
        (DATE_FORMAT_JALALI, "YYYY/MM/DD (Persian)"),
    ]

    # One-to-one relationship with tenant
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name="settings",
        help_text="Tenant that owns these settings",
    )

    # Business Information (Requirement 20.1)
    business_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Official business name (can differ from tenant company_name)",
    )

    business_registration_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Business registration or license number",
    )

    tax_identification_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Tax ID or VAT number",
    )

    # Contact Information
    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state_province = models.CharField(max_length=100, blank=True)
    postal_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)

    phone = models.CharField(max_length=20, blank=True)
    fax = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)

    # Branding
    logo = models.ImageField(
        upload_to="tenant_logos/",
        blank=True,
        null=True,
        help_text="Business logo for invoices and receipts",
    )

    primary_color = models.CharField(
        max_length=7,
        default="#1f2937",
        help_text="Primary brand color (hex format, e.g., #1f2937)",
    )

    secondary_color = models.CharField(
        max_length=7,
        default="#6b7280",
        help_text="Secondary brand color (hex format)",
    )

    # Localization (Requirement 20.6)
    timezone = models.CharField(
        max_length=50,
        default="UTC",
        help_text="Business timezone (e.g., America/New_York, Asia/Tehran)",
    )

    currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default=CURRENCY_USD,
        help_text="Default currency for transactions",
    )

    date_format = models.CharField(
        max_length=20,
        choices=DATE_FORMAT_CHOICES,
        default=DATE_FORMAT_MDY,
        help_text="Preferred date format for display",
    )

    # Business Hours (Requirement 20.7)
    business_hours = models.JSONField(
        default=dict,
        blank=True,
        help_text="Weekly business hours in format: {'monday': {'open': '09:00', 'close': '18:00', 'closed': false}, ...}",
    )

    # Holiday Calendar (Requirement 20.7)
    holidays = models.JSONField(
        default=list,
        blank=True,
        help_text="List of holiday dates and names: [{'date': '2024-01-01', 'name': 'New Year'}, ...]",
    )

    # Tax Configuration (Requirement 20.3)
    default_tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        default=0.0000,
        help_text="Default tax rate as decimal (e.g., 0.0825 for 8.25%)",
    )

    tax_inclusive_pricing = models.BooleanField(
        default=False,
        help_text="Whether prices include tax by default",
    )

    # Security Settings (Requirement 20.10)
    require_mfa_for_managers = models.BooleanField(
        default=False,
        help_text="Require MFA for tenant managers and owners",
    )

    password_expiry_days = models.IntegerField(
        default=0,
        help_text="Password expiry in days (0 = no expiry)",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "tenant_settings"
        verbose_name = "Tenant Settings"
        verbose_name_plural = "Tenant Settings"

    def __str__(self):
        return f"Settings for {self.tenant.company_name}"

    def get_full_address(self):
        """Return formatted full address."""
        parts = [
            self.address_line_1,
            self.address_line_2,
            self.city,
            self.state_province,
            self.postal_code,
            self.country,
        ]
        return ", ".join(filter(None, parts))

    def is_business_day(self, date):
        """Check if given date is a business day (not weekend or holiday)."""
        # Check if it's a holiday
        date_str = date.strftime("%Y-%m-%d")
        for holiday in self.holidays:
            if holiday.get("date") == date_str:
                return False

        # Check business hours for the day
        day_name = date.strftime("%A").lower()
        day_hours = self.business_hours.get(day_name, {})

        return not day_hours.get("closed", True)

    def get_business_hours_for_day(self, day_name):
        """Get business hours for a specific day."""
        return self.business_hours.get(
            day_name.lower(), {"open": "09:00", "close": "18:00", "closed": True}
        )


class InvoiceSettings(models.Model):
    """
    Invoice and receipt customization settings.

    Stores invoice templates, numbering schemes, and display preferences
    per Requirement 20.2.
    """

    # Invoice template choices
    TEMPLATE_STANDARD = "standard"
    TEMPLATE_MINIMAL = "minimal"
    TEMPLATE_DETAILED = "detailed"
    TEMPLATE_CUSTOM = "custom"

    TEMPLATE_CHOICES = [
        (TEMPLATE_STANDARD, "Standard Template"),
        (TEMPLATE_MINIMAL, "Minimal Template"),
        (TEMPLATE_DETAILED, "Detailed Template"),
        (TEMPLATE_CUSTOM, "Custom Template"),
    ]

    # Numbering scheme choices
    NUMBERING_SEQUENTIAL = "sequential"
    NUMBERING_YEARLY = "yearly"
    NUMBERING_MONTHLY = "monthly"
    NUMBERING_CUSTOM = "custom"

    NUMBERING_CHOICES = [
        (NUMBERING_SEQUENTIAL, "Sequential (1, 2, 3, ...)"),
        (NUMBERING_YEARLY, "Yearly (2024-001, 2024-002, ...)"),
        (NUMBERING_MONTHLY, "Monthly (2024-01-001, 2024-01-002, ...)"),
        (NUMBERING_CUSTOM, "Custom Format"),
    ]

    # One-to-one relationship with tenant
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name="invoice_settings",
        help_text="Tenant that owns these invoice settings",
    )

    # Template Configuration
    invoice_template = models.CharField(
        max_length=20,
        choices=TEMPLATE_CHOICES,
        default=TEMPLATE_STANDARD,
        help_text="Invoice template to use",
    )

    receipt_template = models.CharField(
        max_length=20,
        choices=TEMPLATE_CHOICES,
        default=TEMPLATE_STANDARD,
        help_text="Receipt template to use",
    )

    # Numbering Configuration
    invoice_numbering_scheme = models.CharField(
        max_length=20,
        choices=NUMBERING_CHOICES,
        default=NUMBERING_SEQUENTIAL,
        help_text="Invoice numbering scheme",
    )

    invoice_number_prefix = models.CharField(
        max_length=10,
        default="INV",
        help_text="Prefix for invoice numbers (e.g., INV, BILL)",
    )

    invoice_number_format = models.CharField(
        max_length=50,
        default="{prefix}-{number:06d}",
        help_text="Custom format string for invoice numbers",
    )

    next_invoice_number = models.IntegerField(
        default=1,
        help_text="Next invoice number to use",
    )

    receipt_numbering_scheme = models.CharField(
        max_length=20,
        choices=NUMBERING_CHOICES,
        default=NUMBERING_SEQUENTIAL,
        help_text="Receipt numbering scheme",
    )

    receipt_number_prefix = models.CharField(
        max_length=10,
        default="RCP",
        help_text="Prefix for receipt numbers",
    )

    receipt_number_format = models.CharField(
        max_length=50,
        default="{prefix}-{number:06d}",
        help_text="Custom format string for receipt numbers",
    )

    next_receipt_number = models.IntegerField(
        default=1,
        help_text="Next receipt number to use",
    )

    # Display Options
    show_item_codes = models.BooleanField(
        default=True,
        help_text="Show item SKU/codes on invoices",
    )

    show_item_descriptions = models.BooleanField(
        default=True,
        help_text="Show detailed item descriptions",
    )

    show_item_weights = models.BooleanField(
        default=True,
        help_text="Show item weights (important for jewelry)",
    )

    show_karat_purity = models.BooleanField(
        default=True,
        help_text="Show gold karat purity",
    )

    show_tax_breakdown = models.BooleanField(
        default=True,
        help_text="Show detailed tax breakdown",
    )

    show_payment_terms = models.BooleanField(
        default=False,
        help_text="Show payment terms and conditions",
    )

    # Custom Fields
    custom_field_1_label = models.CharField(
        max_length=50,
        blank=True,
        help_text="Label for custom field 1",
    )

    custom_field_1_value = models.CharField(
        max_length=255,
        blank=True,
        help_text="Default value for custom field 1",
    )

    custom_field_2_label = models.CharField(
        max_length=50,
        blank=True,
        help_text="Label for custom field 2",
    )

    custom_field_2_value = models.CharField(
        max_length=255,
        blank=True,
        help_text="Default value for custom field 2",
    )

    # Footer Text
    invoice_footer_text = models.TextField(
        blank=True,
        help_text="Custom footer text for invoices",
    )

    receipt_footer_text = models.TextField(
        blank=True,
        help_text="Custom footer text for receipts",
    )

    # Terms and Conditions
    payment_terms = models.TextField(
        blank=True,
        help_text="Payment terms and conditions",
    )

    return_policy = models.TextField(
        blank=True,
        help_text="Return and exchange policy",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "invoice_settings"
        verbose_name = "Invoice Settings"
        verbose_name_plural = "Invoice Settings"

    def __str__(self):
        return f"Invoice Settings for {self.tenant.company_name}"

    def generate_invoice_number(self):
        """Generate the next invoice number based on the numbering scheme."""
        import datetime

        if self.invoice_numbering_scheme == self.NUMBERING_SEQUENTIAL:
            number = self.next_invoice_number
            format_str = self.invoice_number_format
        elif self.invoice_numbering_scheme == self.NUMBERING_YEARLY:
            year = datetime.datetime.now().year
            number = self.next_invoice_number
            format_str = f"{year}-{{number:03d}}"
        elif self.invoice_numbering_scheme == self.NUMBERING_MONTHLY:
            now = datetime.datetime.now()
            number = self.next_invoice_number
            format_str = f"{now.year}-{now.month:02d}-{{number:03d}}"
        else:  # NUMBERING_CUSTOM
            number = self.next_invoice_number
            format_str = self.invoice_number_format

        # Increment the counter
        self.next_invoice_number += 1
        self.save(update_fields=["next_invoice_number"])

        # Format the number
        return format_str.format(
            prefix=self.invoice_number_prefix,
            number=number,
            year=datetime.datetime.now().year,
            month=datetime.datetime.now().month,
        )

    def generate_receipt_number(self):
        """Generate the next receipt number based on the numbering scheme."""
        import datetime

        if self.receipt_numbering_scheme == self.NUMBERING_SEQUENTIAL:
            number = self.next_receipt_number
            format_str = self.receipt_number_format
        elif self.receipt_numbering_scheme == self.NUMBERING_YEARLY:
            year = datetime.datetime.now().year
            number = self.next_receipt_number
            format_str = f"{year}-{{number:03d}}"
        elif self.receipt_numbering_scheme == self.NUMBERING_MONTHLY:
            now = datetime.datetime.now()
            number = self.next_receipt_number
            format_str = f"{now.year}-{now.month:02d}-{{number:03d}}"
        else:  # NUMBERING_CUSTOM
            number = self.next_receipt_number
            format_str = self.receipt_number_format

        # Increment the counter
        self.next_receipt_number += 1
        self.save(update_fields=["next_receipt_number"])

        # Format the number
        return format_str.format(
            prefix=self.receipt_number_prefix,
            number=number,
            year=datetime.datetime.now().year,
            month=datetime.datetime.now().month,
        )


class IntegrationSettings(models.Model):
    """
    Third-party integration settings and API credentials.

    Stores encrypted API credentials for payment gateways, SMS providers,
    email services, and other external integrations per Requirement 20.4 and 20.5.
    """

    # Integration types
    INTEGRATION_PAYMENT = "payment"
    INTEGRATION_SMS = "sms"
    INTEGRATION_EMAIL = "email"
    INTEGRATION_GOLD_RATE = "gold_rate"
    INTEGRATION_ACCOUNTING = "accounting"
    INTEGRATION_SHIPPING = "shipping"
    INTEGRATION_WEBHOOK = "webhook"

    INTEGRATION_CHOICES = [
        (INTEGRATION_PAYMENT, "Payment Gateway"),
        (INTEGRATION_SMS, "SMS Provider"),
        (INTEGRATION_EMAIL, "Email Provider"),
        (INTEGRATION_GOLD_RATE, "Gold Rate API"),
        (INTEGRATION_ACCOUNTING, "Accounting Software"),
        (INTEGRATION_SHIPPING, "Shipping Provider"),
        (INTEGRATION_WEBHOOK, "Webhook Endpoint"),
    ]

    # Provider choices for each integration type
    PAYMENT_STRIPE = "stripe"
    PAYMENT_PAYPAL = "paypal"
    PAYMENT_SQUARE = "square"
    PAYMENT_RAZORPAY = "razorpay"

    SMS_TWILIO = "twilio"
    SMS_NEXMO = "nexmo"
    SMS_AWS_SNS = "aws_sns"

    EMAIL_SENDGRID = "sendgrid"
    EMAIL_MAILGUN = "mailgun"
    EMAIL_AWS_SES = "aws_ses"
    EMAIL_SMTP = "smtp"

    GOLD_RATE_GOLDAPI = "goldapi"
    GOLD_RATE_METALS_API = "metals_api"
    GOLD_RATE_FIXER = "fixer"

    # One-to-one relationship with tenant
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name="integration_settings",
        help_text="Tenant that owns these integration settings",
    )

    # Payment Gateway Settings (Requirement 20.4)
    payment_gateway_enabled = models.BooleanField(
        default=False,
        help_text="Enable payment gateway integration",
    )

    payment_gateway_provider = models.CharField(
        max_length=50,
        blank=True,
        help_text="Payment gateway provider (stripe, paypal, square, etc.)",
    )

    payment_gateway_api_key = models.TextField(
        blank=True,
        help_text="Encrypted API key for payment gateway",
    )

    payment_gateway_secret_key = models.TextField(
        blank=True,
        help_text="Encrypted secret key for payment gateway",
    )

    payment_gateway_webhook_secret = models.TextField(
        blank=True,
        help_text="Encrypted webhook secret for payment gateway",
    )

    payment_gateway_test_mode = models.BooleanField(
        default=True,
        help_text="Use test/sandbox mode for payment gateway",
    )

    # SMS Provider Settings (Requirement 20.5)
    sms_provider_enabled = models.BooleanField(
        default=False,
        help_text="Enable SMS notifications",
    )

    sms_provider = models.CharField(
        max_length=50,
        blank=True,
        help_text="SMS provider (twilio, nexmo, aws_sns, etc.)",
    )

    sms_api_key = models.TextField(
        blank=True,
        help_text="Encrypted API key for SMS provider",
    )

    sms_api_secret = models.TextField(
        blank=True,
        help_text="Encrypted API secret for SMS provider",
    )

    sms_sender_id = models.CharField(
        max_length=20,
        blank=True,
        help_text="SMS sender ID or phone number",
    )

    # Email Provider Settings (Requirement 20.5)
    email_provider_enabled = models.BooleanField(
        default=False,
        help_text="Enable custom email provider (uses Django default if disabled)",
    )

    email_provider = models.CharField(
        max_length=50,
        blank=True,
        help_text="Email provider (sendgrid, mailgun, aws_ses, smtp, etc.)",
    )

    email_api_key = models.TextField(
        blank=True,
        help_text="Encrypted API key for email provider",
    )

    email_from_address = models.EmailField(
        blank=True,
        help_text="Default 'from' email address",
    )

    email_from_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Default 'from' name",
    )

    # SMTP Settings (for email_provider = 'smtp')
    smtp_host = models.CharField(
        max_length=255,
        blank=True,
        help_text="SMTP server hostname",
    )

    smtp_port = models.IntegerField(
        null=True,
        blank=True,
        help_text="SMTP server port (usually 587 or 465)",
    )

    smtp_username = models.CharField(
        max_length=255,
        blank=True,
        help_text="SMTP username",
    )

    smtp_password = models.TextField(
        blank=True,
        help_text="Encrypted SMTP password",
    )

    smtp_use_tls = models.BooleanField(
        default=True,
        help_text="Use TLS encryption for SMTP",
    )

    # Gold Rate API Settings
    gold_rate_api_enabled = models.BooleanField(
        default=False,
        help_text="Enable automatic gold rate updates",
    )

    gold_rate_api_provider = models.CharField(
        max_length=50,
        blank=True,
        help_text="Gold rate API provider",
    )

    gold_rate_api_key = models.TextField(
        blank=True,
        help_text="Encrypted API key for gold rate provider",
    )

    gold_rate_update_frequency = models.IntegerField(
        default=60,
        help_text="Update frequency in minutes",
    )

    # Webhook Settings (Requirement 32)
    webhook_url = models.URLField(
        blank=True,
        help_text="Webhook URL for external integrations",
    )

    webhook_secret = models.TextField(
        blank=True,
        help_text="Encrypted webhook secret for HMAC verification",
    )

    webhook_events = models.JSONField(
        default=list,
        blank=True,
        help_text="List of events to send via webhook (e.g., ['sale.created', 'inventory.updated'])",
    )

    # Additional Configuration
    additional_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional provider-specific configuration (JSON format)",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "integration_settings"
        verbose_name = "Integration Settings"
        verbose_name_plural = "Integration Settings"

    def __str__(self):
        return f"Integration Settings for {self.tenant.company_name}"

    def encrypt_field(self, value):
        """Encrypt a sensitive field value."""
        if not value:
            return ""

        from django.conf import settings

        from cryptography.fernet import Fernet

        # Get encryption key from settings
        key = getattr(settings, "FIELD_ENCRYPTION_KEY", None)
        if not key:
            raise ValueError("FIELD_ENCRYPTION_KEY not configured in settings")

        f = Fernet(key.encode())
        return f.encrypt(value.encode()).decode()

    def decrypt_field(self, encrypted_value):
        """Decrypt a sensitive field value."""
        if not encrypted_value:
            return ""

        from django.conf import settings

        from cryptography.fernet import Fernet

        # Get encryption key from settings
        key = getattr(settings, "FIELD_ENCRYPTION_KEY", None)
        if not key:
            raise ValueError("FIELD_ENCRYPTION_KEY not configured in settings")

        f = Fernet(key.encode())
        return f.decrypt(encrypted_value.encode()).decode()

    def set_payment_gateway_api_key(self, value):
        """Set encrypted payment gateway API key."""
        self.payment_gateway_api_key = self.encrypt_field(value)

    def get_payment_gateway_api_key(self):
        """Get decrypted payment gateway API key."""
        return self.decrypt_field(self.payment_gateway_api_key)

    def set_payment_gateway_secret_key(self, value):
        """Set encrypted payment gateway secret key."""
        self.payment_gateway_secret_key = self.encrypt_field(value)

    def get_payment_gateway_secret_key(self):
        """Get decrypted payment gateway secret key."""
        return self.decrypt_field(self.payment_gateway_secret_key)

    def set_sms_api_key(self, value):
        """Set encrypted SMS API key."""
        self.sms_api_key = self.encrypt_field(value)

    def get_sms_api_key(self):
        """Get decrypted SMS API key."""
        return self.decrypt_field(self.sms_api_key)

    def set_email_api_key(self, value):
        """Set encrypted email API key."""
        self.email_api_key = self.encrypt_field(value)

    def get_email_api_key(self):
        """Get decrypted email API key."""
        return self.decrypt_field(self.email_api_key)

    def set_sms_api_secret(self, value):
        """Set encrypted SMS API secret."""
        self.sms_api_secret = self.encrypt_field(value)

    def get_sms_api_secret(self):
        """Get decrypted SMS API secret."""
        return self.decrypt_field(self.sms_api_secret)

    def set_smtp_password(self, value):
        """Set encrypted SMTP password."""
        self.smtp_password = self.encrypt_field(value)

    def get_smtp_password(self):
        """Get decrypted SMTP password."""
        return self.decrypt_field(self.smtp_password)


class SubscriptionPlan(models.Model):
    """
    Subscription plan model defining pricing and resource limits.

    Platform administrators create and manage subscription plans that tenants
    can subscribe to. Each plan defines pricing, billing cycle, and resource limits
    per Requirement 5.2.
    """

    # Billing cycle choices
    BILLING_MONTHLY = "monthly"
    BILLING_QUARTERLY = "quarterly"
    BILLING_YEARLY = "yearly"
    BILLING_LIFETIME = "lifetime"

    BILLING_CYCLE_CHOICES = [
        (BILLING_MONTHLY, "Monthly"),
        (BILLING_QUARTERLY, "Quarterly"),
        (BILLING_YEARLY, "Yearly"),
        (BILLING_LIFETIME, "Lifetime"),
    ]

    # Status choices
    STATUS_ACTIVE = "active"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the subscription plan",
    )

    # Plan details
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Plan name (e.g., 'Starter', 'Professional', 'Enterprise')",
    )

    description = models.TextField(
        blank=True,
        help_text="Detailed description of the plan features",
    )

    # Pricing
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Plan price in USD",
    )

    billing_cycle = models.CharField(
        max_length=20,
        choices=BILLING_CYCLE_CHOICES,
        default=BILLING_MONTHLY,
        help_text="Billing frequency for this plan",
    )

    # Resource limits (Requirement 5.2)
    user_limit = models.IntegerField(
        default=5,
        help_text="Maximum number of users allowed",
    )

    branch_limit = models.IntegerField(
        default=1,
        help_text="Maximum number of branches allowed",
    )

    inventory_limit = models.IntegerField(
        default=1000,
        help_text="Maximum number of inventory items allowed",
    )

    storage_limit_gb = models.IntegerField(
        default=10,
        help_text="Maximum storage space in GB for media files",
    )

    api_calls_per_month = models.IntegerField(
        default=10000,
        help_text="Maximum API calls per month",
    )

    # Feature flags
    enable_multi_branch = models.BooleanField(
        default=False,
        help_text="Enable multi-branch management features",
    )

    enable_advanced_reporting = models.BooleanField(
        default=False,
        help_text="Enable advanced reporting and analytics",
    )

    enable_api_access = models.BooleanField(
        default=False,
        help_text="Enable API access for integrations",
    )

    enable_custom_branding = models.BooleanField(
        default=False,
        help_text="Enable custom branding and white-labeling",
    )

    enable_priority_support = models.BooleanField(
        default=False,
        help_text="Enable priority customer support",
    )

    # Plan status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        help_text="Plan status (active plans can be assigned to tenants)",
    )

    # Display order
    display_order = models.IntegerField(
        default=0,
        help_text="Order in which plans are displayed (lower numbers first)",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the plan was created",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the plan was last updated",
    )

    archived_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the plan was archived",
    )

    class Meta:
        db_table = "subscription_plans"
        ordering = ["display_order", "name"]
        verbose_name = "Subscription Plan"
        verbose_name_plural = "Subscription Plans"
        indexes = [
            models.Index(fields=["status"], name="plan_status_idx"),
            models.Index(fields=["display_order"], name="plan_display_order_idx"),
        ]

    def __str__(self):
        return f"{self.name} (${self.price}/{self.billing_cycle})"

    def archive(self):
        """
        Archive the plan.

        Archived plans cannot be assigned to new tenants but existing
        subscriptions remain active per Requirement 5.2.
        """
        from django.utils import timezone

        self.status = self.STATUS_ARCHIVED
        self.archived_at = timezone.now()
        self.save(update_fields=["status", "archived_at", "updated_at"])

    def activate(self):
        """Activate an archived plan."""
        self.status = self.STATUS_ACTIVE
        self.archived_at = None
        self.save(update_fields=["status", "archived_at", "updated_at"])

    def is_active(self):
        """Check if plan is active."""
        return self.status == self.STATUS_ACTIVE

    def is_archived(self):
        """Check if plan is archived."""
        return self.status == self.STATUS_ARCHIVED

    def get_monthly_price(self):
        """
        Calculate equivalent monthly price for comparison.

        Returns the price normalized to a monthly basis for easy comparison
        across different billing cycles.
        """
        if self.billing_cycle == self.BILLING_MONTHLY:
            return self.price
        elif self.billing_cycle == self.BILLING_QUARTERLY:
            return self.price / 3
        elif self.billing_cycle == self.BILLING_YEARLY:
            return self.price / 12
        else:  # BILLING_LIFETIME
            return 0  # Lifetime plans have no recurring cost

    def get_annual_price(self):
        """Calculate equivalent annual price."""
        if self.billing_cycle == self.BILLING_MONTHLY:
            return self.price * 12
        elif self.billing_cycle == self.BILLING_QUARTERLY:
            return self.price * 4
        elif self.billing_cycle == self.BILLING_YEARLY:
            return self.price
        else:  # BILLING_LIFETIME
            return self.price  # One-time payment


class TenantSubscription(models.Model):
    """
    Tenant subscription model linking tenants to subscription plans.

    Tracks the current subscription status, billing information, and allows
    for plan-specific limit overrides per Requirement 5.3, 5.4, and 5.5.
    """

    # Subscription status choices
    STATUS_ACTIVE = "active"
    STATUS_TRIAL = "trial"
    STATUS_PAST_DUE = "past_due"
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_TRIAL, "Trial"),
        (STATUS_PAST_DUE, "Past Due"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_EXPIRED, "Expired"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the subscription",
    )

    # Relationships
    tenant = models.OneToOneField(
        Tenant,
        on_delete=models.CASCADE,
        related_name="subscription",
        help_text="Tenant that owns this subscription",
    )

    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
        help_text="Subscription plan for this tenant",
    )

    # Subscription status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_TRIAL,
        help_text="Current subscription status",
    )

    # Billing information
    current_period_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Start date of the current billing period",
    )

    current_period_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End date of the current billing period",
    )

    next_billing_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date of the next billing charge",
    )

    trial_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Start date of trial period",
    )

    trial_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End date of trial period",
    )

    # Resource limit overrides (Requirement 5.4)
    # These override the plan defaults for this specific tenant
    user_limit_override = models.IntegerField(
        null=True,
        blank=True,
        help_text="Override for user limit (null = use plan default)",
    )

    branch_limit_override = models.IntegerField(
        null=True,
        blank=True,
        help_text="Override for branch limit (null = use plan default)",
    )

    inventory_limit_override = models.IntegerField(
        null=True,
        blank=True,
        help_text="Override for inventory limit (null = use plan default)",
    )

    storage_limit_gb_override = models.IntegerField(
        null=True,
        blank=True,
        help_text="Override for storage limit in GB (null = use plan default)",
    )

    api_calls_per_month_override = models.IntegerField(
        null=True,
        blank=True,
        help_text="Override for API calls per month (null = use plan default)",
    )

    # Feature flag overrides
    enable_multi_branch_override = models.BooleanField(
        null=True,
        blank=True,
        help_text="Override for multi-branch feature (null = use plan default)",
    )

    enable_advanced_reporting_override = models.BooleanField(
        null=True,
        blank=True,
        help_text="Override for advanced reporting (null = use plan default)",
    )

    enable_api_access_override = models.BooleanField(
        null=True,
        blank=True,
        help_text="Override for API access (null = use plan default)",
    )

    enable_custom_branding_override = models.BooleanField(
        null=True,
        blank=True,
        help_text="Override for custom branding (null = use plan default)",
    )

    enable_priority_support_override = models.BooleanField(
        null=True,
        blank=True,
        help_text="Override for priority support (null = use plan default)",
    )

    # Payment gateway integration
    stripe_customer_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Stripe customer ID for payment processing",
    )

    stripe_subscription_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Stripe subscription ID",
    )

    # Cancellation tracking
    cancelled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when subscription was cancelled",
    )

    cancellation_reason = models.TextField(
        blank=True,
        help_text="Reason for cancellation",
    )

    # Notes
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about this subscription",
    )

    # Timestamps
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the subscription was created",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp when the subscription was last updated",
    )

    class Meta:
        db_table = "tenant_subscriptions"
        ordering = ["-created_at"]
        verbose_name = "Tenant Subscription"
        verbose_name_plural = "Tenant Subscriptions"
        indexes = [
            models.Index(fields=["status"], name="subscription_status_idx"),
            models.Index(fields=["next_billing_date"], name="subscription_billing_date_idx"),
            models.Index(fields=["plan", "status"], name="subscription_plan_status_idx"),
        ]

    def __str__(self):
        return f"{self.tenant.company_name} - {self.plan.name} ({self.status})"

    def get_user_limit(self):
        """Get effective user limit (override or plan default)."""
        return (
            self.user_limit_override
            if self.user_limit_override is not None
            else self.plan.user_limit
        )

    def get_branch_limit(self):
        """Get effective branch limit (override or plan default)."""
        return (
            self.branch_limit_override
            if self.branch_limit_override is not None
            else self.plan.branch_limit
        )

    def get_inventory_limit(self):
        """Get effective inventory limit (override or plan default)."""
        return (
            self.inventory_limit_override
            if self.inventory_limit_override is not None
            else self.plan.inventory_limit
        )

    def get_storage_limit_gb(self):
        """Get effective storage limit (override or plan default)."""
        return (
            self.storage_limit_gb_override
            if self.storage_limit_gb_override is not None
            else self.plan.storage_limit_gb
        )

    def get_api_calls_per_month(self):
        """Get effective API calls limit (override or plan default)."""
        return (
            self.api_calls_per_month_override
            if self.api_calls_per_month_override is not None
            else self.plan.api_calls_per_month
        )

    def has_multi_branch_enabled(self):
        """Check if multi-branch feature is enabled (override or plan default)."""
        return (
            self.enable_multi_branch_override
            if self.enable_multi_branch_override is not None
            else self.plan.enable_multi_branch
        )

    def has_advanced_reporting_enabled(self):
        """Check if advanced reporting is enabled (override or plan default)."""
        return (
            self.enable_advanced_reporting_override
            if self.enable_advanced_reporting_override is not None
            else self.plan.enable_advanced_reporting
        )

    def has_api_access_enabled(self):
        """Check if API access is enabled (override or plan default)."""
        return (
            self.enable_api_access_override
            if self.enable_api_access_override is not None
            else self.plan.enable_api_access
        )

    def has_custom_branding_enabled(self):
        """Check if custom branding is enabled (override or plan default)."""
        return (
            self.enable_custom_branding_override
            if self.enable_custom_branding_override is not None
            else self.plan.enable_custom_branding
        )

    def has_priority_support_enabled(self):
        """Check if priority support is enabled (override or plan default)."""
        return (
            self.enable_priority_support_override
            if self.enable_priority_support_override is not None
            else self.plan.enable_priority_support
        )

    def is_active(self):
        """Check if subscription is active."""
        return self.status == self.STATUS_ACTIVE

    def is_trial(self):
        """Check if subscription is in trial period."""
        return self.status == self.STATUS_TRIAL

    def is_past_due(self):
        """Check if subscription payment is past due."""
        return self.status == self.STATUS_PAST_DUE

    def is_cancelled(self):
        """Check if subscription is cancelled."""
        return self.status == self.STATUS_CANCELLED

    def is_expired(self):
        """Check if subscription is expired."""
        return self.status == self.STATUS_EXPIRED

    def activate(self):
        """
        Activate the subscription (Requirement 5.5).

        This manually activates a subscription, typically used by admins
        for manual subscription management.
        """
        self.status = self.STATUS_ACTIVE
        self.cancelled_at = None
        self.save(update_fields=["status", "cancelled_at", "updated_at"])

    def deactivate(self):
        """
        Deactivate the subscription (Requirement 5.5).

        This manually deactivates a subscription, typically used by admins
        for manual subscription management.
        """
        from django.utils import timezone

        self.status = self.STATUS_CANCELLED
        self.cancelled_at = timezone.now()
        self.save(update_fields=["status", "cancelled_at", "updated_at"])

    def cancel(self, reason=""):
        """
        Cancel the subscription.

        Args:
            reason: Optional reason for cancellation
        """
        from django.utils import timezone

        self.status = self.STATUS_CANCELLED
        self.cancelled_at = timezone.now()
        self.cancellation_reason = reason
        self.save(update_fields=["status", "cancelled_at", "cancellation_reason", "updated_at"])

    def change_plan(self, new_plan):
        """
        Change the subscription plan (Requirement 5.3).

        Args:
            new_plan: The new SubscriptionPlan to switch to
        """
        self.plan = new_plan
        self.save(update_fields=["plan", "updated_at"])

        # Note: Plan changes should be logged in the admin/API layer
        # where we have access to the actor (user making the change)

    def days_until_renewal(self):
        """Get the number of days until the next billing date."""
        from django.utils import timezone

        if not self.next_billing_date:
            return None

        delta = self.next_billing_date - timezone.now()
        return max(0, delta.days)

    def is_trial_expired(self):
        """Check if trial period has expired."""
        from django.utils import timezone

        if not self.trial_end:
            return False

        return timezone.now() > self.trial_end

    def days_remaining_in_trial(self):
        """Get the number of days remaining in trial period."""
        from django.utils import timezone

        if not self.trial_end:
            return None

        delta = self.trial_end - timezone.now()
        return max(0, delta.days)
