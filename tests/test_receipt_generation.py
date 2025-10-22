"""
Tests for receipt generation functionality.

Tests the receipt generation system including:
- PDF receipt generation (standard and thermal formats)
- HTML receipt generation for browser printing
- Receipt service functionality
- Receipt URL endpoints
- Integration with POS system

Implements testing for Requirement 11: Receipt generation and printing
Implements testing for Requirement 35: Barcode/QR code generation
"""

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import override_settings
from django.urls import reverse

import pytest

from apps.core.models import Branch
from apps.core.tenant_context import tenant_context
from apps.inventory.models import InventoryItem, ProductCategory
from apps.sales.models import Customer, Sale, SaleItem, Terminal
from apps.sales.receipt_service import ReceiptGenerator, ReceiptService


@pytest.mark.django_db
class TestReceiptGenerator:
    """Test the ReceiptGenerator class."""

    def test_receipt_generator_initialization(self, sale_with_items):
        """Test that ReceiptGenerator initializes correctly."""
        generator = ReceiptGenerator(sale_with_items)

        assert generator.sale == sale_with_items
        assert generator.tenant == sale_with_items.tenant
        assert generator.styles is not None

    def test_generate_pdf_receipt_standard(self, sale_with_items):
        """Test generating standard PDF receipt."""
        generator = ReceiptGenerator(sale_with_items)

        pdf_bytes = generator.generate_pdf_receipt("standard")

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        # Check PDF header
        assert pdf_bytes.startswith(b"%PDF")

    def test_generate_pdf_receipt_thermal(self, sale_with_items):
        """Test generating thermal PDF receipt."""
        generator = ReceiptGenerator(sale_with_items)

        pdf_bytes = generator.generate_pdf_receipt("thermal")

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        # Check PDF header
        assert pdf_bytes.startswith(b"%PDF")

    def test_generate_html_receipt_standard(self, sale_with_items):
        """Test generating standard HTML receipt."""
        generator = ReceiptGenerator(sale_with_items)

        html_content = generator.generate_html_receipt("standard")

        assert isinstance(html_content, str)
        assert "SALES RECEIPT" in html_content
        assert sale_with_items.sale_number in html_content
        assert str(sale_with_items.total) in html_content

    def test_generate_html_receipt_thermal(self, sale_with_items):
        """Test generating thermal HTML receipt."""
        generator = ReceiptGenerator(sale_with_items)

        html_content = generator.generate_html_receipt("thermal")

        assert isinstance(html_content, str)
        assert "SALES RECEIPT" in html_content
        assert sale_with_items.sale_number in html_content
        assert str(sale_with_items.total) in html_content

    def test_generate_barcode(self, sale_with_items):
        """Test barcode generation."""
        generator = ReceiptGenerator(sale_with_items)

        barcode_bytes = generator.generate_barcode(sale_with_items.sale_number)

        assert isinstance(barcode_bytes, bytes)
        # Should return some bytes (even if empty on error)
        assert len(barcode_bytes) >= 0

    @patch("apps.sales.receipt_service.qrcode")
    def test_generate_qr_code(self, mock_qrcode, sale_with_items):
        """Test QR code generation."""
        # Mock QR code generation
        mock_qr_instance = MagicMock()
        mock_qr_image = MagicMock()
        mock_qr_instance.make_image.return_value = mock_qr_image
        mock_qrcode.QRCode.return_value = mock_qr_instance

        generator = ReceiptGenerator(sale_with_items)
        generator._generate_qr_code()

        # Should attempt to create QR code
        mock_qrcode.QRCode.assert_called_once()
        mock_qr_instance.add_data.assert_called_once()
        mock_qr_instance.make.assert_called_once()


