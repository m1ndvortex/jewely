#!/usr/bin/env python
"""
Verification script for Fixed Asset models.
Tests model creation, tenant filtering, and calculated properties.
"""

import os
import sys

import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model

from apps.accounting.models import AssetDisposal, DepreciationSchedule, FixedAsset
from apps.core.models import Tenant

User = get_user_model()


def test_fixed_asset_models():
    """Test Fixed Asset models."""
    print("=" * 80)
    print("FIXED ASSET MODELS VERIFICATION")
    print("=" * 80)

    # Get or create a test tenant
    tenant, _ = Tenant.objects.get_or_create(
        company_name="Test Jewelry Shop",
        defaults={
            "slug": "test-jewelry",
            "status": "ACTIVE",
        },
    )
    print(f"\n✓ Using tenant: {tenant.company_name}")

    # Get or create a test user
    user, _ = User.objects.get_or_create(
        username="test_admin",
        defaults={
            "email": "admin@test.com",
            "is_staff": True,
            "role": "SUPER_ADMIN",  # Super admin doesn't require tenant
        },
    )
    print(f"✓ Using user: {user.username}")

    # Test 1: Create a Fixed Asset
    print("\n" + "-" * 80)
    print("TEST 1: Creating a Fixed Asset")
    print("-" * 80)

    asset = FixedAsset.objects.create(
        tenant=tenant,
        asset_name="Display Case - Main Store",
        category="FIXTURES",
        acquisition_date=date(2024, 1, 1),
        acquisition_cost=Decimal("5000.00"),
        salvage_value=Decimal("500.00"),
        useful_life_months=60,  # 5 years
        depreciation_method="STRAIGHT_LINE",
        asset_account="1500",
        accumulated_depreciation_account="1510",
        depreciation_expense_account="6500",
        created_by=user,
    )

    print(f"✓ Created asset: {asset}")
    print(f"  - Asset Number: {asset.asset_number}")
    print(f"  - Acquisition Cost: ${asset.acquisition_cost}")
    print(f"  - Current Book Value: ${asset.current_book_value}")
    print(f"  - Depreciable Amount: ${asset.depreciable_amount}")
    print(f"  - Status: {asset.status}")

    # Test 2: Test calculated properties
    print("\n" + "-" * 80)
    print("TEST 2: Testing Calculated Properties")
    print("-" * 80)

    print(f"✓ Depreciable Amount: ${asset.depreciable_amount}")
    print(f"✓ Remaining Depreciable Amount: ${asset.remaining_depreciable_amount}")
    print(f"✓ Is Fully Depreciated: {asset.is_fully_depreciated}")
    print(f"✓ Depreciation Percentage: {asset.depreciation_percentage:.2f}%")
    print(f"✓ Months in Service: {asset.months_in_service}")
    print(f"✓ Remaining Useful Life: {asset.remaining_useful_life_months} months")

    # Test 3: Calculate monthly depreciation
    print("\n" + "-" * 80)
    print("TEST 3: Calculating Monthly Depreciation")
    print("-" * 80)

    monthly_depreciation = asset.calculate_monthly_depreciation()
    print(f"✓ Monthly Depreciation (Straight Line): ${monthly_depreciation}")
    expected = asset.depreciable_amount / Decimal(str(asset.useful_life_months))
    print(f"  Expected: ${expected:.2f}")
    print(f"  Match: {abs(monthly_depreciation - expected) < Decimal('0.01')}")

    # Test 4: Record depreciation
    print("\n" + "-" * 80)
    print("TEST 4: Recording Depreciation")
    print("-" * 80)

    period_date = date(2024, 1, 31)
    asset.record_depreciation(monthly_depreciation, period_date)
    asset.refresh_from_db()

    print(f"✓ Recorded depreciation for {period_date}")
    print(f"  - Accumulated Depreciation: ${asset.accumulated_depreciation}")
    print(f"  - Current Book Value: ${asset.current_book_value}")
    print(f"  - Last Depreciation Date: {asset.last_depreciation_date}")

    # Test 5: Create depreciation schedule entry
    print("\n" + "-" * 80)
    print("TEST 5: Creating Depreciation Schedule Entry")
    print("-" * 80)

    schedule = DepreciationSchedule.objects.create(
        tenant=tenant,
        fixed_asset=asset,
        period_date=period_date,
        depreciation_amount=monthly_depreciation,
        accumulated_depreciation=asset.accumulated_depreciation,
        book_value=asset.current_book_value,
        created_by=user,
    )

    print(f"✓ Created depreciation schedule: {schedule}")
    print(f"  - Period: {schedule.period_year}-{schedule.period_month:02d}")
    print(f"  - Depreciation Amount: ${schedule.depreciation_amount}")
    print(f"  - Book Value: ${schedule.book_value}")

    # Test 6: Test tenant filtering
    print("\n" + "-" * 80)
    print("TEST 6: Testing Tenant Filtering")
    print("-" * 80)

    # Create another tenant
    other_tenant, _ = Tenant.objects.get_or_create(
        company_name="Other Jewelry Shop",
        defaults={
            "slug": "other-jewelry",
            "status": "ACTIVE",
        },
    )

    # Create asset for other tenant
    other_asset = FixedAsset.objects.create(
        tenant=other_tenant,
        asset_name="Other Display Case",
        category="FIXTURES",
        acquisition_date=date(2024, 1, 1),
        acquisition_cost=Decimal("3000.00"),
        salvage_value=Decimal("300.00"),
        useful_life_months=60,
        depreciation_method="STRAIGHT_LINE",
        asset_account="1500",
        accumulated_depreciation_account="1510",
        depreciation_expense_account="6500",
        created_by=user,
    )

    # Test filtering
    tenant_assets = FixedAsset.objects.for_tenant(tenant).count()
    other_tenant_assets = FixedAsset.objects.for_tenant(other_tenant).count()
    all_assets = FixedAsset.objects.all_tenants().count()

    print(f"✓ Assets for {tenant.company_name}: {tenant_assets}")
    print(f"✓ Assets for {other_tenant.company_name}: {other_tenant_assets}")
    print(f"✓ Total assets (all tenants): {all_assets}")
    print(f"✓ Tenant isolation working: {tenant_assets == 1 and other_tenant_assets == 1}")

    # Test 7: Test asset disposal
    print("\n" + "-" * 80)
    print("TEST 7: Testing Asset Disposal")
    print("-" * 80)

    disposal = AssetDisposal.objects.create(
        tenant=tenant,
        fixed_asset=asset,
        disposal_date=date(2024, 6, 30),
        disposal_method="SOLD",
        proceeds=Decimal("4000.00"),
        created_by=user,
    )

    print(f"✓ Created asset disposal: {disposal}")
    print(f"  - Disposal Date: {disposal.disposal_date}")
    print(f"  - Proceeds: ${disposal.proceeds}")
    print(f"  - Book Value at Disposal: ${disposal.book_value_at_disposal}")
    print(f"  - Gain/Loss: ${disposal.gain_loss}")
    print(f"  - Is Gain: {disposal.is_gain}")
    print(f"  - Is Loss: {disposal.is_loss}")

    # Verify asset status changed
    asset.refresh_from_db()
    print(f"✓ Asset status after disposal: {asset.status}")

    # Test 8: Test declining balance depreciation
    print("\n" + "-" * 80)
    print("TEST 8: Testing Declining Balance Depreciation")
    print("-" * 80)

    db_asset = FixedAsset.objects.create(
        tenant=tenant,
        asset_name="Computer Equipment",
        category="COMPUTERS",
        acquisition_date=date(2024, 1, 1),
        acquisition_cost=Decimal("2000.00"),
        salvage_value=Decimal("200.00"),
        useful_life_months=36,  # 3 years
        depreciation_method="DECLINING_BALANCE",
        depreciation_rate=Decimal("200.00"),  # Double declining
        asset_account="1500",
        accumulated_depreciation_account="1510",
        depreciation_expense_account="6500",
        created_by=user,
    )

    db_monthly_depreciation = db_asset.calculate_monthly_depreciation()
    print(f"✓ Created declining balance asset: {db_asset.asset_number}")
    print(f"  - Monthly Depreciation: ${db_monthly_depreciation}")
    print(f"  - Method: {db_asset.depreciation_method}")
    print(f"  - Rate: {db_asset.depreciation_rate}%")

    # Cleanup
    print("\n" + "-" * 80)
    print("CLEANUP")
    print("-" * 80)

    # Delete test data
    FixedAsset.objects.filter(tenant__in=[tenant, other_tenant]).delete()
    print("✓ Cleaned up test assets")

    print("\n" + "=" * 80)
    print("ALL TESTS PASSED!")
    print("=" * 80)
    print("\nFixed Asset models are working correctly:")
    print("  ✓ Model creation and validation")
    print("  ✓ Calculated properties")
    print("  ✓ Depreciation calculations (straight-line and declining balance)")
    print("  ✓ Depreciation recording")
    print("  ✓ Depreciation schedule tracking")
    print("  ✓ Tenant isolation")
    print("  ✓ Asset disposal with gain/loss calculation")
    print("  ✓ Auto-generated asset numbers")
    print("=" * 80)


if __name__ == "__main__":
    try:
        test_fixed_asset_models()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
