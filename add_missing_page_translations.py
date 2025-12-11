#!/usr/bin/env python3
"""
Add comprehensive missing Persian translations for all webapp pages
Covers: Accounting, Inventory, POS, Customers, and common UI elements
"""

import re
from pathlib import Path

# Comprehensive translations organized by module
TRANSLATIONS = {
    # ============ ACCOUNTING MODULE ============
    "Accounting & Finance": "حسابداری و امور مالی",
    "View Reports": "مشاهده گزارش‌ها",
    "Total Revenue": "کل درآمد",
    "Total Expenses": "کل هزینه‌ها",
    "Net Income": "درآمد خالص",
    "Total Assets": "کل دارایی‌ها",
    "vs last period": "نسبت به دوره قبل",
    "profit margin": "حاشیه سود",
    "liabilities": "بدهی‌ها",
    "Accounting Modules": "ماژول‌های حسابداری",
    "View All →": "مشاهده همه ←",
    # Accounting Module Cards
    "REPORTS": "گزارش‌ها",
    "Financial Reports": "گزارش‌های مالی",
    "Balance Sheet, Income Statement, Cash Flow, Trial Balance with PDF/Excel export": "ترازنامه، صورت سود و زیان، جریان وجوه نقد، تراز آزمایشی با خروجی PDF/Excel",
    "Open Reports": "باز کردن گزارش‌ها",
    "ACCOUNTS": "حساب‌ها",
    "Chart of Accounts": "دفتر حساب‌ها",
    "Manage account structure, view balances, Assets, Liabilities, Equity, Revenue, Expenses": "مدیریت ساختار حساب‌ها، مشاهده موجودی، دارایی‌ها، بدهی‌ها، سرمایه، درآمد، هزینه‌ها",
    "Manage Accounts": "مدیریت حساب‌ها",
    "ENTRIES": "ثبت‌ها",
    "Journal Entries": "ثبت‌های روزنامه",
    "View and manage all journal entries, automatic double-entry bookkeeping transactions": "مشاهده و مدیریت تمام ثبت‌های روزنامه، تراکنش‌های خودکار دفترداری دوطرفه",
    "View Entries": "مشاهده ثبت‌ها",
    "LEDGER": "دفتر کل",
    "General Ledger": "دفتر کل",
    "Complete transaction history, account movements, and audit trail for all entries": "تاریخچه کامل تراکنش‌ها، حرکت‌های حساب و ردیابی حسابرسی برای همه ثبت‌ها",
    "View Ledger": "مشاهده دفتر کل",
    "PAYABLES": "پرداختنی‌ها",
    "Bills & Payables": "صورتحساب‌ها و پرداختنی‌ها",
    "Manage supplier bills, track payments, aging reports, and outstanding payables": "مدیریت صورتحساب‌های تامین‌کننده، پیگیری پرداخت‌ها، گزارش‌های قدمت و پرداختنی‌های معوق",
    "Manage Bills": "مدیریت صورتحساب‌ها",
    "SUPPLIERS": "تامین‌کنندگان",
    "Suppliers": "تامین‌کنندگان",
    "View supplier accounting details, statements, and payment history": "مشاهده جزئیات حسابداری تامین‌کننده، صورت‌حساب‌ها و تاریخچه پرداخت",
    "View Suppliers": "مشاهده تامین‌کنندگان",
    "INVOICES": "فاکتورها",
    "Invoices & Receivables": "فاکتورها و دریافتنی‌ها",
    "Manage customer invoices, track payments, aging reports, and credit memos": "مدیریت فاکتورهای مشتری، پیگیری پرداخت‌ها، گزارش‌های قدمت و یادداشت‌های اعتباری",
    "Manage Invoices": "مدیریت فاکتورها",
    "CUSTOMERS": "مشتریان",
    "View customer accounting details, invoices, statements, and credit limits": "مشاهده جزئیات حسابداری مشتری، فاکتورها، صورت‌حساب‌ها و محدودیت‌های اعتباری",
    "View Customers": "مشاهده مشتریان",
    "RECEIVABLES": "دریافتنی‌ها",
    "Accounts Receivable": "حساب‌های دریافتنی",
    "Track customer invoices, payments due, and manage outstanding receivables": "پیگیری فاکتورهای مشتری، پرداخت‌های سررسید و مدیریت دریافتنی‌های معوق",
    "Manage Receivables": "مدیریت دریافتنی‌ها",
    "Bank Accounts": "حساب‌های بانکی",
    "Manage bank accounts, track balances, reconciliation status, and transactions": "مدیریت حساب‌های بانکی، پیگیری موجودی، وضعیت تطبیق و تراکنش‌ها",
    "BANKING": "بانکداری",
    "Bank Reconciliation": "تطبیق بانکی",
    "Match bank statements with ledger entries, reconcile accounts automatically": "تطبیق صورت‌حساب‌های بانکی با ثبت‌های دفتر کل، تطبیق خودکار حساب‌ها",
    "Reconcile Accounts": "تطبیق حساب‌ها",
    "ASSETS": "دارایی‌ها",
    "Fixed Assets": "دارایی‌های ثابت",
    "Manage fixed assets register, track depreciation, asset disposal, and book values": "مدیریت ثبت دارایی‌های ثابت، پیگیری استهلاک، واگذاری دارایی و ارزش دفتری",
    "Manage Assets": "مدیریت دارایی‌ها",
    "Depreciation Schedule": "جدول استهلاک",
    "View projected depreciation for all assets, export to PDF/Excel for planning": "مشاهده استهلاک پیش‌بینی شده برای همه دارایی‌ها، خروجی به PDF/Excel برای برنامه‌ریزی",
    "View Schedule": "مشاهده جدول",
    "SETTINGS": "تنظیمات",
    "Configuration": "پیکربندی",
    "Manage fiscal year, accounting periods, currencies, and system preferences": "مدیریت سال مالی، دوره‌های حسابداری، ارزها و تنظیمات سیستم",
    "Configure": "پیکربندی",
    # Accounting Dashboard
    "Current Period Overview": "نمای کلی دوره جاری",
    "Fiscal Period": "دوره مالی",
    "Accounting Status": "وضعیت حسابداری",
    "Active & Synchronized": "فعال و همگام‌سازی شده",
    "All financial transactions are automatically recorded using double-entry bookkeeping. Data is synchronized in real-time from sales, purchases, and expenses.": "تمام تراکنش‌های مالی به صورت خودکار با استفاده از دفترداری دوطرفه ثبت می‌شوند. داده‌ها در زمان واقعی از فروش، خرید و هزینه‌ها همگام‌سازی می‌شوند.",
    "Auto Journal Entries": "ثبت‌های خودکار روزنامه",
    "Real-time Sync": "همگام‌سازی آنی",
    "Audit Trail": "ردیابی حسابرسی",
    "Add Account": "افزودن حساب",
    "Export Data": "خروجی داده",
    "Need Help?": "نیاز به کمک دارید؟",
    "Check our documentation or contact support for assistance with accounting features.": "مستندات ما را بررسی کنید یا برای کمک در ویژگی‌های حسابداری با پشتیبانی تماس بگیرید.",
    # ============ INVENTORY MODULE ============
    "Inventory Management": "مدیریت موجودی",
    "Manage your jewelry inventory, track stock levels, and generate reports": "مدیریت موجودی جواهرات، پیگیری سطح موجودی و ایجاد گزارش‌ها",
    "Categories": "دسته‌بندی‌ها",
    "Total Items": "کل اقلام",
    "Total Quantity": "کل مقدار",
    "Low Stock": "موجودی کم",
    "Out of Stock": "ناموجود",
    "SKU, name, serial, barcode...": "شناسه، نام، سریال، بارکد...",
    "All Categories": "همه دسته‌بندی‌ها",
    "Branch": "شعبه",
    "All Branches": "همه شعبه‌ها",
    "All Karats": "همه عیارها",
    "All Status": "همه وضعیت‌ها",
    "Sort By": "مرتب‌سازی بر اساس",
    "Newest First": "جدیدترین",
    "Oldest First": "قدیمی‌ترین",
    "Name A-Z": "نام الف-ی",
    "Name Z-A": "نام ی-الف",
    "SKU A-Z": "شناسه الف-ی",
    "Price High-Low": "قیمت بالا-پایین",
    "Price Low-High": "قیمت پایین-بالا",
    "Stock High-Low": "موجودی بالا-پایین",
    "Stock Low-High": "موجودی پایین-بالا",
    "No inventory items found": "هیچ موجودی یافت نشد",
    "Get started by adding your first inventory item.": "با افزودن اولین مورد موجودی خود شروع کنید.",
    "Add Inventory Item": "افزودن مورد موجودی",
    # ============ POS MODULE ============
    "Store": "فروشگاه",
    "Jewelry POS": "صندوق فروش جواهرات",
    "All Products": "همه محصولات",
    "Rings": "انگشترها",
    "Necklaces": "گردنبندها",
    "Bracelets": "دستبندها",
    "Earrings": "گوشواره‌ها",
    "Filters": "فیلترها",
    "Price Range": "محدوده قیمت",
    "Material": "جنس",
    "All Materials": "همه جنس‌ها",
    "Transaction Dashboard": "داشبورد تراکنش",
    "Manage sales and customer transactions efficiently": "مدیریت کارآمد فروش و تراکنش‌های مشتری",
    "Online": "آنلاین",
    "Search product name, SKU, or scan barcode": "جستجوی نام محصول، شناسه یا اسکن بارکد",
    "Cart (0)": "سبد خرید (0)",
    "Recent Items": "اقلام اخیر",
    "Your cart is empty": "سبد خرید شما خالی است",
    "Add products to begin a new sale.": "محصولات را اضافه کنید تا فروش جدیدی شروع شود.",
    "Customer": "مشتری",
    "Search customer...": "جستجوی مشتری...",
    "Terminal": "ترمینال",
    "Select Terminal": "انتخاب ترمینال",
    "Current": "فعلی",
    "Not selected": "انتخاب نشده",
    "Payment": "پرداخت",
    "Cash": "نقدی",
    "Card": "کارت",
    "Store Credit": "اعتبار فروشگاه",
    "Order Summary": "خلاصه سفارش",
    "Subtotal": "جمع جزء",
    "Tax (10%)": "مالیات (10%)",
    "Discount": "تخفیف",
    "Total": "جمع کل",
    "Hold Sale": "نگهداری فروش",
    "Complete Sale": "تکمیل فروش",
    "Reprint Receipt": "چاپ مجدد رسید",
    "Held Sales": "فروش‌های نگهداری شده",
    # ============ CUSTOMERS MODULE ============
    "Customers": "مشتریان",
    "Manage your customer relationships": "مدیریت روابط مشتریان خود",
    "Add Customer": "افزودن مشتری",
    "Search by name, phone, email, or customer number...": "جستجو بر اساس نام، تلفن، ایمیل یا شماره مشتری...",
    "Search": "جستجو",
    "Loyalty Tier": "سطح وفاداری",
    "All Tiers": "همه سطوح",
    "Status": "وضعیت",
    "Active": "فعال",
    "Inactive": "غیرفعال",
    "Tag": "برچسب",
    "All Tags": "همه برچسب‌ها",
    "Highest Spending": "بیشترین خرج",
    "Lowest Spending": "کمترین خرج",
    "Most Points": "بیشترین امتیاز",
    "Name (A-Z)": "نام (الف-ی)",
    "Name (Z-A)": "نام (ی-الف)",
    "No customers found": "هیچ مشتری یافت نشد",
    "Get started by adding your first customer": "با افزودن اولین مشتری خود شروع کنید",
}


