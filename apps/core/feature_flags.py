"""
Feature flag management system extending django-waffle.
Per Requirement 30 - Feature Flag Management

This module provides:
1. Global and per-tenant feature control
2. Gradual rollout by percentage
3. Specific tenant targeting
4. Change tracking and history
5. Emergency kill switch
6. A/B testing support
7. Conversion metrics tracking
"""

from django.db import models
from django.utils import timezone

from waffle import flag_is_active
from waffle.models import Flag


class TenantFeatureFlag(models.Model):
    """
    Per-tenant feature flag overrides.
    Allows enabling/disabling features for specific tenants.
    Acceptance Criteria 1, 3
    """

    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="feature_flags",
    )
    flag = models.ForeignKey(
        Flag,
        on_delete=models.CASCADE,
        related_name="tenant_overrides",
    )
    enabled = models.BooleanField(
        default=False,
        help_text="Override flag state for this tenant",
    )
    notes = models.TextField(
        blank=True,
        help_text="Reason for override (e.g., beta testing, early access)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_tenant_flags",
    )

    class Meta:
        db_table = "core_tenant_feature_flag"
        unique_together = [["tenant", "flag"]]
        indexes = [
            models.Index(fields=["tenant", "flag"]),
            models.Index(fields=["enabled"]),
        ]
        verbose_name = "Tenant Feature Flag"
        verbose_name_plural = "Tenant Feature Flags"

    def __str__(self):
        return f"{self.tenant.company_name} - {self.flag.name}: {self.enabled}"


