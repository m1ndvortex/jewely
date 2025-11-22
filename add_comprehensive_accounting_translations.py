#!/usr/bin/env python
"""
Comprehensive Persian Translation Addition Script
Adds ALL missing Persian translations for accounting module and general UI
Production-ready dual-language support
"""

import re
import sys
from pathlib import Path

# Comprehensive translation dictionary - Accounting Module
ACCOUNTING_TRANSLATIONS = {
    # Accounting Dashboard
    "Accounting & Finance": "حسابداری و امور مالی",
    "Accounting": "حسابداری",
    "View Reports": "مشاهده گزارش‌ها",
    "Export": "خروجی",
    "Total Revenue": "درآمد کل",
    "Total Expenses": "هزینه‌های کل",
    "Net Income": "درآمد خالص",
    "Total Assets": "دارایی‌های کل",
    "vs last period": "در مقایسه با دوره قبل",
    "profit margin": "حاشیه سود",
    "liabilities": "بدهی‌ها",
    # Accounting Modules
    "Accounting Modules": "ماژول‌های حسابداری",
    "View All": "مشاهده همه",
    "Financial Reports": "گزارش‌های مالی",
    "Balance Sheet": "ترازنامه",
    "Income Statement": "صورت سود و زیان",
    "Cash Flow": "جریان نقدی",
    "Trial Balance": "تراز آزمایشی",
    "with PDF/Excel export": "با امکان خروجی PDF/Excel",
    "Open Reports": "گزارش‌ها",
    # Chart of Accounts
    "Chart of Accounts": "دفتر حساب‌ها",
    "Manage account structure": "مدیریت ساختار حساب‌ها",
    "view balances": "مشاهده مانده‌ها",
    "Assets": "دارایی‌ها",
    "Liabilities": "بدهی‌ها",
    "Equity": "حقوق صاحبان سهام",
    "Revenue": "درآمد",
    "Expenses": "هزینه‌ها",
    "Manage Accounts": "مدیریت حساب‌ها",
    # Journal Entries
    "Journal Entries": "ثبت‌های روزنامه",
    "View and manage all journal entries": "مشاهده و مدیریت همه ثبت‌های روزنامه",
    "automatic double-entry bookkeeping transactions": "تراکنش‌های خودکار دفترداری دوطرفه",
    "View Entries": "مشاهده ثبت‌ها",
    # General Ledger
    "General Ledger": "دفتر کل",
    "Complete transaction history": "تاریخچه کامل تراکنش‌ها",
    "account movements": "جابجایی‌های حساب",
    "audit trail for all entries": "ردیاب حسابرسی برای همه ثبت‌ها",
    "View Ledger": "مشاهده دفتر کل",
    # Bills & Payables
    "Bills & Payables": "قبوض و حساب‌های پرداختنی",
    "Manage supplier bills": "مدیریت قبوض تأمین‌کنندگان",
    "track payments": "پیگیری پرداخت‌ها",
    "aging reports": "گزارش‌های سنی",
    "outstanding payables": "حساب‌های پرداختنی معوق",
    "Manage Bills": "مدیریت قبوض",
    # Suppliers
    "Suppliers": "تأمین‌کنندگان",
    "View supplier accounting details": "مشاهده جزئیات حسابداری تأمین‌کننده",
    "statements": "صورت‌حساب‌ها",
    "payment history": "تاریخچه پرداخت‌ها",
    "View Suppliers": "مشاهده تأمین‌کنندگان",
    # Invoices & Receivables
    "Invoices & Receivables": "فاکتورها و حساب‌های دریافتنی",
    "Manage customer invoices": "مدیریت فاکتورهای مشتریان",
    "credit memos": "یادداشت‌های اعتباری",
    "Manage Invoices": "مدیریت فاکتورها",
    # Customers
    "Customers": "مشتریان",
    "View customer accounting details": "مشاهده جزئیات حسابداری مشتری",
    "invoices": "فاکتورها",
    "credit limits": "محدودیت‌های اعتباری",
    "View Customers": "مشاهده مشتریان",
    # Accounts Receivable
    "Accounts Receivable": "حساب‌های دریافتنی",
    "Track customer invoices": "پیگیری فاکتورهای مشتریان",
    "payments due": "پرداخت‌های سررسید",
    "manage outstanding receivables": "مدیریت دریافتنی‌های معوق",
    "Manage Receivables": "مدیریت دریافتنی‌ها",
    # Bank Accounts
    "Bank Accounts": "حساب‌های بانکی",
    "Manage bank accounts": "مدیریت حساب‌های بانکی",
    "track balances": "پیگیری مانده‌ها",
    "reconciliation status": "وضعیت تطبیق",
    "transactions": "تراکنش‌ها",
    # Bank Reconciliation
    "Bank Reconciliation": "تطبیق بانکی",
    "Match bank statements with ledger entries": "تطبیق صورت‌حساب‌های بانکی با ثبت‌های دفتر",
    "reconcile accounts automatically": "تطبیق خودکار حساب‌ها",
    "Reconcile Accounts": "تطبیق حساب‌ها",
    # Fixed Assets
    "Fixed Assets": "دارایی‌های ثابت",
    "Fixed Assets Register": "ثبت دارایی‌های ثابت",
    "Manage fixed assets register": "مدیریت ثبت دارایی‌های ثابت",
    "track depreciation": "پیگیری استهلاک",
    "asset disposal": "واگذاری دارایی",
    "book values": "ارزش دفتری",
    "Manage Assets": "مدیریت دارایی‌ها",
    "Register New Asset": "ثبت دارایی جدید",
    "Total Acquisition Cost": "هزینه خرید کل",
    "Accumulated Depreciation": "استهلاک انباشته",
    "Net Book Value": "ارزش دفتری خالص",
    # Depreciation
    "Depreciation Schedule": "جدول استهلاک",
    "View projected depreciation for all assets": "مشاهده استهلاک پیش‌بینی شده برای همه دارایی‌ها",
    "export to PDF/Excel for planning": "خروجی PDF/Excel برای برنامه‌ریزی",
    "View Schedule": "مشاهده جدول",
    # Configuration
    "Configuration": "تنظیمات",
    "Manage fiscal year": "مدیریت سال مالی",
    "accounting periods": "دوره‌های حسابداری",
    "currencies": "ارزها",
    "system preferences": "تنظیمات سیستم",
    "Configure": "پیکربندی",
    # Current Period
    "Current Period Overview": "نمای کلی دوره جاری",
    "Fiscal Period": "دوره مالی",
    "Accounting Status": "وضعیت حسابداری",
    "Active & Synchronized": "فعال و همگام‌سازی شده",
    "All financial transactions are automatically recorded": "همه تراکنش‌های مالی به صورت خودکار ثبت می‌شوند",
    "using double-entry bookkeeping": "با استفاده از دفترداری دوطرفه",
    "Data is synchronized in real-time": "داده‌ها به صورت لحظه‌ای همگام‌سازی می‌شوند",
    "from sales, purchases, and expenses": "از فروش، خرید و هزینه‌ها",
    "Auto Journal Entries": "ثبت‌های روزنامه خودکار",
    "Real-time Sync": "همگام‌سازی لحظه‌ای",
    "Audit Trail": "ردیاب حسابرسی",
    # Quick Actions
    "Quick Actions": "اقدامات سریع",
    "Generate Report": "تولید گزارش",
    "Add Account": "افزودن حساب",
    "Export Data": "خروجی داده‌ها",
    "Settings": "تنظیمات",
    "Need Help?": "نیاز به کمک؟",
    "Check our documentation": "مستندات ما را بررسی کنید",
    "or contact support": "یا با پشتیبانی تماس بگیرید",
    "for assistance with accounting features": "برای کمک در ویژگی‌های حسابداری",
    # Accounting System Setup
    "Accounting System Not Configured": "سیستم حسابداری پیکربندی نشده است",
    "Your accounting system needs to be initialized": "سیستم حسابداری شما نیاز به راه‌اندازی اولیه دارد",
    "before you can access financial features": "قبل از دسترسی به ویژگی‌های مالی",
    "This one-time setup will create your chart of accounts": "این راه‌اندازی یکبار انجام خواهد شد و دفتر حساب‌های شما را ایجاد می‌کند",
    "and configure the double-entry accounting system": "و سیستم حسابداری دوطرفه را پیکربندی می‌کند",
    "Initialize Accounting System": "راه‌اندازی سیستم حسابداری",
    "Learn More": "بیشتر بدانید",
}

