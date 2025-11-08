#!/usr/bin/env python3
"""
Validate environment configuration before deployment.

This script checks that all required environment variables are set
and have valid values for the specified environment.

Usage:
    python scripts/validate_env.py --env development
    python scripts/validate_env.py --env staging
    python scripts/validate_env.py --env production
    python scripts/validate_env.py --env production --env-file .env.production
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, Tuple

# Required variables for all environments
REQUIRED_ALL = [
    "DJANGO_SECRET_KEY",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_HOST",
    "REDIS_HOST",
]

# Required for staging and production
REQUIRED_STAGING_PROD = [
    "DJANGO_ALLOWED_HOSTS",
    "SITE_URL",
    "BACKUP_ENCRYPTION_KEY",
    "FIELD_ENCRYPTION_KEY",
    "DEFAULT_FROM_EMAIL",
]

# Required for production only
REQUIRED_PRODUCTION = [
    "R2_ACCESS_KEY_ID",
    "R2_SECRET_ACCESS_KEY",
    "B2_ACCESS_KEY_ID",
    "B2_SECRET_ACCESS_KEY",
    "SENTRY_DSN",
]

# Recommended for production
RECOMMENDED_PRODUCTION = [
    "GOLDAPI_KEY",
    "METALS_API_KEY",
    "TWILIO_ACCOUNT_SID",
    "TWILIO_AUTH_TOKEN",
    "STRIPE_SECRET_KEY",
    "STRIPE_PUBLISHABLE_KEY",
    "EMAIL_HOST",
    "EMAIL_HOST_USER",
    "EMAIL_HOST_PASSWORD",
]


class Colors:
    """ANSI color codes for terminal output."""

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    BOLD = "\033[1m"
    END = "\033[0m"


def load_env_file(env_file: Path) -> Dict[str, str]:
    """Load environment variables from .env file."""
    env_vars = {}
    if not env_file.exists():
        return env_vars

    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                env_vars[key.strip()] = value.strip()

    return env_vars


def check_variable(name: str, env_vars: Dict[str, str], required: bool = True) -> Tuple[bool, str]:
    """Check if a variable is set and valid."""
    value = env_vars.get(name, os.getenv(name, ""))

    if not value:
        if required:
            return False, f"{Colors.RED}✗{Colors.END} {name}: NOT SET (required)"
        else:
            return True, f"{Colors.YELLOW}⚠{Colors.END} {name}: NOT SET (recommended)"

    # Check for placeholder values
    if "CHANGE_THIS" in value or "change-in-production" in value:
        return False, f"{Colors.RED}✗{Colors.END} {name}: Contains placeholder value"

    # Check SECRET_KEY length
    if name == "DJANGO_SECRET_KEY" and len(value) < 50:
        return False, f"{Colors.RED}✗{Colors.END} {name}: Too short (minimum 50 characters)"

    # Check encryption keys are base64
    if "ENCRYPTION_KEY" in name:
        try:
            from base64 import urlsafe_b64decode

            urlsafe_b64decode(value)
        except Exception:
            return False, f"{Colors.RED}✗{Colors.END} {name}: Invalid base64 encoding"

    # Check URLs
    if name == "SITE_URL":
        if not value.startswith(("http://", "https://")):
            return False, f"{Colors.RED}✗{Colors.END} {name}: Must start with http:// or https://"

    # Check email
    if name == "DEFAULT_FROM_EMAIL":
        if "@" not in value:
            return False, f"{Colors.RED}✗{Colors.END} {name}: Invalid email format"

    return True, f"{Colors.GREEN}✓{Colors.END} {name}: OK"


def validate_environment(env: str, env_file: Path = None) -> bool:
    """Validate environment configuration."""
    print(f"\n{Colors.BOLD}Validating {env.upper()} environment{Colors.END}")
    print("=" * 80)

    # Load environment variables
    env_vars = {}
    if env_file:
        env_vars = load_env_file(env_file)
        print(f"Loaded variables from: {env_file}")
    else:
        print("Checking system environment variables")

    print()

    # Determine required variables based on environment
    required_vars = REQUIRED_ALL.copy()
    if env in ["staging", "production"]:
        required_vars.extend(REQUIRED_STAGING_PROD)
    if env == "production":
        required_vars.extend(REQUIRED_PRODUCTION)

    # Check required variables
    all_valid = True
    errors = []
    warnings = []

    print(f"{Colors.BOLD}Required Variables:{Colors.END}")
    for var in required_vars:
        valid, message = check_variable(var, env_vars, required=True)
        print(f"  {message}")
        if not valid:
            all_valid = False
            errors.append(message)

    # Check recommended variables for production
    if env == "production":
        print(f"\n{Colors.BOLD}Recommended Variables:{Colors.END}")
        for var in RECOMMENDED_PRODUCTION:
            valid, message = check_variable(var, env_vars, required=False)
            print(f"  {message}")
            if not valid:
                warnings.append(message)

    # Check DJANGO_SETTINGS_MODULE
    print(f"\n{Colors.BOLD}Settings Module:{Colors.END}")
    settings_module = env_vars.get(
        "DJANGO_SETTINGS_MODULE", os.getenv("DJANGO_SETTINGS_MODULE", "")
    )
    expected_module = f"config.settings.{env}"

    if settings_module == expected_module:
        print(f"  {Colors.GREEN}✓{Colors.END} DJANGO_SETTINGS_MODULE: {settings_module}")
    elif settings_module:
        print(f"  {Colors.YELLOW}⚠{Colors.END} DJANGO_SETTINGS_MODULE: {settings_module}")
        print(f"    Expected: {expected_module}")
        warnings.append(f"DJANGO_SETTINGS_MODULE mismatch")
    else:
        print(f"  {Colors.RED}✗{Colors.END} DJANGO_SETTINGS_MODULE: NOT SET")
        print(f"    Expected: {expected_module}")
        errors.append("DJANGO_SETTINGS_MODULE not set")
        all_valid = False

    # Summary
    print("\n" + "=" * 80)
    if all_valid and not warnings:
        print(f"{Colors.GREEN}{Colors.BOLD}✓ All checks passed!{Colors.END}")
        print(f"{Colors.GREEN}Environment is ready for {env} deployment.{Colors.END}")
        return True
    elif all_valid and warnings:
        print(f"{Colors.YELLOW}{Colors.BOLD}⚠ Validation passed with warnings{Colors.END}")
        print(f"{Colors.YELLOW}Some recommended variables are missing.{Colors.END}")
        print(f"Warnings: {len(warnings)}")
        return True
    else:
        print(f"{Colors.RED}{Colors.BOLD}✗ Validation failed!{Colors.END}")
        print(f"{Colors.RED}Errors: {len(errors)}{Colors.END}")
        if warnings:
            print(f"{Colors.YELLOW}Warnings: {len(warnings)}{Colors.END}")
        print(f"\n{Colors.BOLD}Action required:{Colors.END}")
        print("1. Fix all errors before deploying")
        print("2. Review warnings and set recommended variables")
        print("3. Run this script again to verify")
        return False


def main():
    parser = argparse.ArgumentParser(description="Validate environment configuration")
    parser.add_argument(
        "--env",
        required=True,
        choices=["development", "staging", "production"],
        help="Environment to validate",
    )
    parser.add_argument("--env-file", type=Path, help="Path to .env file (optional)")
    args = parser.parse_args()

    # If no env file specified, try to find it
    if not args.env_file:
        default_files = [
            Path(".env"),
            Path(f".env.{args.env}"),
        ]
        for f in default_files:
            if f.exists():
                args.env_file = f
                break

    success = validate_environment(args.env, args.env_file)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
