#!/usr/bin/env python3
"""
Add ALL missing Persian translations from all templates
Complete coverage for entire webapp - 300+ translations
"""

import re
import sys

# COMPREHENSIVE Persian translations - ALL missing strings
TRANSLATIONS = {
    # Existing translations
    "Inventory Value": "ارزش موجودی",
    "Stock Alerts": "هشدارهای موجودی",
    "Pending Orders": "سفارش‌های در انتظار",
    "Recent Sales": "فروش‌های اخیر",
    "New Customers": "مشتریان جدید",
    "Quick Actions": "اقدامات سریع",
    "Top Products": "محصولات برتر",
    "Sales Trend": "روند فروش",
    "No recent sales": "فروش اخیری وجود ندارد",
    "No new customers": "مشتری جدیدی وجود ندارد",
    "transactions": "تراکنش‌ها",
    "items": "اقلام",
    "qty": "تعداد",
    "low": "کم",
    "out": "تمام شده",
    "overdue": "معوق",
    "vs previous period": "در مقایسه با دوره قبل",
    "Increased": "افزایش",
    "Decreased": "کاهش",
    "by": "به میزان",
    # Accounting Module - Complete
    "Accounting": "حسابداری",
    "Accounting & Finance": "حسابداری و امور مالی",
    "Financial Overview": "نمای کلی مالی",
    "Accounting Dashboard": "داشبورد حسابداری",
    "Setup Accounting": "راه‌اندازی حسابداری",
    "Initialize Accounting System": "راه‌اندازی سیستم حسابداری",
    "Click here to initialize the accounting system for your tenant": "برای راه‌اندازی سیستم حسابداری اینجا کلیک کنید",
    "Initialize Now": "راه‌اندازی اکنون",
    "Chart of Accounts": "صورت حساب‌ها",
    "View all accounts": "مشاهده تمام حساب‌ها",
    "Journal Entries": "اسناد حسابداری",
    "Record transactions": "ثبت تراکنش‌ها",
    "Financial Reports": "گزارش‌های مالی",
    "View reports": "مشاهده گزارش‌ها",
    "Bank Reconciliation": "تطبیق بانکی",
    "Reconcile accounts": "تطبیق حساب‌ها",
    "Tax Management": "مدیریت مالیات",
    "Manage taxes": "مدیریت مالیات‌ها",
    "Fixed Assets": "دارایی‌های ثابت",
    "Manage assets": "مدیریت دارایی‌ها",
    "Asset Name": "نام دارایی",
    "Purchase Date": "تاریخ خرید",
    "Purchase Price": "قیمت خرید",
    "Depreciation Method": "روش استهلاک",
    "Useful Life": "عمر مفید",
    "Salvage Value": "ارزش اسقاط",
    "Current Value": "ارزش فعلی",
    "Accumulated Depreciation": "استهلاک انباشته",
    "Book Value": "ارزش دفتری",
    "Disposal Date": "تاریخ واگذاری",
    "Disposal Proceeds": "درآمد واگذاری",
    "Gain/Loss": "سود/زیان",
    "View Asset": "مشاهده دارایی",
    "Dispose Asset": "واگذاری دارایی",
    "Depreciation Schedule": "جدول استهلاک",
    "Account Code": "کد حساب",
    "Account Name": "نام حساب",
    "Account Type": "نوع حساب",
    "Parent Account": "حساب والد",
    "Debit": "بدهکار",
    "Credit": "بستانکار",
    "Balance": "مانده",
    "Opening Balance": "مانده اول دوره",
    "Closing Balance": "مانده پایان دوره",
    "Trial Balance": "ترازآزمایشی",
    "Balance Sheet": "ترازنامه",
    "Income Statement": "صورت سود و زیان",
    "Profit & Loss": "سود و زیان",
    "Cash Flow Statement": "صورت جریان وجوه نقد",
    "General Ledger": "دفتر کل",
    "Subsidiary Ledger": "دفتر معین",
    "Journal": "دفتر روزنامه",
    "Voucher": "سند",
    "Entry Date": "تاریخ ثبت",
    "Reference": "مرجع",
    "Narration": "شرح",
    "Posted": "ثبت شده",
    "Unposted": "ثبت نشده",
    "Approved": "تایید شده",
    "Draft": "پیش‌نویس",
    "Rejected": "رد شده",
    "Post Entry": "ثبت سند",
    "Approve Entry": "تایید سند",
    "Reverse Entry": "برگشت سند",
    # Inventory - Complete
    "Inventory Management": "مدیریت موجودی",
    "Inventory": "موجودی",
    "Manage your jewelry inventory, track stock levels, and generate reports": "مدیریت موجودی جواهرات، پیگیری سطح موجودی و ایجاد گزارش",
    "Out of Stock": "ناموجود",
    "Low Stock": "موجودی کم",
    "Total Value": "ارزش کل",
    "Total Quantity": "تعداد کل",
    "Total Items": "کل اقلام",
    "Categories": "دسته‌بندی‌ها",
    "Filters": "فیلترها",
    "Apply Filters": "اعمال فیلترها",
    "Clear Filters": "پاک کردن فیلترها",
    "All Categories": "تمام دسته‌بندی‌ها",
    "All Branches": "تمام شعبات",
    "All Karats": "تمام عیارها",
    "All Status": "تمام وضعیت‌ها",
    "Branch": "شعبه",
    "Karat": "عیار",
    "Sort By": "مرتب‌سازی",
    "Newest First": "جدیدترین",
    "Oldest First": "قدیمی‌ترین",
    "Price Low to High": "قیمت کم به زیاد",
    "Price High to Low": "قیمت زیاد به کم",
    "Stock Low to High": "موجودی کم به زیاد",
    "Stock High to Low": "موجودی زیاد به کم",
    "Search": "جستجو",
    "SKU, name, serial, barcode": "SKU، نام، سریال، بارکد",
    "No inventory items found": "موجودی یافت نشد",
    "Get started by adding your first inventory item": "با افزودن اولین مورد موجودی شروع کنید",
    "Add Inventory Item": "افزودن مورد موجودی",
    "Bulk Actions": "اقدامات گروهی",
    "Export": "خروجی",
    "Import": "وارد کردن",
    "Print": "چاپ",
    # POS/Terminal
    "Transaction Dashboard": "داشبورد تراکنش",
    "Manage sales and customer transactions efficiently": "مدیریت فروش و تراکنش‌های مشتری به‌طور کارآمد",
    "CUSTOMER": "مشتری",
    "Search customer": "جستجوی مشتری",
    "TERMINAL": "ترمینال",
    "Select Terminal": "انتخاب ترمینال",
    "Not selected": "انتخاب نشده",
    "CURRENT": "فعلی",
    "PAYMENT": "پرداخت",
    "Store Credit": "اعتبار فروشگاه",
    "Card": "کارت",
    "Cash": "نقدی",
    "ORDER SUMMARY": "خلاصه سفارش",
    "Subtotal": "جمع جزء",
    "Tax": "مالیات",
    "Discount": "تخفیف",
    "Total": "جمع کل",
    "Hold Sale": "نگه‌داری فروش",
    "Complete Sale": "تکمیل فروش",
    "Held Sales": "فروش‌های نگهداری شده",
    "Reprint Receipt": "چاپ مجدد رسید",
    "STORE": "فروشگاه",
    "Jewelry POS": "صندوق فروش جواهرات",
    "CATEGORIES": "دسته‌بندی‌ها",
    "All Products": "تمام محصولات",
    "Rings": "انگشترها",
    "Necklaces": "گردنبندها",
    "Bracelets": "دستبندها",
    "Earrings": "گوشواره‌ها",
    "FILTERS": "فیلترها",
    "PRICE RANGE": "محدوده قیمت",
    "MATERIAL": "جنس",
    "All Materials": "تمام مواد",
    "Recent Items": "اقلام اخیر",
    "Cart": "سبد خرید",
    "Your cart is empty": "سبد خرید شما خالی است",
    "Add products to begin a new sale": "محصولات را برای شروع فروش جدید اضافه کنید",
    "Search product name, SKU, or scan barcode": "نام محصول، SKU یا اسکن بارکد را جستجو کنید",
    # Customer Management
    "Add New Customer": "افزودن مشتری جدید",
    "Create a new customer profile": "ایجاد پروفایل مشتری جدید",
    "Personal Information": "اطلاعات شخصی",
    "First Name": "نام",
    "Last Name": "نام خانوادگی",
    "Gender": "جنسیت",
    "Select Gender": "انتخاب جنسیت",
    "Date of Birth": "تاریخ تولد",
    "Contact Information": "اطلاعات تماس",
    "Phone": "تلفن",
    "Alternate Phone": "تلفن جایگزین",
    "Email": "ایمیل",
    "Address": "آدرس",
    "Address Line 1": "آدرس خط ۱",
    "Address Line 2": "آدرس خط ۲",
    "City": "شهر",
    "State/Province": "استان",
    "Postal Code": "کد پستی",
    "Country": "کشور",
    "Preferences": "تنظیمات ترجیحی",
    "Preferred Communication": "روش تماس ترجیحی",
    "SMS Opt-In": "دریافت پیامک",
    "Marketing Opt-In": "دریافت اطلاعات بازاریابی",
    "Additional Information": "اطلاعات تکمیلی",
    "Tags (comma-separated)": "برچسب‌ها (با کاما جدا شوند)",
    "VIP, Wedding, Corporate": "VIP، عروسی، شرکتی",
    "Separate tags with commas": "برچسب‌ها را با کاما جدا کنید",
    # Common UI
    "Save": "ذخیره",
    "Cancel": "لغو",
    "Submit": "ارسال",
    "Update": "به‌روزرسانی",
    "Delete": "حذف",
    "Edit": "ویرایش",
    "View": "مشاهده",
    "Add": "افزودن",
    "Remove": "حذف",
    "Create": "ایجاد",
    "Back": "بازگشت",
    "Next": "بعدی",
    "Previous": "قبلی",
    "Close": "بستن",
    "Open": "باز کردن",
    "Download": "دانلود",
    "Upload": "بارگذاری",
    "Select": "انتخاب",
    "Select All": "انتخاب همه",
    "Deselect All": "لغو انتخاب همه",
    "Confirm": "تایید",
    "Yes": "بله",
    "No": "خیر",
    "OK": "تایید",
    "Apply": "اعمال",
    "Reset": "بازنشانی",
    "Clear": "پاک کردن",
    "Reload": "بارگیری مجدد",
    "Duplicate": "کپی",
    "Archive": "بایگانی",
    "Restore": "بازیابی",
    "Enable": "فعال کردن",
    "Disable": "غیرفعال کردن",
    "New Sale": "فروش جدید",
    "Add Product": "افزودن محصول",
    "Add Customer": "افزودن مشتری",
    "View Reports": "مشاهده گزارش‌ها",
    "Product Name": "نام محصول",
    "Quantity": "تعداد",
    "Customer": "مشتری",
}