class FeatureFlagHistory(models.Model):
    """
    Track all changes to feature flags for audit trail.
    Acceptance Criteria 4
    """

    flag_name = models.CharField(max_length=100)
    flag_type = models.CharField(
        max_length=20,
        choices=[
            ("flag", "Flag"),
            ("switch", "Switch"),
            ("sample", "Sample"),
            ("tenant_override", "Tenant Override"),
        ],
    )
    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Tenant if this is a tenant-specific change",
    )
    action = models.CharField(
        max_length=20,
        choices=[
            ("created", "Created"),
            ("enabled", "Enabled"),
            ("disabled", "Disabled"),
            ("percentage_changed", "Percentage Changed"),
            ("emergency_disabled", "Emergency Disabled"),
        ],
    )
    old_value = models.JSONField(
        null=True,
        blank=True,
        help_text="Previous state before change",
    )
    new_value = models.JSONField(
        null=True,
        blank=True,
        help_text="New state after change",
    )
    changed_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="flag_changes",
    )
    reason = models.TextField(
        blank=True,
        help_text="Reason for the change",
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_feature_flag_history"
        indexes = [
            models.Index(fields=["flag_name", "timestamp"]),
            models.Index(fields=["tenant", "timestamp"]),
            models.Index(fields=["action"]),
        ]
        ordering = ["-timestamp"]
        verbose_name = "Feature Flag History"
        verbose_name_plural = "Feature Flag History"

    def __str__(self):
        tenant_str = f" ({self.tenant.company_name})" if self.tenant else ""
        return f"{self.flag_name}{tenant_str} - {self.action} at {self.timestamp}"


class ABTestVariant(models.Model):
    """
    A/B test variant configuration.
    Acceptance Criteria 6
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique name for this A/B test",
    )
    flag = models.ForeignKey(
        Flag,
        on_delete=models.CASCADE,
        related_name="ab_tests",
        help_text="Feature flag being tested",
    )
    control_group_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=50.0,
        help_text="Percentage of users in control group (0-100)",
    )
    variant_group_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=50.0,
        help_text="Percentage of users in variant group (0-100)",
    )
    description = models.TextField(
        blank=True,
        help_text="Description of what is being tested",
    )
    hypothesis = models.TextField(
        blank=True,
        help_text="What you expect to learn from this test",
    )
    start_date = models.DateTimeField(
        default=timezone.now,
        help_text="When the test started",
    )
    end_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the test ended (null if still running)",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this test is currently running",
    )
    created_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_ab_tests",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "core_ab_test_variant"
        indexes = [
            models.Index(fields=["flag", "is_active"]),
            models.Index(fields=["start_date", "end_date"]),
        ]
        verbose_name = "A/B Test Variant"
        verbose_name_plural = "A/B Test Variants"

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.name} ({status})"

    def stop_test(self):
        """Stop the A/B test."""
        self.is_active = False
        self.end_date = timezone.now()
        self.save()


class FeatureFlagMetric(models.Model):
    """
    Track conversion metrics for feature flags and A/B tests.
    Acceptance Criteria 7
    """

    flag_name = models.CharField(max_length=100)
    ab_test = models.ForeignKey(
        ABTestVariant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="metrics",
        help_text="A/B test this metric belongs to (if any)",
    )
    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="flag_metrics",
    )
    user = models.ForeignKey(
        "core.User",
        on_delete=models.CASCADE,
        related_name="flag_metrics",
    )
    variant_group = models.CharField(
        max_length=20,
        choices=[
            ("control", "Control"),
            ("variant", "Variant"),
            ("none", "None"),
        ],
        default="none",
        help_text="Which group the user is in for A/B testing",
    )
    event_type = models.CharField(
        max_length=50,
        help_text="Type of event (e.g., 'viewed', 'clicked', 'converted')",
    )
    event_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Additional event data",
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_feature_flag_metric"
        indexes = [
            models.Index(fields=["flag_name", "timestamp"]),
            models.Index(fields=["ab_test", "variant_group", "event_type"]),
            models.Index(fields=["tenant", "timestamp"]),
        ]
        ordering = ["-timestamp"]
        verbose_name = "Feature Flag Metric"
        verbose_name_plural = "Feature Flag Metrics"

    def __str__(self):
        return f"{self.flag_name} - {self.event_type} by {self.user.username}"


class EmergencyKillSwitch(models.Model):
    """
    Emergency kill switch to quickly disable problematic features.
    Acceptance Criteria 5
    """

    flag_name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Name of the flag to kill",
    )
    reason = models.TextField(
        help_text="Reason for emergency disable",
    )
    disabled_at = models.DateTimeField(auto_now_add=True)
    disabled_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        related_name="emergency_kills",
    )
    re_enabled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the feature was re-enabled",
    )
    re_enabled_by = models.ForeignKey(
        "core.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="emergency_re_enables",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this kill switch is currently active",
    )

    class Meta:
        db_table = "core_emergency_kill_switch"
        indexes = [
            models.Index(fields=["flag_name", "is_active"]),
            models.Index(fields=["disabled_at"]),
        ]
        ordering = ["-disabled_at"]
        verbose_name = "Emergency Kill Switch"
        verbose_name_plural = "Emergency Kill Switches"

    def __str__(self):
        status = "ACTIVE" if self.is_active else "Resolved"
        return f"KILL SWITCH: {self.flag_name} ({status})"

    def re_enable(self, user):
        """Re-enable the feature after emergency disable."""
        self.is_active = False
        self.re_enabled_at = timezone.now()
        self.re_enabled_by = user
        self.save()


# Service functions for feature flag management


def is_flag_active_for_tenant(flag_name, tenant, user=None):
    """
    Check if a flag is active for a specific tenant.
    Checks in order:
    1. Emergency kill switch
    2. Tenant-specific override
    3. Global flag state

    Acceptance Criteria 1, 3, 5
    """
    # Check emergency kill switch first
    if EmergencyKillSwitch.objects.filter(flag_name=flag_name, is_active=True).exists():
        return False

    # Check tenant-specific override
    try:
        flag = Flag.objects.get(name=flag_name)
        tenant_override = TenantFeatureFlag.objects.filter(tenant=tenant, flag=flag).first()
        if tenant_override is not None:
            return tenant_override.enabled

        # Fall back to global flag state
        # Check if flag is explicitly enabled for everyone
        if flag.everyone is True:
            return True
        elif flag.everyone is False:
            return False
        else:
            # If everyone is None, use waffle's normal logic
            return flag_is_active(user, flag_name) if user else False
    except Flag.DoesNotExist:
        return False


def enable_flag_for_tenant(flag_name, tenant, user, notes=""):
    """
    Enable a flag for a specific tenant.
    Acceptance Criteria 1, 3, 4
    """
    flag = Flag.objects.get(name=flag_name)
    tenant_flag, created = TenantFeatureFlag.objects.update_or_create(
        tenant=tenant,
        flag=flag,
        defaults={
            "enabled": True,
            "notes": notes,
            "created_by": user,
        },
    )

    # Track history
    FeatureFlagHistory.objects.create(
        flag_name=flag_name,
        flag_type="tenant_override",
        tenant=tenant,
        action="enabled",
        new_value={"enabled": True, "notes": notes},
        changed_by=user,
        reason=notes,
    )

    return tenant_flag


def disable_flag_for_tenant(flag_name, tenant, user, notes=""):
    """
    Disable a flag for a specific tenant.
    Acceptance Criteria 1, 3, 4
    """
    flag = Flag.objects.get(name=flag_name)
    tenant_flag, created = TenantFeatureFlag.objects.update_or_create(
        tenant=tenant,
        flag=flag,
        defaults={
            "enabled": False,
            "notes": notes,
            "created_by": user,
        },
    )

    # Track history
    FeatureFlagHistory.objects.create(
        flag_name=flag_name,
        flag_type="tenant_override",
        tenant=tenant,
        action="disabled",
        new_value={"enabled": False, "notes": notes},
        changed_by=user,
        reason=notes,
    )

    return tenant_flag


def set_flag_percentage(flag_name, percentage, user, reason=""):
    """
    Set gradual rollout percentage for a flag.
    Acceptance Criteria 2, 4
    """
    flag = Flag.objects.get(name=flag_name)
    old_percentage = flag.percent

    flag.percent = percentage
    flag.save()

    # Track history
    FeatureFlagHistory.objects.create(
        flag_name=flag_name,
        flag_type="flag",
        action="percentage_changed",
        old_value={"percent": float(old_percentage) if old_percentage else 0},
        new_value={"percent": float(percentage)},
        changed_by=user,
        reason=reason,
    )

    return flag


def emergency_disable_flag(flag_name, user, reason):
    """
    Emergency kill switch to immediately disable a flag.
    Acceptance Criteria 5, 4
    """
    # Create kill switch record
    kill_switch = EmergencyKillSwitch.objects.create(
        flag_name=flag_name,
        reason=reason,
        disabled_by=user,
    )

    # Track in history
    FeatureFlagHistory.objects.create(
        flag_name=flag_name,
        flag_type="flag",
        action="emergency_disabled",
        new_value={"emergency_disabled": True, "reason": reason},
        changed_by=user,
        reason=reason,
    )

    return kill_switch


def track_flag_metric(
    flag_name, tenant, user, event_type, event_data=None, ab_test=None, variant_group="none"
):
    """
    Track a metric event for a feature flag.
    Acceptance Criteria 7
    """
    return FeatureFlagMetric.objects.create(
        flag_name=flag_name,
        ab_test=ab_test,
        tenant=tenant,
        user=user,
        variant_group=variant_group,
        event_type=event_type,
        event_data=event_data or {},
    )


def get_flag_conversion_metrics(flag_name, start_date=None, end_date=None):
    """
    Get conversion metrics for a flag.
    Acceptance Criteria 7
    """
    from django.db.models import Count

    queryset = FeatureFlagMetric.objects.filter(flag_name=flag_name)

    if start_date:
        queryset = queryset.filter(timestamp__gte=start_date)
    if end_date:
        queryset = queryset.filter(timestamp__lte=end_date)

    metrics = {
        "total_events": queryset.count(),
        "unique_users": queryset.values("user").distinct().count(),
        "unique_tenants": queryset.values("tenant").distinct().count(),
        "events_by_type": queryset.values("event_type").annotate(count=Count("id")),
    }

    return metrics


def get_ab_test_metrics(ab_test_id):
    """
    Get A/B test metrics comparing control vs variant groups.
    Acceptance Criteria 6, 7
    """
    from django.db.models import Count

    ab_test = ABTestVariant.objects.get(id=ab_test_id)
    metrics = FeatureFlagMetric.objects.filter(ab_test=ab_test)

    control_metrics = metrics.filter(variant_group="control")
    variant_metrics = metrics.filter(variant_group="variant")

    return {
        "test_name": ab_test.name,
        "control": {
            "total_events": control_metrics.count(),
            "unique_users": control_metrics.values("user").distinct().count(),
            "events_by_type": control_metrics.values("event_type").annotate(count=Count("id")),
        },
        "variant": {
            "total_events": variant_metrics.count(),
            "unique_users": variant_metrics.values("user").distinct().count(),
            "events_by_type": variant_metrics.values("event_type").annotate(count=Count("id")),
        },
    }
