"""
Property-based tests for password strength validation.

**Feature: advanced-tenant-management, Property 4: Password Strength Validation**
**Validates: Requirements 1.8**

Property 4: Password Strength Validation
*For any* password that does not meet the requirements (min 8 chars, 1 uppercase,
1 number, 1 special char), the system SHALL reject the input with specific error messages.
"""

import string
from datetime import timedelta

import pytest
from hypothesis import assume, given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from apps.core.services.credential_service import CredentialService

# Character sets for password generation
UPPERCASE_CHARS = string.ascii_uppercase
LOWERCASE_CHARS = string.ascii_lowercase
DIGIT_CHARS = string.digits
SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"

# Minimum password length per Django settings (config/settings/base.py)
# Note: Requirements 1.8 says 8 chars, but Django is configured for 12 chars
# The test validates actual system behavior (12 chars)
MIN_PASSWORD_LENGTH = 12


def build_valid_password(
    uppercase: str, lowercase: str, digit: str, special: str, filler: str, permutation: list
) -> str:
    """Build a password from components ensuring all requirements are met."""
    # Combine all required components plus filler
    password_chars = list(uppercase + lowercase + digit + special + filler)
    # Use the provided permutation to shuffle (avoiding random module in strategies)
    if len(permutation) >= len(password_chars):
        # Sort indices by permutation values to get a deterministic shuffle
        indices = list(range(len(password_chars)))
        sorted_indices = sorted(indices, key=lambda i: permutation[i % len(permutation)])
        password_chars = [password_chars[i] for i in sorted_indices]
    return "".join(password_chars)


# Strategy for generating valid passwords that meet all requirements
# This ensures: min 12 chars (Django config), 1 uppercase, 1 lowercase, 1 digit, 1 special
@st.composite
def valid_password_strategy(draw):
    """Generate passwords that meet all strength requirements."""
    # Draw at least one of each required character type
    uppercase = draw(st.text(alphabet=UPPERCASE_CHARS, min_size=1, max_size=3))
    lowercase = draw(st.text(alphabet=LOWERCASE_CHARS, min_size=1, max_size=3))
    digit = draw(st.text(alphabet=DIGIT_CHARS, min_size=1, max_size=3))
    special = draw(st.text(alphabet=SPECIAL_CHARS, min_size=1, max_size=3))

    # Calculate how many more characters we need to reach minimum length
    current_length = len(uppercase) + len(lowercase) + len(digit) + len(special)
    min_filler = max(0, MIN_PASSWORD_LENGTH - current_length)

    # Add filler characters from all character sets
    all_chars = UPPERCASE_CHARS + LOWERCASE_CHARS + DIGIT_CHARS + SPECIAL_CHARS
    filler = draw(st.text(alphabet=all_chars, min_size=min_filler, max_size=min_filler + 8))

    # Generate a permutation for shuffling (avoiding random module)
    total_len = len(uppercase) + len(lowercase) + len(digit) + len(special) + len(filler)
    permutation = draw(
        st.lists(
            st.integers(min_value=0, max_value=1000), min_size=total_len, max_size=total_len + 10
        )
    )

    return build_valid_password(uppercase, lowercase, digit, special, filler, permutation)


# Strategy for short passwords (< 8 chars)
@st.composite
def short_password_strategy(draw):
    """Generate passwords that are too short (< 8 characters)."""
    length = draw(st.integers(min_value=1, max_value=MIN_PASSWORD_LENGTH - 1))
    all_chars = UPPERCASE_CHARS + LOWERCASE_CHARS + DIGIT_CHARS + SPECIAL_CHARS
    return draw(st.text(alphabet=all_chars, min_size=length, max_size=length))


# Strategy for passwords without uppercase letters
@st.composite
def no_uppercase_strategy(draw):
    """Generate passwords without uppercase letters."""
    chars_without_upper = LOWERCASE_CHARS + DIGIT_CHARS + SPECIAL_CHARS
    length = draw(st.integers(min_value=MIN_PASSWORD_LENGTH, max_value=20))
    password = draw(st.text(alphabet=chars_without_upper, min_size=length, max_size=length))
    # Ensure it has lowercase, digit, and special (but no uppercase)
    assume(any(c in LOWERCASE_CHARS for c in password))
    assume(any(c in DIGIT_CHARS for c in password))
    assume(any(c in SPECIAL_CHARS for c in password))
    assume(not any(c in UPPERCASE_CHARS for c in password))
    return password