# General UI Translations
GENERAL_UI_TRANSLATIONS = {
    # Navigation
    "Dashboard": "داشبورد",
    "Inventory": "موجودی انبار",
    "POS": "صندوق فروش",
    "Sales": "فروش",
    "More": "بیشتر",
    # User Interface
    "Toggle theme": "تغییر پوسته",
    "View notifications": "مشاهده اعلان‌ها",
    "Open user menu": "باز کردن منوی کاربر",
    "Skip to main content": "رفتن به محتوای اصلی",
    "Skip to navigation": "رفتن به ناوبری",
    "Main navigation": "ناوبری اصلی",
    "Main content": "محتوای اصلی",
    "Breadcrumb": "مسیر صفحه",
    # Common Actions
    "Create": "ایجاد",
    "Edit": "ویرایش",
    "Delete": "حذف",
    "Save": "ذخیره",
    "Cancel": "انصراف",
    "Search": "جستجو",
    "Filter": "فیلتر",
    "Sort": "مرتب‌سازی",
    "Refresh": "تازه‌سازی",
    "Close": "بستن",
    "Submit": "ارسال",
    "Update": "به‌روزرسانی",
    "Confirm": "تأیید",
    "Back": "بازگشت",
    "Next": "بعدی",
    "Previous": "قبلی",
    "Continue": "ادامه",
    # Status
    "Active": "فعال",
    "Inactive": "غیرفعال",
    "Pending": "در انتظار",
    "Completed": "تکمیل شده",
    "Cancelled": "لغو شده",
    "Draft": "پیش‌نویس",
    "Published": "منتشر شده",
    # Date & Time
    "Today": "امروز",
    "Yesterday": "دیروز",
    "Tomorrow": "فردا",
    "This Week": "این هفته",
    "This Month": "این ماه",
    "This Year": "امسال",
    "Last 7 days": "7 روز گذشته",
    "Last 30 days": "30 روز گذشته",
    "Last 90 days": "90 روز گذشته",
    "Last year": "سال گذشته",
    "Custom Range": "بازه دلخواه",
    # Messages
    "Success": "موفق",
    "Error": "خطا",
    "Warning": "هشدار",
    "Info": "اطلاعات",
    "Loading": "در حال بارگذاری",
    "Please wait": "لطفاً صبر کنید",
    "No data available": "داده‌ای موجود نیست",
    "No results found": "نتیجه‌ای یافت نشد",
    "Are you sure?": "آیا مطمئن هستید؟",
    "This action cannot be undone": "این عملیات قابل بازگشت نیست",
}

