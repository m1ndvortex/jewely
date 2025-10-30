"""
Storage service for organizing and managing category image files.

This module provides the CategoryImageStorage class that handles:
- Organized folder structure (media/categories/{year}/{month}/)
- Unique filename generation with timestamps
- Thumbnail storage in dedicated subfolders
- Image cleanup and deletion
"""

import os
from datetime import datetime

from django.conf import settings
from django.utils.text import slugify


class CategoryImageStorage:
    """Service for storing category images in organized folder structure."""

    BASE_PATH = "categories"

    @classmethod
    def generate_filename(cls, original_filename, category_slug):
        """
        Generate unique filename with timestamp and category slug.

        Args:
            original_filename: Original uploaded filename
            category_slug: URL slug of the category

        Returns:
            str: Generated filename in format {timestamp}_{category_slug}_{original_name}

        Example:
            >>> CategoryImageStorage.generate_filename('photo.jpg', 'gold-rings')
            '20250130_123456_gold-rings_photo.jpg'
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Extract extension from original filename
        name, ext = os.path.splitext(original_filename)
        if not ext:
            ext = ".webp"  # Default to webp if no extension

        # Clean the original filename (remove special characters)
        clean_name = slugify(name)

        return f"{timestamp}_{category_slug}_{clean_name}{ext}"

    @classmethod
    def get_upload_path(cls, filename, is_thumbnail=False):
        """
        Get organized upload path: media/categories/{year}/{month}/[thumbnails/]filename

        Args:
            filename: Generated filename
            is_thumbnail: Whether this is a thumbnail image

        Returns:
            str: Relative path for storage

        Example:
            >>> CategoryImageStorage.get_upload_path('20250130_123456_gold-rings_photo.webp')
            'categories/2025/01/20250130_123456_gold-rings_photo.webp'

            >>> CategoryImageStorage.get_upload_path('20250130_123456_gold-rings_photo.webp', True)
            'categories/2025/01/thumbnails/20250130_123456_gold-rings_photo.webp'
        """
        now = datetime.now()
        year = now.strftime("%Y")
        month = now.strftime("%m")

        path_parts = [cls.BASE_PATH, year, month]
        if is_thumbnail:
            path_parts.append("thumbnails")
        path_parts.append(filename)

        return os.path.join(*path_parts)

    @classmethod
    def save_image(cls, image_bytes, original_filename, category_slug):
        """
        Save optimized image to storage with automatic directory creation.

        Args:
            image_bytes: Optimized image bytes
            original_filename: Original uploaded filename
            category_slug: URL slug of the category

        Returns:
            str: Relative path to saved file

        Raises:
            IOError: If file cannot be written

        Example:
            >>> storage = CategoryImageStorage()
            >>> path = storage.save_image(image_data, 'photo.jpg', 'gold-rings')
            >>> print(path)
            'categories/2025/01/20250130_123456_gold-rings_photo.webp'
        """
        # Generate unique filename
        filename = cls.generate_filename(original_filename, category_slug)

        # Get organized upload path
        upload_path = cls.get_upload_path(filename, is_thumbnail=False)

        # Construct full filesystem path
        full_path = os.path.join(settings.MEDIA_ROOT, upload_path)

        # Ensure directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Save file
        with open(full_path, "wb") as f:
            f.write(image_bytes)

        return upload_path

    @classmethod
    def save_thumbnail(cls, thumbnail_bytes, original_filename, category_slug):
        """
        Save thumbnail image to storage in thumbnails subfolder.

        Args:
            thumbnail_bytes: Thumbnail image bytes
            original_filename: Original uploaded filename
            category_slug: URL slug of the category

        Returns:
            str: Relative path to saved thumbnail

        Raises:
            IOError: If file cannot be written

        Example:
            >>> storage = CategoryImageStorage()
            >>> path = storage.save_thumbnail(thumb_data, 'photo.jpg', 'gold-rings')
            >>> print(path)
            'categories/2025/01/thumbnails/20250130_123456_gold-rings_photo_thumb.webp'
        """
        # Generate unique filename with _thumb suffix
        filename = cls.generate_filename(original_filename, category_slug)
        name, ext = os.path.splitext(filename)
        filename = f"{name}_thumb{ext}"

        # Get organized upload path for thumbnail
        upload_path = cls.get_upload_path(filename, is_thumbnail=True)

        # Construct full filesystem path
        full_path = os.path.join(settings.MEDIA_ROOT, upload_path)

        # Ensure directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        # Save file
        with open(full_path, "wb") as f:
            f.write(thumbnail_bytes)

        return upload_path

    @classmethod
    def delete_image(cls, image_path):
        """
        Delete image and its thumbnail from storage.

        Args:
            image_path: Relative path to image file

        Example:
            >>> CategoryImageStorage.delete_image('categories/2025/01/20250130_123456_gold-rings_photo.webp')
            # Deletes both the main image and its thumbnail
        """
        if not image_path:
            return

        # Delete main image
        full_path = os.path.join(settings.MEDIA_ROOT, image_path)
        if os.path.exists(full_path):
            try:
                os.remove(full_path)
            except OSError:
                pass  # Silently fail if file cannot be deleted

        # Construct thumbnail path
        # Example: categories/2025/01/file.webp -> categories/2025/01/thumbnails/file_thumb.webp
        path_parts = image_path.split(os.sep)
        filename = path_parts[-1]

        # Add _thumb suffix to filename
        name, ext = os.path.splitext(filename)
        thumb_filename = f"{name}_thumb{ext}"

        # Insert 'thumbnails' folder before filename
        path_parts[-1] = thumb_filename
        path_parts.insert(-1, "thumbnails")
        thumb_path = os.sep.join(path_parts)

        # Delete thumbnail
        full_thumb_path = os.path.join(settings.MEDIA_ROOT, thumb_path)
        if os.path.exists(full_thumb_path):
            try:
                os.remove(full_thumb_path)
            except OSError:
                pass  # Silently fail if file cannot be deleted