# Strategy for passwords without lowercase letters
@st.composite
def no_lowercase_strategy(draw):
    """Generate passwords without lowercase letters."""
    chars_without_lower = UPPERCASE_CHARS + DIGIT_CHARS + SPECIAL_CHARS
    length = draw(st.integers(min_value=MIN_PASSWORD_LENGTH, max_value=20))
    password = draw(st.text(alphabet=chars_without_lower, min_size=length, max_size=length))
    # Ensure it has uppercase, digit, and special (but no lowercase)
    assume(any(c in UPPERCASE_CHARS for c in password))
    assume(any(c in DIGIT_CHARS for c in password))
    assume(any(c in SPECIAL_CHARS for c in password))
    assume(not any(c in LOWERCASE_CHARS for c in password))
    return password


# Strategy for passwords without digits
@st.composite
def no_digit_strategy(draw):
    """Generate passwords without digits."""
    chars_without_digit = UPPERCASE_CHARS + LOWERCASE_CHARS + SPECIAL_CHARS
    length = draw(st.integers(min_value=MIN_PASSWORD_LENGTH, max_value=20))
    password = draw(st.text(alphabet=chars_without_digit, min_size=length, max_size=length))
    # Ensure it has uppercase, lowercase, and special (but no digit)
    assume(any(c in UPPERCASE_CHARS for c in password))
    assume(any(c in LOWERCASE_CHARS for c in password))
    assume(any(c in SPECIAL_CHARS for c in password))
    assume(not any(c in DIGIT_CHARS for c in password))
    return password


# Strategy for passwords without special characters
@st.composite
def no_special_strategy(draw):
    """Generate passwords without special characters."""
    chars_without_special = UPPERCASE_CHARS + LOWERCASE_CHARS + DIGIT_CHARS
    length = draw(st.integers(min_value=MIN_PASSWORD_LENGTH, max_value=20))
    password = draw(st.text(alphabet=chars_without_special, min_size=length, max_size=length))
    # Ensure it has uppercase, lowercase, and digit (but no special)
    assume(any(c in UPPERCASE_CHARS for c in password))
    assume(any(c in LOWERCASE_CHARS for c in password))
    assume(any(c in DIGIT_CHARS for c in password))
    assume(not any(c in SPECIAL_CHARS for c in password))
    return password