def update_po_file():
    """Update the Persian translation file with new translations"""
    po_file = Path("locale/fa/LC_MESSAGES/django.po")

    if not po_file.exists():
        print(f"❌ Translation file not found: {po_file}")
        return False

    # Read current content
    content = po_file.read_text(encoding="utf-8")

    # Track statistics
    added = 0
    updated = 0

    for english, persian in TRANSLATIONS.items():
        # Escape quotes for regex matching
        english_escaped = re.escape(english)

        # Check if translation exists
        pattern = f'msgid "{english_escaped}"\\s*\\nmsgstr "([^"]*)"'
        matches = list(re.finditer(pattern, content, re.MULTILINE))

        if matches:
            for match in matches:
                current_translation = match.group(1)
                if not current_translation or current_translation == "":
                    # Update empty translation
                    content = content.replace(
                        match.group(0), f'msgid "{english}"\nmsgstr "{persian}"'
                    )
                    updated += 1
                    print(f"✅ Updated: {english[:50]}...")
                # If translation exists and is different, keep existing (don't override)
        else:
            # Add new translation entry
            # Find a good place to insert (before final empty line)
            insert_pos = content.rfind('\nmsgid ""')
            if insert_pos == -1:
                insert_pos = len(content)

            new_entry = f'\nmsgid "{english}"\nmsgstr "{persian}"\n'
            content = content[:insert_pos] + new_entry + content[insert_pos:]
            added += 1
            print(f"➕ Added: {english[:50]}...")

    # Write updated content
    po_file.write_text(content, encoding="utf-8")

    print("\n✅ Updated locale/fa/LC_MESSAGES/django.po")
    print(f"   Updated: {updated}, Added: {added}, Total: {updated + added}")
    print("🎉 Complete! Now you can build.")

    return True


if __name__ == "__main__":
    print(f"Adding {len(TRANSLATIONS)} translations...")
    update_po_file()
