"""
Documentation and knowledge base models for platform operations.

This module provides documentation and runbook management for:
- Platform architecture and component documentation
- Step-by-step guides for common admin tasks
- Troubleshooting guides for common issues
- Internal API documentation
- Incident response runbooks
- Maintenance runbooks
- Disaster recovery procedures
- Runbook version tracking
- Admin notes and tips
- FAQ for common tenant questions

Per Requirement 34 - Knowledge Base and Documentation
"""

import uuid

from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils import timezone


class DocumentationPage(models.Model):
    """
    Documentation pages for platform knowledge base.

    Requirement 34.1: Provide documentation of platform architecture and components.
    Requirement 34.2: Provide step-by-step guides for common admin tasks.
    Requirement 34.3: Provide troubleshooting guides for common issues and errors.
    Requirement 34.4: Provide internal API documentation for admin operations.
    Requirement 34.10: Maintain FAQ for common tenant questions.
    """

    # Category choices
    ARCHITECTURE = "ARCHITECTURE"
    ADMIN_GUIDE = "ADMIN_GUIDE"
    TROUBLESHOOTING = "TROUBLESHOOTING"
    API_DOCUMENTATION = "API_DOCUMENTATION"
    FAQ = "FAQ"
    DEVELOPER_GUIDE = "DEVELOPER_GUIDE"
    USER_GUIDE = "USER_GUIDE"

    CATEGORY_CHOICES = [
        (ARCHITECTURE, "Architecture & Components"),
        (ADMIN_GUIDE, "Admin Guide"),
        (TROUBLESHOOTING, "Troubleshooting"),
        (API_DOCUMENTATION, "API Documentation"),
        (FAQ, "Frequently Asked Questions"),
        (DEVELOPER_GUIDE, "Developer Guide"),
        (USER_GUIDE, "User Guide"),
    ]

    # Status choices
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"

    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (PUBLISHED, "Published"),
        (ARCHIVED, "Archived"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the documentation page",
    )

    # Content
    title = models.CharField(
        max_length=255,
        help_text="Title of the documentation page",
    )

    slug = models.SlugField(
        max_length=255,
        unique=True,
        help_text="URL-friendly identifier for the page",
    )

    content = models.TextField(
        help_text="Full content of the documentation page (supports Markdown)",
    )

    summary = models.TextField(
        blank=True,
        help_text="Brief summary or excerpt of the page content",
    )

    # Categorization
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        help_text="Category of the documentation",
    )

    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="List of tags for categorization and search",
    )

    # Version tracking
    version = models.CharField(
        max_length=50,
        default="1.0",
        help_text="Version number of the documentation",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=DRAFT,
        help_text="Publication status of the page",
    )

    # Ordering and hierarchy
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        help_text="Parent page for hierarchical organization",
    )

    order = models.IntegerField(
        default=0,
        help_text="Display order within the same category or parent",
    )

    # Full-text search
    search_vector = SearchVectorField(
        null=True,
        blank=True,
        help_text="Full-text search index for title and content",
    )

    # Metadata
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the page was created",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the page was last updated",
    )

    published_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the page was published",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_documentation_pages",
        help_text="User who created the page",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="updated_documentation_pages",
        help_text="User who last updated the page",
    )

    # Usage tracking
    view_count = models.IntegerField(
        default=0,
        help_text="Number of times this page has been viewed",
    )

    last_viewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the page was last viewed",
    )

    class Meta:
        db_table = "documentation_pages"
        ordering = ["category", "order", "title"]
        indexes = [
            models.Index(fields=["category", "status"]),
            models.Index(fields=["status", "-updated_at"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["parent", "order"]),
            GinIndex(fields=["search_vector"], name="doc_search_idx"),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_category_display()})"

    def publish(self):
        """Publish the documentation page."""
        self.status = self.PUBLISHED
        if not self.published_at:
            self.published_at = timezone.now()
        self.save()

    def archive(self):
        """Archive the documentation page."""
        self.status = self.ARCHIVED
        self.save()

    def increment_view_count(self):
        """Increment the view counter."""
        self.view_count += 1
        self.last_viewed_at = timezone.now()
        self.save(update_fields=["view_count", "last_viewed_at"])

    def get_breadcrumbs(self):
        """
        Get breadcrumb trail for hierarchical navigation.

        Returns:
            List of (title, slug) tuples from root to current page
        """
        breadcrumbs = [(self.title, self.slug)]
        current = self.parent

        while current:
            breadcrumbs.insert(0, (current.title, current.slug))
            current = current.parent

        return breadcrumbs


