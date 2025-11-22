#!/usr/bin/env python3
"""
Add missing POS translations safely to django.po
"""

import os

# POS-specific translations
translations = {
    "Store": "فروشگاه",
    "Jewelry POS": "صندوق فروش جواهرات",
    "All Products": "همه محصولات",
    "Rings": "انگشترها",
    "Necklaces": "گردنبندها",
    "Bracelets": "دستبندها",
    "Earrings": "گوشواره‌ها",
    "Price Range": "محدوده قیمت",
    "Manage sales and customer transactions efficiently": "مدیریت فروش و تراکنش‌های مشتری به صورت کارآمد",
    "Cart": "سبد خرید",
    "Recent Items": "اقلام اخیر",
    "Your cart is empty": "سبد خرید شما خالی است",
    "Add products to begin a new sale.": "محصولات را اضافه کنید تا فروش جدید را شروع کنید.",
    "Terminal": "ترمینال",
    "Select Terminal": "انتخاب ترمینال",
    "Not selected": "انتخاب نشده",
    "Cash": "نقدی",
    "Card": "کارت",
    "Store Credit": "اعتبار فروشگاه",
    "Order Summary": "خلاصه سفارش",
    "Subtotal": "جمع جزء",
    "Discount": "تخفیف",
    "Total": "مجموع",
    "Hold Sale": "نگهداری فروش",
    "Complete Sale": "تکمیل فروش",
    "Processing...": "در حال پردازش...",
    "Reprint Receipt": "چاپ مجدد رسید",
    "Held Sales": "فروش‌های نگهداری شده",
    "Stock": "موجودی",
    "Point of Sale": "نقطه فروش",
    "SKU": "کد محصول",
}

# Path to django.po
po_file = "locale/fa/LC_MESSAGES/django.po"

# Read existing translations
with open(po_file, "r", encoding="utf-8") as f:
    content = f.read()

# Extract existing msgids
existing_msgids = set()
lines = content.split("\n")
for i, line in enumerate(lines):
    if line.startswith('msgid "') and not line.startswith('msgid ""'):
        msgid = line[7:-1]  # Extract text between msgid " and "
        existing_msgids.add(msgid)

# Add new translations
new_entries = []
skipped = []

for english, persian in translations.items():
    if english in existing_msgids:
        skipped.append(english)
        continue

    entry = f'\nmsgid "{english}"\nmsgstr "{persian}"'
    new_entries.append(entry)

# Insert new entries before the final empty line
if new_entries:
    # Find the last msgstr line
    insert_pos = content.rfind("\nmsgstr")
    if insert_pos != -1:
        # Find the end of that entry (next blank line or end of file)
        insert_pos = content.find("\n\n", insert_pos)
        if insert_pos == -1:
            insert_pos = len(content)

        # Insert new entries
        new_content = content[:insert_pos] + "\n" + "\n".join(new_entries) + content[insert_pos:]

        # Write back
        with open(po_file, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"✅ Added {len(new_entries)} new POS translations")
    else:
        print("❌ Could not find insertion point")
else:
    print("ℹ️  No new translations to add")

if skipped:
    print(f"\n⏭️  Skipped {len(skipped)} existing translations:")
    for item in skipped:
        print(f"  - {item}")
