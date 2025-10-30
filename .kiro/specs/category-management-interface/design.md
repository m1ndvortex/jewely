# Design Document

## Overview

This design implements a modern, professional category management interface for the jewelry inventory system. The interface follows the **exact design from screen.png** with three main sections: Basic Information, Category Image, and Advanced Settings. The implementation includes a robust image upload system with automatic optimization, organized storage, and real-time preview functionality.

**Design Reference**: `/home/crystalah/kiro/jewely/screen.png` (2560 x 2716 PNG)

The design leverages Django's existing infrastructure while adding new components for image processing and storage management. All functionality is integrated with the existing ProductCategory model and maintains multi-tenancy isolation.

### Design Specifications from screen.png

**Layout**:
- Modal/Card-based design with white background
- Close button (X) in top-right corner
- Two-column grid layout on desktop
- Left column: Basic Information section
- Right column: Category Image section
- Full-width: Advanced Settings section at bottom
- Full-width: Search Engine Snippet Preview at bottom
- Action buttons: "Cancel" (gray) and "Create Category" (teal/green) at bottom-right

**Typography**:
- Main heading: "Add New Category" (large, bold)
- Subtitle: "Create a new product category with its organizational details." (gray, smaller)
- Section headings: "Basic Information", "Category Image", "Advanced Settings" (medium, bold)
- Section descriptions: Gray, smaller text below headings
- Labels: Medium weight, dark text
- Placeholders: Light gray text