class Runbook(models.Model):
    """
    Operational runbooks for platform management and incident response.

    Requirement 34.5: Provide incident response runbooks with documented procedures.
    Requirement 34.6: Provide maintenance runbooks for routine tasks.
    Requirement 34.7: Provide disaster recovery runbooks with step-by-step procedures.
    Requirement 34.8: Track runbook versions and updates.
    Requirement 34.9: Allow admins to add notes and tips for other admins.
    """

    # Runbook types
    INCIDENT_RESPONSE = "INCIDENT_RESPONSE"
    MAINTENANCE = "MAINTENANCE"
    DISASTER_RECOVERY = "DISASTER_RECOVERY"
    DEPLOYMENT = "DEPLOYMENT"
    TROUBLESHOOTING = "TROUBLESHOOTING"
    BACKUP_RESTORE = "BACKUP_RESTORE"

    RUNBOOK_TYPE_CHOICES = [
        (INCIDENT_RESPONSE, "Incident Response"),
        (MAINTENANCE, "Maintenance"),
        (DISASTER_RECOVERY, "Disaster Recovery"),
        (DEPLOYMENT, "Deployment"),
        (TROUBLESHOOTING, "Troubleshooting"),
        (BACKUP_RESTORE, "Backup & Restore"),
    ]

    # Priority levels
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

    PRIORITY_CHOICES = [
        (CRITICAL, "Critical"),
        (HIGH, "High"),
        (MEDIUM, "Medium"),
        (LOW, "Low"),
    ]

    # Status choices
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"

    STATUS_CHOICES = [
        (DRAFT, "Draft"),
        (ACTIVE, "Active"),
        (DEPRECATED, "Deprecated"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the runbook",
    )

    # Runbook details
    title = models.CharField(
        max_length=255,
        help_text="Title of the runbook",
    )

    slug = models.SlugField(
        max_length=255,
        unique=True,
        help_text="URL-friendly identifier for the runbook",
    )

    description = models.TextField(
        help_text="Brief description of what this runbook covers",
    )

    runbook_type = models.CharField(
        max_length=50,
        choices=RUNBOOK_TYPE_CHOICES,
        help_text="Type of operational runbook",
    )

    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default=MEDIUM,
        help_text="Priority level of the runbook",
    )

    # Procedures
    prerequisites = models.TextField(
        blank=True,
        help_text="Prerequisites or requirements before executing the runbook",
    )

    steps = models.JSONField(
        default=list,
        help_text="List of step-by-step procedures (each step is a dict with title, description, commands)",
    )

    expected_duration = models.DurationField(
        null=True,
        blank=True,
        help_text="Expected time to complete the runbook procedures",
    )

    # Recovery objectives (for DR runbooks)
    rto = models.DurationField(
        null=True,
        blank=True,
        help_text="Recovery Time Objective - maximum acceptable downtime",
    )

    rpo = models.DurationField(
        null=True,
        blank=True,
        help_text="Recovery Point Objective - maximum acceptable data loss",
    )

    # Verification and rollback
    verification_steps = models.JSONField(
        default=list,
        blank=True,
        help_text="Steps to verify successful execution",
    )

    rollback_steps = models.JSONField(
        default=list,
        blank=True,
        help_text="Steps to rollback if something goes wrong",
    )

    # Related information
    related_documentation = models.ManyToManyField(
        DocumentationPage,
        blank=True,
        related_name="related_runbooks",
        help_text="Related documentation pages",
    )

    related_runbooks = models.ManyToManyField(
        "self",
        blank=True,
        symmetrical=False,
        help_text="Related runbooks",
    )

    # Tags and categorization
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="List of tags for categorization and search",
    )

    # Version tracking
    version = models.CharField(
        max_length=50,
        default="1.0",
        help_text="Version number of the runbook",
    )

    changelog = models.TextField(
        blank=True,
        help_text="Change history for this runbook",
    )

    # Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=DRAFT,
        help_text="Status of the runbook",
    )

    # Full-text search
    search_vector = SearchVectorField(
        null=True,
        blank=True,
        help_text="Full-text search index for title, description, and steps",
    )

    # Metadata
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the runbook was created",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the runbook was last updated",
    )

    last_executed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the runbook was last executed",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_runbooks",
        help_text="User who created the runbook",
    )

    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="updated_runbooks",
        help_text="User who last updated the runbook",
    )

    # Usage tracking
    execution_count = models.IntegerField(
        default=0,
        help_text="Number of times this runbook has been executed",
    )

    success_count = models.IntegerField(
        default=0,
        help_text="Number of successful executions",
    )

    failure_count = models.IntegerField(
        default=0,
        help_text="Number of failed executions",
    )

    class Meta:
        db_table = "runbooks"
        ordering = ["-priority", "runbook_type", "title"]
        indexes = [
            models.Index(fields=["runbook_type", "status"]),
            models.Index(fields=["priority", "status"]),
            models.Index(fields=["status", "-updated_at"]),
            models.Index(fields=["slug"]),
            GinIndex(fields=["search_vector"], name="runbook_search_idx"),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_runbook_type_display()})"

    def activate(self):
        """Activate the runbook."""
        self.status = self.ACTIVE
        self.save()

    def deprecate(self):
        """Deprecate the runbook."""
        self.status = self.DEPRECATED
        self.save()

    def record_execution(self, success=True):
        """
        Record a runbook execution.

        Args:
            success: Whether the execution was successful
        """
        self.execution_count += 1
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self.last_executed_at = timezone.now()
        self.save(
            update_fields=["execution_count", "success_count", "failure_count", "last_executed_at"]
        )

    def get_success_rate(self):
        """
        Calculate the success rate of runbook executions.

        Returns:
            Float representing success rate (0.0 to 1.0), or None if never executed
        """
        if self.execution_count == 0:
            return None
        return self.success_count / self.execution_count


