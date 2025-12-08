"""
Property-based tests for required fields validation in tenant creation.

**Feature: advanced-tenant-management, Property 1: Required Fields Validation**
**Validates: Requirements 1.2**

Property 1: Required Fields Validation
*For any* tenant creation request missing company_name, admin_email, admin_username,
or admin_password, the system SHALL reject the request with appropriate validation errors.
"""

import string
from datetime import timedelta

import pytest
from hypothesis import assume, given
from hypothesis import settings as hypothesis_settings
from hypothesis import strategies as st

from apps.core.forms import EnhancedTenantCreateForm

# Character sets for generating valid data
UPPERCASE_CHARS = string.ascii_uppercase
LOWERCASE_CHARS = string.ascii_lowercase
DIGIT_CHARS = string.digits
SPECIAL_CHARS = "!@#$%^&*()_+-=[]{}|;:,.<>?"
ALL_CHARS = UPPERCASE_CHARS + LOWERCASE_CHARS + DIGIT_CHARS + SPECIAL_CHARS

# Minimum password length per Django settings
MIN_PASSWORD_LENGTH = 12


# ============================================================================
# Strategies for generating valid form data
# ============================================================================


@st.composite
def valid_company_name_strategy(draw):
    """Generate valid company names (at least 2 characters)."""
    # Generate a name with letters and spaces, min 2 chars
    name = draw(st.text(alphabet=string.ascii_letters + " ", min_size=2, max_size=50))
    # Ensure it's not just whitespace
    assume(name.strip())
    return name.strip()


@st.composite
def valid_email_strategy(draw):
    """Generate valid email addresses."""
    local_part = draw(
        st.text(alphabet=string.ascii_lowercase + string.digits, min_size=3, max_size=15)
    )
    domain = draw(st.text(alphabet=string.ascii_lowercase, min_size=3, max_size=10))
    tld = draw(st.sampled_from(["com", "org", "net", "io", "co"]))
    assume(local_part and domain)
    return f"{local_part}@{domain}.{tld}"


@st.composite
def valid_username_strategy(draw):
    """Generate valid usernames."""
    username = draw(
        st.text(alphabet=string.ascii_lowercase + string.digits + "_", min_size=3, max_size=20)
    )
    # Ensure it starts with a letter
    assume(username and username[0].isalpha())
    return username


@st.composite
def valid_password_strategy(draw):
    """Generate passwords that meet all strength requirements."""
    # Draw at least one of each required character type
    uppercase = draw(st.text(alphabet=UPPERCASE_CHARS, min_size=1, max_size=2))
    lowercase = draw(st.text(alphabet=LOWERCASE_CHARS, min_size=1, max_size=2))
    digit = draw(st.text(alphabet=DIGIT_CHARS, min_size=1, max_size=2))
    special = draw(st.text(alphabet=SPECIAL_CHARS, min_size=1, max_size=2))

    # Calculate how many more characters we need to reach minimum length
    current_length = len(uppercase) + len(lowercase) + len(digit) + len(special)
    min_filler = max(0, MIN_PASSWORD_LENGTH - current_length)

    # Add filler characters from all character sets
    filler = draw(st.text(alphabet=ALL_CHARS, min_size=min_filler, max_size=min_filler + 4))

    # Combine all parts
    password = uppercase + lowercase + digit + special + filler
    return password


@st.composite
def empty_or_whitespace_strategy(draw):
    """Generate empty strings or strings with only whitespace."""
    choice = draw(st.integers(min_value=0, max_value=2))
    if choice == 0:
        return ""
    elif choice == 1:
        return " " * draw(st.integers(min_value=1, max_value=5))
    else:
        return "\t" * draw(st.integers(min_value=1, max_size=3))


@st.composite
def valid_form_data_strategy(draw):
    """Generate complete valid form data for tenant creation."""
    company_name = draw(valid_company_name_strategy())
    email = draw(valid_email_strategy())
    admin_username = draw(valid_username_strategy())
    admin_email = draw(valid_email_strategy())
    password = draw(valid_password_strategy())

    return {
        "company_name": company_name,
        "email": email,
        "admin_username": admin_username,
        "admin_email": admin_email,
        "admin_password": password,
        "admin_password_confirm": password,
        "status": "ACTIVE",
        "currency": "USD",
        "date_format": "MDY",
    }


# ============================================================================
# Property Tests
# ============================================================================


