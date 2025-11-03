"""
Fixed asset models for asset management and depreciation tracking.

This module contains models for managing fixed assets, depreciation schedules,
and asset disposals with proper tenant isolation.
"""

import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from django_ledger.models import JournalEntryModel

from apps.core.models import Tenant

User = get_user_model()


class TenantManager(models.Manager):
    """
    Custom manager for tenant-aware models.
    Automatically filters queries by tenant for data isolation.
    """

    def get_queryset(self):
        """Override to filter by tenant if available in context."""
        try:
            # Import here to avoid circular imports at module load time
            from apps.core.tenant_context import get_current_tenant

            current = get_current_tenant()
            if current:
                return super().get_queryset().filter(tenant=current)
        except Exception:
            # If anything goes wrong (no DB connection, missing function, etc.),
            # fall back to the unfiltered queryset to avoid breaking callers.
            pass

        return super().get_queryset()

    def for_tenant(self, tenant):
        """Get queryset filtered by specific tenant."""
        return self.get_queryset().filter(tenant=tenant)

    def all_tenants(self):
        """Get all objects without tenant filtering (admin use only)."""
        return super().get_queryset()


class FixedAsset(models.Model):
    """
    Fixed asset model for tracking long-term tangible assets.

    Tracks assets like equipment, fixtures, vehicles, and buildings
    with depreciation calculation and disposal tracking.
    """

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("DISPOSED", "Disposed"),
        ("FULLY_DEPRECIATED", "Fully Depreciated"),
    ]

    DEPRECIATION_METHOD_CHOICES = [
        ("STRAIGHT_LINE", "Straight Line"),
        ("DECLINING_BALANCE", "Declining Balance"),
        ("UNITS_OF_PRODUCTION", "Units of Production"),
    ]

    CATEGORY_CHOICES = [
        ("EQUIPMENT", "Equipment"),
        ("FIXTURES", "Fixtures"),
        ("FURNITURE", "Furniture"),
        ("VEHICLES", "Vehicles"),
        ("BUILDINGS", "Buildings"),
        ("COMPUTERS", "Computers & IT Equipment"),
        ("TOOLS", "Tools"),
        ("OTHER", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="fixed_assets",
        help_text="Tenant that owns this fixed asset",
    )

    # Asset Identification
    asset_name = models.CharField(
        max_length=200,
        help_text="Name/description of the asset",
    )
    asset_number = models.CharField(
        max_length=50,
        help_text="Unique asset identification number",
    )
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default="EQUIPMENT",
        help_text="Category of the asset",
    )
    serial_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Manufacturer's serial number",
    )
    manufacturer = models.CharField(
        max_length=100,
        blank=True,
        help_text="Manufacturer or brand name",
    )
    model_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Model number",
    )

    # Acquisition Information
    acquisition_date = models.DateField(
        help_text="Date when asset was acquired",
    )
    acquisition_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Original cost of the asset",
    )
    salvage_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Estimated salvage/residual value at end of useful life",
    )

    # Depreciation Settings
    useful_life_months = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Useful life in months",
    )
    depreciation_method = models.CharField(
        max_length=30,
        choices=DEPRECIATION_METHOD_CHOICES,
        default="STRAIGHT_LINE",
        help_text="Method used to calculate depreciation",
    )
    depreciation_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Depreciation rate for declining balance method (e.g., 200 for double declining)",
    )

    # Current Status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="ACTIVE",
        help_text="Current status of the asset",
    )
    current_book_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Current book value (cost - accumulated depreciation)",
    )
    accumulated_depreciation = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Total depreciation accumulated to date",
    )
    last_depreciation_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of last depreciation calculation",
    )

    # GL Account References
    asset_account = models.CharField(
        max_length=20,
        help_text="GL account code for the asset (e.g., 1500 - Equipment)",
    )
    accumulated_depreciation_account = models.CharField(
        max_length=20,
        help_text="GL account code for accumulated depreciation (e.g., 1510 - Accumulated Depreciation)",
    )
    depreciation_expense_account = models.CharField(
        max_length=20,
        help_text="GL account code for depreciation expense (e.g., 6500 - Depreciation Expense)",
    )

    # Location and Responsibility
    location = models.CharField(
        max_length=200,
        blank=True,
        help_text="Physical location of the asset",
    )
    department = models.CharField(
        max_length=100,
        blank=True,
        help_text="Department responsible for the asset",
    )
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_assets",
        help_text="User responsible for this asset",
    )

    # Additional Information
    purchase_order_number = models.CharField(
        max_length=50,
        blank=True,
        help_text="Purchase order number for acquisition",
    )
    vendor = models.CharField(
        max_length=200,
        blank=True,
        help_text="Vendor/supplier of the asset",
    )
    warranty_expiration = models.DateField(
        null=True,
        blank=True,
        help_text="Warranty expiration date",
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this asset",
    )

    # Audit Fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_fixed_assets",
        help_text="User who registered this asset",
    )

    # Custom manager
    objects = TenantManager()

    class Meta:
        db_table = "accounting_fixed_assets"
        unique_together = [["tenant", "asset_number"]]
        indexes = [
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["tenant", "category"]),
            models.Index(fields=["acquisition_date"]),
            models.Index(fields=["last_depreciation_date"]),
            models.Index(fields=["status", "last_depreciation_date"]),
        ]
        ordering = ["asset_number"]
        verbose_name = "Fixed Asset"
        verbose_name_plural = "Fixed Assets"

    def __str__(self):
        return f"{self.asset_number} - {self.asset_name}"

    def clean(self):
        """Validate fixed asset data."""
        super().clean()

        # Validate salvage value is less than acquisition cost
        if self.salvage_value >= self.acquisition_cost:
            raise ValidationError(
                {"salvage_value": "Salvage value must be less than acquisition cost"}
            )

        # Validate depreciation rate for declining balance method
        if self.depreciation_method == "DECLINING_BALANCE" and not self.depreciation_rate:
            raise ValidationError(
                {"depreciation_rate": "Depreciation rate is required for declining balance method"}
            )

        # Validate accumulated depreciation doesn't exceed depreciable amount
        depreciable_amount = self.acquisition_cost - self.salvage_value
        if self.accumulated_depreciation > depreciable_amount:
            raise ValidationError(
                {
                    "accumulated_depreciation": f"Accumulated depreciation cannot exceed "
                    f"depreciable amount ({depreciable_amount})"
                }
            )

    @property
    def depreciable_amount(self):
        """Calculate the depreciable amount (cost - salvage value)."""
        return self.acquisition_cost - self.salvage_value

    @property
    def remaining_depreciable_amount(self):
        """Calculate remaining amount to be depreciated."""
        return self.depreciable_amount - self.accumulated_depreciation

    @property
    def is_fully_depreciated(self):
        """Check if asset is fully depreciated."""
        return self.accumulated_depreciation >= self.depreciable_amount

    @property
    def depreciation_percentage(self):
        """Calculate percentage of asset that has been depreciated."""
        if self.depreciable_amount == 0:
            return Decimal("100.00")
        return (self.accumulated_depreciation / self.depreciable_amount) * Decimal("100.00")

    @property
    def months_in_service(self):
        """Calculate number of months asset has been in service."""
        if not self.acquisition_date:
            return 0
        today = timezone.now().date()
        months = (today.year - self.acquisition_date.year) * 12
        months += today.month - self.acquisition_date.month
        return max(0, months)

    @property
    def remaining_useful_life_months(self):
        """Calculate remaining useful life in months."""
        return max(0, self.useful_life_months - self.months_in_service)

    @property
    def is_under_warranty(self):
        """Check if asset is still under warranty."""
        if not self.warranty_expiration:
            return False
        return timezone.now().date() <= self.warranty_expiration

    def calculate_monthly_depreciation(self):
        """
        Calculate monthly depreciation amount based on depreciation method.

        Returns:
            Decimal: Monthly depreciation amount
        """
        if self.is_fully_depreciated or self.status != "ACTIVE":
            return Decimal("0.00")

        if self.depreciation_method == "STRAIGHT_LINE":
            return self._calculate_straight_line_depreciation()
        elif self.depreciation_method == "DECLINING_BALANCE":
            return self._calculate_declining_balance_depreciation()
        elif self.depreciation_method == "UNITS_OF_PRODUCTION":
            # Units of production requires additional tracking of usage
            # For now, return 0 and implement in service layer
            return Decimal("0.00")

        return Decimal("0.00")

    def _calculate_straight_line_depreciation(self):
        """Calculate straight-line depreciation."""
        if self.useful_life_months == 0:
            return Decimal("0.00")

        monthly_depreciation = self.depreciable_amount / Decimal(str(self.useful_life_months))

        # Don't depreciate below salvage value
        if self.accumulated_depreciation + monthly_depreciation > self.depreciable_amount:
            monthly_depreciation = self.depreciable_amount - self.accumulated_depreciation

        return monthly_depreciation.quantize(Decimal("0.01"))

    def _calculate_declining_balance_depreciation(self):
        """Calculate declining balance depreciation."""
        if not self.depreciation_rate or self.useful_life_months == 0:
            return Decimal("0.00")

        # Calculate monthly rate from annual rate
        annual_rate = self.depreciation_rate / Decimal("100.00")
        monthly_rate = annual_rate / Decimal("12.00")

        # Apply rate to current book value
        monthly_depreciation = self.current_book_value * monthly_rate

        # Don't depreciate below salvage value
        if self.current_book_value - monthly_depreciation < self.salvage_value:
            monthly_depreciation = self.current_book_value - self.salvage_value

        return monthly_depreciation.quantize(Decimal("0.01"))

    def record_depreciation(self, amount, period_date):
        """
        Record depreciation for a period.

        Args:
            amount: Depreciation amount
            period_date: Date of the depreciation period
        """
        self.accumulated_depreciation += amount
        self.current_book_value = self.acquisition_cost - self.accumulated_depreciation
        self.last_depreciation_date = period_date

        # Check if fully depreciated
        if self.is_fully_depreciated:
            self.status = "FULLY_DEPRECIATED"

        self.save(
            update_fields=[
                "accumulated_depreciation",
                "current_book_value",
                "last_depreciation_date",
                "status",
                "updated_at",
            ]
        )

    def dispose(self, disposal_date, proceeds=None):
        """
        Mark asset as disposed.

        Args:
            disposal_date: Date of disposal
            proceeds: Amount received from disposal (if sold)
        """
        if self.status == "DISPOSED":
            raise ValidationError("Asset is already disposed")

        self.status = "DISPOSED"
        self.save(update_fields=["status", "updated_at"])

    def reactivate(self):
        """Reactivate a disposed asset."""
        if self.status != "DISPOSED":
            raise ValidationError("Only disposed assets can be reactivated")

        if self.is_fully_depreciated:
            self.status = "FULLY_DEPRECIATED"
        else:
            self.status = "ACTIVE"

        self.save(update_fields=["status", "updated_at"])

    def generate_asset_number(self):
        """Generate a unique asset number for this tenant."""
        today = timezone.now().date()
        year = today.strftime("%Y")

        # Find the last asset number for this tenant and year
        last_asset = (
            FixedAsset.objects.filter(
                tenant=self.tenant,
                asset_number__startswith=f"FA-{year}-",
            )
            .order_by("-asset_number")
            .first()
        )

        if last_asset:
            try:
                last_sequence = int(last_asset.asset_number.split("-")[-1])
                sequence = last_sequence + 1
            except (ValueError, IndexError):
                sequence = 1
        else:
            sequence = 1

        return f"FA-{year}-{sequence:04d}"

    def save(self, *args, **kwargs):
        """Auto-generate asset number and set initial book value."""
        is_new = self._state.adding

        # Generate asset number if not set
        if not self.asset_number:
            self.asset_number = self.generate_asset_number()

        # Set initial book value for new assets
        if is_new:
            self.current_book_value = self.acquisition_cost

        super().save(*args, **kwargs)


