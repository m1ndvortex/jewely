"""
Receipt generation service for jewelry shop POS.

Implements Requirement 11: Receipt generation and printing
- Create receipt template with shop branding
- Generate PDF receipts
- Support thermal printer formats
- Browser print API integration

Implements Requirement 35: Barcode/QR code generation
- Generate barcodes for receipts
- QR codes for digital receipt access
"""

import io
import os
from typing import Optional

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone

import qrcode
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import code128
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch, mm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus.flowables import HRFlowable

from .models import Sale


class ReceiptGenerator:
    """
    Receipt generator for jewelry shop sales.

    Supports multiple formats:
    - PDF receipts for email/storage
    - HTML receipts for browser printing
    - Thermal printer format (80mm width)
    - Standard receipt format (A4/Letter)
    """

    # Receipt dimensions
    THERMAL_WIDTH = 80 * mm  # 80mm thermal paper
    STANDARD_WIDTH = 210 * mm  # A4 width

    # Margins
    THERMAL_MARGIN = 5 * mm
    STANDARD_MARGIN = 20 * mm

    def __init__(self, sale: Sale):
        """Initialize receipt generator with sale data."""
        self.sale = sale
        self.tenant = sale.tenant
        self.styles = getSampleStyleSheet()

        # Create custom styles
        self._create_custom_styles()

    def _create_custom_styles(self):
        """Create custom paragraph styles for receipts."""
        # Header style
        self.header_style = ParagraphStyle(
            "CustomHeader",
            parent=self.styles["Heading1"],
            fontSize=16,
            spaceAfter=12,
            alignment=1,  # Center alignment
            textColor=colors.black,
            fontName="Helvetica-Bold",
        )

        # Shop name style
        self.shop_name_style = ParagraphStyle(
            "ShopName",
            parent=self.styles["Heading1"],
            fontSize=18,
            spaceAfter=6,
            alignment=1,  # Center alignment
            textColor=colors.black,
            fontName="Helvetica-Bold",
        )

        # Thermal header style (smaller)
        self.thermal_header_style = ParagraphStyle(
            "ThermalHeader",
            parent=self.styles["Heading1"],
            fontSize=12,
            spaceAfter=8,
            alignment=1,  # Center alignment
            textColor=colors.black,
            fontName="Helvetica-Bold",
        )

        # Thermal shop name style
        self.thermal_shop_style = ParagraphStyle(
            "ThermalShop",
            parent=self.styles["Heading1"],
            fontSize=14,
            spaceAfter=4,
            alignment=1,  # Center alignment
            textColor=colors.black,
            fontName="Helvetica-Bold",
        )

        # Body text style
        self.body_style = ParagraphStyle(
            "CustomBody",
            parent=self.styles["Normal"],
            fontSize=10,
            spaceAfter=6,
            alignment=0,  # Left alignment
            textColor=colors.black,
        )

        # Thermal body style (smaller)
        self.thermal_body_style = ParagraphStyle(
            "ThermalBody",
            parent=self.styles["Normal"],
            fontSize=8,
            spaceAfter=4,
            alignment=0,  # Left alignment
            textColor=colors.black,
        )

        # Total style
        self.total_style = ParagraphStyle(
            "CustomTotal",
            parent=self.styles["Normal"],
            fontSize=12,
            spaceAfter=6,
            alignment=2,  # Right alignment
            textColor=colors.black,
            fontName="Helvetica-Bold",
        )

        # Thermal total style
        self.thermal_total_style = ParagraphStyle(
            "ThermalTotal",
            parent=self.styles["Normal"],
            fontSize=10,
            spaceAfter=4,
            alignment=2,  # Right alignment
            textColor=colors.black,
            fontName="Helvetica-Bold",
        )

    def generate_pdf_receipt(self, format_type: str = "standard") -> bytes:
        """
        Generate PDF receipt.

        Args:
            format_type: 'standard' for A4/Letter, 'thermal' for 80mm thermal paper

        Returns:
            PDF bytes
        """
        buffer = io.BytesIO()

        if format_type == "thermal":
            # Thermal receipt (80mm width)
            doc = SimpleDocTemplate(
                buffer,
                pagesize=(self.THERMAL_WIDTH, 11 * inch),  # Variable height
                rightMargin=self.THERMAL_MARGIN,
                leftMargin=self.THERMAL_MARGIN,
                topMargin=self.THERMAL_MARGIN,
                bottomMargin=self.THERMAL_MARGIN,
            )
            story = self._build_thermal_receipt_content()
        else:
            # Standard receipt (A4/Letter)
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=self.STANDARD_MARGIN,
                leftMargin=self.STANDARD_MARGIN,
                topMargin=self.STANDARD_MARGIN,
                bottomMargin=self.STANDARD_MARGIN,
            )
            story = self._build_standard_receipt_content()

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        return pdf_bytes

    def _build_standard_receipt_content(self):
        """Build content for standard receipt format."""
        story = []

        # Shop branding section
        story.extend(self._build_shop_header(thermal=False))

        # Receipt header
        story.append(Paragraph("SALES RECEIPT", self.header_style))
        story.append(Spacer(1, 12))

        # Sale information
        story.extend(self._build_sale_info(thermal=False))

        # Items table
        story.extend(self._build_items_table(thermal=False))

        # Totals section
        story.extend(self._build_totals_section(thermal=False))

        # Payment information
        story.extend(self._build_payment_info(thermal=False))

        # Footer
        story.extend(self._build_receipt_footer(thermal=False))

        return story

    def _build_thermal_receipt_content(self):
        """Build content for thermal receipt format."""
        story = []

        # Shop branding section
        story.extend(self._build_shop_header(thermal=True))

        # Receipt header
        story.append(Paragraph("SALES RECEIPT", self.thermal_header_style))
        story.append(Spacer(1, 8))

        # Sale information
        story.extend(self._build_sale_info(thermal=True))

        # Items table
        story.extend(self._build_items_table(thermal=True))

        # Totals section
        story.extend(self._build_totals_section(thermal=True))

        # Payment information
        story.extend(self._build_payment_info(thermal=True))

        # Footer
        story.extend(self._build_receipt_footer(thermal=True))

        return story

    def _build_shop_header(self, thermal: bool = False):
        """Build shop branding header."""
        elements = []

        # Shop name
        shop_name = getattr(self.tenant, "company_name", "Jewelry Shop")
        style = self.thermal_shop_style if thermal else self.shop_name_style
        elements.append(Paragraph(shop_name, style))

        # Shop address and contact (if available)
        # Note: This would come from tenant settings in a real implementation
        shop_info = [
            "123 Jewelry Street",
            "Gold City, GC 12345",
            "Phone: (555) 123-4567",
            "Email: info@jewelryshop.com",
        ]

        body_style = self.thermal_body_style if thermal else self.body_style
        for info in shop_info:
            elements.append(Paragraph(f"<para align='center'>{info}</para>", body_style))

        elements.append(Spacer(1, 12 if not thermal else 8))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.black))
        elements.append(Spacer(1, 12 if not thermal else 8))

        return elements

    def _build_sale_info(self, thermal: bool = False):
        """Build sale information section."""
        elements = []
        body_style = self.thermal_body_style if thermal else self.body_style

        # Sale details
        sale_info = [
            f"Receipt #: {self.sale.sale_number}",
            f"Date: {self.sale.created_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Cashier: {self.sale.employee.get_full_name()}",
            f"Terminal: {self.sale.terminal.terminal_id}",
        ]

        if self.sale.customer:
            sale_info.append(f"Customer: {self.sale.customer.get_full_name()}")
            sale_info.append(f"Phone: {self.sale.customer.phone}")

        for info in sale_info:
            elements.append(Paragraph(info, body_style))

        elements.append(Spacer(1, 12 if not thermal else 8))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.black))
        elements.append(Spacer(1, 12 if not thermal else 8))

        return elements

    def _build_items_table(self, thermal: bool = False):
        """Build items table."""
        elements = []

        # Table data
        if thermal:
            # Simplified table for thermal printer
            data = [["Item", "Qty", "Price", "Total"]]
            col_widths = [35 * mm, 10 * mm, 15 * mm, 15 * mm]
            font_size = 7
        else:
            # Full table for standard receipt
            data = [["Item", "SKU", "Qty", "Unit Price", "Discount", "Total"]]
            col_widths = [60 * mm, 30 * mm, 20 * mm, 25 * mm, 25 * mm, 25 * mm]
            font_size = 9

        # Add items
        for item in self.sale.items.all():
            if thermal:
                # Simplified row for thermal
                row = [
                    item.inventory_item.name[:20]
                    + ("..." if len(item.inventory_item.name) > 20 else ""),
                    str(item.quantity),
                    f"${item.unit_price:.2f}",
                    f"${item.subtotal:.2f}",
                ]
            else:
                # Full row for standard
                row = [
                    item.inventory_item.name,
                    item.inventory_item.sku,
                    str(item.quantity),
                    f"${item.unit_price:.2f}",
                    f"${item.discount:.2f}" if item.discount > 0 else "-",
                    f"${item.subtotal:.2f}",
                ]
            data.append(row)

        # Create table
        table = Table(data, colWidths=col_widths)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, 0), font_size + 1),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 1), (-1, -1), font_size),
                    ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
                    ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                    ("GRID", (0, 0), (-1, -1), 1, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ]
            )
        )

        elements.append(table)
        elements.append(Spacer(1, 12 if not thermal else 8))

        return elements

    def _build_totals_section(self, thermal: bool = False):
        """Build totals section."""
        elements = []
        body_style = self.thermal_body_style if thermal else self.body_style
        total_style = self.thermal_total_style if thermal else self.total_style

        # Totals
        totals_data = [
            f"Subtotal: ${self.sale.subtotal:.2f}",
            f"Discount: ${self.sale.discount:.2f}",
            f"Tax: ${self.sale.tax:.2f}",
        ]

        for total in totals_data:
            elements.append(Paragraph(f"<para align='right'>{total}</para>", body_style))

        elements.append(HRFlowable(width="100%", thickness=2, color=colors.black))
        elements.append(
            Paragraph(
                f"<para align='right'><b>TOTAL: ${self.sale.total:.2f}</b></para>", total_style
            )
        )
        elements.append(Spacer(1, 12 if not thermal else 8))

        return elements

    def _build_payment_info(self, thermal: bool = False):
        """Build payment information section."""
        elements = []
        body_style = self.thermal_body_style if thermal else self.body_style

        # Payment method
        payment_method = dict(self.sale.PAYMENT_METHOD_CHOICES).get(
            self.sale.payment_method, self.sale.payment_method
        )
        elements.append(Paragraph(f"Payment Method: {payment_method}", body_style))

        # Split payment details if applicable
        if self.sale.payment_method == "SPLIT" and self.sale.payment_details.get("split_payments"):
            elements.append(Paragraph("Payment Breakdown:", body_style))
            for payment in self.sale.payment_details["split_payments"]:
                method_name = dict(self.sale.PAYMENT_METHOD_CHOICES).get(
                    payment["method"], payment["method"]
                )
                elements.append(Paragraph(f"  {method_name}: ${payment['amount']}", body_style))

        elements.append(Spacer(1, 12 if not thermal else 8))

        return elements

    def _build_receipt_footer(self, thermal: bool = False):
        """Build receipt footer."""
        elements = []
        body_style = self.thermal_body_style if thermal else self.body_style

        elements.append(HRFlowable(width="100%", thickness=1, color=colors.black))
        elements.append(Spacer(1, 8 if thermal else 12))

        # Footer messages
        footer_messages = [
            "Thank you for your business!",
            "Please keep this receipt for your records.",
            "Returns accepted within 30 days with receipt.",
        ]

        for message in footer_messages:
            elements.append(Paragraph(f"<para align='center'>{message}</para>", body_style))

        # QR code for digital receipt (if not thermal)
        if not thermal:
            elements.append(Spacer(1, 12))
            qr_code = self._generate_qr_code()
            if qr_code:
                elements.append(qr_code)
                elements.append(
                    Paragraph("<para align='center'>Scan for digital receipt</para>", body_style)
                )

        return elements

    def _generate_qr_code(self) -> Optional[Image]:
        """Generate QR code for digital receipt access."""
        try:
            # Create QR code with receipt URL (placeholder)
            receipt_url = f"https://jewelryshop.com/receipts/{self.sale.id}"

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=3,
                border=2,
            )
            qr.add_data(receipt_url)
            qr.make(fit=True)

            # Create QR code image
            qr_img = qr.make_image(fill_color="black", back_color="white")

            # Save to temporary buffer
            buffer = io.BytesIO()
            qr_img.save(buffer, format="PNG")
            buffer.seek(0)

            # Create ReportLab Image
            img = Image(buffer, width=1 * inch, height=1 * inch)
            img.hAlign = "CENTER"

            return img

        except Exception as e:
            # Log error but don't fail receipt generation
            print(f"Error generating QR code: {e}")
            return None

    def generate_html_receipt(self, format_type: str = "standard") -> str:
        """
        Generate HTML receipt for browser printing.

        Args:
            format_type: 'standard' or 'thermal'

        Returns:
            HTML string
        """
        template_name = f"sales/receipt_{format_type}.html"

        # Get current gold rates for display on receipt
        current_gold_rates = None
        try:
            from apps.pricing.models import GoldRate

            current_gold_rates = GoldRate.get_latest_rate()
        except ImportError:
            pass  # Pricing app not available

        context = {
            "sale": self.sale,
            "tenant": self.tenant,
            "items": self.sale.items.select_related("inventory_item").all(),
            "current_time": timezone.now(),
            "current_gold_rates": current_gold_rates,
            "payment_method_display": dict(self.sale.PAYMENT_METHOD_CHOICES).get(
                self.sale.payment_method, self.sale.payment_method
            ),
        }

        return render_to_string(template_name, context)

    def generate_barcode(self, value: str) -> bytes:
        """
        Generate Code 128 barcode.

        Args:
            value: Value to encode in barcode

        Returns:
            PNG image bytes
        """
        try:
            # Create barcode
            barcode = code128.Code128(value, barHeight=20 * mm, barWidth=0.5 * mm)

            # Create drawing
            drawing = Drawing(100 * mm, 30 * mm)
            barcode.x = 10 * mm
            barcode.y = 5 * mm
            drawing.add(barcode)

            # Render to bytes
            buffer = io.BytesIO()
            renderPDF.drawToFile(drawing, buffer)
            barcode_bytes = buffer.getvalue()
            buffer.close()

            return barcode_bytes

        except Exception as e:
            print(f"Error generating barcode: {e}")
            return b""