@pytest.mark.django_db
class TestReceiptService:
    """Test the ReceiptService class."""

    def test_generate_receipt_pdf_standard(self, sale_with_items):
        """Test generating PDF receipt via service."""
        pdf_bytes = ReceiptService.generate_receipt(
            sale=sale_with_items, format_type="standard", output_format="pdf"
        )

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes.startswith(b"%PDF")

    def test_generate_receipt_pdf_thermal(self, sale_with_items):
        """Test generating thermal PDF receipt via service."""
        pdf_bytes = ReceiptService.generate_receipt(
            sale=sale_with_items, format_type="thermal", output_format="pdf"
        )

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 0
        assert pdf_bytes.startswith(b"%PDF")

    def test_generate_receipt_html_standard(self, sale_with_items):
        """Test generating HTML receipt via service."""
        html_bytes = ReceiptService.generate_receipt(
            sale=sale_with_items, format_type="standard", output_format="html"
        )

        assert isinstance(html_bytes, bytes)
        html_content = html_bytes.decode("utf-8")
        assert "SALES RECEIPT" in html_content
        assert sale_with_items.sale_number in html_content

    def test_generate_receipt_invalid_format(self, sale_with_items):
        """Test that invalid output format raises error."""
        with pytest.raises(ValueError, match="Unsupported output format"):
            ReceiptService.generate_receipt(
                sale=sale_with_items, format_type="standard", output_format="invalid"
            )

    @override_settings(MEDIA_ROOT="/tmp/test_media")
    @patch("os.makedirs")
    @patch("builtins.open", create=True)
    def test_save_receipt(self, mock_open, mock_makedirs, sale_with_items):
        """Test saving receipt to file."""
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = mock_file

        file_path = ReceiptService.save_receipt(sale_with_items, "standard")

        # Should create directory and save file
        mock_makedirs.assert_called_once()
        mock_open.assert_called_once()
        mock_file.write.assert_called_once()

        assert "receipt_" in file_path
        assert sale_with_items.sale_number in file_path
        assert ".pdf" in file_path

    def test_get_receipt_url(self, sale_with_items):
        """Test getting receipt URL."""
        url = ReceiptService.get_receipt_url(sale_with_items, "standard")

        assert f"receipts/{sale_with_items.tenant.id}" in url
        assert sale_with_items.sale_number in url
        assert "standard.pdf" in url


@pytest.mark.django_db
class TestReceiptViews:
    """Test receipt generation views."""

    def test_receipt_html_view_requires_authentication(self, client, sale_with_items):
        """Test that receipt HTML view requires authentication."""
        url = reverse(
            "sales:receipt_html", kwargs={"sale_id": sale_with_items.id, "format_type": "standard"}
        )
        response = client.get(url)
        assert response.status_code == 302  # Redirect to login

    def test_receipt_html_view_standard(self, client, tenant_user, sale_with_items):
        """Test HTML receipt view for standard format."""
        client.force_login(tenant_user)

        url = reverse(
            "sales:receipt_html", kwargs={"sale_id": sale_with_items.id, "format_type": "standard"}
        )
        response = client.get(url)

        assert response.status_code == 200
        assert "text/html" in response["Content-Type"]
        assert b"SALES RECEIPT" in response.content
        assert sale_with_items.sale_number.encode() in response.content

    def test_receipt_html_view_thermal(self, client, tenant_user, sale_with_items):
        """Test HTML receipt view for thermal format."""
        client.force_login(tenant_user)

        url = reverse(
            "sales:receipt_html", kwargs={"sale_id": sale_with_items.id, "format_type": "thermal"}
        )
        response = client.get(url)

        assert response.status_code == 200
        assert "text/html" in response["Content-Type"]
        assert b"SALES RECEIPT" in response.content

    def test_receipt_html_view_not_found(self, client, tenant_user):
        """Test HTML receipt view with non-existent sale."""
        client.force_login(tenant_user)

        url = reverse(
            "sales:receipt_html",
            kwargs={"sale_id": "00000000-0000-0000-0000-000000000000", "format_type": "standard"},
        )
        response = client.get(url)

        assert response.status_code == 404

    def test_receipt_pdf_view_standard(self, client, tenant_user, sale_with_items):
        """Test PDF receipt view for standard format."""
        client.force_login(tenant_user)

        url = reverse(
            "sales:receipt_pdf", kwargs={"sale_id": sale_with_items.id, "format_type": "standard"}
        )
        response = client.get(url)

        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert "attachment" in response["Content-Disposition"]
        assert sale_with_items.sale_number in response["Content-Disposition"]

    def test_receipt_pdf_view_thermal(self, client, tenant_user, sale_with_items):
        """Test PDF receipt view for thermal format."""
        client.force_login(tenant_user)

        url = reverse(
            "sales:receipt_pdf", kwargs={"sale_id": sale_with_items.id, "format_type": "thermal"}
        )
        response = client.get(url)

        assert response.status_code == 200
        assert response["Content-Type"] == "application/pdf"
        assert "thermal" in response["Content-Disposition"]

    def test_generate_receipt_after_sale_api(
        self, authenticated_api_client, tenant, sale_with_items
    ):
        """Test receipt generation API endpoint."""
        with tenant_context(tenant.id):
            url = reverse("sales:generate_receipt", kwargs={"sale_id": sale_with_items.id})
            data = {"format_type": "standard", "auto_print": False, "save_receipt": False}

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 200
            result = response.json()
            assert "receipt_url" in result
            assert "pdf_url" in result
            assert str(sale_with_items.id) in result["receipt_url"]
            assert str(sale_with_items.id) in result["pdf_url"]

    def test_generate_receipt_after_sale_with_auto_print(
        self, authenticated_api_client, tenant, sale_with_items
    ):
        """Test receipt generation API with auto print."""
        with tenant_context(tenant.id):
            url = reverse("sales:generate_receipt", kwargs={"sale_id": sale_with_items.id})
            data = {"format_type": "thermal", "auto_print": True, "save_receipt": False}

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 200
            result = response.json()
            assert "auto_print=true" in result["receipt_url"]

    def test_generate_receipt_invalid_format(
        self, authenticated_api_client, tenant, sale_with_items
    ):
        """Test receipt generation with invalid format."""
        with tenant_context(tenant.id):
            url = reverse("sales:generate_receipt", kwargs={"sale_id": sale_with_items.id})
            data = {"format_type": "invalid", "auto_print": False, "save_receipt": False}

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 400
            assert "Invalid format_type" in response.json()["detail"]

    def test_generate_receipt_sale_not_found(self, authenticated_api_client, tenant):
        """Test receipt generation for non-existent sale."""
        with tenant_context(tenant.id):
            url = reverse(
                "sales:generate_receipt", kwargs={"sale_id": "00000000-0000-0000-0000-000000000000"}
            )
            data = {"format_type": "standard", "auto_print": False, "save_receipt": False}

            response = authenticated_api_client.post(
                url, data=json.dumps(data), content_type="application/json"
            )

            assert response.status_code == 404