# Fixed Assets Translations
FIXED_ASSETS_TRANSLATIONS = {
    "Asset Name": "نام دارایی",
    "Asset Number": "شماره دارایی",
    "Category": "دسته‌بندی",
    "Description": "توضیحات",
    "Acquisition Date": "تاریخ خرید",
    "Acquisition Cost": "هزینه خرید",
    "Salvage Value": "ارزش باقیمانده",
    "Useful Life (Years)": "عمر مفید (سال)",
    "Depreciation Method": "روش استهلاک",
    "Straight Line": "خط مستقیم",
    "Declining Balance": "مانده نزولی",
    "Units of Production": "واحدهای تولید",
    "Equipment": "تجهیزات",
    "Fixtures": "وسایل ثابت",
    "Furniture": "مبلمان",
    "Vehicles": "وسایل نقلیه",
    "Buildings": "ساختمان‌ها",
    "Computers & IT Equipment": "کامپیوتر و تجهیزات فناوری اطلاعات",
    "Tools": "ابزار",
    "Other": "سایر",
    "Disposed": "واگذار شده",
    "Fully Depreciated": "کاملاً مستهلک شده",
    "Disposal Date": "تاریخ واگذاری",
    "Disposal Method": "روش واگذاری",
    "Disposal Proceeds": "عواید واگذاری",
    "Book Value at Disposal": "ارزش دفتری در هنگام واگذاری",
    "Gain/Loss on Disposal": "سود/زیان واگذاری",
    "Notes": "یادداشت‌ها",
}


