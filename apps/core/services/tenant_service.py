"""
Tenant Service for tenant management operations.

This service handles:
- Tenant creation with owner user in atomic transaction
- Tenant updates with audit logging
- Tenant statistics for Information tab
- Bulk status changes for tenant list operations

Requirements: 1.6, 1.7, 1.11, 2.7, 6.1, 6.2, 6.3, 6.4, 8.4
"""

from datetime import timedelta
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count
from django.template.loader import render_to_string
from django.utils import timezone

if TYPE_CHECKING:
    from apps.core.models import Tenant, User


class TenantService:
    """
    Service for managing tenant lifecycle and operations.

    Provides atomic tenant creation, updates with audit logging,
    statistics calculation, and bulk operations.

    Per Requirements 1.6, 1.7, 1.11, 2.7, 6.1-6.4, 8.4.
    """

    def __init__(self):
        """Initialize the tenant service."""
        from apps.core.services.credential_service import CredentialService
        from apps.core.services.domain_service import DomainService

        self._credential_service = CredentialService()
        self._domain_service = DomainService()

    @transaction.atomic
    def create_tenant_with_owner(
        self,
        tenant_data: dict,
        settings_data: dict,
        owner_data: dict,
        domain_data: dict,
        created_by: "User",
    ) -> tuple["Tenant", "User", str]:
        """
        Create tenant, settings, domain, and owner user atomically.

        This method creates all required records for a new tenant in a single
        atomic transaction. If any step fails, all changes are rolled back.

        Args:
            tenant_data: Dictionary with Tenant model fields:
                - company_name (required): Name of the company
                - slug (optional): URL-friendly identifier, auto-generated if not provided
                - status (optional): Initial status, defaults to ACTIVE
            settings_data: Dictionary with TenantSettings model fields:
                - business_name, business_registration_number, tax_identification_number
                - address_line_1, address_line_2, city, state_province, postal_code, country
                - phone, fax, email, website
                - timezone, currency, date_format
                - require_mfa_for_managers, password_expiry_days
                - primary_color, secondary_color
            owner_data: Dictionary with User model fields:
                - username (required): Owner's username
                - email (required): Owner's email
                - password (optional): If not provided, a secure password is generated
                - phone (optional): Owner's phone number
            domain_data: Dictionary with domain configuration:
                - custom_domain (optional): Custom domain to add
            created_by: The platform admin creating the tenant

        Returns:
            Tuple of (tenant, owner_user, initial_password)
            - tenant: The created Tenant instance
            - owner_user: The created User instance with TENANT_OWNER role
            - initial_password: The plaintext password (for one-time display)

        Raises:
            ValueError: If required fields are missing or validation fails
            IntegrityError: If unique constraints are violated

        Per Requirements 1.6, 1.7, 1.11 for atomic tenant creation.
        """
        from apps.core.audit_models import AuditLog
        from apps.core.models import Tenant, TenantDomain, TenantSettings, User

        # Validate required fields
        if not tenant_data.get("company_name"):
            raise ValueError("company_name is required")
        if not owner_data.get("username"):
            raise ValueError("admin_username is required")
        if not owner_data.get("email"):
            raise ValueError("admin_email is required")

        # Step 1: Create Tenant
        tenant = Tenant.objects.create(
            company_name=tenant_data["company_name"],
            slug=tenant_data.get("slug", ""),  # Will be auto-generated if empty
            status=tenant_data.get("status", Tenant.ACTIVE),
        )

        # Step 2: Create TenantSettings
        settings_fields = {
            "tenant": tenant,
            "business_name": settings_data.get("business_name", ""),
            "business_registration_number": settings_data.get("business_registration_number", ""),
            "tax_identification_number": settings_data.get("tax_identification_number", ""),
            "address_line_1": settings_data.get("address_line_1", ""),
            "address_line_2": settings_data.get("address_line_2", ""),
            "city": settings_data.get("city", ""),
            "state_province": settings_data.get("state_province", ""),
            "postal_code": settings_data.get("postal_code", ""),
            "country": settings_data.get("country", ""),
            "phone": settings_data.get("phone", ""),
            "fax": settings_data.get("fax", ""),
            "email": settings_data.get("email", ""),
            "website": settings_data.get("website", ""),
            "timezone": settings_data.get("timezone", "UTC"),
            "currency": settings_data.get("currency", TenantSettings.CURRENCY_USD),
            "date_format": settings_data.get("date_format", TenantSettings.DATE_FORMAT_MDY),
        }

        # Add optional security settings if provided
        if "require_mfa_for_managers" in settings_data:
            settings_fields["require_mfa_for_managers"] = settings_data["require_mfa_for_managers"]
        if "password_expiry_days" in settings_data:
            settings_fields["password_expiry_days"] = settings_data["password_expiry_days"]
        if "primary_color" in settings_data:
            settings_fields["primary_color"] = settings_data["primary_color"]
        if "secondary_color" in settings_data:
            settings_fields["secondary_color"] = settings_data["secondary_color"]

        TenantSettings.objects.create(**settings_fields)

        # Step 3: Create TenantDomain (subdomain)
        subdomain = self._domain_service.generate_subdomain(tenant.slug)
        TenantDomain.objects.create(
            tenant=tenant,
            domain_type=TenantDomain.DOMAIN_TYPE_SUBDOMAIN,
            domain=subdomain,
            is_primary=True,
            verification_status=TenantDomain.VERIFICATION_VERIFIED,
            verified_at=timezone.now(),
        )

        # Step 3b: Add custom domain if provided
        custom_domain = domain_data.get("custom_domain")
        if custom_domain:
            self._domain_service.add_custom_domain(tenant, custom_domain)

        # Step 4: Create Owner User
        # Generate password if not provided
        password = owner_data.get("password")
        if not password:
            password = self._credential_service.generate_secure_password()
        else:
            # Validate provided password
            is_valid, errors = self._credential_service.validate_password_strength(password)
            if not is_valid:
                raise ValueError(f"Password validation failed: {'; '.join(errors)}")

        owner_user = User.objects.create_user(
            username=owner_data["username"],
            email=owner_data["email"],
            password=password,
            tenant=tenant,
            role=User.TENANT_OWNER,
            phone=owner_data.get("phone", ""),
            language=owner_data.get("language", User.LANGUAGE_ENGLISH),
            theme=owner_data.get("theme", User.THEME_LIGHT),
        )

        # Step 5: Log TENANT_CREATE in AuditLog
        AuditLog.objects.create(
            tenant=tenant,
            user=created_by,
            category=AuditLog.CATEGORY_ADMIN,
            action=AuditLog.ACTION_TENANT_CREATE,
            severity=AuditLog.SEVERITY_INFO,
            description=f"Tenant '{tenant.company_name}' created with owner '{owner_user.username}'",
            content_type=ContentType.objects.get_for_model(Tenant),
            object_id=str(tenant.id),
            new_values={
                "company_name": tenant.company_name,
                "slug": tenant.slug,
                "status": tenant.status,
                "owner_username": owner_user.username,
                "owner_email": owner_user.email,
            },
            metadata={
                "created_by": created_by.username if created_by else "system",
                "subdomain": subdomain,
                "custom_domain": custom_domain,
            },
        )

        return (tenant, owner_user, password)

    @transaction.atomic
    def update_tenant(
        self,
        tenant: "Tenant",
        tenant_data: dict,
        settings_data: dict,
        domain_data: dict,
        modified_by: "User",
    ) -> "Tenant":
        """
        Update tenant and related settings with audit logging.

        Captures old_values and new_values for complete audit trail.

        Args:
            tenant: The Tenant instance to update
            tenant_data: Dictionary with Tenant model fields to update
            settings_data: Dictionary with TenantSettings model fields to update
            domain_data: Dictionary with domain configuration changes
            modified_by: The user making the modification

        Returns:
            The updated Tenant instance

        Per Requirement 2.7 for audit logging with old/new values.
        """
        from apps.core.audit_models import AuditLog
        from apps.core.models import TenantDomain

        old_values = {}
        new_values = {}

        # Track tenant field changes
        tenant_fields = ["company_name", "slug", "status"]
        for field in tenant_fields:
            if field in tenant_data:
                old_value = getattr(tenant, field)
                new_value = tenant_data[field]
                if old_value != new_value:
                    old_values[f"tenant.{field}"] = old_value
                    new_values[f"tenant.{field}"] = new_value
                    setattr(tenant, field, new_value)

        # Save tenant if changed
        if any(f"tenant.{field}" in new_values for field in tenant_fields):
            tenant.save()

        # Track settings field changes
        if settings_data and hasattr(tenant, "settings"):
            settings = tenant.settings
            settings_fields = [
                "business_name",
                "business_registration_number",
                "tax_identification_number",
                "address_line_1",
                "address_line_2",
                "city",
                "state_province",
                "postal_code",
                "country",
                "phone",
                "fax",
                "email",
                "website",
                "timezone",
                "currency",
                "date_format",
                "require_mfa_for_managers",
                "password_expiry_days",
                "primary_color",
                "secondary_color",
            ]

            for field in settings_fields:
                if field in settings_data:
                    old_value = getattr(settings, field)
                    new_value = settings_data[field]
                    if old_value != new_value:
                        old_values[f"settings.{field}"] = (
                            str(old_value) if old_value is not None else None
                        )
                        new_values[f"settings.{field}"] = (
                            str(new_value) if new_value is not None else None
                        )
                        setattr(settings, field, new_value)

            # Save settings if changed
            if any(key.startswith("settings.") for key in new_values):
                settings.save()

        # Handle domain changes
        if domain_data:
            custom_domain = domain_data.get("custom_domain")
            if custom_domain:
                # Check if domain already exists
                existing = TenantDomain.objects.filter(
                    tenant=tenant,
                    domain_type=TenantDomain.DOMAIN_TYPE_CUSTOM,
                    domain=custom_domain,
                ).exists()

                if not existing:
                    self._domain_service.add_custom_domain(tenant, custom_domain)
                    new_values["custom_domain_added"] = custom_domain

        # Log the update if there were changes
        if old_values or new_values:
            AuditLog.objects.create(
                tenant=tenant,
                user=modified_by,
                category=AuditLog.CATEGORY_ADMIN,
                action=AuditLog.ACTION_TENANT_UPDATE,
                severity=AuditLog.SEVERITY_INFO,
                description=f"Tenant '{tenant.company_name}' updated",
                content_type=ContentType.objects.get_for_model(tenant),
                object_id=str(tenant.id),
                old_values=old_values,
                new_values=new_values,
                metadata={
                    "modified_by": modified_by.username if modified_by else "system",
                    "fields_changed": list(new_values.keys()),
                },
            )

        return tenant

    def get_tenant_statistics(self, tenant: "Tenant") -> dict:
        """
        Calculate and return statistics for the Information tab.

        Returns comprehensive statistics about tenant usage including
        user counts, branch information, storage usage, and activity.

        Args:
            tenant: The Tenant instance to get statistics for

        Returns:
            Dictionary with statistics:
            {
                "user_count": int,
                "active_users": int,
                "inactive_users": int,
                "users_by_role": {role: count},
                "branch_count": int,
                "branch_names": [str],
                "storage_used_bytes": int,
                "storage_percentage": float,
                "last_activity_timestamp": datetime or None,
                "last_active_user": str or None,
            }

        Per Requirements 6.1-6.4 for Information tab statistics.
        """
        from apps.core.audit_models import AuditLog
        from apps.core.models import Branch, User

        # User statistics (Requirement 6.1)
        users = User.objects.filter(tenant=tenant)
        user_count = users.count()
        active_users = users.filter(is_active=True).count()
        inactive_users = users.filter(is_active=False).count()

        # Users by role
        users_by_role = {}
        role_counts = users.values("role").annotate(count=Count("id"))
        for item in role_counts:
            role_display = dict(User.ROLE_CHOICES).get(item["role"], item["role"])
            users_by_role[role_display] = item["count"]

        # Branch statistics (Requirement 6.2)
        branches = Branch.objects.filter(tenant=tenant)
        branch_count = branches.count()
        branch_names = list(branches.values_list("name", flat=True))

        # Storage usage (Requirement 6.3)
        storage_used_bytes = self._calculate_storage_usage(tenant)
        # Assume 10GB default limit (from SubscriptionPlan)
        storage_limit_bytes = 10 * 1024 * 1024 * 1024  # 10GB in bytes
        storage_percentage = (
            (storage_used_bytes / storage_limit_bytes * 100) if storage_limit_bytes > 0 else 0
        )

        # Last activity (Requirement 6.4)
        last_activity = AuditLog.objects.filter(tenant=tenant).order_by("-timestamp").first()
        last_activity_timestamp = last_activity.timestamp if last_activity else None
        last_active_user = (
            last_activity.user.username if last_activity and last_activity.user else None
        )

        return {
            "user_count": user_count,
            "active_users": active_users,
            "inactive_users": inactive_users,
            "users_by_role": users_by_role,
            "branch_count": branch_count,
            "branch_names": branch_names,
            "storage_used_bytes": storage_used_bytes,
            "storage_percentage": round(storage_percentage, 2),
            "last_activity_timestamp": last_activity_timestamp,
            "last_active_user": last_active_user,
        }

    def _calculate_storage_usage(self, tenant: "Tenant") -> int:
        """
        Calculate storage usage for a tenant in bytes.

        Calculates total size of media files associated with the tenant.

        Args:
            tenant: The Tenant instance

        Returns:
            Total storage used in bytes
        """
        total_bytes = 0

        # Check tenant logo
        if hasattr(tenant, "settings") and tenant.settings.logo:
            try:
                if tenant.settings.logo.name:
                    total_bytes += tenant.settings.logo.size
            except (FileNotFoundError, ValueError):
                pass

        # In a full implementation, you would also calculate:
        # - Product images from inventory
        # - Document attachments
        # - Other media files
        # This would require iterating through related models

        return total_bytes

    @transaction.atomic
    def bulk_change_status(
        self,
        tenant_ids: list[UUID],
        new_status: str,
        reason: str,
        modified_by: "User",
    ) -> int:
        """
        Bulk status change for multiple tenants with audit logging.

        Changes the status of multiple tenants atomically. If any update
        fails, all changes are rolled back.

        Args:
            tenant_ids: List of tenant UUIDs to update
            new_status: The new status to set (ACTIVE, SUSPENDED, PENDING_DELETION)
            reason: Reason for the status change (for audit log)
            modified_by: The user making the modification

        Returns:
            Count of tenants successfully updated

        Raises:
            ValueError: If new_status is invalid

        Per Requirement 8.4 for bulk status change operations.
        """
        from apps.core.audit_models import AuditLog
        from apps.core.models import Tenant

        # Validate status
        valid_statuses = [Tenant.ACTIVE, Tenant.SUSPENDED, Tenant.PENDING_DELETION]
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status '{new_status}'. Must be one of: {valid_statuses}")

        # Get tenants to update
        tenants = Tenant.objects.filter(id__in=tenant_ids)
        updated_count = 0

        for tenant in tenants:
            old_status = tenant.status

            # Skip if status is already the same
            if old_status == new_status:
                continue

            # Update status
            tenant.status = new_status

            # Handle status-specific fields
            if new_status == Tenant.SUSPENDED:
                tenant.suspended_at = timezone.now()
            elif new_status == Tenant.ACTIVE:
                tenant.suspended_at = None
                tenant.scheduled_deletion_at = None
            elif new_status == Tenant.PENDING_DELETION:
                tenant.scheduled_deletion_at = timezone.now() + timedelta(
                    days=tenant.deletion_grace_period_days
                )

            tenant.save()
            updated_count += 1

            # Determine action type for audit log
            if new_status == Tenant.ACTIVE:
                action = AuditLog.ACTION_TENANT_ACTIVATE
            elif new_status == Tenant.SUSPENDED:
                action = AuditLog.ACTION_TENANT_SUSPEND
            else:
                action = AuditLog.ACTION_TENANT_UPDATE

            # Log each change
            AuditLog.objects.create(
                tenant=tenant,
                user=modified_by,
                category=AuditLog.CATEGORY_ADMIN,
                action=action,
                severity=(
                    AuditLog.SEVERITY_WARNING
                    if new_status != Tenant.ACTIVE
                    else AuditLog.SEVERITY_INFO
                ),
                description=f"Tenant '{tenant.company_name}' status changed from {old_status} to {new_status}. Reason: {reason}",
                content_type=ContentType.objects.get_for_model(Tenant),
                object_id=str(tenant.id),
                old_values={"status": old_status},
                new_values={"status": new_status},
                metadata={
                    "modified_by": modified_by.username if modified_by else "system",
                    "reason": reason,
                    "bulk_operation": True,
                    "total_in_batch": len(tenant_ids),
                },
            )

        return updated_count

    def get_tenant_by_domain(self, domain: str) -> Optional["Tenant"]:
        """
        Get tenant by domain name.

        Looks up tenant by subdomain or custom domain.

        Args:
            domain: The domain name to look up

        Returns:
            The Tenant instance if found, None otherwise
        """
        from apps.core.models import TenantDomain

        try:
            tenant_domain = TenantDomain.objects.select_related("tenant").get(
                domain=domain.lower(),
                verification_status=TenantDomain.VERIFICATION_VERIFIED,
            )
            return tenant_domain.tenant
        except TenantDomain.DoesNotExist:
            return None

    def get_tenant_domains(self, tenant: "Tenant") -> list[dict]:
        """
        Get all domains for a tenant.

        Args:
            tenant: The Tenant instance

        Returns:
            List of domain dictionaries with domain info
        """
        from apps.core.models import TenantDomain

        domains = TenantDomain.objects.filter(tenant=tenant)
        return [
            {
                "id": str(domain.id),
                "domain": domain.domain,
                "domain_type": domain.domain_type,
                "is_primary": domain.is_primary,
                "verification_status": domain.verification_status,
                "verified_at": domain.verified_at,
            }
            for domain in domains
        ]

    def send_welcome_email(
        self,
        tenant: "Tenant",
        owner: "User",
        initial_password: str,
        verification_url: Optional[str] = None,
    ) -> bool:
        """
        Send welcome email to tenant owner with login credentials.

        This method sends a welcome email containing:
        - Login credentials (username and initial password)
        - Tenant access URL
        - Email verification link (if provided)
        - Getting started information

        Args:
            tenant: The Tenant instance
            owner: The owner User instance
            initial_password: The plaintext initial password (one-time display)
            verification_url: Optional email verification URL

        Returns:
            True if email was sent successfully, False otherwise

        Per Requirement 1.10 for welcome email with credentials.
        """
        from apps.core.models import TenantDomain

        try:
            # Get primary domain for tenant access URL
            primary_domain = TenantDomain.objects.filter(tenant=tenant, is_primary=True).first()

            if primary_domain:
                # Build full URL with protocol
                protocol = "https" if not settings.DEBUG else "http"
                tenant_url = f"{protocol}://{primary_domain.domain}"
                login_url = f"{tenant_url}/login/"
            else:
                # Fallback to base URL
                tenant_url = settings.BASE_URL
                login_url = f"{tenant_url}/login/"

            # Prepare email context
            context = {
                "tenant": tenant,
                "owner": owner,
                "initial_password": initial_password,
                "tenant_url": tenant_url,
                "login_url": login_url,
                "verification_url": verification_url,
            }

            # Render HTML and text versions
            html_message = render_to_string("emails/transactional/tenant_welcome.html", context)
            text_message = render_to_string("emails/transactional/tenant_welcome.txt", context)

            # Send email
            send_mail(
                subject=f"Welcome to Jewelry Management System - {tenant.company_name}",
                message=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[owner.email],
                html_message=html_message,
                fail_silently=False,
            )

            return True

        except Exception as e:
            # Log the error but don't fail the tenant creation
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                f"Failed to send welcome email to {owner.email} for tenant {tenant.company_name}: {str(e)}"
            )
            return False
