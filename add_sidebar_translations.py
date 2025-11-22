#!/usr/bin/env python3
"""Add POS sidebar translations to Persian locale."""


def add_translations():
    po_file = "locale/fa/LC_MESSAGES/django.po"

    # New translations for sidebar
    translations = {
        "Customer": "مشتری",
        "Search customer...": "جستجوی مشتری...",
        "Terminal": "ترمینال",
        "Select Terminal": "انتخاب ترمینال",
        "Current": "فعلی",
        "Not selected": "انتخاب نشده",
        "Payment": "پرداخت",
        "Store Credit": "اعتبار فروشگاه",
        "Order Summary": "خلاصه سفارش",
        "Subtotal": "جمع جزء",
        "Tax (10%)": "مالیات (۱۰٪)",
        "Discount": "تخفیف",
        "Total": "جمع کل",
        "Hold Sale": "نگه‌داری فروش",
        "Complete Sale": "تکمیل فروش",
        "Processing...": "در حال پردازش...",
        "Reprint Receipt": "چاپ مجدد رسید",
        "Held Sales": "فروش‌های نگهداری شده",
    }

    with open(po_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Add translations
    for en, fa in translations.items():
        # Check if translation already exists
        if f'msgid "{en}"' not in content:
            entry = f'\nmsgid "{en}"\nmsgstr "{fa}"\n'
            # Insert before the final empty line
            content = content.rstrip() + entry + "\n"
            print(f"✓ Added: {en} -> {fa}")
        else:
            print(f"⊗ Already exists: {en}")

    with open(po_file, "w", encoding="utf-8") as f:
        f.write(content)

    print("\n✓ Translation file updated successfully!")


if __name__ == "__main__":
    add_translations()
