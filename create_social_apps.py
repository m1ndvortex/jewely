#!/usr/bin/env python
"""Create SocialApp records for all configured providers"""

import os
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from allauth.socialaccount.models import SocialApp
from django.contrib.sites.models import Site

# Get the current site
site = Site.objects.get(id=1)

# GitHub configuration
github_client_id = os.getenv("GITHUB_OAUTH_CLIENT_ID", "")
github_secret = os.getenv("GITHUB_OAUTH_CLIENT_SECRET", "dummy_secret_for_development")

if github_client_id:
    github_app, created = SocialApp.objects.update_or_create(
        provider="github",
        defaults={
            "name": "GitHub",
            "client_id": github_client_id,
            "secret": github_secret,
        },
    )
    github_app.sites.add(site)
    print(f"{'Created' if created else 'Updated'} GitHub SocialApp")
else:
    # Create dummy GitHub app so template doesn't error
    github_app, created = SocialApp.objects.get_or_create(
        provider="github",
        defaults={
            "name": "GitHub",
            "client_id": "github_not_configured",
            "secret": "github_not_configured",
        },
    )
    github_app.sites.add(site)
    print(f"{'Created' if created else 'Found'} GitHub SocialApp (placeholder)")

# Facebook configuration
facebook_client_id = os.getenv("FACEBOOK_OAUTH_CLIENT_ID", "")
facebook_secret = os.getenv("FACEBOOK_OAUTH_CLIENT_SECRET", "dummy_secret_for_development")

if facebook_client_id:
    facebook_app, created = SocialApp.objects.update_or_create(
        provider="facebook",
        defaults={
            "name": "Facebook",
            "client_id": facebook_client_id,
            "secret": facebook_secret,
        },
    )
    facebook_app.sites.add(site)
    print(f"{'Created' if created else 'Updated'} Facebook SocialApp")
else:
    # Create dummy Facebook app so template doesn't error
    facebook_app, created = SocialApp.objects.get_or_create(
        provider="facebook",
        defaults={
            "name": "Facebook",
            "client_id": "facebook_not_configured",
            "secret": "facebook_not_configured",
        },
    )
    facebook_app.sites.add(site)
    print(f"{'Created' if created else 'Found'} Facebook SocialApp (placeholder)")

# Google configuration
google_client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
google_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "dummy_secret_for_development")

if google_client_id:
    google_app, created = SocialApp.objects.update_or_create(
        provider="google",
        defaults={
            "name": "Google",
            "client_id": google_client_id,
            "secret": google_secret,
        },
    )
    google_app.sites.add(site)
    print(f"{'Created' if created else 'Updated'} Google SocialApp")
else:
    # Create dummy Google app so template doesn't error
    google_app, created = SocialApp.objects.get_or_create(
        provider="google",
        defaults={
            "name": "Google",
            "client_id": "google_not_configured",
            "secret": "google_not_configured",
        },
    )
    google_app.sites.add(site)
    print(f"{'Created' if created else 'Found'} Google SocialApp (placeholder)")

print("\n✓ All SocialApp records created/updated!")
print("Note: Check which providers have real OAuth credentials configured.")
