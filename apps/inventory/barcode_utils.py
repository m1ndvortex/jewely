"""
Barcode and QR code generation utilities.

Provides functions for generating:
- Barcodes (Code128, EAN13, etc.)
- QR codes
- Printable labels
"""

import io

import barcode
import qrcode
from barcode.writer import ImageWriter
from PIL import Image, ImageDraw, ImageFont


def generate_barcode_image(code: str, barcode_type: str = "code128") -> bytes:
    """
    Generate barcode image.

    Args:
        code: The code to encode
        barcode_type: Type of barcode (code128, ean13, etc.)

    Returns:
        PNG image as bytes
    """
    try:
        # Get barcode class
        barcode_class = barcode.get_barcode_class(barcode_type)

        # Generate barcode
        barcode_instance = barcode_class(code, writer=ImageWriter())

        # Save to bytes buffer
        buffer = io.BytesIO()
        barcode_instance.write(
            buffer,
            options={
                "module_width": 0.3,
                "module_height": 15.0,
                "quiet_zone": 6.5,
                "font_size": 10,
                "text_distance": 5.0,
                "background": "white",
                "foreground": "black",
            },
        )

        buffer.seek(0)
        return buffer.getvalue()

    except Exception as e:
        # Return error image
        img = Image.new("RGB", (200, 100), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((10, 40), f"Error: {str(e)}", fill="red")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()


def generate_qr_code_image(data: str, size: int = 10) -> bytes:
    """
    Generate QR code image.

    Args:
        data: Data to encode in QR code
        size: Size of QR code (1-40)

    Returns:
        PNG image as bytes
    """
    try:
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=size,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        # Create image
        img = qr.make_image(fill_color="black", back_color="white")

        # Save to bytes buffer
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()

    except Exception as e:
        # Return error image
        img = Image.new("RGB", (200, 200), color="white")
        draw = ImageDraw.Draw(img)
        draw.text((10, 90), f"Error: {str(e)}", fill="red")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()


def generate_product_label(
    name: str, sku: str, price: str, barcode_data: str, size: tuple = (400, 200)
) -> bytes:
    """
    Generate printable product label with barcode.

    Args:
        name: Product name
        sku: Product SKU
        price: Product price
        barcode_data: Data for barcode
        size: Label size (width, height)

    Returns:
        PNG image as bytes
    """
    try:
        # Create label image
        img = Image.new("RGB", size, color="white")
        draw = ImageDraw.Draw(img)

        # Try to use a nice font, fall back to default
        try:
            title_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16
            )
            text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
        except Exception:
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()

        # Draw product name
        draw.text((10, 10), name[:30], fill="black", font=title_font)

        # Draw SKU
        draw.text((10, 35), f"SKU: {sku}", fill="black", font=text_font)

        # Draw price
        draw.text((10, 55), f"Price: ${price}", fill="black", font=title_font)

        # Generate and paste barcode
        barcode_img_bytes = generate_barcode_image(barcode_data)
        barcode_img = Image.open(io.BytesIO(barcode_img_bytes))

        # Resize barcode to fit
        barcode_img.thumbnail((size[0] - 20, 100))

        # Paste barcode
        img.paste(barcode_img, (10, 85))

        # Save to bytes buffer
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()

    except Exception as e:
        # Return error image
        img = Image.new("RGB", size, color="white")
        draw = ImageDraw.Draw(img)
        draw.text((10, size[1] // 2), f"Error: {str(e)}", fill="red")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()


def generate_qr_label(
    name: str, sku: str, price: str, qr_data: str, size: tuple = (300, 300)
) -> bytes:
    """
    Generate printable product label with QR code.

    Args:
        name: Product name
        sku: Product SKU
        price: Product price
        qr_data: Data for QR code
        size: Label size (width, height)

    Returns:
        PNG image as bytes
    """
    try:
        # Create label image
        img = Image.new("RGB", size, color="white")
        draw = ImageDraw.Draw(img)

        # Try to use a nice font
        try:
            title_font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14
            )
            text_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        except Exception:
            title_font = ImageFont.load_default()
            text_font = ImageFont.load_default()

        # Draw product info
        draw.text((10, 10), name[:25], fill="black", font=title_font)
        draw.text((10, 30), f"SKU: {sku}", fill="black", font=text_font)
        draw.text((10, 48), f"${price}", fill="black", font=title_font)

        # Generate and paste QR code
        qr_img_bytes = generate_qr_code_image(qr_data, size=8)
        qr_img = Image.open(io.BytesIO(qr_img_bytes))

        # Resize QR code
        qr_img.thumbnail((size[0] - 20, size[1] - 80))

        # Center QR code
        qr_x = (size[0] - qr_img.width) // 2
        img.paste(qr_img, (qr_x, 70))

        # Save to bytes buffer
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()

    except Exception as e:
        # Return error image
        img = Image.new("RGB", size, color="white")
        draw = ImageDraw.Draw(img)
        draw.text((10, size[1] // 2), f"Error: {str(e)}", fill="red")

        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)
        return buffer.getvalue()
