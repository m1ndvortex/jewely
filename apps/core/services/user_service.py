"""
User Management Service for tenant user operations.

This service handles:
- Creating tenant users with audit logging
- Updating tenant users with change tracking
- Generating temporary passwords with expiry
- Retrieving login history from LoginAttempt model
- Counting failed logins for security monitoring
- Protecting the last tenant owner from deactivation

Requirements: 3.3, 3.4, 3.5, 3.6, 3.8, 3.9, 3.10, 3.11, 10.2
"""

from datetime import timedelta
from typing import TYPE_CHECKING, Optional

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import QuerySet
from django.utils import timezone

if TYPE_CHECKING:
    from apps.core.audit_models import LoginAttempt
    from apps.core.models import TemporaryPassword, Tenant, User


class UserManagementService:
    """
    Service for managing tenant users including creation, updates,
    temporary passwords, and security monitoring.

    Per Requirements 3.3-3.11, 10.2 for user management.
    """

    def __init__(self):
        """Initialize the user management service."""
        from apps.core.services.credential_service import CredentialService

        self._credential_service = CredentialService()

    @transaction.atomic
    def create_tenant_user(
        self,
        tenant: "Tenant",
        user_data: dict,
        created_by: "User",
    ) -> tuple["User", str]:
        """
        Create a new user for a tenant with audit logging.

        Args:
            tenant: The Tenant instance to create user for
            user_data: Dictionary with User model fields:
                - username (required): User's username
                - email (required): User's email
                - password (optional): If not provided, a secure password is generated
                - role (optional): User role, defaults to TENANT_EMPLOYEE
                - branch (optional): Branch FK
                - phone (optional): User's phone number
                - language (optional): User's preferred language
                - theme (optional): User's preferred theme
                - force_mfa (optional): Whether to require MFA
            created_by: The user creating this user (platform admin or tenant owner)

        Returns:
            Tuple of (user, initial_password)
            - user: The created User instance
            - initial_password: The plaintext password (for one-time display)

        Raises:
            ValueError: If required fields are missing or validation fails

        Per Requirements 3.3, 3.4, 3.11 for user creation.
        """
        from apps.core.audit_models import AuditLog
        from apps.core.models import User

        # Validate required fields
        if not user_data.get("username"):
            raise ValueError("username is required")
        if not user_data.get("email"):
            raise ValueError("email is required")

        # Generate password if not provided
        password = user_data.get("password")
        if not password:
            password = self._credential_service.generate_secure_password()
        else:
            # Validate provided password
            is_valid, errors = self._credential_service.validate_password_strength(password)
            if not is_valid:
                raise ValueError(f"Password validation failed: {'; '.join(errors)}")

        # Determine role (default to TENANT_EMPLOYEE)
        role = user_data.get("role", User.TENANT_EMPLOYEE)

        # Validate role is a tenant role (not PLATFORM_ADMIN)
        if role == User.PLATFORM_ADMIN:
            raise ValueError("Cannot create platform admin users through this service")

        # Create user
        user = User.objects.create_user(
            username=user_data["username"],
            email=user_data["email"],
            password=password,
            tenant=tenant,
            role=role,
            branch=user_data.get("branch"),
            phone=user_data.get("phone", ""),
            language=user_data.get("language", User.LANGUAGE_ENGLISH),
            theme=user_data.get("theme", User.THEME_LIGHT),
            is_mfa_enabled=user_data.get("force_mfa", False),
        )

        # Log USER_CREATE in AuditLog
        AuditLog.objects.create(
            tenant=tenant,
            user=created_by,
            category=AuditLog.CATEGORY_ADMIN,
            action=AuditLog.ACTION_USER_CREATE,
            severity=AuditLog.SEVERITY_INFO,
            description=f"User '{user.username}' created for tenant '{tenant.company_name}'",
            content_type=ContentType.objects.get_for_model(User),
            object_id=str(user.id),
            new_values={
                "username": user.username,
                "email": user.email,
                "role": user.role,
                "branch": str(user.branch.id) if user.branch else None,
                "is_mfa_enabled": user.is_mfa_enabled,
            },
            metadata={
                "created_by": created_by.username if created_by else "system",
                "tenant_id": str(tenant.id),
            },
        )

        return (user, password)

    @transaction.atomic
    def update_tenant_user(
        self,
        user: "User",
        user_data: dict,
        modified_by: "User",
    ) -> "User":
        """
        Update a tenant user with change tracking and audit logging.

        Args:
            user: The User instance to update
            user_data: Dictionary with fields to update:
                - email (optional)
                - role (optional)
                - branch (optional)
                - phone (optional)
                - language (optional)
                - theme (optional)
                - is_active (optional)
                - is_mfa_enabled (optional)
            modified_by: The user making the modification

        Returns:
            The updated User instance

        Raises:
            ValueError: If trying to deactivate last owner

        Per Requirements 3.5, 3.11 for user updates.
        """
        from apps.core.audit_models import AuditLog
        from apps.core.models import User

        old_values = {}
        new_values = {}

        # Track changes for audit log
        updatable_fields = [
            "email",
            "role",
            "branch",
            "phone",
            "language",
            "theme",
            "is_active",
            "is_mfa_enabled",
        ]

        for field in updatable_fields:
            if field in user_data:
                old_value = getattr(user, field)
                new_value = user_data[field]

                # Handle branch FK specially
                if field == "branch":
                    old_value = str(old_value.id) if old_value else None
                    new_value = str(new_value.id) if new_value else None

                if old_value != new_value:
                    old_values[field] = old_value
                    new_values[field] = new_value

        # Check if trying to deactivate or change role of last owner
        if "is_active" in user_data and not user_data["is_active"]:
            can_deactivate, reason = self.can_deactivate_user(user)
            if not can_deactivate:
                raise ValueError(reason)

        if "role" in user_data and user_data["role"] != user.role:
            if user.role == User.TENANT_OWNER:
                can_change, reason = self.can_deactivate_user(user)
                if not can_change:
                    raise ValueError("Cannot change role of the last active tenant owner")

        # Apply changes
        for field in updatable_fields:
            if field in user_data:
                setattr(user, field, user_data[field])

        # Save if there were changes
        if new_values:
            user.save()

            # Log USER_UPDATE in AuditLog
            AuditLog.objects.create(
                tenant=user.tenant,
                user=modified_by,
                category=AuditLog.CATEGORY_ADMIN,
                action=AuditLog.ACTION_USER_UPDATE,
                severity=AuditLog.SEVERITY_INFO,
                description=f"User '{user.username}' updated",
                content_type=ContentType.objects.get_for_model(User),
                object_id=str(user.id),
                old_values=old_values,
                new_values=new_values,
                metadata={
                    "modified_by": modified_by.username if modified_by else "system",
                    "fields_changed": list(new_values.keys()),
                },
            )

        return user

    def generate_temporary_password(
        self,
        user: "User",
        expiry_hours: int,
        generated_by: "User",
    ) -> str:
        """
        Generate a temporary password for a user with configurable expiry.

        Creates a TemporaryPassword record and logs the action.

        Args:
            user: The User to generate temporary password for
            expiry_hours: Hours until the password expires (1, 24, or 168 for 7 days)
            generated_by: The admin generating the password

        Returns:
            The plaintext temporary password (for one-time display)

        Per Requirements 3.9, 7.4 for temporary password generation.
        """
        from apps.core.audit_models import AuditLog
        from apps.core.models import TemporaryPassword, User

        # Generate secure password
        password = self._credential_service.generate_secure_password()

        # Hash the password
        password_hash = self._credential_service.hash_password(password)

        # Calculate expiry
        expires_at = timezone.now() + timedelta(hours=expiry_hours)

        # Create TemporaryPassword record
        temp_password = TemporaryPassword.objects.create(
            user=user,
            password_hash=password_hash,
            expires_at=expires_at,
            created_by=generated_by,
        )

        # Log the action
        AuditLog.objects.create(
            tenant=user.tenant,
            user=generated_by,
            category=AuditLog.CATEGORY_ADMIN,
            action=AuditLog.ACTION_USER_UPDATE,
            severity=AuditLog.SEVERITY_WARNING,
            description=f"Temporary password generated for user '{user.username}'",
            content_type=ContentType.objects.get_for_model(User),
            object_id=str(user.id),
            new_values={
                "temporary_password_created": True,
                "expires_at": expires_at.isoformat(),
            },
            metadata={
                "generated_by": generated_by.username if generated_by else "system",
                "expiry_hours": expiry_hours,
                "temp_password_id": str(temp_password.id),
            },
        )

        return password

    def get_login_history(
        self,
        user: "User",
        limit: int = 10,
    ) -> QuerySet["LoginAttempt"]:
        """
        Get recent login attempts for a user.

        Args:
            user: The User to get login history for
            limit: Maximum number of attempts to return (default 10)

        Returns:
            QuerySet of LoginAttempt records ordered by timestamp descending

        Per Requirement 3.6 for login history display.
        """
        from apps.core.audit_models import LoginAttempt

        return LoginAttempt.objects.filter(user=user).order_by("-timestamp")[:limit]

    def get_failed_login_count_24h(self, user: "User") -> int:
        """
        Get count of failed login attempts in the last 24 hours.

        Args:
            user: The User to check

        Returns:
            Count of failed login attempts

        Per Requirement 10.2 for security monitoring.
        """
        from apps.core.audit_models import LoginAttempt

        last_24h = timezone.now() - timedelta(hours=24)

        return (
            LoginAttempt.objects.filter(
                user=user,
                timestamp__gte=last_24h,
            )
            .exclude(result=LoginAttempt.RESULT_SUCCESS)
            .count()
        )

    def can_deactivate_user(self, user: "User") -> tuple[bool, str]:
        """
        Check if a user can be deactivated.

        Prevents deactivation of the last active tenant owner.

        Args:
            user: The User to check

        Returns:
            Tuple of (can_deactivate, reason_if_not)

        Per Requirement 3.8 for last owner protection.
        """
        from apps.core.models import User

        # Platform admins can always be deactivated (not tenant-specific)
        if user.role == User.PLATFORM_ADMIN:
            return (True, "")

        # Non-owners can always be deactivated
        if user.role != User.TENANT_OWNER:
            return (True, "")

        # Check if this is the last active owner for the tenant
        if user.tenant:
            active_owners_count = (
                User.objects.filter(
                    tenant=user.tenant,
                    role=User.TENANT_OWNER,
                    is_active=True,
                )
                .exclude(id=user.id)
                .count()
            )

            if active_owners_count == 0:
                return (
                    False,
                    "Cannot deactivate the last active tenant owner. "
                    "Please assign another owner first.",
                )

        return (True, "")

    def get_users_with_failed_login_warning(
        self,
        tenant: "Tenant",
        threshold: int = 5,
    ) -> list[dict]:
        """
        Get users with failed login count exceeding threshold.

        Args:
            tenant: The Tenant to check users for
            threshold: Number of failed logins to trigger warning (default 5)

        Returns:
            List of dicts with user info and failed login count

        Per Requirement 10.3 for security warning display.
        """
        from apps.core.audit_models import LoginAttempt
        from apps.core.models import User

        last_24h = timezone.now() - timedelta(hours=24)

        users_with_warnings = []

        for user in User.objects.filter(tenant=tenant, is_active=True):
            failed_count = (
                LoginAttempt.objects.filter(
                    user=user,
                    timestamp__gte=last_24h,
                )
                .exclude(result=LoginAttempt.RESULT_SUCCESS)
                .count()
            )

            if failed_count > threshold:
                users_with_warnings.append(
                    {
                        "user_id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "failed_login_count": failed_count,
                    }
                )

        return users_with_warnings

    def send_password_reset_email(
        self,
        user: "User",
        sent_by: "User",
    ) -> bool:
        """
        Send a password reset email to a user.

        Uses Django's password reset mechanism with token generation
        and email sending.

        Args:
            user: The User to send reset email to
            sent_by: The admin sending the reset email

        Returns:
            True if email was sent successfully, False otherwise

        Per Requirement 3.10 for password reset email.
        """
        from django.conf import settings
        from django.contrib.contenttypes.models import ContentType
        from django.core.mail import send_mail
        from django.template.loader import render_to_string
        from django.urls import reverse
        from django.utils import timezone
        from django.utils.encoding import force_bytes
        from django.utils.http import urlsafe_base64_encode

        from apps.core.audit_models import AuditLog
        from apps.core.models import User

        try:
            # Create password reset token
            token = self._credential_service.create_password_reset_token(user)

            # Generate password reset URL
            # Encode user ID for URL
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            # Build reset URL
            # In a multi-tenant system, we need to use the tenant's domain
            from apps.core.models import TenantDomain

            primary_domain = TenantDomain.objects.filter(
                tenant=user.tenant, is_primary=True
            ).first()

            if primary_domain:
                protocol = "https" if not settings.DEBUG else "http"
                base_url = f"{protocol}://{primary_domain.domain}"
            else:
                base_url = settings.BASE_URL

            # Build the password reset URL
            reset_path = reverse("password_reset_confirm", kwargs={"uidb64": uid, "token": token})
            reset_url = f"{base_url}{reset_path}"

            # Prepare email context
            context = {
                "user": user,
                "reset_url": reset_url,
                "expiry_hours": 24,  # Django default is 24 hours
                "timestamp": timezone.now(),
            }

            # Render HTML and text versions
            html_message = render_to_string("emails/transactional/password_reset.html", context)
            text_message = render_to_string("emails/transactional/password_reset.txt", context)

            # Send email
            send_mail(
                subject="Password Reset Request - Jewelry Management System",
                message=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                html_message=html_message,
                fail_silently=False,
            )

            # Log the action
            AuditLog.objects.create(
                tenant=user.tenant,
                user=sent_by,
                category=AuditLog.CATEGORY_ADMIN,
                action=AuditLog.ACTION_USER_UPDATE,
                severity=AuditLog.SEVERITY_INFO,
                description=f"Password reset email sent to user '{user.username}'",
                content_type=ContentType.objects.get_for_model(User),
                object_id=str(user.id),
                new_values={
                    "password_reset_sent": True,
                },
                metadata={
                    "sent_by": sent_by.username if sent_by else "system",
                    "user_email": user.email,
                },
            )

            return True

        except Exception as e:
            # Log the error
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send password reset email to {user.email}: {str(e)}")
            return False

    def verify_temporary_password(
        self,
        user: "User",
        password: str,
    ) -> Optional["TemporaryPassword"]:
        """
        Verify a temporary password for a user.

        Checks if the password matches any valid (not expired, not used)
        temporary password for the user.

        Args:
            user: The User to verify password for
            password: The plaintext password to verify

        Returns:
            The TemporaryPassword record if valid, None otherwise

        Per Requirement 7.4 for temporary password verification.
        """
        from apps.core.models import TemporaryPassword

        # Get all valid temporary passwords for the user
        temp_passwords = TemporaryPassword.objects.filter(
            user=user,
            used_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).order_by("-created_at")

        for temp_pwd in temp_passwords:
            if self._credential_service.verify_password(password, temp_pwd.password_hash):
                return temp_pwd

        return None

    def mark_temporary_password_used(
        self,
        temp_password: "TemporaryPassword",
    ) -> None:
        """
        Mark a temporary password as used.

        Args:
            temp_password: The TemporaryPassword to mark as used
        """
        temp_password.used_at = timezone.now()
        temp_password.save(update_fields=["used_at"])