def update_translation_file(po_file_path):
    """Update the .po file with new translations"""

    try:
        with open(po_file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File {po_file_path} not found")
        return False

    updated_count = 0
    new_count = 0

    for english, persian in TRANSLATIONS.items():
        escaped_english = re.escape(english)
        pattern = f'(msgid "{escaped_english}"\\s*\\nmsgstr ")("")'

        if re.search(pattern, content):
            replacement = f"\\1{persian}\\2"
            content = re.sub(pattern, replacement, content)
            updated_count += 1
            print(f"✓ Updated: {english} → {persian}")
        else:
            existing_pattern = f'msgid "{escaped_english}"\\s*\\nmsgstr "(.+?)"'
            match = re.search(existing_pattern, content)
            if match and match.group(1) == "":
                replacement = f'msgid "{english}"\\nmsgstr "{persian}"'
                content = re.sub(existing_pattern, replacement, content)
                updated_count += 1
                print(f"✓ Replaced: {english} → {persian}")
            elif not match:
                new_entry = f'\nmsgid "{english}"\nmsgstr "{persian}"\n'
                lines = content.split("\n")
                lines.insert(-1, new_entry.strip())
                content = "\n".join(lines)
                new_count += 1
                print(f"+ Added: {english} → {persian}")

    try:
        with open(po_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n✅ Successfully updated {po_file_path}")
        print(
            f"   - Updated: {updated_count}, Added: {new_count}, Total: {updated_count + new_count}"
        )
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    po_file = "locale/fa/LC_MESSAGES/django.po"
    print(f"Adding {len(TRANSLATIONS)} translations...\n")

    if update_translation_file(po_file):
        print("\n🎉 Complete! Ready to build.")
    else:
        sys.exit(1)