**Colors**:
- Primary action button: Teal/green (#10B981 or similar)
- Background: White (#FFFFFF)
- Borders: Light gray (#E5E7EB)
- Text: Dark gray (#111827)
- Secondary text: Medium gray (#6B7280)
- Placeholder text: Light gray (#9CA3AF)

**Spacing**:
- Section padding: 24px (p-6)
- Gap between sections: 24px (gap-6)
- Form field spacing: 16px (space-y-4)
- Label to input spacing: 8px (mt-2)

## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser (Client)                         │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Category Form UI (HTML + Tailwind CSS + Alpine.js)   │ │
│  │  - Drag & Drop Upload                                  │ │
│  │  - Real-time Preview                                   │ │
│  │  - SEO Snippet Preview                                 │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ HTTP POST (multipart/form-data)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Django Web Server                          │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Category View (web_views.py)                          │ │
│  │  - Form Validation                                     │ │
│  │  - Tenant Context                                      │ │
│  └────────────────────────────────────────────────────────┘ │
│                            │                                 │
│                            ▼                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Image Processing Service (image_utils.py)            │ │
│  │  - Validation (size, format)                           │ │
│  │  - Optimization (resize, compress)                     │ │
│  │  - Format Conversion (WebP)                            │ │
│  │  - Thumbnail Generation                                │ │
│  └────────────────────────────────────────────────────────┘ │
│                            │                                 │
│                            ▼                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  Storage Service (storage.py)                          │ │
│  │  - Organized Folder Structure                          │ │
│  │  - Unique Filename Generation                          │ │
│  │  - Path Management                                     │ │
│  └────────────────────────────────────────────────────────┘ │
│                            │                                 │
│                            ▼                                 │
│  ┌────────────────────────────────────────────────────────┐ │
│  │  ProductCategory Model (models.py)                     │ │
│  │  - Database Persistence                                │ │
│  │  - Tenant Isolation                                    │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    File System Storage                       │
│  media/categories/2025/01/                                   │
│  ├── 20250130_123456_gold-rings_image.webp                  │
│  ├── 20250130_123457_silver-necklaces_photo.webp            │
│  └── thumbnails/                                             │
│      ├── 20250130_123456_gold-rings_image_thumb.webp        │
│      └── 20250130_123457_silver-necklaces_photo_thumb.webp  │
└─────────────────────────────────────────────────────────────┘
```

### Component Interaction Flow

1. **User Interaction**: User fills form and uploads image via drag-and-drop or file picker
2. **Client-Side Validation**: JavaScript validates file size and format before upload
3. **Form Submission**: Form data and image sent to Django view via POST request
4. **Server-Side Validation**: Django form validates all fields including image
5. **Image Processing**: Image service optimizes and converts image
6. **Storage**: Storage service saves optimized image with organized naming
7. **Database**: Category data saved to PostgreSQL with image path
8. **Response**: User redirected to category list with success message

## Components and Interfaces

### 1. Frontend Components

#### 1.1 Category Form Template (`category_form.html`)

**Purpose**: Render the category creation/edit form with modern UI

**Key Features**:
- Three-section layout (Basic Info, Image, Advanced Settings)
- Drag-and-drop image upload area
- Real-time SEO snippet preview
- Character counter for meta description
- Auto-slug generation from category name
- Responsive design (2-column on desktop, 1-column on mobile)

**Technologies**:
- Django Templates
- Tailwind CSS for styling
- Alpine.js for interactive components
- JavaScript for drag-and-drop functionality

**Template Structure** (matching screen.png exactly):
```django
{% extends "base.html" %}

{% block content %}
<div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
    <!-- Header with Close Button -->
    <div class="flex items-start justify-between mb-6">
        <div>
            <h1 class="text-2xl font-bold text-gray-900">Add New Category</h1>
            <p class="mt-1 text-sm text-gray-500">Create a new product category with its organizational details.</p>
        </div>
        <a href="{% url 'inventory:category_list' %}" class="text-gray-400 hover:text-gray-500">
            <svg class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
        </a>
    </div>

    <form method="post" enctype="multipart/form-data" x-data="categoryForm()">
        {% csrf_token %}
        
        <!-- Two-column grid on desktop -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            
            <!-- Left Column: Basic Information -->
            <div class="bg-white rounded-lg border border-gray-200 p-6">
                <div class="mb-4">
                    <h3 class="text-lg font-semibold text-gray-900">Basic Information</h3>
                    <p class="text-sm text-gray-500">Essential category details.</p>
                </div>
                
                <!-- Category Name -->
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700">Category Name*</label>
                    {{ form.name }}
                    <p class="mt-1 text-xs text-gray-500">e.g. Rings, Necklaces, Bracelets</p>
                </div>
                
                <!-- Parent Category -->
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700">Parent Category</label>
                    {{ form.parent }}
                </div>
                
                <!-- Description -->
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700">Description</label>
                    {{ form.description }}
                    <p class="mt-1 text-xs text-gray-500">Provide a detailed description of this category.</p>
                </div>
                
                <!-- Active Checkbox -->
                <div class="flex items-start">
                    <div class="flex items-center h-5">
                        {{ form.is_active }}
                    </div>
                    <div class="ml-3">
                        <label class="text-sm font-medium text-gray-700">Active</label>
                        <p class="text-xs text-gray-500">Inactive categories are hidden from the store.</p>
                    </div>
                </div>
            </div>

            <!-- Right Column: Category Image -->
            <div class="bg-white rounded-lg border border-gray-200 p-6">
                <div class="mb-4">
                    <h3 class="text-lg font-semibold text-gray-900">Category Image</h3>
                    <p class="text-sm text-gray-500">Upload an image to represent this category.</p>
                </div>
                
                <!-- Upload Area -->
                <div x-data="imageUpload()" class="mt-4">
                    <div 
                        @dragover.prevent="handleDragOver"
                        @dragleave.prevent="handleDragLeave"
                        @drop.prevent="handleDrop"
                        :class="{'border-teal-500 bg-teal-50': isDragging}"
                        class="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center cursor-pointer hover:border-gray-400 transition-colors"
                        @click="$refs.fileInput.click()"
                    >
                        <template x-if="!imagePreview">
                            <div>
                                <!-- Cloud Upload Icon -->
                                <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                                </svg>
                                <p class="mt-2 text-sm text-gray-600">
                                    <span class="font-medium text-teal-600 hover:text-teal-500">Upload a file</span>
                                    <span class="text-gray-500"> or drag and drop</span>
                                </p>
                                <p class="mt-1 text-xs text-gray-500">PNG, JPG, GIF up to 10MB</p>
                            </div>
                        </template>
                        
                        <template x-if="imagePreview">
                            <div class="relative">
                                <img :src="imagePreview" class="mx-auto max-h-48 rounded-lg" />
                                <button 
                                    type="button"
                                    @click.stop="removeImage"
                                    class="absolute top-2 right-2 bg-red-500 text-white rounded-full p-1 hover:bg-red-600"
                                >
                                    <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                                <p class="mt-2 text-sm text-gray-600" x-text="fileName"></p>
                                <p class="text-xs text-gray-500" x-text="fileSize"></p>
                            </div>
                        </template>
                    </div>
                    
                    <input 
                        type="file" 
                        x-ref="fileInput"
                        @change="handleFileSelect"
                        accept="image/png,image/jpeg,image/jpg,image/gif"
                        class="hidden"
                        id="id_image"
                        name="image"
                    />
                </div>
            </div>
        </div>

        <!-- Advanced Settings Section -->
        <div class="bg-white rounded-lg border border-gray-200 p-6 mt-6">
            <div class="mb-4">
                <h3 class="text-lg font-semibold text-gray-900">Advanced Settings</h3>
                <p class="text-sm text-gray-500">URL and search engine optimization.</p>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <!-- URL Slug -->
                <div>
                    <label class="block text-sm font-medium text-gray-700">URL Slug</label>
                    {{ form.slug }}
                    <p class="mt-1 text-xs text-gray-500">e.g. gold-engagement-rings</p>
                </div>
                
                <!-- Display Order -->
                <div>
                    <label class="block text-sm font-medium text-gray-700">Display Order</label>
                    {{ form.display_order }}
                </div>
            </div>
            
            <div class="mt-4">
                <!-- SEO Title -->
                <div class="mb-4">
                    <label class="block text-sm font-medium text-gray-700">SEO Title (Optional)</label>
                    {{ form.meta_title }}
                    <p class="mt-1 text-xs text-gray-500">Title for search engines</p>
                </div>
                
                <!-- SEO Meta Description -->
                <div>
                    <label class="block text-sm font-medium text-gray-700">SEO Meta Description (Optional)</label>
                    {{ form.meta_description }}
                    <div class="flex justify-between mt-1">
                        <p class="text-xs text-gray-500">Characters: <span x-text="descriptionLength">0</span></p>
                        <p class="text-xs text-gray-500">Recommended: 120-158 characters</p>
                    </div>
                </div>
            </div>
        </div>

        <!-- Search Engine Snippet Preview -->
        <div class="bg-white rounded-lg border border-gray-200 p-6 mt-6" x-data="seoPreview()">
            <h3 class="text-lg font-semibold text-gray-900 mb-4">Search Engine Snippet Preview</h3>
            
            <div class="bg-gray-50 rounded-lg p-4">
                <p class="text-sm text-green-600" x-text="previewUrl"></p>
                <h4 class="text-lg text-blue-600 hover:underline cursor-pointer mt-1" x-text="previewTitle"></h4>
                <p class="text-sm text-gray-600 mt-1" x-text="previewDescription"></p>
            </div>
        </div>

        <!-- Action Buttons -->
        <div class="flex justify-end gap-3 mt-6">
            <a href="{% url 'inventory:category_list' %}" 
               class="px-4 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50">
                Cancel
            </a>
            <button type="submit" 
                    class="px-4 py-2 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-teal-600 hover:bg-teal-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-teal-500">
                <svg class="inline-block h-4 w-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
                </svg>
                Create Category
            </button>
        </div>
    </form>
</div>
{% endblock %}
```

#### 1.2 Image Upload Component

**Purpose**: Handle drag-and-drop and click-to-upload functionality

**JavaScript Implementation**:
```javascript
// Alpine.js component for image upload
Alpine.data('imageUpload', () => ({
    isDragging: false,
    imagePreview: null,
    fileName: null,
    fileSize: null,
    
    handleDragOver(e) {
        e.preventDefault();
        this.isDragging = true;
    },
    
    handleDragLeave(e) {
        e.preventDefault();
        this.isDragging = false;
    },
    
    handleDrop(e) {
        e.preventDefault();
        this.isDragging = false;
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            this.handleFile(files[0]);
        }
    },
    
    handleFileSelect(e) {
        const files = e.target.files;
        if (files.length > 0) {
            this.handleFile(files[0]);
        }
    },
    
    handleFile(file) {
        // Validate file type
        const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif'];
        if (!validTypes.includes(file.type)) {
            alert('Only PNG, JPG, and GIF files are supported');
            return;
        }
        
        // Validate file size (10MB)
        if (file.size > 10 * 1024 * 1024) {
            alert('File size must be less than 10MB');
            return;
        }
        
        // Show preview
        this.fileName = file.name;
        this.fileSize = this.formatFileSize(file.size);
        
        const reader = new FileReader();
        reader.onload = (e) => {
            this.imagePreview = e.target.result;
        };
        reader.readAsDataURL(file);
    },
    
    removeImage() {
        this.imagePreview = null;
        this.fileName = null;
        this.fileSize = null;
        document.getElementById('id_image').value = '';
    },
    
    formatFileSize(bytes) {
        if (bytes < 1024) return bytes + ' B';
        if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
        return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    }
}));
```

#### 1.3 SEO Preview Component

**Purpose**: Real-time preview of search engine snippet

**JavaScript Implementation**:
```javascript
// Alpine.js component for SEO preview
Alpine.data('seoPreview', () => ({
    title: '',
    description: '',
    slug: '',
    baseUrl: window.location.origin,
    
    get previewUrl() {
        return `${this.baseUrl}/categories/${this.slug || 'new-category'}`;
    },
    
    get previewTitle() {
        return this.title || 'Title for search engines';
    },
    
    get previewDescription() {
        return this.description || 'Description for search engines';
    },
    
    get descriptionLength() {
        return this.description.length;
    },
    
    updateSlug(name) {
        if (!this.slug) {
            this.slug = name.toLowerCase()
                .replace(/[^a-z0-9]+/g, '-')
                .replace(/^-+|-+$/g, '');
        }
    }
}));
```

### 2. Backend Components

#### 2.1 Image Processing Service (`apps/inventory/image_utils.py`)

**Purpose**: Handle image validation, optimization, and format conversion

**Class: ImageProcessor**

```python
from PIL import Image
from io import BytesIO
import os

class ImageProcessor:
    """Service for processing and optimizing category images."""
    
    MAX_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_FORMATS = ['PNG', 'JPEG', 'JPG', 'GIF']
    MAX_WIDTH = 800
    MAX_HEIGHT = 800
    THUMBNAIL_SIZE = (200, 200)
    WEBP_QUALITY = 85
    JPEG_QUALITY = 90
    
    @classmethod
    def validate_image(cls, image_file):
        """
        Validate uploaded image file.
        
        Args:
            image_file: Django UploadedFile object
            
        Returns:
            tuple: (is_valid, error_message)
        """
        # Check file size
        if image_file.size > cls.MAX_SIZE:
            return False, "File size must be less than 10MB"
        
        # Check file format
        try:
            img = Image.open(image_file)
            if img.format not in cls.ALLOWED_FORMATS:
                return False, "Only PNG, JPG, and GIF files are supported"
        except Exception as e:
            return False, f"Invalid image file: {str(e)}"
        
        return True, None
    
    @classmethod
    def optimize_image(cls, image_file):
        """
        Optimize image by resizing and compressing.
        
        Args:
            image_file: Django UploadedFile object
            
        Returns:
            tuple: (optimized_image_bytes, thumbnail_bytes, format)
        """
        # Open image
        img = Image.open(image_file)
        
        # Convert RGBA to RGB if necessary
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        
        # Resize if necessary (maintain aspect ratio)
        if img.width > cls.MAX_WIDTH or img.height > cls.MAX_HEIGHT:
            img.thumbnail((cls.MAX_WIDTH, cls.MAX_HEIGHT), Image.Resampling.LANCZOS)
        
        # Save optimized image to bytes (WebP format)
        optimized_buffer = BytesIO()
        img.save(optimized_buffer, format='WEBP', quality=cls.WEBP_QUALITY, optimize=True)
        optimized_bytes = optimized_buffer.getvalue()
        
        # Create thumbnail
        thumbnail = img.copy()
        thumbnail.thumbnail(cls.THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
        thumbnail_buffer = BytesIO()
        thumbnail.save(thumbnail_buffer, format='WEBP', quality=cls.WEBP_QUALITY, optimize=True)
        thumbnail_bytes = thumbnail_buffer.getvalue()
        
        return optimized_bytes, thumbnail_bytes, 'webp'
    
    @classmethod
    def process_category_image(cls, image_file):
        """
        Complete processing pipeline for category images.
        
        Args:
            image_file: Django UploadedFile object
            
        Returns:
            tuple: (optimized_bytes, thumbnail_bytes, format) or (None, None, None) if invalid
        """
        # Validate
        is_valid, error = cls.validate_image(image_file)
        if not is_valid:
            raise ValueError(error)
        
        # Optimize
        return cls.optimize_image(image_file)
```

#### 2.2 Storage Service (`apps/inventory/storage.py`)

**Purpose**: Manage organized file storage with proper naming conventions

**Class: CategoryImageStorage**

```python
import os
from datetime import datetime
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils.text import slugify

class CategoryImageStorage:
    """Service for storing category images in organized folder structure."""
    
    BASE_PATH = 'categories'
    
    @classmethod
    def generate_filename(cls, original_filename, category_slug):
        """
        Generate unique filename with timestamp and category slug.
        
        Args:
            original_filename: Original uploaded filename
            category_slug: URL slug of the category
            
        Returns:
            str: Generated filename
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        ext = os.path.splitext(original_filename)[1].lower()
        if not ext:
            ext = '.webp'
        
        return f"{timestamp}_{category_slug}{ext}"
    
    @classmethod
    def get_upload_path(cls, filename, is_thumbnail=False):
        """
        Get organized upload path: media/categories/{year}/{month}/[thumbnails/]filename
        
        Args:
            filename: Generated filename
            is_thumbnail: Whether this is a thumbnail image
            
        Returns:
            str: Relative path for storage
        """
        now = datetime.now()
        year = now.strftime('%Y')
        month = now.strftime('%m')
        
        path_parts = [cls.BASE_PATH, year, month]
        if is_thumbnail:
            path_parts.append('thumbnails')
        path_parts.append(filename)
        
        return os.path.join(*path_parts)
    
    @classmethod
    def save_image(cls, image_bytes, original_filename, category_slug):
        """
        Save optimized image to storage.
        
        Args:
            image_bytes: Optimized image bytes
            original_filename: Original uploaded filename
            category_slug: URL slug of the category
            
        Returns:
            str: Relative path to saved file
        """
        filename = cls.generate_filename(original_filename, category_slug)
        upload_path = cls.get_upload_path(filename, is_thumbnail=False)
        
        # Ensure directory exists
        full_path = os.path.join(settings.MEDIA_ROOT, upload_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Save file
        with open(full_path, 'wb') as f:
            f.write(image_bytes)
        
        return upload_path
    
    @classmethod
    def save_thumbnail(cls, thumbnail_bytes, original_filename, category_slug):
        """
        Save thumbnail image to storage.
        
        Args:
            thumbnail_bytes: Thumbnail image bytes
            original_filename: Original uploaded filename
            category_slug: URL slug of the category
            
        Returns:
            str: Relative path to saved thumbnail
        """
        filename = cls.generate_filename(original_filename, category_slug)
        filename = filename.replace('.', '_thumb.')
        upload_path = cls.get_upload_path(filename, is_thumbnail=True)
        
        # Ensure directory exists
        full_path = os.path.join(settings.MEDIA_ROOT, upload_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        # Save file
        with open(full_path, 'wb') as f:
            f.write(thumbnail_bytes)
        
        return upload_path
    
    @classmethod
    def delete_image(cls, image_path):
        """
        Delete image and its thumbnail from storage.
        
        Args:
            image_path: Relative path to image file
        """
        if not image_path:
            return
        
        # Delete main image
        full_path = os.path.join(settings.MEDIA_ROOT, image_path)
        if os.path.exists(full_path):
            os.remove(full_path)
        
        # Delete thumbnail
        path_parts = image_path.split('/')
        filename = path_parts[-1]
        thumb_filename = filename.replace('.', '_thumb.')
        path_parts[-1] = thumb_filename
        path_parts.insert(-1, 'thumbnails')
        thumb_path = '/'.join(path_parts)
        
        full_thumb_path = os.path.join(settings.MEDIA_ROOT, thumb_path)
        if os.path.exists(full_thumb_path):
            os.remove(full_thumb_path)
```

#### 2.3 Updated Category Form (`apps/inventory/forms.py`)

**Enhancement**: Add image validation and processing integration

```python
class ProductCategoryForm(forms.ModelForm):
    """Enhanced form with image processing."""
    
    # ... existing fields ...
    
    def clean_image(self):
        """Validate uploaded image."""
        image = self.cleaned_data.get('image')
        if image:
            from .image_utils import ImageProcessor
            is_valid, error = ImageProcessor.validate_image(image)
            if not is_valid:
                raise ValidationError(error)
        return image
    
    def save(self, commit=True):
        """Save category with image processing."""
        instance = super().save(commit=False)
        
        # Process image if uploaded
        if 'image' in self.changed_data and self.cleaned_data.get('image'):
            from .image_utils import ImageProcessor
            from .storage import CategoryImageStorage
            
            image_file = self.cleaned_data['image']
            
            # Delete old image if exists
            if instance.pk and instance.image:
                CategoryImageStorage.delete_image(instance.image.name)
            
            # Process new image
            optimized_bytes, thumbnail_bytes, format = ImageProcessor.process_category_image(image_file)
            
            # Generate slug if not set
            if not instance.slug:
                instance.slug = slugify(instance.name)
            
            # Save optimized image
            image_path = CategoryImageStorage.save_image(
                optimized_bytes,
                image_file.name,
                instance.slug
            )
            
            # Save thumbnail
            CategoryImageStorage.save_thumbnail(
                thumbnail_bytes,
                image_file.name,
                instance.slug
            )
            
            # Update instance with new path
            instance.image = image_path
        
        if commit:
            instance.save()
        
        return instance
```

#### 2.4 Updated Category View (`apps/inventory/web_views.py`)

**Enhancement**: Handle image processing in view

```python
@login_required
@tenant_required
@require_http_methods(["GET", "POST"])
def category_create_view(request):
    """Create new product category with image processing."""
    if request.method == "POST":
        form = ProductCategoryForm(request.POST, request.FILES, tenant=request.user.tenant)
        if form.is_valid():
            try:
                category = form.save(commit=False)
                category.tenant = request.user.tenant
                category.save()
                messages.success(
                    request,
                    _('Category "{}" created successfully.').format(category.name)
                )
                return redirect("inventory:category_list")
            except ValueError as e:
                messages.error(request, str(e))
        else:
            # Show form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        # Pre-select parent if provided in URL
        parent_id = request.GET.get("parent")
        initial = {}
        if parent_id:
            try:
                parent = ProductCategory.objects.get(id=parent_id, tenant=request.user.tenant)
                initial["parent"] = parent
            except ProductCategory.DoesNotExist:
                pass

        form = ProductCategoryForm(tenant=request.user.tenant, initial=initial)

    return render(
        request,
        "inventory/category_form.html",
        {
            "form": form,
            "title": _("Add New Category"),
            "is_edit": False,
            "max_file_size_mb": 10,
            "allowed_formats": "PNG, JPG, GIF"
        },
    )
```

## Data Models

### ProductCategory Model (Existing - No Changes Required)

The existing `ProductCategory` model already has all necessary fields:

```python
class ProductCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    parent = models.ForeignKey('self', null=True, blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='category_images/', null=True, blank=True)
    slug = models.SlugField(max_length=120, blank=True)
    display_order = models.IntegerField(default=0)
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

**Note**: The `upload_to` parameter will be overridden by our storage service to use the organized folder structure.

## Error Handling

### Client-Side Error Handling

1. **File Size Validation**: JavaScript checks file size before upload
2. **File Type Validation**: JavaScript validates file extension
3. **User Feedback**: Alert messages for validation errors

### Server-Side Error Handling

1. **Form Validation Errors**: Django form validation with field-specific errors
2. **Image Processing Errors**: Try-catch blocks with user-friendly messages
3. **Storage Errors**: Handle file system errors gracefully
4. **Database Errors**: Transaction rollback on failure

**Error Response Flow**:
```python
try:
    # Validate image
    is_valid, error = ImageProcessor.validate_image(image_file)
    if not is_valid:
        raise ValueError(error)
    
    # Process image
    optimized_bytes, thumbnail_bytes, format = ImageProcessor.optimize_image(image_file)
    
    # Save to storage
    image_path = CategoryImageStorage.save_image(...)
    
    # Save to database
    category.save()
    
except ValueError as e:
    messages.error(request, f"Image validation failed: {str(e)}")
except IOError as e:
    messages.error(request, f"Failed to save image: {str(e)}")
except Exception as e:
    messages.error(request, f"An unexpected error occurred: {str(e)}")
    # Log error for debugging
    logger.exception("Category creation failed")
```

## Testing Strategy

### Unit Tests

1. **Image Processing Tests** (`test_image_utils.py`):
   - Test image validation (size, format)
   - Test image optimization (resize, compress)
   - Test format conversion (PNG/JPG to WebP)
   - Test thumbnail generation
   - Test error handling for invalid images

2. **Storage Tests** (`test_storage.py`):
   - Test filename generation
   - Test path generation
   - Test file saving
   - Test file deletion
   - Test directory creation

3. **Form Tests** (`test_forms.py`):
   - Test form validation
   - Test image field validation
   - Test slug auto-generation
   - Test parent category validation

### Integration Tests

1. **Category Creation Flow** (`test_category_creation.py`):
   - Test complete category creation with image
   - Test category creation without image
   - Test category update with new image
   - Test category update without changing image
   - Test image replacement

2. **View Tests** (`test_category_views.py`):
   - Test GET request renders form
   - Test POST request creates category
   - Test POST with invalid data shows errors
   - Test tenant isolation
   - Test permission checks

### Browser Tests (Playwright)

1. **UI Interaction Tests**:
   - Test drag-and-drop upload
   - Test click-to-upload
   - Test image preview display
   - Test image removal
   - Test SEO preview updates
   - Test form submission
   - Test validation messages

2. **Responsive Design Tests**:
   - Test layout on desktop (1920x1080)
   - Test layout on tablet (768x1024)
   - Test layout on mobile (375x667)

### Test Data Requirements

- Sample images in various formats (PNG, JPG, GIF)
- Sample images of various sizes (< 1MB, 5MB, > 10MB)
- Sample images with different dimensions
- Sample category data with various field combinations

## Performance Considerations

### Image Processing Optimization

1. **Lazy Loading**: Process images asynchronously if needed
2. **Caching**: Cache processed images to avoid reprocessing
3. **Progressive Upload**: Show upload progress for large files
4. **Background Processing**: Consider Celery for large batch operations

### Storage Optimization

1. **CDN Integration**: Serve images from CDN in production
2. **Compression**: Use WebP format for 30-50% size reduction
3. **Lazy Loading**: Implement lazy loading for category images in lists
4. **Cleanup**: Periodic cleanup of orphaned images

### Database Optimization

1. **Indexes**: Existing indexes on tenant, slug, and parent are sufficient
2. **Query Optimization**: Use select_related for parent category
3. **Caching**: Cache category tree structure

## Security Considerations

### File Upload Security

1. **File Type Validation**: Strict validation of file types
2. **File Size Limits**: Enforce 10MB limit
3. **Filename Sanitization**: Remove special characters from filenames
4. **Path Traversal Prevention**: Use safe path joining methods
5. **Virus Scanning**: Consider integrating virus scanning for production

### Access Control

1. **Tenant Isolation**: Ensure users can only access their tenant's categories
2. **Permission Checks**: Verify user has permission to create/edit categories
3. **CSRF Protection**: Django CSRF tokens on all forms
4. **XSS Prevention**: Escape all user input in templates

### Data Validation

1. **Server-Side Validation**: Never trust client-side validation alone
2. **SQL Injection Prevention**: Use Django ORM (parameterized queries)
3. **Input Sanitization**: Sanitize all text inputs
4. **Image Validation**: Verify image content, not just extension

## Deployment Considerations

### Environment Configuration

```python
# settings.py additions
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# Image processing settings
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_IMAGE_FORMATS = ['PNG', 'JPEG', 'JPG', 'GIF']
IMAGE_MAX_WIDTH = 800
IMAGE_MAX_HEIGHT = 800
THUMBNAIL_SIZE = (200, 200)
```

### Dependencies

```txt
# requirements.txt additions
Pillow==10.1.0  # Image processing
```

### Static Files

- Ensure MEDIA_ROOT directory exists and is writable
- Configure web server (nginx) to serve media files
- Set up proper permissions (755 for directories, 644 for files)

### Production Checklist

- [ ] Configure CDN for media files
- [ ] Set up automated backups for media directory
- [ ] Configure proper file permissions
- [ ] Enable image optimization
- [ ] Set up monitoring for storage usage
- [ ] Configure rate limiting for uploads
- [ ] Test image processing performance
- [ ] Verify tenant isolation
- [ ] Test responsive design on real devices
- [ ] Validate accessibility compliance
