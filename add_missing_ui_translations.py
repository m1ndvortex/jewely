#!/usr/bin/env python3
"""
Add all missing POS and Accounting translations
"""

import re

PO_FILE = "locale/fa/LC_MESSAGES/django.po"

# All missing translations found on the pages
TRANSLATIONS = {
    # POS Interface
    "Transaction Dashboard": "داشبورد تراکنش‌ها",
    "Manage sales and customer transactions efficiently": "مدیریت کارآمد فروش و تراکنش‌های مشتریان",
    "Search product name, SKU, or scan barcode": "جستجوی نام محصول، SKU یا اسکن بارکد",
    "Cart": "سبد خرید",
    "Recent Items": "موارد اخیر",
    "Your cart is empty": "سبد خرید شما خالی است",
    "Add products to begin a new sale.": "برای شروع فروش جدید، محصولات را اضافه کنید.",
    "Customer": "مشتری",
    "Search customer...": "جستجوی مشتری...",
    "Terminal": "ترمینال",
    "Select Terminal": "انتخاب ترمینال",
    "Current": "جاری",
    "Not selected": "انتخاب نشده",
    "Payment": "پرداخت",
    "Cash": "نقد",
    "Card": "کارت",
    "Store Credit": "اعتبار فروشگاه",
    "Order Summary": "خلاصه سفارش",
    "Subtotal": "جمع جزء",
    "Tax (10%)": "مالیات (10%)",
    "Discount": "تخفیف",
    "Total": "جمع کل",
    "Hold Sale": "نگه داشتن فروش",
    "Complete Sale": "تکمیل فروش",
    "Reprint Receipt": "چاپ مجدد رسید",
    "Held Sales": "فروش‌های نگه داشته شده",
    "Cart (0)": "سبد خرید (0)",
    # Accounting Dashboard
    "vs last period": "نسبت به دوره قبل",
    "Net Income": "درآمد خالص",
    "profit margin": "حاشیه سود",
    "Balance Sheet, Income Statement, Cash Flow, Trial Balance with PDF/Excel export": "ترازنامه، صورت سود و زیان، جریان وجوه نقد، تراز آزمایشی با خروجی PDF/Excel",
    "Manage account structure, view balances, Assets, Liabilities, Equity, Revenue, Expenses": "مدیریت ساختار حساب، مشاهده موجودی‌ها، دارایی‌ها، بدهی‌ها، حقوق صاحبان سهام، درآمد، هزینه‌ها",
    "Journal Entries": "اسناد حسابداری",
    "View and manage all journal entries, automatic double-entry bookkeeping transactions": "مشاهده و مدیریت تمام اسناد حسابداری، تراکنش‌های دفترداری دوطرفه خودکار",
    "Complete transaction history, account movements, and audit trail for all entries": "تاریخچه کامل تراکنش‌ها، گردش حساب‌ها و ردپای حسابرسی برای تمام ورودی‌ها",
    "Bills & Payables": "صورتحساب‌ها و پرداختنی‌ها",
    "Manage supplier bills, track payments, aging reports, and outstanding payables": "مدیریت صورتحساب‌های تامین‌کننده، پیگیری پرداخت‌ها، گزارش‌های سنی و پرداختنی‌های معوق",
    "View supplier accounting details, statements, and payment history": "مشاهده جزئیات حسابداری تامین‌کننده، صورت‌حساب‌ها و تاریخچه پرداخت",
    "Invoices & Receivables": "فاکتورها و دریافتنی‌ها",
    "Manage customer invoices, track payments, aging reports, and credit memos": "مدیریت فاکتورهای مشتری، پیگیری پرداخت‌ها، گزارش‌های سنی و یادداشت‌های بستانکاری",
    "View customer accounting details, invoices, statements, and credit limits": "مشاهده جزئیات حسابداری مشتری، فاکتورها، صورت‌حساب‌ها و محدودیت‌های اعتباری",
    "Track customer invoices, payments due, and manage outstanding receivables": "پیگیری فاکتورهای مشتری، پرداخت‌های سررسید شده و مدیریت دریافتنی‌های معوق",
    "Manage bank accounts, track balances, reconciliation status, and transactions": "مدیریت حساب‌های بانکی، پیگیری موجودی‌ها، وضعیت مغایرت‌گیری و تراکنش‌ها",
    "Match bank statements with ledger entries, reconcile accounts automatically": "تطبیق صورت‌حساب‌های بانکی با ورودی‌های دفتر کل، مغایرت‌گیری خودکار حساب‌ها",
    "Manage fixed assets register, track depreciation, asset disposal, and book values": "مدیریت دفتر دارایی‌های ثابت، پیگیری استهلاک، واگذاری دارایی و ارزش دفتری",
    "Depreciation Schedule": "جدول استهلاک",
    "View projected depreciation for all assets, export to PDF/Excel for planning": "مشاهده استهلاک پیش‌بینی شده برای تمام دارایی‌ها، خروجی PDF/Excel برای برنامه‌ریزی",
    "Manage fiscal year, accounting periods, currencies, and system preferences": "مدیریت سال مالی، دوره‌های حسابداری، ارزها و ترجیحات سیستم",
    "Active & Synchronized": "فعال و همگام‌سازی شده",
    "All financial transactions are automatically recorded using double-entry bookkeeping. Data is synchronized in real-time from sales, purchases, and expenses.": "تمام تراکنش‌های مالی به صورت خودکار با استفاده از دفترداری دوطرفه ثبت می‌شوند. داده‌ها به صورت بلادرنگ از فروش، خرید و هزینه‌ها همگام‌سازی می‌شوند.",
    "Auto Journal Entries": "اسناد حسابداری خودکار",
    "Real-time Sync": "همگام‌سازی بلادرنگ",
    "Need Help?": "نیاز به کمک دارید؟",
    "Check our documentation or contact support for assistance with accounting features.": "برای راهنمایی در مورد ویژگی‌های حسابداری، مستندات ما را بررسی کنید یا با پشتیبانی تماس بگیرید.",
}


def main():
    with open(PO_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    i = 0
    translated_count = 0

    while i < len(lines):
        line = lines[i]
        # Check if this is a msgid
        if line.startswith('msgid "') and i + 1 < len(lines):
            msgid_match = re.match(r'msgid "(.*?)"', line)
            if msgid_match:
                msgid = msgid_match.group(1)
                # Check if next line is empty msgstr
                if lines[i + 1].strip() == 'msgstr ""':
                    if msgid in TRANSLATIONS:
                        # Replace with translation
                        new_lines.append(line)
                        new_lines.append(f'msgstr "{TRANSLATIONS[msgid]}"\n')
                        i += 2
                        translated_count += 1
                        print(f"Translated: {msgid}")
                        continue

        new_lines.append(line)
        i += 1

    with open(PO_FILE, "w", encoding="utf-8") as f:
        f.writelines(new_lines)

    print(f"\n✓ Added {translated_count} translations")


if __name__ == "__main__":
    main()
