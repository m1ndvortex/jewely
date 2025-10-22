"""
Barcode and QR code generation utilities for inventory items.

Implements Requirement 9 and 35:
- Generate barcodes for inventory items using python-barcode
- Generate QR codes using qrcode library
- Create printable barcode labels
"""

import io
from typing import Optional, Tuple

import barcode
import qrcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont


class BarcodeGenerator:
    """
    Generate barcodes for inventory items.

    Supports multiple barcode formats including:
    - CODE128 (default, alphanumeric)
    - EAN13 (13-digit numeric)
    - EAN8 (8-digit numeric)
    - CODE39 (alphanumeric)
    """

    # Supported barcode formats
    CODE128 = "code128"
    EAN13 = "ean13"
    EAN8 = "ean8"
    CODE39 = "code39"

    DEFAULT_FORMAT = CODE128

    @staticmethod
    def generate_barcode(
        data: str, barcode_format: str = DEFAULT_FORMAT, writer_options: Optional[dict] = None
    ) -> Tuple[bytes, str]:
        """
        Generate a barcode image.

        Args:
            data: Data to encode in the barcode (SKU, serial number, etc.)
            barcode_format: Barcode format (code128, ean13, ean8, code39)
            writer_options: Optional writer configuration

        Returns:
            Tuple of (image_bytes, mime_type)

        Raises:
            ValueError: If data is invalid for the specified format
        """
        # Default writer options
        if writer_options is None:
            writer_options = {
                "module_width": 0.3,  # Width of narrowest bar
                "module_height": 15.0,  # Height of bars in mm
                "quiet_zone": 6.5,  # Quiet zone in mm
                "font_size": 10,  # Font size for text
                "text_distance": 5.0,  # Distance between bars and text
                "background": "white",
                "foreground": "black",
            }

        # Get barcode class
        try:
            barcode_class = barcode.get_barcode_class(barcode_format)
        except barcode.errors.BarcodeNotFoundError:
            raise ValueError(f"Unsupported barcode format: {barcode_format}")

        # Create barcode instance
        try:
            barcode_instance = barcode_class(data, writer=ImageWriter())
        except Exception as e:
            raise ValueError(f"Invalid data for {barcode_format}: {str(e)}")

        # Generate barcode image
        buffer = io.BytesIO()
        barcode_instance.write(buffer, options=writer_options)
        buffer.seek(0)

        return buffer.getvalue(), "image/png"

    @staticmethod
    def generate_barcode_for_sku(sku: str) -> Tuple[bytes, str]:
        """
        Generate a CODE128 barcode for an SKU.

        Args:
            sku: Stock Keeping Unit

        Returns:
            Tuple of (image_bytes, mime_type)
        """
        return BarcodeGenerator.generate_barcode(sku, BarcodeGenerator.CODE128)

    @staticmethod
    def generate_barcode_for_serial(serial_number: str) -> Tuple[bytes, str]:
        """
        Generate a CODE128 barcode for a serial number.

        Args:
            serial_number: Serial number

        Returns:
            Tuple of (image_bytes, mime_type)
        """
        return BarcodeGenerator.generate_barcode(serial_number, BarcodeGenerator.CODE128)


class QRCodeGenerator:
    """
    Generate QR codes for inventory items, invoices, and customer loyalty cards.

    QR codes can store more data than barcodes and can be scanned by smartphones.
    """

    @staticmethod
    def generate_qr_code(
        data: str,
        version: Optional[int] = None,
        error_correction: int = qrcode.constants.ERROR_CORRECT_M,
        box_size: int = 10,
        border: int = 4,
        fill_color: str = "black",
        back_color: str = "white",
    ) -> Tuple[bytes, str]:
        """
        Generate a QR code image.

        Args:
            data: Data to encode in the QR code
            version: QR code version (1-40, None for auto)
            error_correction: Error correction level (L, M, Q, H)
            box_size: Size of each box in pixels
            border: Border size in boxes
            fill_color: Foreground color
            back_color: Background color

        Returns:
            Tuple of (image_bytes, mime_type)
        """
        # Create QR code instance
        qr = qrcode.QRCode(
            version=version,
            error_correction=error_correction,
            box_size=box_size,
            border=border,
        )

        # Add data
        qr.add_data(data)
        qr.make(fit=True)

        # Create image
        img = qr.make_image(fill_color=fill_color, back_color=back_color)

        # Convert to bytes
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return buffer.getvalue(), "image/png"

    @staticmethod
    def generate_qr_code_for_item(item_data: dict) -> Tuple[bytes, str]:
        """
        Generate a QR code for an inventory item with comprehensive data.

        Args:
            item_data: Dictionary with item information (sku, name, price, etc.)

        Returns:
            Tuple of (image_bytes, mime_type)
        """
        import json

        # Create compact JSON representation
        qr_data = json.dumps(item_data, separators=(",", ":"))

        return QRCodeGenerator.generate_qr_code(qr_data)

    @staticmethod
    def generate_qr_code_for_url(url: str) -> Tuple[bytes, str]:
        """
        Generate a QR code for a URL (e.g., product page, invoice).

        Args:
            url: URL to encode

        Returns:
            Tuple of (image_bytes, mime_type)
        """
        return QRCodeGenerator.generate_qr_code(url)