class DepreciationSchedule(models.Model):
    """
    Depreciation schedule tracking for fixed assets.

    Records each period's depreciation calculation with journal entry
    reference for audit trail and reporting.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="depreciation_schedules",
        help_text="Tenant that owns this depreciation record",
    )
    fixed_asset = models.ForeignKey(
        FixedAsset,
        on_delete=models.CASCADE,
        related_name="depreciation_schedules",
        help_text="Fixed asset this depreciation applies to",
    )

    # Period Information
    period_date = models.DateField(
        help_text="Date of the depreciation period (typically month-end)",
    )
    period_month = models.IntegerField(
        help_text="Month number (1-12)",
    )
    period_year = models.IntegerField(
        help_text="Year",
    )

    # Depreciation Amounts
    depreciation_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Depreciation amount for this period",
    )
    accumulated_depreciation = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Total accumulated depreciation after this period",
    )
    book_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Book value after this period's depreciation",
    )

    # Accounting Integration
    journal_entry = models.ForeignKey(
        JournalEntryModel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="depreciation_schedules",
        help_text="Journal entry created for this depreciation",
    )

    # Additional Information
    notes = models.TextField(
        blank=True,
        help_text="Notes about this depreciation entry",
    )
    is_adjustment = models.BooleanField(
        default=False,
        help_text="Whether this is an adjustment entry",
    )

    # Audit Fields
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_depreciation_schedules",
        help_text="User who created this depreciation entry",
    )

    # Custom manager
    objects = TenantManager()

    class Meta:
        db_table = "accounting_depreciation_schedules"
        unique_together = [["fixed_asset", "period_date"]]
        indexes = [
            models.Index(fields=["tenant", "period_date"]),
            models.Index(fields=["fixed_asset", "period_date"]),
            models.Index(fields=["period_year", "period_month"]),
            models.Index(fields=["journal_entry"]),
        ]
        ordering = ["-period_date"]
        verbose_name = "Depreciation Schedule"
        verbose_name_plural = "Depreciation Schedules"

    def __str__(self):
        return f"{self.fixed_asset.asset_number} - {self.period_date} - {self.depreciation_amount}"

    def clean(self):
        """Validate depreciation schedule data."""
        super().clean()

        # Ensure tenant matches asset tenant
        if self.fixed_asset and self.fixed_asset.tenant != self.tenant:
            raise ValidationError({"fixed_asset": "Fixed asset must belong to the same tenant"})

        # Validate period month and year
        if self.period_month and (self.period_month < 1 or self.period_month > 12):
            raise ValidationError({"period_month": "Period month must be between 1 and 12"})

        # Check for duplicate depreciation in same period
        if self.fixed_asset and self.period_date:
            existing = (
                DepreciationSchedule.objects.filter(
                    fixed_asset=self.fixed_asset,
                    period_date=self.period_date,
                )
                .exclude(pk=self.pk)
                .exists()
            )
            if existing:
                raise ValidationError(
                    {
                        "period_date": f"Depreciation already recorded for "
                        f"{self.fixed_asset.asset_number} on {self.period_date}"
                    }
                )

    def save(self, *args, **kwargs):
        """Auto-populate period month and year from period date."""
        if self.period_date:
            self.period_month = self.period_date.month
            self.period_year = self.period_date.year

        super().save(*args, **kwargs)


class AssetDisposal(models.Model):
    """
    Asset disposal tracking.

    Records when assets are sold, scrapped, donated, or otherwise
    disposed of, with gain/loss calculation and journal entry creation.
    """

    DISPOSAL_METHOD_CHOICES = [
        ("SOLD", "Sold"),
        ("SCRAPPED", "Scrapped"),
        ("DONATED", "Donated"),
        ("TRADED", "Traded In"),
        ("LOST", "Lost/Stolen"),
        ("OTHER", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="asset_disposals",
        help_text="Tenant that owns this disposal record",
    )
    fixed_asset = models.OneToOneField(
        FixedAsset,
        on_delete=models.CASCADE,
        related_name="disposal",
        help_text="Fixed asset being disposed",
    )

    # Disposal Information
    disposal_date = models.DateField(
        help_text="Date when asset was disposed",
    )
    disposal_method = models.CharField(
        max_length=20,
        choices=DISPOSAL_METHOD_CHOICES,
        help_text="Method of disposal",
    )
    proceeds = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Amount received from disposal (if sold)",
    )

    # Financial Calculations
    book_value_at_disposal = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text="Book value of asset at time of disposal",
    )
    gain_loss = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Gain or loss on disposal (proceeds - book value)",
    )

    # Accounting Integration
    journal_entry = models.ForeignKey(
        JournalEntryModel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="asset_disposals",
        help_text="Journal entry created for this disposal",
    )

    # Additional Information
    buyer_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Name of buyer (if sold)",
    )
    disposal_reason = models.TextField(
        blank=True,
        help_text="Reason for disposal",
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about the disposal",
    )

    # Audit Fields
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="created_asset_disposals",
        help_text="User who recorded this disposal",
    )

    # Custom manager
    objects = TenantManager()

    class Meta:
        db_table = "accounting_asset_disposals"
        indexes = [
            models.Index(fields=["tenant", "disposal_date"]),
            models.Index(fields=["fixed_asset"]),
            models.Index(fields=["disposal_method"]),
            models.Index(fields=["journal_entry"]),
        ]
        ordering = ["-disposal_date"]
        verbose_name = "Asset Disposal"
        verbose_name_plural = "Asset Disposals"

    def __str__(self):
        return f"{self.fixed_asset.asset_number} - Disposed {self.disposal_date}"

    def clean(self):
        """Validate asset disposal data."""
        super().clean()

        # Ensure tenant matches asset tenant
        if self.fixed_asset and self.fixed_asset.tenant != self.tenant:
            raise ValidationError({"fixed_asset": "Fixed asset must belong to the same tenant"})

        # Validate disposal date is not before acquisition date
        if self.fixed_asset and self.disposal_date < self.fixed_asset.acquisition_date:
            raise ValidationError(
                {"disposal_date": "Disposal date cannot be before acquisition date"}
            )

    def calculate_gain_loss(self):
        """Calculate gain or loss on disposal."""
        self.gain_loss = self.proceeds - self.book_value_at_disposal
        self.save(update_fields=["gain_loss"])

    @property
    def is_gain(self):
        """Check if disposal resulted in a gain."""
        return self.gain_loss > 0

    @property
    def is_loss(self):
        """Check if disposal resulted in a loss."""
        return self.gain_loss < 0

    def save(self, *args, **kwargs):
        """Auto-calculate gain/loss and update asset status."""
        is_new = self._state.adding

        # Set book value at disposal from asset's current book value
        if is_new and self.fixed_asset:
            self.book_value_at_disposal = self.fixed_asset.current_book_value

        # Calculate gain/loss
        self.gain_loss = self.proceeds - self.book_value_at_disposal

        super().save(*args, **kwargs)

        # Mark asset as disposed
        if is_new and self.fixed_asset:
            self.fixed_asset.dispose(self.disposal_date, self.proceeds)