def add_translations_to_po_file(po_file_path, translations):
    """Add missing translations to .po file."""
    try:
        with open(po_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        added_count = 0
        updated_count = 0

        for english, persian in translations.items():
            # Escape quotes in the strings
            english_escaped = english.replace('"', '\\"')
            persian_escaped = persian.replace('"', '\\"')

            # Pattern to find msgid with empty or incorrect msgstr
            pattern = rf'msgid "{re.escape(english_escaped)}"\nmsgstr "([^"]*)"'

            if re.search(pattern, content):
                # Check if translation is empty or different
                match = re.search(pattern, content)
                if match and (not match.group(1) or match.group(1) != persian_escaped):
                    # Update existing empty translation
                    content = re.sub(
                        pattern, f'msgid "{english_escaped}"\nmsgstr "{persian_escaped}"', content
                    )
                    updated_count += 1
                    print(f"  ✓ Updated: {english} -> {persian}")
            else:
                # Add new translation entry
                new_entry = f'\nmsgid "{english_escaped}"\nmsgstr "{persian_escaped}"\n'
                # Add before the last line (usually empty)
                content = content.rstrip() + new_entry + "\n"
                added_count += 1
                print(f"  + Added: {english} -> {persian}")

        # Write updated content
        with open(po_file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return added_count, updated_count

    except Exception as e:
        print(f"Error processing {po_file_path}: {e}")
        return 0, 0


def main():
    """Main function to add all translations."""
    po_file = Path(__file__).parent / "locale" / "fa" / "LC_MESSAGES" / "django.po"

    if not po_file.exists():
        print(f"Error: Translation file not found at {po_file}")
        sys.exit(1)

    print("=" * 70)
    print("Persian Translation Addition - Production Ready")
    print("=" * 70)
    print()

    print("📝 Adding Accounting Module Translations...")
    print("-" * 70)
    acc_added, acc_updated = add_translations_to_po_file(po_file, ACCOUNTING_TRANSLATIONS)
    print(f"\n✓ Accounting: {acc_added} added, {acc_updated} updated\n")

    print("📝 Adding General UI Translations...")
    print("-" * 70)
    ui_added, ui_updated = add_translations_to_po_file(po_file, GENERAL_UI_TRANSLATIONS)
    print(f"\n✓ General UI: {ui_added} added, {ui_updated} updated\n")

    print("📝 Adding Fixed Assets Translations...")
    print("-" * 70)
    fa_added, fa_updated = add_translations_to_po_file(po_file, FIXED_ASSETS_TRANSLATIONS)
    print(f"\n✓ Fixed Assets: {fa_added} added, {fa_updated} updated\n")

    total_added = acc_added + ui_added + fa_added
    total_updated = acc_updated + ui_updated + fa_updated

    print("=" * 70)
    print(f"✅ COMPLETE: {total_added} new translations added, {total_updated} updated")
    print("=" * 70)
    print()
    print("Next steps:")
    print("1. Run: python manage.py compilemessages")
    print("2. Rebuild Docker image")
    print("3. Deploy to Kubernetes")
    print()


if __name__ == "__main__":
    main()