@pytest.mark.django_db
class TestRequiredFieldsValidation:
    """
    **Feature: advanced-tenant-management, Property 1: Required Fields Validation**
    **Validates: Requirements 1.2**

    Property tests for required fields validation ensuring:
    1. Missing company_name causes validation failure
    2. Missing admin_email causes validation failure
    3. Missing admin_username causes validation failure
    4. Missing admin_password causes validation failure
    5. Complete valid data passes validation
    """

    @given(form_data=valid_form_data_strategy())
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
    )
    def test_missing_company_name_fails_validation(self, form_data):
        """
        **Feature: advanced-tenant-management, Property 1: Required Fields Validation**
        **Validates: Requirements 1.2**

        For any tenant creation request missing company_name,
        the system SHALL reject the request with a validation error.
        """
        # Remove company_name from form data
        form_data_without_company = form_data.copy()
        form_data_without_company["company_name"] = ""

        form = EnhancedTenantCreateForm(data=form_data_without_company)

        # Property: Form should be invalid when company_name is missing
        assert not form.is_valid(), "Form should be invalid when company_name is missing"

        # Property: Error should be on company_name field
        assert (
            "company_name" in form.errors
        ), f"Error should be on company_name field. Errors: {form.errors}"

    @given(form_data=valid_form_data_strategy())
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
    )
    def test_whitespace_company_name_fails_validation(self, form_data):
        """
        **Feature: advanced-tenant-management, Property 1: Required Fields Validation**
        **Validates: Requirements 1.2**

        For any tenant creation request with whitespace-only company_name,
        the system SHALL reject the request with a validation error.
        """
        # Set company_name to whitespace
        form_data_whitespace = form_data.copy()
        form_data_whitespace["company_name"] = "   "

        form = EnhancedTenantCreateForm(data=form_data_whitespace)

        # Property: Form should be invalid when company_name is whitespace
        assert not form.is_valid(), "Form should be invalid when company_name is whitespace"

        # Property: Error should be on company_name field
        assert (
            "company_name" in form.errors
        ), f"Error should be on company_name field. Errors: {form.errors}"

    @given(form_data=valid_form_data_strategy())
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
    )
    def test_missing_admin_username_fails_validation(self, form_data):
        """
        **Feature: advanced-tenant-management, Property 1: Required Fields Validation**
        **Validates: Requirements 1.2**

        For any tenant creation request missing admin_username,
        the system SHALL reject the request with a validation error.
        """
        # Remove admin_username from form data
        form_data_without_username = form_data.copy()
        form_data_without_username["admin_username"] = ""

        form = EnhancedTenantCreateForm(data=form_data_without_username)

        # Property: Form should be invalid when admin_username is missing
        assert not form.is_valid(), "Form should be invalid when admin_username is missing"

        # Property: Error should be on admin_username field
        assert (
            "admin_username" in form.errors
        ), f"Error should be on admin_username field. Errors: {form.errors}"

    @given(form_data=valid_form_data_strategy())
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
    )
    def test_missing_admin_email_fails_validation(self, form_data):
        """
        **Feature: advanced-tenant-management, Property 1: Required Fields Validation**
        **Validates: Requirements 1.2**

        For any tenant creation request missing admin_email,
        the system SHALL reject the request with a validation error.
        """
        # Remove admin_email from form data
        form_data_without_email = form_data.copy()
        form_data_without_email["admin_email"] = ""

        form = EnhancedTenantCreateForm(data=form_data_without_email)

        # Property: Form should be invalid when admin_email is missing
        assert not form.is_valid(), "Form should be invalid when admin_email is missing"

        # Property: Error should be on admin_email field
        assert (
            "admin_email" in form.errors
        ), f"Error should be on admin_email field. Errors: {form.errors}"

    @given(form_data=valid_form_data_strategy())
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
    )
    def test_missing_admin_password_fails_validation(self, form_data):
        """
        **Feature: advanced-tenant-management, Property 1: Required Fields Validation**
        **Validates: Requirements 1.2**

        For any tenant creation request missing admin_password,
        the system SHALL reject the request with a validation error.
        """
        # Remove admin_password from form data
        form_data_without_password = form_data.copy()
        form_data_without_password["admin_password"] = ""
        form_data_without_password["admin_password_confirm"] = ""

        form = EnhancedTenantCreateForm(data=form_data_without_password)

        # Property: Form should be invalid when admin_password is missing
        assert not form.is_valid(), "Form should be invalid when admin_password is missing"

        # Property: Error should be on admin_password field
        assert (
            "admin_password" in form.errors
        ), f"Error should be on admin_password field. Errors: {form.errors}"

    @given(form_data=valid_form_data_strategy())
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
    )
    def test_missing_business_email_fails_validation(self, form_data):
        """
        **Feature: advanced-tenant-management, Property 1: Required Fields Validation**
        **Validates: Requirements 1.2**

        For any tenant creation request missing business email,
        the system SHALL reject the request with a validation error.
        """
        # Remove email (business email) from form data
        form_data_without_email = form_data.copy()
        form_data_without_email["email"] = ""

        form = EnhancedTenantCreateForm(data=form_data_without_email)

        # Property: Form should be invalid when email is missing
        assert not form.is_valid(), "Form should be invalid when business email is missing"

        # Property: Error should be on email field
        assert "email" in form.errors, f"Error should be on email field. Errors: {form.errors}"

    @given(
        missing_field=st.sampled_from(
            ["company_name", "admin_username", "admin_email", "admin_password", "email"]
        ),
        form_data=valid_form_data_strategy(),
    )
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
    )
    def test_any_missing_required_field_fails_validation(self, missing_field, form_data):
        """
        **Feature: advanced-tenant-management, Property 1: Required Fields Validation**
        **Validates: Requirements 1.2**

        For any tenant creation request missing any required field
        (company_name, admin_email, admin_username, admin_password, or business email),
        the system SHALL reject the request with appropriate validation errors.
        """
        # Remove the specified required field
        form_data_incomplete = form_data.copy()
        form_data_incomplete[missing_field] = ""

        # Also clear password confirm if password is being removed
        if missing_field == "admin_password":
            form_data_incomplete["admin_password_confirm"] = ""

        form = EnhancedTenantCreateForm(data=form_data_incomplete)

        # Property: Form should be invalid when any required field is missing
        assert not form.is_valid(), f"Form should be invalid when {missing_field} is missing"

        # Property: Error should be on the missing field
        assert (
            missing_field in form.errors
        ), f"Error should be on {missing_field} field. Errors: {form.errors}"

    @given(num_missing=st.integers(min_value=2, max_value=5), form_data=valid_form_data_strategy())
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
    )
    def test_multiple_missing_required_fields_all_reported(self, num_missing, form_data):
        """
        **Feature: advanced-tenant-management, Property 1: Required Fields Validation**
        **Validates: Requirements 1.2**

        For any tenant creation request missing multiple required fields,
        the system SHALL report validation errors for all missing fields.
        """
        required_fields = [
            "company_name",
            "admin_username",
            "admin_email",
            "admin_password",
            "email",
        ]

        # Select fields to remove (up to num_missing)
        fields_to_remove = required_fields[: min(num_missing, len(required_fields))]

        # Remove the selected fields
        form_data_incomplete = form_data.copy()
        for field in fields_to_remove:
            form_data_incomplete[field] = ""

        # Also clear password confirm if password is being removed
        if "admin_password" in fields_to_remove:
            form_data_incomplete["admin_password_confirm"] = ""

        form = EnhancedTenantCreateForm(data=form_data_incomplete)

        # Property: Form should be invalid
        assert (
            not form.is_valid()
        ), f"Form should be invalid when multiple required fields are missing"

        # Property: All missing required fields should have errors
        for field in fields_to_remove:
            assert (
                field in form.errors
            ), f"Error should be reported for missing field {field}. Errors: {form.errors}"

    @given(form_data=valid_form_data_strategy())
    @hypothesis_settings(
        max_examples=100,
        deadline=timedelta(seconds=10),
    )
    def test_validation_is_deterministic(self, form_data):
        """
        **Feature: advanced-tenant-management, Property 1: Required Fields Validation**
        **Validates: Requirements 1.2**

        For any form data, validation results SHALL be deterministic
        (same input always produces same validation result).
        """
        # Remove a required field to test validation
        form_data_incomplete = form_data.copy()
        form_data_incomplete["company_name"] = ""

        # Validate multiple times
        form1 = EnhancedTenantCreateForm(data=form_data_incomplete)
        form2 = EnhancedTenantCreateForm(data=form_data_incomplete)
        form3 = EnhancedTenantCreateForm(data=form_data_incomplete)

        result1 = form1.is_valid()
        result2 = form2.is_valid()
        result3 = form3.is_valid()

        # Property: Validation should be deterministic
        assert (
            result1 == result2 == result3
        ), f"Validation is not deterministic. Results: {result1}, {result2}, {result3}"

        # Property: Errors should be the same
        assert set(form1.errors.keys()) == set(form2.errors.keys()) == set(form3.errors.keys()), (
            f"Error fields are not deterministic. "
            f"Errors: {form1.errors.keys()}, {form2.errors.keys()}, {form3.errors.keys()}"
        )
