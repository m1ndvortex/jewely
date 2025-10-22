"""
Tests for barcode and QR code generation functionality.

Implements testing for Requirement 9 and 35:
- Barcode generation for inventory items
- QR code generation for inventory items
- Printable label generation
"""

import io

from django.urls import reverse

import pytest
from PIL import Image
from rest_framework import status

from apps.core.models import Branch, Tenant, User
from apps.inventory.barcode_utils import BarcodeGenerator, LabelGenerator, QRCodeGenerator
from apps.inventory.models import InventoryItem, ProductCategory


@pytest.fixture
def tenant(db):
    """Create a test tenant."""
    return Tenant.objects.create(
        company_name="Test Jewelry Shop",
        slug="test-shop",
        status="ACTIVE",
    )


@pytest.fixture
def branch(db, tenant):
    """Create a test branch."""
    return Branch.objects.create(
        tenant=tenant,
        name="Main Branch",
        address="123 Main St",
        phone="555-0100",
        is_active=True,
    )


@pytest.fixture
def user(db, tenant, branch):
    """Create a test user."""
    return User.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
        tenant=tenant,
        branch=branch,
        role="TENANT_OWNER",
    )


@pytest.fixture
def category(db, tenant):
    """Create a test product category."""
    return ProductCategory.objects.create(
        tenant=tenant,
        name="Rings",
        is_active=True,
    )


@pytest.fixture
def inventory_item(db, tenant, branch, category):
    """Create a test inventory item."""
    return InventoryItem.objects.create(
        tenant=tenant,
        sku="RING-001",
        name="24K Gold Ring",
        category=category,
        karat=24,
        weight_grams=5.5,
        cost_price=500.00,
        selling_price=750.00,
        quantity=10,
        branch=branch,
        serial_number="SN123456",
        barcode="123456789012",
    )


@pytest.mark.django_db
class TestBarcodeGenerator:
    """Test barcode generation utilities."""

    def test_generate_code128_barcode(self):
        """Test generating CODE128 barcode."""
        data = "RING-001"
        barcode_bytes, mime_type = BarcodeGenerator.generate_barcode(data, BarcodeGenerator.CODE128)

        assert barcode_bytes is not None
        assert len(barcode_bytes) > 0
        assert mime_type == "image/png"

        # Verify it's a valid PNG image
        img = Image.open(io.BytesIO(barcode_bytes))
        assert img.format == "PNG"
        assert img.size[0] > 0
        assert img.size[1] > 0

    def test_generate_barcode_for_sku(self):
        """Test generating barcode for SKU."""
        sku = "RING-001"
        barcode_bytes, mime_type = BarcodeGenerator.generate_barcode_for_sku(sku)

        assert barcode_bytes is not None
        assert mime_type == "image/png"

        # Verify it's a valid image
        img = Image.open(io.BytesIO(barcode_bytes))
        assert img.format == "PNG"

    def test_generate_barcode_for_serial(self):
        """Test generating barcode for serial number."""
        serial = "SN123456"
        barcode_bytes, mime_type = BarcodeGenerator.generate_barcode_for_serial(serial)

        assert barcode_bytes is not None
        assert mime_type == "image/png"

        # Verify it's a valid image
        img = Image.open(io.BytesIO(barcode_bytes))
        assert img.format == "PNG"

    def test_generate_barcode_invalid_format(self):
        """Test generating barcode with invalid format."""
        with pytest.raises(ValueError, match="Unsupported barcode format"):
            BarcodeGenerator.generate_barcode("TEST", "invalid_format")

    def test_generate_barcode_custom_options(self):
        """Test generating barcode with custom writer options."""
        data = "TEST123"
        options = {
            "module_width": 0.5,
            "module_height": 20.0,
            "font_size": 12,
        }
        barcode_bytes, mime_type = BarcodeGenerator.generate_barcode(
            data, BarcodeGenerator.CODE128, options
        )

        assert barcode_bytes is not None
        assert mime_type == "image/png"


