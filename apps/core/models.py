"""
Core models for the jewelry shop SaaS platform.
"""

import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.text import slugify


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

    def suspend(self):
        """Suspend the tenant account."""
        self.status = self.SUSPENDED
        self.save(update_fields=["status", "updated_at"])

    def activate(self):
        """Activate the tenant account."""
        self.status = self.ACTIVE
        self.save(update_fields=["status", "updated_at"])

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
