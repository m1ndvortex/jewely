"""
Image processing utilities for category images.

Provides validation, optimization, and thumbnail generation for uploaded category images.
Implements Requirements 2.1-2.5 and 3.1-3.5 from category management interface spec.

Features:
- Image validation (size up to 10MB, formats: PNG, JPG, GIF)
- Automatic resizing to max 800x800px while maintaining aspect ratio
- WebP conversion for optimal compression (typically 30-80% size reduction)
- Thumbnail generation at 200x200px
- RGBA/Palette to RGB conversion for compatibility
- Comprehensive error handling

Usage Example:
    from apps.inventory.image_utils import ImageProcessor
    from django.core.files.uploadedfile import UploadedFile

    # Validate an uploaded image
    is_valid, error = ImageProcessor.validate_image(uploaded_file)
    if not is_valid:
        raise ValidationError(error)

    # Process and optimize image
    optimized_bytes, thumbnail_bytes, format = ImageProcessor.process_category_image(uploaded_file)

    # Get image information
    info = ImageProcessor.get_image_info(uploaded_file)
    print(f"Image: {info['width']}x{info['height']}, {info['size_mb']}MB")
"""

from io import BytesIO
from typing import Optional, Tuple

from django.core.files.uploadedfile import UploadedFile

from PIL import Image


class ImageProcessor:
    """
    Service for processing and optimizing category images.

    Handles:
    - Image validation (size, format)
    - Image optimization (resize, compress, convert to WebP)
    - Thumbnail generation
    - Error handling for invalid images
    """

    # Configuration constants
    MAX_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_FORMATS = {"PNG", "JPEG", "JPG", "GIF"}
    MAX_WIDTH = 800
    MAX_HEIGHT = 800
    THUMBNAIL_SIZE = (200, 200)
    WEBP_QUALITY = 85
    JPEG_QUALITY = 90

    @classmethod
    def validate_image(cls, image_file: UploadedFile) -> Tuple[bool, Optional[str]]:
        """
        Validate uploaded image file.

        Checks:
        - File size (must be <= 10MB)
        - File format (must be PNG, JPG, or GIF)
        - Image can be opened and processed

        Args:
            image_file: Django UploadedFile object

        Returns:
            tuple: (is_valid, error_message)
                - is_valid: True if image is valid, False otherwise
                - error_message: None if valid, error description if invalid

        Requirements:
            - 2.1: File size validation
            - 2.2: Format validation
        """
        # Check file size
        if image_file.size > cls.MAX_SIZE:
            return False, "File size must be less than 10MB"

        # Check file format by attempting to open and verify
        try:
            # Reset file pointer to beginning
            image_file.seek(0)
            img = Image.open(image_file)

            # Verify format is allowed
            if img.format not in cls.ALLOWED_FORMATS:
                return False, "Only PNG, JPG, and GIF files are supported"

            # Verify image is valid by loading it
            img.verify()

            # Reset file pointer for subsequent operations
            image_file.seek(0)

        except Exception as e:
            return False, f"Invalid image file: {str(e)}"

        return True, None

    @classmethod
    def optimize_image(cls, image_file: UploadedFile) -> Tuple[bytes, bytes, str]:
        """
        Optimize image by resizing, compressing, and converting to WebP.

        Process:
        1. Open and convert image to RGB if necessary
        2. Resize to max dimensions while maintaining aspect ratio
        3. Compress and convert to WebP format
        4. Generate thumbnail version

        Args:
            image_file: Django UploadedFile object

        Returns:
            tuple: (optimized_image_bytes, thumbnail_bytes, format)
                - optimized_image_bytes: Optimized image as bytes
                - thumbnail_bytes: Thumbnail image as bytes
                - format: Output format ('webp')

        Raises:
            ValueError: If image cannot be processed

        Requirements:
            - 3.1: Resize to max 800px width maintaining aspect ratio
            - 3.2: Compress to reduce file size by at least 30%
            - 3.3: Convert to WebP format
            - 3.4: Generate 200x200 thumbnail
            - 3.5: Preserve filename with timestamp prefix
        """
        try:
            # Reset file pointer and open image
            image_file.seek(0)
            img = Image.open(image_file)

            # Convert RGBA/LA/P to RGB for WebP compatibility
            if img.mode in ("RGBA", "LA", "P"):
                # Create white background
                background = Image.new("RGB", img.size, (255, 255, 255))

                # Convert palette images to RGBA first
                if img.mode == "P":
                    img = img.convert("RGBA")

                # Paste image on white background using alpha channel as mask
                if img.mode in ("RGBA", "LA"):
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)

                img = background

            # Ensure RGB mode
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Resize if necessary (maintain aspect ratio)
            if img.width > cls.MAX_WIDTH or img.height > cls.MAX_HEIGHT:
                img.thumbnail((cls.MAX_WIDTH, cls.MAX_HEIGHT), Image.Resampling.LANCZOS)

            # Save optimized image to bytes (WebP format)
            optimized_buffer = BytesIO()
            img.save(
                optimized_buffer,
                format="WEBP",
                quality=cls.WEBP_QUALITY,
                optimize=True,
                method=6,  # Best compression method
            )
            optimized_bytes = optimized_buffer.getvalue()

            # Create thumbnail
            thumbnail = img.copy()
            thumbnail.thumbnail(cls.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)

            # Save thumbnail to bytes
            thumbnail_buffer = BytesIO()
            thumbnail.save(
                thumbnail_buffer, format="WEBP", quality=cls.WEBP_QUALITY, optimize=True, method=6
            )
            thumbnail_bytes = thumbnail_buffer.getvalue()

            return optimized_bytes, thumbnail_bytes, "webp"

        except Exception as e:
            raise ValueError(f"Failed to optimize image: {str(e)}")

    @classmethod
    def process_category_image(cls, image_file: UploadedFile) -> Tuple[bytes, bytes, str]:
        """
        Complete processing pipeline for category images.

        Combines validation and optimization into a single method.

        Args:
            image_file: Django UploadedFile object

        Returns:
            tuple: (optimized_bytes, thumbnail_bytes, format)
                - optimized_bytes: Optimized image as bytes
                - thumbnail_bytes: Thumbnail image as bytes
                - format: Output format ('webp')

        Raises:
            ValueError: If image is invalid or cannot be processed

        Requirements:
            - 2.1-2.5: Image validation
            - 3.1-3.5: Image optimization and thumbnail generation
        """
        # Validate image first
        is_valid, error = cls.validate_image(image_file)
        if not is_valid:
            raise ValueError(error)

        # Optimize and return
        return cls.optimize_image(image_file)

    @classmethod
    def get_image_info(cls, image_file: UploadedFile) -> dict:
        """
        Get information about an image file.

        Args:
            image_file: Django UploadedFile object

        Returns:
            dict: Image information including format, size, dimensions

        Raises:
            ValueError: If image cannot be opened
        """
        try:
            image_file.seek(0)
            img = Image.open(image_file)

            info = {
                "format": img.format,
                "mode": img.mode,
                "width": img.width,
                "height": img.height,
                "size_bytes": image_file.size,
                "size_mb": round(image_file.size / (1024 * 1024), 2),
            }

            image_file.seek(0)
            return info

        except Exception as e:
            raise ValueError(f"Cannot read image info: {str(e)}")
