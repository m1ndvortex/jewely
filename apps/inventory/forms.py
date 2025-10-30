"""
Forms for inventory management.

Provides comprehensive forms with validation for:
- Inventory item creation and editing
- Stock adjustments
- Product categories with automatic image processing

ProductCategoryForm includes:
- Server-side image validation (size, format)
- Automatic image optimization (resize, compress, WebP conversion)
- Thumbnail generation (200x200px)
- Organized storage (media/categories/{year}/{month}/)
- Old image cleanup when replacing
- Tenant context preservation
- Automatic slug generation
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from apps.core.models import Branch

from .models import InventoryItem, ProductCategory


class InventoryItemForm(forms.ModelForm):
    """
    Comprehensive form for creating and editing inventory items.

    Features:
    - Field validation
    - Dynamic category and branch selection
    - Price validation
    - Stock level validation
    """

    class Meta:
        model = InventoryItem
        fields = [
            "sku",
            "name",
            "description",
            "category",
            "branch",
            "karat",
            "weight_grams",
            "craftsmanship_level",
            "cost_price",
            "markup_percentage",
            "selling_price",
            "quantity",
            "min_quantity",
            "serial_number",
            "lot_number",
            "barcode",
            "supplier_sku",
            "is_active",
        ]
        widgets = {
            "sku": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "placeholder": _("Enter SKU"),
                }
            ),
            "name": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "placeholder": _("Enter product name"),
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "rows": 4,
                    "placeholder": _("Enter product description"),
                }
            ),
            "category": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                }
            ),
            "branch": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                }
            ),
            "karat": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                }
            ),
            "weight_grams": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "step": "0.001",
                    "placeholder": _("Weight in grams"),
                }
            ),
            "craftsmanship_level": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                }
            ),
            "cost_price": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "step": "0.01",
                    "placeholder": _("Cost price"),
                }
            ),
            "markup_percentage": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "step": "0.01",
                    "placeholder": _("Markup %"),
                }
            ),
            "selling_price": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "step": "0.01",
                    "placeholder": _("Selling price"),
                }
            ),
            "quantity": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "placeholder": _("Current quantity"),
                }
            ),
            "min_quantity": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "placeholder": _("Minimum quantity threshold"),
                }
            ),
            "serial_number": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "placeholder": _("Serial number (optional)"),
                }
            ),
            "lot_number": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "placeholder": _("Lot number (optional)"),
                }
            ),
            "barcode": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "placeholder": _("Barcode (optional)"),
                }
            ),
            "supplier_sku": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "placeholder": _("Supplier SKU (optional)"),
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600"
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        # Filter categories and branches by tenant
        if self.tenant:
            self.fields["category"].queryset = ProductCategory.objects.filter(
                tenant=self.tenant
            ).order_by("name")
            self.fields["branch"].queryset = Branch.objects.filter(tenant=self.tenant).order_by(
                "name"
            )

        # Make some fields optional
        self.fields["serial_number"].required = False
        self.fields["lot_number"].required = False
        self.fields["barcode"].required = False
        self.fields["supplier_sku"].required = False
        self.fields["description"].required = False
        self.fields["markup_percentage"].required = False

    def clean(self):
        """Validate form data."""
        cleaned_data = super().clean()

        # Validate prices
        cost_price = cleaned_data.get("cost_price")
        selling_price = cleaned_data.get("selling_price")

        if cost_price and selling_price:
            if selling_price < cost_price:
                raise ValidationError(
                    {"selling_price": _("Selling price cannot be less than cost price.")}
                )

        # Validate stock levels
        quantity = cleaned_data.get("quantity")
        min_quantity = cleaned_data.get("min_quantity")

        if quantity and quantity < 0:
            raise ValidationError({"quantity": _("Quantity cannot be negative.")})

        if min_quantity and min_quantity < 0:
            raise ValidationError({"min_quantity": _("Minimum quantity cannot be negative.")})

        # Validate weight
        weight_grams = cleaned_data.get("weight_grams")
        if weight_grams and weight_grams <= 0:
            raise ValidationError({"weight_grams": _("Weight must be greater than zero.")})

        return cleaned_data


class StockAdjustmentForm(forms.Form):
    """
    Form for adjusting stock levels.
    """

    ADJUSTMENT_TYPES = [
        ("increase", _("Increase Stock")),
        ("decrease", _("Decrease Stock")),
    ]

    REASON_CHOICES = [
        ("purchase", _("Purchase/Receiving")),
        ("sale", _("Sale")),
        ("return", _("Customer Return")),
        ("damage", _("Damage/Loss")),
        ("theft", _("Theft")),
        ("adjustment", _("Stock Count Adjustment")),
        ("transfer", _("Transfer")),
        ("other", _("Other")),
    ]

    adjustment_type = forms.ChoiceField(
        choices=ADJUSTMENT_TYPES,
        widget=forms.RadioSelect(
            attrs={"class": "focus:ring-blue-500 h-4 w-4 text-blue-600 border-gray-300"}
        ),
        label=_("Adjustment Type"),
    )

    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(
            attrs={
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                "placeholder": _("Enter quantity"),
            }
        ),
        label=_("Quantity"),
    )

    reason = forms.ChoiceField(
        choices=REASON_CHOICES,
        widget=forms.Select(
            attrs={
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
            }
        ),
        label=_("Reason"),
    )

    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                "rows": 3,
                "placeholder": _("Additional notes (optional)"),
            }
        ),
        label=_("Notes"),
    )


class ProductCategoryForm(forms.ModelForm):
    """
    Form for creating and editing product categories with full support for images and metadata.
    Includes automatic image processing, optimization, and organized storage.
    """

    class Meta:
        model = ProductCategory
        fields = [
            "name",
            "parent",
            "description",
            "image",
            "slug",
            "display_order",
            "meta_title",
            "meta_description",
            "is_active",
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "placeholder": _("Enter category name"),
                }
            ),
            "parent": forms.Select(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                }
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "rows": 4,
                    "placeholder": _("Enter category description (optional)"),
                }
            ),
            "image": forms.FileInput(
                attrs={
                    "class": "mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100 dark:file:bg-gray-700 dark:file:text-gray-300",
                    "accept": "image/*",
                }
            ),
            "slug": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "placeholder": _("Auto-generated from name if left empty"),
                }
            ),
            "display_order": forms.NumberInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "placeholder": _("0"),
                }
            ),
            "meta_title": forms.TextInput(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "placeholder": _("SEO title (optional)"),
                }
            ),
            "meta_description": forms.Textarea(
                attrs={
                    "class": "mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:text-white",
                    "rows": 2,
                    "placeholder": _("SEO description (optional)"),
                }
            ),
            "is_active": forms.CheckboxInput(
                attrs={
                    "class": "rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-500 focus:ring-blue-500 dark:bg-gray-700 dark:border-gray-600"
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        self.tenant = kwargs.pop("tenant", None)
        super().__init__(*args, **kwargs)

        # Filter parent categories by tenant (exclude self to prevent circular reference)
        if self.tenant:
            queryset = ProductCategory.objects.filter(tenant=self.tenant).order_by("name")
            if self.instance.pk:
                queryset = queryset.exclude(pk=self.instance.pk)
            self.fields["parent"].queryset = queryset

        # Make fields optional
        self.fields["description"].required = False
        self.fields["parent"].required = False
        self.fields["parent"].empty_label = _("No parent (top-level category)")
        self.fields["image"].required = False
        self.fields["slug"].required = False
        self.fields["meta_title"].required = False
        self.fields["meta_description"].required = False

    def clean_image(self):
        """
        Validate uploaded image file.

        Performs server-side validation for:
        - File size (max 10MB)
        - File format (PNG, JPG, GIF only)
        - Image integrity

        Returns:
            UploadedFile: Validated image file or None

        Raises:
            ValidationError: If image validation fails
        """
        image = self.cleaned_data.get("image")

        if image:
            try:
                from .image_utils import ImageProcessor

                # Validate image using ImageProcessor
                is_valid, error = ImageProcessor.validate_image(image)
                if not is_valid:
                    raise ValidationError(error)

                # Reset file pointer after validation
                image.seek(0)

            except ImportError:
                # If ImageProcessor not available, skip validation
                pass
            except Exception as e:
                raise ValidationError(_("Error validating image: %(error)s") % {"error": str(e)})

        return image

    def clean(self):
        """Validate category data."""
        cleaned_data = super().clean()

        # Prevent circular parent relationships
        parent = cleaned_data.get("parent")
        if parent and self.instance.pk:
            if parent.id == self.instance.id:
                raise ValidationError({"parent": _("A category cannot be its own parent.")})

            # Check for circular reference
            current = parent
            while current:
                if current.id == self.instance.id:
                    raise ValidationError(
                        {"parent": _("This would create a circular parent relationship.")}
                    )
                current = current.parent

        return cleaned_data

    def save(self, commit=True):  # noqa: C901
        """
        Save category with automatic image processing.

        Handles:
        - Image optimization (resize, compress, convert to WebP)
        - Thumbnail generation
        - Organized storage (media/categories/{year}/{month}/)
        - Old image cleanup when replacing
        - Automatic slug generation
        - Tenant context preservation

        Args:
            commit: Whether to save to database immediately

        Returns:
            ProductCategory: Saved category instance

        Raises:
            ValueError: If image processing fails
        """
        from django.utils.text import slugify

        instance = super().save(commit=False)

        # Ensure tenant context is maintained
        if self.tenant and not instance.tenant_id:
            instance.tenant = self.tenant

        # Generate slug if not provided
        if not instance.slug and instance.name:
            instance.slug = slugify(instance.name)

        # Process image if uploaded
        if "image" in self.changed_data and self.cleaned_data.get("image"):
            try:
                from .image_utils import ImageProcessor
                from .storage import CategoryImageStorage

                image_file = self.cleaned_data["image"]

                # Store old image path for cleanup
                old_image_path = None
                if instance.pk and instance.image:
                    old_image_path = instance.image.name

                # Process new image (optimize, resize, convert to WebP)
                optimized_bytes, thumbnail_bytes, format_ext = (
                    ImageProcessor.process_category_image(image_file)
                )

                # Save optimized image with organized naming
                image_path = CategoryImageStorage.save_image(
                    optimized_bytes, image_file.name, instance.slug
                )

                # Save thumbnail
                CategoryImageStorage.save_thumbnail(thumbnail_bytes, image_file.name, instance.slug)

                # Update instance with new image path
                instance.image = image_path

                # Delete old image after successful processing
                if old_image_path:
                    try:
                        CategoryImageStorage.delete_image(old_image_path)
                    except Exception:
                        # Don't fail if old image deletion fails
                        pass

            except ImportError:
                # If image processing modules not available, raise clear error
                raise ValidationError(
                    _("Image processing is not available. Please ensure Pillow is installed.")
                )
            except ValueError as e:
                # Image validation or processing error
                raise ValidationError(_("Image processing failed: %(error)s") % {"error": str(e)})
            except Exception as e:
                # Unexpected error during image processing
                raise ValidationError(
                    _("Unexpected error processing image: %(error)s") % {"error": str(e)}
                )

        if commit:
            instance.save()

        return instance
