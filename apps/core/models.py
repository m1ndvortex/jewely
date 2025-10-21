"""
Core models for the jewelry shop SaaS platform.
"""

import uuid

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
