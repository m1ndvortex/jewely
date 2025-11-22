#!/usr/bin/env python
"""
Setup social authentication apps for django-allauth
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from django.contrib.sites.models import Site
from allauth.socialaccount.models import SocialApp
from django.conf import settings


def setup_social_apps():
    """Create or update social authentication apps"""

    # Get the default site
    site = Site.objects.get_current()
    print(f"Using site: {site.domain}")

    # Google OAuth
    google_client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
    google_client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")

    if google_client_id:
        google_app, created = SocialApp.objects.update_or_create(
            provider="google",
            defaults={
                "name": "Google",
                "client_id": google_client_id,
                "secret": google_client_secret,
            },
        )
        google_app.sites.add(site)
        print(f"{'Created' if created else 'Updated'} Google OAuth app")
    else:
        print("⚠ Google OAuth credentials not configured (skipping)")

    # GitHub OAuth
    github_client_id = os.getenv("GITHUB_OAUTH_CLIENT_ID", "")
    github_client_secret = os.getenv("GITHUB_OAUTH_CLIENT_SECRET", "")

    if github_client_id:
        github_app, created = SocialApp.objects.update_or_create(
            provider="github",
            defaults={
                "name": "GitHub",
                "client_id": github_client_id,
                "secret": github_client_secret,
            },
        )
        github_app.sites.add(site)
        print(f"{'Created' if created else 'Updated'} GitHub OAuth app")
    else:
        print("⚠ GitHub OAuth credentials not configured (skipping)")

    # Facebook OAuth
    facebook_client_id = os.getenv("FACEBOOK_OAUTH_CLIENT_ID", "")
    facebook_client_secret = os.getenv("FACEBOOK_OAUTH_CLIENT_SECRET", "")

    if facebook_client_id:
        facebook_app, created = SocialApp.objects.update_or_create(
            provider="facebook",
            defaults={
                "name": "Facebook",
                "client_id": facebook_client_id,
                "secret": facebook_client_secret,
            },
        )
        facebook_app.sites.add(site)
        print(f"{'Created' if created else 'Updated'} Facebook OAuth app")
    else:
        print("⚠ Facebook OAuth credentials not configured (skipping)")

    print("\n✓ Social app setup complete!")


if __name__ == "__main__":
    setup_social_apps()