class LabelGenerator:
    """
    Generate printable labels with barcodes/QR codes and product information.

    Creates labels suitable for:
    - Price tags
    - Product labels
    - Shelf labels
    - Inventory tags
    """

    # Standard label sizes in mm (width, height)
    LABEL_SMALL = (50, 25)  # Small price tag
    LABEL_MEDIUM = (75, 50)  # Medium product label
    LABEL_LARGE = (100, 75)  # Large shelf label

    @staticmethod
    def create_product_label(
        sku: str,
        name: str,
        price: str,
        barcode_data: bytes,
        label_size: Tuple[int, int] = LABEL_MEDIUM,
        dpi: int = 300,
    ) -> Tuple[bytes, str]:
        """
        Create a printable product label with barcode and information.

        Args:
            sku: Stock Keeping Unit
            name: Product name
            price: Formatted price string
            barcode_data: Barcode image bytes
            label_size: Label size in mm (width, height)
            dpi: Dots per inch for printing

        Returns:
            Tuple of (image_bytes, mime_type)
        """
        # Convert mm to pixels
        mm_to_inch = 0.0393701
        width_px = int(label_size[0] * mm_to_inch * dpi)
        height_px = int(label_size[1] * mm_to_inch * dpi)

        # Create blank label
        label = Image.new("RGB", (width_px, height_px), "white")
        draw = ImageDraw.Draw(label)

        # Load barcode image
        barcode_img = Image.open(io.BytesIO(barcode_data))

        # Resize barcode to fit label (60% of width)
        barcode_width = int(width_px * 0.6)
        barcode_height = int(barcode_img.height * (barcode_width / barcode_img.width))
        barcode_img = barcode_img.resize((barcode_width, barcode_height))

        # Calculate positions
        margin = int(width_px * 0.05)
        current_y = margin

        # Try to load a font, fall back to default if not available
        try:
            font_large = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(dpi * 0.15)
            )
            font_medium = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(dpi * 0.12)
            )
            font_small = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(dpi * 0.10)
            )
        except (OSError, IOError):
            # Fall back to default font
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Draw product name (truncate if too long)
        max_name_length = 30
        display_name = name[:max_name_length] + "..." if len(name) > max_name_length else name
        draw.text((margin, current_y), display_name, fill="black", font=font_medium)
        current_y += int(dpi * 0.15)

        # Draw SKU
        draw.text((margin, current_y), f"SKU: {sku}", fill="black", font=font_small)
        current_y += int(dpi * 0.12)

        # Draw price
        draw.text((margin, current_y), price, fill="black", font=font_large)
        current_y += int(dpi * 0.18)

        # Paste barcode
        barcode_x = (width_px - barcode_width) // 2
        label.paste(barcode_img, (barcode_x, current_y))

        # Convert to bytes
        buffer = io.BytesIO()
        label.save(buffer, format="PNG", dpi=(dpi, dpi))
        buffer.seek(0)

        return buffer.getvalue(), "image/png"

    @staticmethod
    def create_qr_label(
        title: str,
        subtitle: str,
        qr_data: bytes,
        label_size: Tuple[int, int] = LABEL_MEDIUM,
        dpi: int = 300,
    ) -> Tuple[bytes, str]:
        """
        Create a printable label with QR code.

        Args:
            title: Main title text
            subtitle: Subtitle text
            qr_data: QR code image bytes
            label_size: Label size in mm (width, height)
            dpi: Dots per inch for printing

        Returns:
            Tuple of (image_bytes, mime_type)
        """
        # Convert mm to pixels
        mm_to_inch = 0.0393701
        width_px = int(label_size[0] * mm_to_inch * dpi)
        height_px = int(label_size[1] * mm_to_inch * dpi)

        # Create blank label
        label = Image.new("RGB", (width_px, height_px), "white")
        draw = ImageDraw.Draw(label)

        # Load QR code image
        qr_img = Image.open(io.BytesIO(qr_data))

        # Resize QR code to fit label (50% of width)
        qr_size = int(width_px * 0.5)
        qr_img = qr_img.resize((qr_size, qr_size))

        # Calculate positions
        margin = int(width_px * 0.05)

        # Try to load fonts
        try:
            font_title = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", int(dpi * 0.12)
            )
            font_subtitle = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", int(dpi * 0.10)
            )
        except (OSError, IOError):
            font_title = ImageFont.load_default()
            font_subtitle = ImageFont.load_default()

        # Draw title (centered)
        title_bbox = draw.textbbox((0, 0), title, font=font_title)
        title_width = title_bbox[2] - title_bbox[0]
        title_x = (width_px - title_width) // 2
        draw.text((title_x, margin), title, fill="black", font=font_title)

        # Draw subtitle (centered)
        subtitle_bbox = draw.textbbox((0, 0), subtitle, font=font_subtitle)
        subtitle_width = subtitle_bbox[2] - subtitle_bbox[0]
        subtitle_x = (width_px - subtitle_width) // 2
        draw.text(
            (subtitle_x, margin + int(dpi * 0.15)), subtitle, fill="black", font=font_subtitle
        )

        # Paste QR code (centered)
        qr_x = (width_px - qr_size) // 2
        qr_y = margin + int(dpi * 0.30)
        label.paste(qr_img, (qr_x, qr_y))

        # Convert to bytes
        buffer = io.BytesIO()
        label.save(buffer, format="PNG", dpi=(dpi, dpi))
        buffer.seek(0)

        return buffer.getvalue(), "image/png"
