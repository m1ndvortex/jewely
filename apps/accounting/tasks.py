"""
Celery tasks for accounting operations.

This module contains background tasks for automated accounting processes
including monthly depreciation runs.
"""

import logging
from datetime import date, datetime
from typing import Dict, List

from django.contrib.auth import get_user_model
from django.db import transaction

from celery import shared_task

from apps.core.audit_models import AuditLog
from apps.core.models import Tenant

logger = logging.getLogger(__name__)
User = get_user_model()


@shared_task(
    name="apps.accounting.tasks.run_monthly_depreciation_all_tenants",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def run_monthly_depreciation_all_tenants(self, period_date_str: str = None):
    """
    Run monthly depreciation for all active tenants.

    This task is scheduled to run on the first day of each month and processes
    depreciation for all active fixed assets across all tenants.

    Args:
        period_date_str: Optional date string in YYYY-MM-DD format.
                        If not provided, uses the last day of previous month.

    Returns:
        Dict with summary of depreciation run across all tenants

    Requirements: 5.3, 5.8
    """
    from apps.accounting.services import FixedAssetService

    try:
        # Determine the period date
        if period_date_str:
            period_date = datetime.strptime(period_date_str, "%Y-%m-%d").date()
        else:
            # Use the last day of the previous month
            today = date.today()
            if today.day == 1:
                # If running on the 1st, use the last day of previous month
                from calendar import monthrange

                if today.month == 1:
                    year = today.year - 1
                    month = 12
                else:
                    year = today.year
                    month = today.month - 1
                last_day = monthrange(year, month)[1]
                period_date = date(year, month, last_day)
            else:
                # Otherwise use yesterday
                from datetime import timedelta

                period_date = today - timedelta(days=1)

        logger.info(f"Starting monthly depreciation run for period: {period_date}")

        # Get all active tenants
        active_tenants = Tenant.objects.filter(status=Tenant.ACTIVE)

        overall_results = {
            "period_date": period_date.isoformat(),
            "total_tenants": active_tenants.count(),
            "tenants_processed": 0,
            "tenants_failed": 0,
            "total_assets_processed": 0,
            "total_depreciation_amount": 0,
            "tenant_details": [],
        }

        # Get or create a system user for automated tasks
        system_user = User.objects.filter(username="system", role=User.PLATFORM_ADMIN).first()

        if not system_user:
            logger.warning("System user not found. Creating automated task user.")
            system_user = User.objects.create_user(
                username="system",
                email="system@automated.local",
                role=User.PLATFORM_ADMIN,
                is_staff=True,
                is_active=True,
            )

        # Process each tenant
        for tenant in active_tenants:
            try:
                logger.info(f"Processing depreciation for tenant: {tenant.company_name}")

                # Run depreciation for this tenant
                with transaction.atomic():
                    tenant_result = FixedAssetService.run_monthly_depreciation(
                        tenant=tenant, period_date=period_date, user=system_user
                    )

                overall_results["tenants_processed"] += 1
                overall_results["total_assets_processed"] += tenant_result.get("processed", 0)
                overall_results["total_depreciation_amount"] += float(
                    tenant_result.get("total_depreciation", 0)
                )

                overall_results["tenant_details"].append(
                    {
                        "tenant_id": str(tenant.id),
                        "tenant_name": tenant.company_name,
                        "status": "success",
                        "assets_processed": tenant_result.get("processed", 0),
                        "assets_skipped": tenant_result.get("skipped", 0),
                        "already_recorded": tenant_result.get("already_recorded", 0),
                        "errors": tenant_result.get("errors", 0),
                        "total_depreciation": float(tenant_result.get("total_depreciation", 0)),
                    }
                )

                logger.info(
                    f"Successfully processed depreciation for {tenant.company_name} - "
                    f"Processed: {tenant_result.get('processed', 0)}, "
                    f"Amount: ${tenant_result.get('total_depreciation', 0)}"
                )

            except Exception as tenant_error:
                overall_results["tenants_failed"] += 1
                overall_results["tenant_details"].append(
                    {
                        "tenant_id": str(tenant.id),
                        "tenant_name": tenant.company_name,
                        "status": "error",
                        "error": str(tenant_error),
                    }
                )

                logger.error(
                    f"Failed to process depreciation for tenant "
                    f"{tenant.company_name}: {str(tenant_error)}",
                    exc_info=True,
                )

                # Log to audit trail for this tenant
                try:
                    AuditLog.objects.create(
                        tenant=tenant,
                        user=system_user,
                        category="ACCOUNTING",
                        action="BATCH_PROCESS_ERROR",
                        severity="ERROR",
                        description=(
                            f"Failed to run monthly depreciation for "
                            f"{period_date.strftime('%B %Y')}: {str(tenant_error)}"
                        ),
                    )
                except Exception as audit_error:
                    logger.error(
                        f"Failed to create audit log for tenant {tenant.company_name}: "
                        f"{str(audit_error)}"
                    )

        # Log overall summary
        logger.info(
            f"Monthly depreciation run completed - "
            f"Period: {period_date}, "
            f"Tenants Processed: {overall_results['tenants_processed']}, "
            f"Tenants Failed: {overall_results['tenants_failed']}, "
            f"Total Assets: {overall_results['total_assets_processed']}, "
            f"Total Depreciation: ${overall_results['total_depreciation_amount']:.2f}"
        )

        return overall_results

    except Exception as e:
        logger.error(f"Critical error in monthly depreciation task: {str(e)}", exc_info=True)

        # Retry the task if we haven't exceeded max retries
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error(
                "Max retries exceeded for monthly depreciation task. "
                "Manual intervention required."
            )
            return {
                "status": "failed",
                "error": str(e),
                "period_date": period_date_str or "auto-calculated",
            }


@shared_task(
    name="apps.accounting.tasks.run_monthly_depreciation_single_tenant",
    bind=True,
    max_retries=3,
    default_retry_delay=180,  # 3 minutes
)
def run_monthly_depreciation_single_tenant(
    self, tenant_id: str, period_date_str: str, user_id: int = None
):
    """
    Run monthly depreciation for a single tenant.

    This task can be called manually or triggered by specific events
    to run depreciation for a single tenant.

    Args:
        tenant_id: UUID of the tenant
        period_date_str: Date string in YYYY-MM-DD format
        user_id: Optional user ID who triggered the task

    Returns:
        Dict with summary of depreciation run for the tenant

    Requirements: 5.3, 5.8
    """
    from apps.accounting.services import FixedAssetService

    try:
        # Get tenant
        tenant = Tenant.objects.get(id=tenant_id, status=Tenant.ACTIVE)

        # Parse period date
        period_date = datetime.strptime(period_date_str, "%Y-%m-%d").date()

        # Get user
        if user_id:
            user = User.objects.get(id=user_id)
        else:
            user = User.objects.filter(username="system", role=User.PLATFORM_ADMIN).first()

            if not user:
                user = User.objects.create_user(
                    username="system",
                    email="system@automated.local",
                    role=User.PLATFORM_ADMIN,
                    is_staff=True,
                    is_active=True,
                )

        logger.info(
            f"Running depreciation for tenant {tenant.company_name} " f"for period {period_date}"
        )

        # Run depreciation
        with transaction.atomic():
            result = FixedAssetService.run_monthly_depreciation(
                tenant=tenant, period_date=period_date, user=user
            )

        logger.info(
            f"Depreciation completed for {tenant.company_name} - "
            f"Processed: {result.get('processed', 0)}, "
            f"Amount: ${result.get('total_depreciation', 0)}"
        )

        return result

    except Tenant.DoesNotExist:
        error_msg = f"Tenant with ID {tenant_id} not found or inactive"
        logger.error(error_msg)
        return {"status": "failed", "error": error_msg}

    except Exception as e:
        logger.error(f"Error running depreciation for tenant {tenant_id}: {str(e)}", exc_info=True)

        # Retry the task
        try:
            raise self.retry(exc=e)
        except self.MaxRetriesExceededError:
            logger.error(f"Max retries exceeded for tenant {tenant_id} depreciation task")
            return {
                "status": "failed",
                "error": str(e),
                "tenant_id": tenant_id,
                "period_date": period_date_str,
            }
