#!/usr/bin/env python
"""Test the language switch endpoint"""
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "apps.multi_tenant_saas.settings.production")
django.setup()

import json  # noqa: E402

from django.test import Client, RequestFactory  # noqa: E402

from apps.core.models import User  # noqa: E402
from apps.core.views import LanguageSwitchView  # noqa: E402

# Create a test client
client = Client()

# Get a user
user = User.objects.first()
if not user:
    print("No users found!")
    exit(1)

print(f"Testing with user: {user.email}")

# Login the user
client.force_login(user)

# Test the endpoint
response = client.post(
    "/api/user/language/switch/",
    data=json.dumps({"language": "fa"}),
    content_type="application/json",
)

print(f"Status Code: {response.status_code}")
print(f"Content-Type: {response.get('Content-Type')}")
print(f"Response Content: {response.content.decode()[:500]}")

# Also test the view directly
print("\n--- Testing view directly ---")
factory = RequestFactory()
request = factory.post(
    "/api/user/language/switch/",
    data=json.dumps({"language": "fa"}),
    content_type="application/json",
)
request.user = user

view = LanguageSwitchView.as_view()
response = view(request)

print(f"Direct Status Code: {response.status_code}")
print(f"Direct Content: {response.render().content.decode()[:500]}")
