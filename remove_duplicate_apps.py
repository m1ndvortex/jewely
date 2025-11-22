#!/usr/bin/env python
"""
Remove duplicate SocialApp records
"""
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()

from allauth.socialaccount.models import SocialApp


def remove_duplicates():
    """Remove duplicate social apps"""

    for provider in ["google", "github", "facebook"]:
        apps = SocialApp.objects.filter(provider=provider)
        count = apps.count()

        if count > 1:
            # Keep the first one, delete the rest
            to_keep = apps.first()
            to_delete = apps.exclude(id=to_keep.id)
            deleted_count = to_delete.count()
            to_delete.delete()
            print(f"{provider}: Deleted {deleted_count} duplicates, kept app ID {to_keep.id}")
        elif count == 1:
            print(f"{provider}: No duplicates (1 app found)")
        else:
            print(f"{provider}: No apps found")

    print("\n✓ Cleanup complete!")


if __name__ == "__main__":
    remove_duplicates()