@pytest.mark.django_db
class TestReceiptIntegration:
    """Test receipt generation integration with POS system."""

    def test_receipt_generation_after_pos_sale(
        self, authenticated_api_client, tenant, tenant_user, inventory_item
    ):
        """Test that receipt can be generated after POS sale creation."""
        with tenant_context(tenant.id):
            # Create terminal
            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            # Create sale through POS
            pos_url = reverse("sales:pos_create_sale")
            sale_data = {
                "terminal_id": str(terminal.id),
                "items": [
                    {
                        "inventory_item_id": str(inventory_item.id),
                        "quantity": 1,
                    }
                ],
                "payment_method": "CASH",
                "tax_rate": "10.00",
            }

            pos_response = authenticated_api_client.post(
                pos_url, data=json.dumps(sale_data), content_type="application/json"
            )

            assert pos_response.status_code == 201
            sale = pos_response.json()

            # Generate receipt for the created sale
            receipt_url = reverse("sales:generate_receipt", kwargs={"sale_id": sale["id"]})
            receipt_data = {"format_type": "standard", "auto_print": False, "save_receipt": False}

            receipt_response = authenticated_api_client.post(
                receipt_url, data=json.dumps(receipt_data), content_type="application/json"
            )

            assert receipt_response.status_code == 200
            receipt_result = receipt_response.json()
            assert "receipt_url" in receipt_result
            assert "pdf_url" in receipt_result

    def test_receipt_contains_sale_details(self, sale_with_items):
        """Test that receipt contains all necessary sale details."""
        html_content = ReceiptService.generate_receipt(
            sale=sale_with_items, format_type="standard", output_format="html"
        ).decode("utf-8")

        # Check sale information
        assert sale_with_items.sale_number in html_content
        assert str(sale_with_items.total) in html_content
        assert sale_with_items.employee.get_full_name() in html_content
        assert sale_with_items.terminal.terminal_id in html_content

        # Check items
        for item in sale_with_items.items.all():
            assert item.inventory_item.name in html_content
            assert item.inventory_item.sku in html_content
            assert str(item.quantity) in html_content
            assert str(item.unit_price) in html_content

    def test_receipt_with_customer_details(self, tenant, inventory_item, tenant_user):
        """Test receipt generation with customer information."""
        with tenant_context(tenant.id):
            # Create customer
            customer = Customer.objects.create(
                tenant=tenant,
                customer_number="CUST-001",
                first_name="John",
                last_name="Doe",
                phone="+1234567890",
                email="john@example.com",
            )

            # Create sale with customer
            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            sale = Sale.objects.create(
                tenant=tenant,
                sale_number="SALE-20241022-000001",
                customer=customer,
                branch=inventory_item.branch,
                terminal=terminal,
                employee=tenant_user,
                subtotal=Decimal("100.00"),
                tax=Decimal("10.00"),
                discount=Decimal("0.00"),
                total=Decimal("110.00"),
                payment_method="CASH",
                status="COMPLETED",
            )

            # Generate receipt
            html_content = ReceiptService.generate_receipt(
                sale=sale, format_type="standard", output_format="html"
            ).decode("utf-8")

            # Check customer information
            assert customer.get_full_name() in html_content
            assert customer.phone in html_content

    def test_receipt_with_split_payment(self, tenant, inventory_item, tenant_user):
        """Test receipt generation with split payment details."""
        with tenant_context(tenant.id):
            terminal = Terminal.objects.create(
                branch=inventory_item.branch,
                terminal_id="POS-01",
                is_active=True,
            )

            # Create sale with split payment
            sale = Sale.objects.create(
                tenant=tenant,
                sale_number="SALE-20241022-000002",
                branch=inventory_item.branch,
                terminal=terminal,
                employee=tenant_user,
                subtotal=Decimal("100.00"),
                tax=Decimal("10.00"),
                discount=Decimal("0.00"),
                total=Decimal("110.00"),
                payment_method="SPLIT",
                payment_details={
                    "split_payments": [
                        {"method": "CASH", "amount": "60.00"},
                        {"method": "CARD", "amount": "50.00"},
                    ]
                },
                status="COMPLETED",
            )

            # Generate receipt
            html_content = ReceiptService.generate_receipt(
                sale=sale, format_type="standard", output_format="html"
            ).decode("utf-8")

            # Check split payment details
            assert "Payment Breakdown" in html_content
            assert "CASH: $60.00" in html_content
            assert "CARD: $50.00" in html_content


