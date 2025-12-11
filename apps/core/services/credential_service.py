"""
Credential Service for password generation, validation, and management.

This service handles:
- Secure password generation meeting strength requirements
- Password strength validation using Django validators
- Password hashing using Django's make_password
- Password reset token creation using PasswordResetTokenGenerator

Requirements: 1.8, 3.9, 7.4
"""

import re
import secrets
import string
from typing import TYPE_CHECKING, Optional

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.password_validation import ValidationError, validate_password
from django.contrib.auth.tokens import PasswordResetTokenGenerator

if TYPE_CHECKING:
    from apps.core.models import User


class CredentialService:
    """
    Service for managing user credentials including password generation,
    validation, hashing, and reset token creation.

    Per Requirements 1.8, 3.9, 7.4 for credential management.
    """

    # Password strength requirements per Requirement 1.8
    MIN_PASSWORD_LENGTH = 8
    REQUIRE_UPPERCASE = True
    REQUIRE_LOWERCASE = True
    REQUIRE_DIGIT = True
    REQUIRE_SPECIAL = True

    # Character sets for password generation
    UPPERCASE_CHARS = string.ascii_uppercase
    LOWERCASE_CHARS = string.ascii_lowercase
    DIGIT_CHARS = string.digits
    SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"

    def __init__(self):
        """Initialize the credential service."""
        self._token_generator = PasswordResetTokenGenerator()

    def generate_secure_password(self, length: int = 16) -> str:
        """
        Generate a secure random password meeting all strength requirements.

        The generated password will contain:
        - At least 1 uppercase letter
        - At least 1 lowercase letter
        - At least 1 digit
        - At least 1 special character
        - Minimum length of 8 characters (default 16)

        Args:
            length: Desired password length (minimum 8, default 16)

        Returns:
            A secure random password string

        Raises:
            ValueError: If length is less than minimum required

        Per Requirement 1.8 for password strength requirements.
        """
        if length < self.MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"Password length must be at least {self.MIN_PASSWORD_LENGTH} characters"
            )

        # Ensure we have at least one of each required character type
        password_chars = [
            secrets.choice(self.UPPERCASE_CHARS),
            secrets.choice(self.LOWERCASE_CHARS),
            secrets.choice(self.DIGIT_CHARS),
            secrets.choice(self.SPECIAL_CHARS),
        ]

        # Fill remaining length with random characters from all sets
        all_chars = (
            self.UPPERCASE_CHARS + self.LOWERCASE_CHARS + self.DIGIT_CHARS + self.SPECIAL_CHARS
        )
        remaining_length = length - len(password_chars)
        password_chars.extend(secrets.choice(all_chars) for _ in range(remaining_length))

        # Shuffle to avoid predictable positions
        # Using Fisher-Yates shuffle with secrets for cryptographic randomness
        password_list = list(password_chars)
        for i in range(len(password_list) - 1, 0, -1):
            j = secrets.randbelow(i + 1)
            password_list[i], password_list[j] = password_list[j], password_list[i]

        return "".join(password_list)

    def validate_password_strength(
        self, password: str, user: Optional["User"] = None
    ) -> tuple[bool, list[str]]:
        """
        Validate password meets all strength requirements.

        Checks:
        - Minimum length (8 characters)
        - At least 1 uppercase letter
        - At least 1 lowercase letter
        - At least 1 digit
        - At least 1 special character
        - Django's built-in validators (common passwords, similarity, etc.)

        Args:
            password: The password to validate
            user: Optional user instance for similarity checking

        Returns:
            Tuple of (is_valid, list_of_error_messages)

        Per Requirement 1.8 for password strength validation.
        """
        errors = []

        # Check minimum length
        if len(password) < self.MIN_PASSWORD_LENGTH:
            errors.append(f"Password must be at least {self.MIN_PASSWORD_LENGTH} characters long")

        # Check for uppercase letter
        if self.REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
            errors.append("Password must contain at least one uppercase letter")

        # Check for lowercase letter
        if self.REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
            errors.append("Password must contain at least one lowercase letter")

        # Check for digit
        if self.REQUIRE_DIGIT and not re.search(r"\d", password):
            errors.append("Password must contain at least one number")

        # Check for special character
        if self.REQUIRE_SPECIAL and not re.search(r"[!@#$%^&*()\-_=+\[\]{}|;:,.<>?]", password):
            errors.append("Password must contain at least one special character")

        # Run Django's built-in validators
        try:
            validate_password(password, user=user)
        except ValidationError as e:
            errors.extend(e.messages)

        return (len(errors) == 0, errors)

    def hash_password(self, password: str) -> str:
        """
        Hash a password using Django's make_password.

        Uses the default hasher configured in settings (Argon2 in this project).

        Args:
            password: The plaintext password to hash

        Returns:
            The hashed password string

        Per Requirement 7.4 for secure password storage.
        """
        return make_password(password)

    def verify_password(self, password: str, hashed: str) -> bool:
        """
        Verify a password against a hash.

        Args:
            password: The plaintext password to verify
            hashed: The hashed password to check against

        Returns:
            True if password matches, False otherwise
        """
        return check_password(password, hashed)

    def create_password_reset_token(self, user: "User") -> str:
        """
        Create a password reset token for a user.

        Uses Django's PasswordResetTokenGenerator which creates a secure,
        time-limited token based on the user's password hash and last login.

        Args:
            user: The user to create a reset token for

        Returns:
            The password reset token string

        Per Requirement 3.10 for password reset functionality.
        """
        return self._token_generator.make_token(user)

    def verify_password_reset_token(self, user: "User", token: str) -> bool:
        """
        Verify a password reset token for a user.

        Args:
            user: The user the token was created for
            token: The token to verify

        Returns:
            True if token is valid, False otherwise
        """
        return self._token_generator.check_token(user, token)