class RunbookExecution(models.Model):
    """
    Track individual runbook executions for audit and analysis.

    Requirement 34.8: Track runbook versions and updates.
    """

    # Status choices
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

    STATUS_CHOICES = [
        (IN_PROGRESS, "In Progress"),
        (COMPLETED, "Completed"),
        (FAILED, "Failed"),
        (CANCELLED, "Cancelled"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the execution",
    )

    # References
    runbook = models.ForeignKey(
        Runbook,
        on_delete=models.CASCADE,
        related_name="executions",
        help_text="The runbook that was executed",
    )

    runbook_version = models.CharField(
        max_length=50,
        help_text="Version of the runbook at time of execution",
    )

    # Execution details
    executed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="runbook_executions",
        help_text="User who executed the runbook",
    )

    started_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the execution started",
    )

    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the execution completed",
    )

    duration = models.DurationField(
        null=True,
        blank=True,
        help_text="Total duration of the execution",
    )

    # Status and results
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=IN_PROGRESS,
        help_text="Current status of the execution",
    )

    steps_completed = models.JSONField(
        default=list,
        help_text="List of step indices that have been completed",
    )

    current_step = models.IntegerField(
        null=True,
        blank=True,
        help_text="Index of the current step being executed",
    )

    # Notes and observations
    notes = models.TextField(
        blank=True,
        help_text="Notes and observations during execution",
    )

    error_message = models.TextField(
        blank=True,
        help_text="Error message if execution failed",
    )

    # Verification results
    verification_passed = models.BooleanField(
        null=True,
        blank=True,
        help_text="Whether verification steps passed",
    )

    rollback_performed = models.BooleanField(
        default=False,
        help_text="Whether rollback was performed",
    )

    class Meta:
        db_table = "runbook_executions"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["runbook", "-started_at"]),
            models.Index(fields=["executed_by", "-started_at"]),
            models.Index(fields=["status", "-started_at"]),
        ]

    def __str__(self):
        return f"Execution of {self.runbook.title} at {self.started_at}"

    def complete(self, success=True, notes=""):
        """
        Mark the execution as complete.

        Args:
            success: Whether the execution was successful
            notes: Additional notes about the execution
        """
        self.status = self.COMPLETED if success else self.FAILED
        self.completed_at = timezone.now()
        self.duration = self.completed_at - self.started_at
        if notes:
            self.notes = notes
        self.save()

        # Update runbook statistics
        self.runbook.record_execution(success=success)

    def cancel(self, reason=""):
        """
        Cancel the execution.

        Args:
            reason: Reason for cancellation
        """
        self.status = self.CANCELLED
        self.completed_at = timezone.now()
        self.duration = self.completed_at - self.started_at
        if reason:
            self.notes = f"Cancelled: {reason}"
        self.save()


