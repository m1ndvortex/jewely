"""
URL configuration for jewelry shop SaaS platform.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),  # django-allauth URLs
    path("", include("apps.core.urls")),
    path("", include("apps.inventory.urls")),
    path("", include("apps.sales.urls")),
    path("", include("apps.crm.urls")),
    path("accounting/", include("apps.accounting.urls")),
    path("repair/", include("apps.repair.urls")),
    path("procurement/", include("apps.procurement.urls")),
    path("pricing/", include("apps.pricing.urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