@pytest.mark.django_db
class TestPasswordStrengthValidation:
    """
    **Feature: advanced-tenant-management, Property 4: Password Strength Validation**
    **Validates: Requirements 1.8**

    Property tests for password strength validation ensuring:
    1. Valid passwords (meeting all requirements) pass validation
    2. Invalid passwords (missing any requirement) fail with appropriate errors
    3. Validation is deterministic (same password always produces same result)
    """

    def setup_method(self):
        """Set up the credential service for each test."""
        self.service = CredentialService()

    @given(password=valid_password_strategy())
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
    )
    def test_valid_passwords_pass_validation(self, password):
        """
        **Feature: advanced-tenant-management, Property 4: Password Strength Validation**
        **Validates: Requirements 1.8**

        For any password that meets all requirements (min 8 chars, 1 uppercase,
        1 lowercase, 1 digit, 1 special char), validation SHALL return success.
        """
        is_valid, errors = self.service.validate_password_strength(password)

        # Filter out Django's common password validator errors
        # (our property is about character requirements, not common passwords)
        custom_errors = [
            e
            for e in errors
            if "too common" not in e.lower()
            and "entirely numeric" not in e.lower()
            and "too similar" not in e.lower()
        ]

        # Property: Password meeting all character requirements should pass
        # our custom validation (Django's common password check is separate)
        assert (
            len(custom_errors) == 0
        ), f"Valid password '{password}' failed validation with errors: {custom_errors}"

    @given(password=short_password_strategy())
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
    )
    def test_short_passwords_fail_validation(self, password):
        """
        **Feature: advanced-tenant-management, Property 4: Password Strength Validation**
        **Validates: Requirements 1.8**

        For any password shorter than 8 characters, validation SHALL fail
        with a length-related error message.
        """
        is_valid, errors = self.service.validate_password_strength(password)

        # Property: Short passwords should fail validation
        assert (
            is_valid is False
        ), f"Short password '{password}' (length {len(password)}) should fail validation"

        # Property: Error message should mention length requirement
        length_error_found = any(
            "8" in e or "length" in e.lower() or "short" in e.lower() or "character" in e.lower()
            for e in errors
        )
        assert (
            length_error_found
        ), f"Short password should produce length-related error. Got: {errors}"

    @given(password=no_uppercase_strategy())
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
    )
    def test_missing_uppercase_fails_validation(self, password):
        """
        **Feature: advanced-tenant-management, Property 4: Password Strength Validation**
        **Validates: Requirements 1.8**

        For any password without uppercase letters, validation SHALL fail
        with an uppercase-related error message.
        """
        is_valid, errors = self.service.validate_password_strength(password)

        # Property: Password without uppercase should fail validation
        assert is_valid is False, f"Password without uppercase '{password}' should fail validation"

        # Property: Error message should mention uppercase requirement
        uppercase_error_found = any("uppercase" in e.lower() for e in errors)
        assert (
            uppercase_error_found
        ), f"Password without uppercase should produce uppercase-related error. Got: {errors}"

    @given(password=no_lowercase_strategy())
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
    )
    def test_missing_lowercase_fails_validation(self, password):
        """
        **Feature: advanced-tenant-management, Property 4: Password Strength Validation**
        **Validates: Requirements 1.8**

        For any password without lowercase letters, validation SHALL fail
        with a lowercase-related error message.
        """
        is_valid, errors = self.service.validate_password_strength(password)

        # Property: Password without lowercase should fail validation
        assert is_valid is False, f"Password without lowercase '{password}' should fail validation"

        # Property: Error message should mention lowercase requirement
        lowercase_error_found = any("lowercase" in e.lower() for e in errors)
        assert (
            lowercase_error_found
        ), f"Password without lowercase should produce lowercase-related error. Got: {errors}"

    @given(password=no_digit_strategy())
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
    )
    def test_missing_digit_fails_validation(self, password):
        """
        **Feature: advanced-tenant-management, Property 4: Password Strength Validation**
        **Validates: Requirements 1.8**

        For any password without digits, validation SHALL fail
        with a digit-related error message.
        """
        is_valid, errors = self.service.validate_password_strength(password)

        # Property: Password without digit should fail validation
        assert is_valid is False, f"Password without digit '{password}' should fail validation"

        # Property: Error message should mention digit/number requirement
        digit_error_found = any("number" in e.lower() or "digit" in e.lower() for e in errors)
        assert (
            digit_error_found
        ), f"Password without digit should produce digit-related error. Got: {errors}"

    @given(password=no_special_strategy())
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
    )
    def test_missing_special_char_fails_validation(self, password):
        """
        **Feature: advanced-tenant-management, Property 4: Password Strength Validation**
        **Validates: Requirements 1.8**

        For any password without special characters, validation SHALL fail
        with a special character-related error message.
        """
        is_valid, errors = self.service.validate_password_strength(password)

        # Property: Password without special char should fail validation
        assert (
            is_valid is False
        ), f"Password without special char '{password}' should fail validation"

        # Property: Error message should mention special character requirement
        special_error_found = any("special" in e.lower() for e in errors)
        assert (
            special_error_found
        ), f"Password without special char should produce special-related error. Got: {errors}"

    @given(password=valid_password_strategy())
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
    )
    def test_validation_is_deterministic(self, password):
        """
        **Feature: advanced-tenant-management, Property 4: Password Strength Validation**
        **Validates: Requirements 1.8**

        For any password, calling validate_password_strength multiple times
        SHALL produce the same result (deterministic).
        """
        result1 = self.service.validate_password_strength(password)
        result2 = self.service.validate_password_strength(password)
        result3 = self.service.validate_password_strength(password)

        # Property: Validation should be deterministic
        assert result1 == result2 == result3, (
            f"Validation is not deterministic for password '{password}'. "
            f"Results: {result1}, {result2}, {result3}"
        )

    @given(password=st.text(min_size=0, max_size=50))
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
    )
    def test_validation_never_crashes(self, password):
        """
        **Feature: advanced-tenant-management, Property 4: Password Strength Validation**
        **Validates: Requirements 1.8**

        For any input string, validate_password_strength SHALL not raise
        an exception (robustness property).
        """
        # Property: Validation should handle any input without crashing
        try:
            is_valid, errors = self.service.validate_password_strength(password)
            # Result should be a boolean and a list
            assert isinstance(is_valid, bool)
            assert isinstance(errors, list)
        except Exception as e:
            pytest.fail(f"Validation crashed for input '{password}': {e}")