class ReceiptService:
    """
    Service class for receipt operations.

    Provides high-level interface for receipt generation,
    storage, and retrieval.
    """

    @staticmethod
    def generate_receipt(
        sale: Sale, format_type: str = "standard", output_format: str = "pdf"
    ) -> bytes:
        """
        Generate receipt for a sale.

        Args:
            sale: Sale instance
            format_type: 'standard' or 'thermal'
            output_format: 'pdf' or 'html'

        Returns:
            Receipt bytes (PDF) or HTML string
        """
        generator = ReceiptGenerator(sale)

        if output_format == "pdf":
            return generator.generate_pdf_receipt(format_type)
        elif output_format == "html":
            return generator.generate_html_receipt(format_type).encode("utf-8")
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    @staticmethod
    def save_receipt(sale: Sale, format_type: str = "standard") -> str:
        """
        Generate and save receipt to file.

        Args:
            sale: Sale instance
            format_type: 'standard' or 'thermal'

        Returns:
            File path of saved receipt
        """
        # Generate receipt
        receipt_bytes = ReceiptService.generate_receipt(sale, format_type, "pdf")

        # Create receipts directory if it doesn't exist
        receipts_dir = os.path.join(settings.MEDIA_ROOT, "receipts", str(sale.tenant.id))
        os.makedirs(receipts_dir, exist_ok=True)

        # Save receipt
        filename = f"receipt_{sale.sale_number}_{format_type}.pdf"
        file_path = os.path.join(receipts_dir, filename)

        with open(file_path, "wb") as f:
            f.write(receipt_bytes)

        return file_path

    @staticmethod
    def get_receipt_url(sale: Sale, format_type: str = "standard") -> str:
        """
        Get URL for accessing receipt.

        Args:
            sale: Sale instance
            format_type: 'standard' or 'thermal'

        Returns:
            Receipt URL
        """
        filename = f"receipt_{sale.sale_number}_{format_type}.pdf"
        return f"{settings.MEDIA_URL}receipts/{sale.tenant.id}/{filename}"
