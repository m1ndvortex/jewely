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
            if not self.tenant:
                raise ValueError(f"Users with role {self.role} must have a tenant assigned")

        # Branch must belong to the same tenant
        if self.branch and self.tenant:
            if self.branch.tenant_id != self.tenant_id:
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