@pytest.mark.django_db
class TestQRCodeGenerator:
    """Test QR code generation utilities."""

    def test_generate_qr_code(self):
        """Test generating basic QR code."""
        data = "RING-001"
        qr_bytes, mime_type = QRCodeGenerator.generate_qr_code(data)

        assert qr_bytes is not None
        assert len(qr_bytes) > 0
        assert mime_type == "image/png"

        # Verify it's a valid PNG image
        img = Image.open(io.BytesIO(qr_bytes))
        assert img.format == "PNG"
        assert img.size[0] > 0
        assert img.size[1] > 0

    def test_generate_qr_code_for_item(self):
        """Test generating QR code with item data."""
        item_data = {
            "sku": "RING-001",
            "name": "24K Gold Ring",
            "karat": 24,
            "weight": "5.5",
            "price": "750.00",
        }
        qr_bytes, mime_type = QRCodeGenerator.generate_qr_code_for_item(item_data)

        assert qr_bytes is not None
        assert mime_type == "image/png"

        # Verify it's a valid image
        img = Image.open(io.BytesIO(qr_bytes))
        assert img.format == "PNG"

    def test_generate_qr_code_for_url(self):
        """Test generating QR code for URL."""
        url = "https://example.com/product/RING-001"
        qr_bytes, mime_type = QRCodeGenerator.generate_qr_code_for_url(url)

        assert qr_bytes is not None
        assert mime_type == "image/png"

        # Verify it's a valid image
        img = Image.open(io.BytesIO(qr_bytes))
        assert img.format == "PNG"

    def test_generate_qr_code_custom_options(self):
        """Test generating QR code with custom options."""
        data = "TEST123"
        qr_bytes, mime_type = QRCodeGenerator.generate_qr_code(
            data,
            box_size=15,
            border=2,
            fill_color="blue",
            back_color="yellow",
        )

        assert qr_bytes is not None
        assert mime_type == "image/png"


@pytest.mark.django_db
class TestLabelGenerator:
    """Test label generation utilities."""

    def test_create_product_label(self):
        """Test creating product label with barcode."""
        # Generate barcode first
        barcode_bytes, _ = BarcodeGenerator.generate_barcode_for_sku("RING-001")

        # Create label
        label_bytes, mime_type = LabelGenerator.create_product_label(
            sku="RING-001",
            name="24K Gold Ring",
            price="$750.00",
            barcode_data=barcode_bytes,
            label_size=LabelGenerator.LABEL_MEDIUM,
            dpi=300,
        )

        assert label_bytes is not None
        assert mime_type == "image/png"

        # Verify it's a valid image
        img = Image.open(io.BytesIO(label_bytes))
        assert img.format == "PNG"
        assert img.size[0] > 0
        assert img.size[1] > 0

    def test_create_product_label_different_sizes(self):
        """Test creating labels with different sizes."""
        barcode_bytes, _ = BarcodeGenerator.generate_barcode_for_sku("RING-001")

        sizes = [
            LabelGenerator.LABEL_SMALL,
            LabelGenerator.LABEL_MEDIUM,
            LabelGenerator.LABEL_LARGE,
        ]

        for size in sizes:
            label_bytes, mime_type = LabelGenerator.create_product_label(
                sku="RING-001",
                name="24K Gold Ring",
                price="$750.00",
                barcode_data=barcode_bytes,
                label_size=size,
                dpi=300,
            )

            assert label_bytes is not None
            assert mime_type == "image/png"

    def test_create_qr_label(self):
        """Test creating QR code label."""
        # Generate QR code first
        qr_bytes, _ = QRCodeGenerator.generate_qr_code("RING-001")

        # Create label
        label_bytes, mime_type = LabelGenerator.create_qr_label(
            title="24K Gold Ring",
            subtitle="SKU: RING-001",
            qr_data=qr_bytes,
            label_size=LabelGenerator.LABEL_MEDIUM,
            dpi=300,
        )

        assert label_bytes is not None
        assert mime_type == "image/png"

        # Verify it's a valid image
        img = Image.open(io.BytesIO(label_bytes))
        assert img.format == "PNG"
        assert img.size[0] > 0
        assert img.size[1] > 0


