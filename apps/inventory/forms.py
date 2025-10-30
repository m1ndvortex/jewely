"""
Forms for inventory management.

Provides comprehensive forms with validation for:
- Inventory item creation and editing
- Stock adjustments
- Product categories
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