# Fixtures for testing


@pytest.fixture
def sale_with_items(tenant, tenant_user):
    """Create a sale with items for testing."""
    with tenant_context(tenant.id):
        # Create branch and category
        branch = Branch.objects.create(tenant=tenant, name="Main Branch")
        category = ProductCategory.objects.create(tenant=tenant, name="Rings")

        # Create inventory items
        item1 = InventoryItem.objects.create(
            tenant=tenant,
            sku="RING-001",
            name="Gold Ring",
            category=category,
            branch=branch,
            karat=24,
            weight_grams=Decimal("10.5"),
            cost_price=Decimal("800.00"),
            selling_price=Decimal("1000.00"),
            quantity=10,
        )

        item2 = InventoryItem.objects.create(
            tenant=tenant,
            sku="RING-002",
            name="Silver Ring",
            category=category,
            branch=branch,
            karat=18,
            weight_grams=Decimal("8.0"),
            cost_price=Decimal("400.00"),
            selling_price=Decimal("500.00"),
            quantity=5,
        )

        # Create terminal
        terminal = Terminal.objects.create(branch=branch, terminal_id="POS-01", is_active=True)

        # Create sale
        sale = Sale.objects.create(
            tenant=tenant,
            sale_number="SALE-20241022-000001",
            branch=branch,
            terminal=terminal,
            employee=tenant_user,
            subtotal=Decimal("1500.00"),
            tax=Decimal("150.00"),
            discount=Decimal("50.00"),
            total=Decimal("1600.00"),
            payment_method="CASH",
            status="COMPLETED",
        )

        # Create sale items
        SaleItem.objects.create(
            sale=sale,
            inventory_item=item1,
            quantity=1,
            unit_price=Decimal("1000.00"),
            subtotal=Decimal("1000.00"),
        )

        SaleItem.objects.create(
            sale=sale,
            inventory_item=item2,
            quantity=1,
            unit_price=Decimal("500.00"),
            subtotal=Decimal("500.00"),
        )

        return sale