@pytest.mark.django_db
class TestBarcodeLookup:
    """Test barcode scanning and lookup functionality."""

    def test_lookup_by_barcode_success(self, api_client, user, inventory_item):
        """Test successful barcode lookup."""
        api_client.force_authenticate(user=user)

        url = reverse("inventory:lookup_by_barcode")
        response = api_client.get(url, {"barcode": inventory_item.barcode})

        assert response.status_code == status.HTTP_200_OK
        assert response.data["sku"] == inventory_item.sku
        assert response.data["name"] == inventory_item.name

    def test_lookup_by_barcode_not_found(self, api_client, user):
        """Test barcode lookup with non-existent barcode."""
        api_client.force_authenticate(user=user)

        url = reverse("inventory:lookup_by_barcode")
        response = api_client.get(url, {"barcode": "NONEXISTENT123"})

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_lookup_by_barcode_missing_parameter(self, api_client, user):
        """Test barcode lookup without barcode parameter."""
        api_client.force_authenticate(user=user)

        url = reverse("inventory:lookup_by_barcode")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_lookup_by_barcode_unauthenticated(self, api_client, inventory_item):
        """Test barcode lookup without authentication."""
        url = reverse("inventory:lookup_by_barcode")
        response = api_client.get(url, {"barcode": inventory_item.barcode})

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestBarcodeAPIEndpoints:
    """Test barcode generation API endpoints."""

    def test_generate_barcode_endpoint(self, api_client, user, inventory_item):
        """Test barcode generation endpoint."""
        api_client.force_authenticate(user=user)

        url = reverse("inventory:generate_barcode", kwargs={"item_id": inventory_item.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "image/png"
        assert len(response.content) > 0

        # Verify it's a valid image
        img = Image.open(io.BytesIO(response.content))
        assert img.format == "PNG"

    def test_generate_barcode_with_serial(self, api_client, user, inventory_item):
        """Test barcode generation using serial number."""
        api_client.force_authenticate(user=user)

        url = reverse("inventory:generate_barcode", kwargs={"item_id": inventory_item.id})
        response = api_client.get(url, {"data_type": "serial"})

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "image/png"

    def test_generate_barcode_not_found(self, api_client, user):
        """Test barcode generation for non-existent item."""
        api_client.force_authenticate(user=user)

        url = reverse(
            "inventory:generate_barcode",
            kwargs={"item_id": "00000000-0000-0000-0000-000000000000"},
        )
        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_generate_barcode_unauthenticated(self, api_client, inventory_item):
        """Test barcode generation without authentication."""
        url = reverse("inventory:generate_barcode", kwargs={"item_id": inventory_item.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestQRCodeAPIEndpoints:
    """Test QR code generation API endpoints."""

    def test_generate_qr_code_endpoint(self, api_client, user, inventory_item):
        """Test QR code generation endpoint."""
        api_client.force_authenticate(user=user)

        url = reverse("inventory:generate_qr_code", kwargs={"item_id": inventory_item.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "image/png"
        assert len(response.content) > 0

        # Verify it's a valid image
        img = Image.open(io.BytesIO(response.content))
        assert img.format == "PNG"

    def test_generate_qr_code_full_data(self, api_client, user, inventory_item):
        """Test QR code generation with full item data."""
        api_client.force_authenticate(user=user)

        url = reverse("inventory:generate_qr_code", kwargs={"item_id": inventory_item.id})
        response = api_client.get(url, {"data_type": "full"})

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "image/png"

    def test_generate_qr_code_sku_only(self, api_client, user, inventory_item):
        """Test QR code generation with SKU only."""
        api_client.force_authenticate(user=user)

        url = reverse("inventory:generate_qr_code", kwargs={"item_id": inventory_item.id})
        response = api_client.get(url, {"data_type": "sku"})

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "image/png"

    def test_generate_qr_code_url(self, api_client, user, inventory_item):
        """Test QR code generation with custom URL."""
        api_client.force_authenticate(user=user)

        url = reverse("inventory:generate_qr_code", kwargs={"item_id": inventory_item.id})
        response = api_client.get(
            url, {"data_type": "url", "url": "https://example.com/product/RING-001"}
        )

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "image/png"

    def test_generate_qr_code_url_missing_parameter(self, api_client, user, inventory_item):
        """Test QR code generation with URL type but missing URL parameter."""
        api_client.force_authenticate(user=user)

        url = reverse("inventory:generate_qr_code", kwargs={"item_id": inventory_item.id})
        response = api_client.get(url, {"data_type": "url"})

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_generate_qr_code_not_found(self, api_client, user):
        """Test QR code generation for non-existent item."""
        api_client.force_authenticate(user=user)

        url = reverse(
            "inventory:generate_qr_code",
            kwargs={"item_id": "00000000-0000-0000-0000-000000000000"},
        )
        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestLabelAPIEndpoints:
    """Test label generation API endpoints."""

    def test_generate_product_label_endpoint(self, api_client, user, inventory_item):
        """Test product label generation endpoint."""
        api_client.force_authenticate(user=user)

        url = reverse("inventory:generate_product_label", kwargs={"item_id": inventory_item.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "image/png"
        assert len(response.content) > 0

        # Verify it's a valid image
        img = Image.open(io.BytesIO(response.content))
        assert img.format == "PNG"

    def test_generate_product_label_different_sizes(self, api_client, user, inventory_item):
        """Test product label generation with different sizes."""
        api_client.force_authenticate(user=user)

        url = reverse("inventory:generate_product_label", kwargs={"item_id": inventory_item.id})

        for size in ["small", "medium", "large"]:
            response = api_client.get(url, {"size": size})
            assert response.status_code == status.HTTP_200_OK
            assert response["Content-Type"] == "image/png"

    def test_generate_product_label_different_dpi(self, api_client, user, inventory_item):
        """Test product label generation with different DPI."""
        api_client.force_authenticate(user=user)

        url = reverse("inventory:generate_product_label", kwargs={"item_id": inventory_item.id})

        for dpi in [150, 300, 600]:
            response = api_client.get(url, {"dpi": str(dpi)})
            assert response.status_code == status.HTTP_200_OK
            assert response["Content-Type"] == "image/png"

    def test_generate_qr_label_endpoint(self, api_client, user, inventory_item):
        """Test QR label generation endpoint."""
        api_client.force_authenticate(user=user)

        url = reverse("inventory:generate_qr_label", kwargs={"item_id": inventory_item.id})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "image/png"
        assert len(response.content) > 0

        # Verify it's a valid image
        img = Image.open(io.BytesIO(response.content))
        assert img.format == "PNG"

    def test_generate_qr_label_different_sizes(self, api_client, user, inventory_item):
        """Test QR label generation with different sizes."""
        api_client.force_authenticate(user=user)

        url = reverse("inventory:generate_qr_label", kwargs={"item_id": inventory_item.id})

        for size in ["small", "medium", "large"]:
            response = api_client.get(url, {"size": size})
            assert response.status_code == status.HTTP_200_OK
            assert response["Content-Type"] == "image/png"

    def test_generate_label_not_found(self, api_client, user):
        """Test label generation for non-existent item."""
        api_client.force_authenticate(user=user)

        url = reverse(
            "inventory:generate_product_label",
            kwargs={"item_id": "00000000-0000-0000-0000-000000000000"},
        )
        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