class AdminNote(models.Model):
    """
    Notes and tips from admins for other admins.

    Requirement 34.9: Allow admins to add notes and tips for other admins.
    """

    # Note types
    TIP = "TIP"
    WARNING = "WARNING"
    BEST_PRACTICE = "BEST_PRACTICE"
    LESSON_LEARNED = "LESSON_LEARNED"

    NOTE_TYPE_CHOICES = [
        (TIP, "Tip"),
        (WARNING, "Warning"),
        (BEST_PRACTICE, "Best Practice"),
        (LESSON_LEARNED, "Lesson Learned"),
    ]

    # Primary key
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text="Unique identifier for the note",
    )

    # Content
    title = models.CharField(
        max_length=255,
        help_text="Title of the note",
    )

    content = models.TextField(
        help_text="Full content of the note",
    )

    note_type = models.CharField(
        max_length=50,
        choices=NOTE_TYPE_CHOICES,
        default=TIP,
        help_text="Type of note",
    )

    # Related items
    documentation_page = models.ForeignKey(
        DocumentationPage,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="admin_notes",
        help_text="Related documentation page",
    )

    runbook = models.ForeignKey(
        Runbook,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="admin_notes",
        help_text="Related runbook",
    )

    # Tags
    tags = models.JSONField(
        default=list,
        blank=True,
        help_text="List of tags for categorization",
    )

    # Visibility
    is_pinned = models.BooleanField(
        default=False,
        help_text="Whether this note is pinned to the top",
    )

    # Metadata
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the note was created",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the note was last updated",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_admin_notes",
        help_text="Admin who created the note",
    )

    # Engagement tracking
    helpful_count = models.IntegerField(
        default=0,
        help_text="Number of admins who found this note helpful",
    )

    class Meta:
        db_table = "admin_notes"
        ordering = ["-is_pinned", "-created_at"]
        indexes = [
            models.Index(fields=["documentation_page", "-created_at"]),
            models.Index(fields=["runbook", "-created_at"]),
            models.Index(fields=["note_type", "-created_at"]),
            models.Index(fields=["-is_pinned", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_note_type_display()})"

    def mark_helpful(self):
        """Increment the helpful counter."""
        self.helpful_count += 1
        self.save(update_fields=["helpful_count"])

    def pin(self):
        """Pin the note to the top."""
        self.is_pinned = True
        self.save(update_fields=["is_pinned"])

    def unpin(self):
        """Unpin the note."""
        self.is_pinned = False
        self.save(update_fields=["is_pinned"])
