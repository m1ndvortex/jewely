"""
Translation utilities and examples for the jewelry shop platform.

This module demonstrates proper use of Django's translation functions.
"""

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from django.utils.translation import ngettext, pgettext

# Use gettext_lazy for module-level strings that will be evaluated later
# This is important for strings in model fields, form fields, etc.
DASHBOARD_TITLE = _lazy("Dashboard")
INVENTORY_TITLE = _lazy("Inventory Management")
SALES_TITLE = _lazy("Sales")
CUSTOMERS_TITLE = _lazy("Customers")


# Status choices for models (use lazy translation)
STATUS_CHOICES = [
    ("active", _lazy("Active")),
    ("inactive", _lazy("Inactive")),
    ("pending", _lazy("Pending")),
    ("suspended", _lazy("Suspended")),
]


# Payment method choices
PAYMENT_METHODS = [
    ("cash", _lazy("Cash")),
    ("card", _lazy("Credit/Debit Card")),
    ("bank_transfer", _lazy("Bank Transfer")),
    ("store_credit", _lazy("Store Credit")),
]


def get_welcome_message(user_name):
    """
    Get a personalized welcome message.

    Use gettext (not lazy) for strings that are evaluated immediately.
    """
    return _("Welcome back, %(name)s!") % {"name": user_name}


def get_item_count_message(count):
    """
    Get a message about item count with proper pluralization.

    ngettext handles singular/plural forms correctly for different languages.
    """
    return ngettext(
        "You have %(count)d item in your inventory.",
        "You have %(count)d items in your inventory.",
        count,
    ) % {"count": count}


def get_sale_status_message(status):
    """
    Get a status message with context.

    pgettext provides context to disambiguate translations.
    """
    if status == "completed":
        return pgettext("sale status", "Completed")
    elif status == "pending":
        return pgettext("sale status", "Pending")
    elif status == "cancelled":
        return pgettext("sale status", "Cancelled")
    return status


def get_error_messages():
    """
    Common error messages used throughout the application.
    """
    return {
        "required_field": _("This field is required."),
        "invalid_email": _("Please enter a valid email address."),
        "invalid_phone": _("Please enter a valid phone number."),
        "insufficient_stock": _("Insufficient stock available."),
        "invalid_credentials": _("Invalid username or password."),
        "permission_denied": _("You do not have permission to perform this action."),
        "item_not_found": _("The requested item was not found."),
        "duplicate_entry": _("An item with this information already exists."),
    }


def get_success_messages():
    """
    Common success messages used throughout the application.
    """
    return {
        "item_created": _("Item created successfully."),
        "item_updated": _("Item updated successfully."),
        "item_deleted": _("Item deleted successfully."),
        "sale_completed": _("Sale completed successfully."),
        "customer_added": _("Customer added successfully."),
        "email_sent": _("Email sent successfully."),
        "settings_saved": _("Settings saved successfully."),
    }


def get_confirmation_messages():
    """
    Confirmation messages for destructive actions.
    """
    return {
        "delete_item": _("Are you sure you want to delete this item?"),
        "delete_customer": _("Are you sure you want to delete this customer?"),
        "cancel_sale": _("Are you sure you want to cancel this sale?"),
        "logout": _("Are you sure you want to log out?"),
    }


# Field labels for forms (use lazy translation)
FIELD_LABELS = {
    "name": _lazy("Name"),
    "email": _lazy("Email Address"),
    "phone": _lazy("Phone Number"),
    "address": _lazy("Address"),
    "city": _lazy("City"),
    "country": _lazy("Country"),
    "postal_code": _lazy("Postal Code"),
    "description": _lazy("Description"),
    "price": _lazy("Price"),
    "quantity": _lazy("Quantity"),
    "sku": _lazy("SKU"),
    "barcode": _lazy("Barcode"),
    "category": _lazy("Category"),
    "weight": _lazy("Weight"),
    "karat": _lazy("Karat"),
    "date": _lazy("Date"),
    "status": _lazy("Status"),
}


# Help text for forms (use lazy translation)
FIELD_HELP_TEXT = {
    "sku": _lazy("Unique identifier for this product"),
    "barcode": _lazy("Barcode or QR code for scanning"),
    "weight": _lazy("Weight in grams"),
    "karat": _lazy("Gold purity (e.g., 18K, 22K, 24K)"),
    "email": _lazy("We'll never share your email with anyone else."),
    "phone": _lazy("Include country code for international numbers"),
}


# Button labels (use lazy translation)
BUTTON_LABELS = {
    "save": _lazy("Save"),
    "cancel": _lazy("Cancel"),
    "delete": _lazy("Delete"),
    "edit": _lazy("Edit"),
    "add": _lazy("Add"),
    "search": _lazy("Search"),
    "filter": _lazy("Filter"),
    "export": _lazy("Export"),
    "import": _lazy("Import"),
    "print": _lazy("Print"),
    "submit": _lazy("Submit"),
    "back": _lazy("Back"),
    "next": _lazy("Next"),
    "previous": _lazy("Previous"),
    "close": _lazy("Close"),
}


# Navigation menu items (use lazy translation)
MENU_ITEMS = {
    "dashboard": _lazy("Dashboard"),
    "inventory": _lazy("Inventory"),
    "sales": _lazy("Sales"),
    "pos": _lazy("Point of Sale"),
    "customers": _lazy("Customers"),
    "accounting": _lazy("Accounting"),
    "reports": _lazy("Reports"),
    "settings": _lazy("Settings"),
    "logout": _lazy("Logout"),
}


# Date and time formats (these will be localized automatically)
def format_date_range(start_date, end_date):
    """
    Format a date range for display.
    """
    return _("%(start)s to %(end)s") % {
        "start": start_date.strftime("%Y-%m-%d"),
        "end": end_date.strftime("%Y-%m-%d"),
    }


def format_currency(amount, currency="USD"):
    """
    Format currency for display.
    Note: For proper currency formatting, consider using babel or django-money.
    """
    return _("%(amount)s %(currency)s") % {
        "amount": f"{amount:,.2f}",
        "currency": currency,
    }
