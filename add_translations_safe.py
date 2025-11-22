#!/usr/bin/env python3
"""
Safe translation addition script.
Checks for duplicates before adding new translations.
"""

import re

# All missing translations found from browsing
translations = {
    # POS Page
    "Tax (10%)": "مالیات (۱۰٪)",
    "Transaction Dashboard": "داشبورد تراکنش",
    "Current": "فعلی",
    # Accounting Page
    "Accounting System Not Configured": "سیستم حسابداری پیکربندی نشده است",
    "Your accounting system needs to be initialized before you can access financial features. This one-time setup will create your chart of accounts and configure the double-entry accounting system.": "سیستم حسابداری شما باید قبل از دسترسی به ویژگی‌های مالی راه‌اندازی شود. این راه‌اندازی یک‌بار انجام می‌شود و چارت حساب‌های شما را ایجاد و سیستم حسابداری دوطرفه را پیکربندی می‌کند.",
    "Initialize Accounting System": "راه‌اندازی سیستم حسابداری",
    "Learn More": "بیشتر بدانید",
    # Dashboard
    "transactions": "تراکنش",
    "items": "مورد",
    "qty": "تعداد",
    "low": "کم",
    "out": "خارج",
    "overdue": "عقب‌افتاده",
    # Inventory Page
    "Manage your jewelry inventory, track stock levels, and generate reports": "موجودی جواهرات خود را مدیریت کنید، سطوح موجودی را پیگیری کنید و گزارش تولید کنید",
    "Out of Stock": "خارج از موجودی",
    "SKU, name, serial, barcode...": "SKU، نام، سریال، بارکد...",
    "Sort By": "مرتب‌سازی بر اساس",
    "Newest First": "جدیدترین ابتدا",
    "Oldest First": "قدیمی‌ترین ابتدا",
    "SKU A-Z": "SKU الف-ی",
    "Price High-Low": "قیمت بالا-پایین",
    "Price Low-High": "قیمت پایین-بالا",
    "Stock High-Low": "موجودی بالا-پایین",
    "Stock Low-High": "موجودی پایین-بالا",
    "Get started by adding your first inventory item.": "با افزودن اولین مورد موجودی خود شروع کنید.",
    # Sales Page
    "View, manage, and export all sales transactions": "مشاهده، مدیریت و خروجی همه تراکنش‌های فروش",
    # Customers Page
    "Customers": "مشتریان",
    "Manage your customer relationships": "روابط مشتریان خود را مدیریت کنید",
    "Add Customer": "افزودن مشتری",
    "Search by name, phone, email, or customer number...": "جستجو بر اساس نام، تلفن، ایمیل یا شماره مشتری...",
    "Search": "جستجو",
    "Loyalty Tier": "سطح وفاداری",
    "All Tiers": "همه سطوح",
    "Status": "وضعیت",
    "All Status": "تمام وضعیت‌ها",
    "Active": "فعال",
    "Inactive": "غیرفعال",
    "Tag": "برچسب",
    "All Tags": "همه برچسب‌ها",
    "Highest Spending": "بیشترین خرج",
    "Lowest Spending": "کمترین خرج",
    "Most Points": "بیشترین امتیاز",
    "Name (A-Z)": "نام (الف-ی)",
    "Name (Z-A)": "نام (ی-الف)",
    "No customers found": "مشتری یافت نشد",
    "Get started by adding your first customer": "با افزودن اولین مشتری خود شروع کنید",
    # Reports Page
    "Search reports...": "جستجوی گزارش‌ها...",
    "No reports yet": "هنوز گزارشی وجود ندارد",
    "Get started by creating your first custom report or exploring pre-built reports.": "با ایجاد اولین گزارش سفارشی خود یا کاوش در گزارش‌های از پیش ساخته شده شروع کنید.",
    # Settings Page
    "Settings": "تنظیمات",
    "Configure your shop settings, branding, and integrations": "تنظیمات فروشگاه، برندسازی و یکپارچه‌سازی‌های خود را پیکربندی کنید",
    "Overview": "نمای کلی",
    "Shop Profile": "پروفایل فروشگاه",
    "Branding": "برندسازی",
    "Business Hours": "ساعات کاری",
    "Holiday Calendar": "تقویم تعطیلات",
    "Integrations": "یکپارچه‌سازی‌ها",
    "Invoice Settings": "تنظیمات فاکتور",
    "Business information and contact details": "اطلاعات کسب‌وکار و جزئیات تماس",
    "Business Name:": "نام کسب‌وکار:",
    "Phone:": "تلفن:",
    "Email:": "ایمیل:",
    "Not set": "تنظیم نشده",
    "Configure": "پیکربندی",
    "Logo, colors, and visual identity": "لوگو، رنگ‌ها و هویت بصری",
    "No logo": "بدون لوگو",
    "Brand colors": "رنگ‌های برند",
    "Operating hours and schedules": "ساعات کاری و برنامه‌ها",
    "Business hours not configured": "ساعات کاری پیکربندی نشده است",
    "Holidays and special closures": "تعطیلات و تعطیلی‌های ویژه",
    "Holidays configured:": "تعطیلات پیکربندی شده:",
    "Invoice templates and numbering": "قالب‌های فاکتور و شماره‌گذاری",
    "Template:": "قالب:",
    "Standard": "استاندارد",
    "Next Invoice:": "فاکتور بعدی:",
    "Payment, SMS, and email providers": "ارائه‌دهندگان پرداخت، پیامک و ایمیل",
    "Payment": "پرداخت",
    "SMS": "پیامک",
    "Email": "ایمیل",
}

# Read existing django.po
po_file_path = "locale/fa/LC_MESSAGES/django.po"
with open(po_file_path, "r", encoding="utf-8") as f:
    po_content = f.read()

# Extract existing msgid entries
existing_msgids = set()
for match in re.finditer(r'^msgid "(.*?)"', po_content, re.MULTILINE):
    existing_msgids.add(match.group(1))

# Prepare new entries to add
new_entries = []
skipped = []

for english, persian in translations.items():
    # Escape quotes in the strings
    english_escaped = english.replace('"', '\\"')
    persian_escaped = persian.replace('"', '\\"')

    if english_escaped in existing_msgids or english in existing_msgids:
        skipped.append(english)
        continue

    # Create the entry
    entry = f'\nmsgid "{english_escaped}"\nmsgstr "{persian_escaped}"\n'
    new_entries.append(entry)

# Add new entries before the last line of the file
if new_entries:
    # Split content at the last msgstr
    lines = po_content.split("\n")

    # Find a good insertion point (before any existing empty entries at the end)
    insert_point = len(lines)
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip() and not lines[i].startswith("#"):
            insert_point = i + 1
            break

    # Insert new entries
    for entry in new_entries:
        lines.insert(insert_point, entry)
        insert_point += 1

    # Write back
    new_content = "\n".join(lines)
    with open(po_file_path, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"✅ Added {len(new_entries)} new translations")
    print(f"⏭️  Skipped {len(skipped)} existing translations")
    if skipped:
        print("\nSkipped (already exist):")
        for item in skipped[:10]:  # Show first 10
            print(f"  - {item}")
        if len(skipped) > 10:
            print(f"  ... and {len(skipped) - 10} more")
else:
    print("✅ All translations already exist!")
    print(f"⏭️  Skipped {len(skipped)} translations")
