#!/usr/bin/env python3
"""
Translate final batch: goods receipts, reports, and remaining strings
"""
import re

TRANSLATIONS = {
    # Goods receipt status
    "Current Status": "وضعیت فعلی",
    "Inventory Impact": "تأثیر موجودی",
    "Items Added": "اقلام اضافه شده",
    "Complete Receipt & Update Inventory": "تکمیل رسید و به‌روزرسانی موجودی",
    
    # Goods receipt main
    "Goods Receipt": "رسید کالا",
    "Complete Receipt": "تکمیل رسید",
    "Back to List": "بازگشت به لیست",
    
    # Receipt information
    "Receipt Information": "اطلاعات رسید",
    "Received By": "دریافت شده توسط",
    "Invoice Number": "شماره فاکتور",
    "Tracking Number": "شماره پیگیری",
    "Discrepancy Notes": "یادداشت‌های عدم تطابق",
    
    # Receipt items
    "Receipt Items": "اقلام رسید",
    "Ordered": "سفارش داده شده",
    "Accepted": "پذیرفته شده",
    "Passed": "قبول شده",
    "No items in this receipt": "موردی در این رسید وجود ندارد",
    
    # Quality and matching
    "Quality Check Summary": "خلاصه کنترل کیفیت",
    "Three-Way Matching": "تطبیق سه‌طرفه",
    "Match Complete": "تطبیق کامل",
    "PO, receipt, and invoice quantities match": "تعداد سفارش خرید، رسید و فاکتور مطابقت دارند",
    "Pending Match": "تطبیق در انتظار",
    "Quantities do not match or receipt incomplete": "تعداد مطابقت ندارد یا رسید ناقص است",
    
    # Purchase order summary
    "Purchase Order Summary": "خلاصه سفارش خرید",
    "PO Number": "شماره سفارش خرید",
    "PO Status": "وضعیت سفارش خرید",
    "View Purchase Order": "مشاهده سفارش خرید",
    
    # Receipt creation
    "Create Goods Receipt": "ایجاد رسید کالا",
    "Add Item": "افزودن مورد",
    "Purchase Order Item": "مورد سفارش خرید",
    "Quantity Received": "تعداد دریافت شده",
    "Quantity Rejected": "تعداد رد شده",
    "Quality Notes": "یادداشت‌های کیفیت",
    "Discrepancy Reason": "دلیل عدم تطابق",
    
    # Purchase order details
    "Purchase Order Details": "جزئیات سفارش خرید",
    "Please select a purchase order first to add items.": "لطفاً ابتدا یک سفارش خرید برای افزودن اقلام انتخاب کنید.",
    "Rejected quantity cannot exceed received quantity": "تعداد رد شده نمی‌تواند از تعداد دریافت شده بیشتر باشد",
    
    # Goods receipts list
    "Goods Receipts": "رسیدهای کالا",
    "New Goods Receipt": "رسید کالای جدید",
    "Receipt number, PO number, invoice...": "شماره رسید، شماره سفارش خرید، فاکتور...",
    "All Purchase Orders": "تمام سفارش‌های خرید",
    "Discrepancy": "عدم تطابق",
    "Has Discrepancy": "دارای عدم تطابق",
    "No Discrepancy": "بدون عدم تطابق",
    "Has discrepancy": "دارای عدم تطابق",
    "No discrepancy": "بدون عدم تطابق",
    "Goods receipts pagination": "صفحه‌بندی رسیدهای کالا",
    "No goods receipts found": "رسید کالایی یافت نشد",
    "Create your first goods receipt to track received shipments.": "اولین رسید کالای خود را برای پیگیری محموله‌های دریافتی ایجاد کنید.",
    
    # Reports
    "Back to Reports": "بازگشت به گزارش‌ها",
    "Report Parameters": "پارامترهای گزارش",
    "Select...": "انتخاب...",
    "Output Format": "قالب خروجی",
    "Email Recipients": "گیرندگان ایمیل",
    "optional": "اختیاری",
    "Enter email addresses separated by commas": "آدرس‌های ایمیل را با کاما جدا کنید",
    "Leave empty to download directly": "برای دانلود مستقیم خالی بگذارید",
    
    # Report information
    "Report Information": "اطلاعات گزارش",
    "Available Formats": "قالب‌های موجود",
    "Parameters": "پارامترها",
    "parameter(s)": "پارامتر(ها)",
    
    # Pre-built reports
    "Pre-built Reports": "گزارش‌های از پیش ساخته شده",
    "Ready-to-use reports for common business analysis needs": "گزارش‌های آماده برای نیازهای تحلیل کسب‌وکار رایج",
    "Run Report": "اجرای گزارش",
    "Execute Report": "اجرای گزارش",
    
    # Report execution
    "Output Formats": "قالب‌های خروجی",
    "Execution Parameters": "پارامترهای اجرا",
    "Select an option": "یک گزینه انتخاب کنید",
    "Choose the format for the generated report": "قالب را برای گزارش تولید شده انتخاب کنید",
    
    # Execution information
    "Execution Information": "اطلاعات اجرا",
    "Report execution may take several minutes for large datasets": "اجرای گزارش ممکن است برای مجموعه داده‌های بزرگ چند دقیقه طول بکشد",
    "You will be notified when the report is ready": "هنگامی که گزارش آماده شد به شما اطلاع داده می‌شود",
    "Otherwise, you can download the report from the execution history": "در غیر این صورت، می‌توانید گزارش را از تاریخچه اجرا دانلود کنید",
}


def update_po_final(filepath):
    """Apply final batch translations."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    translated = 0
    for en, fa in TRANSLATIONS.items():
        old_pattern = f'msgid "{en}"\nmsgstr ""'
        new_pattern = f'msgid "{en}"\nmsgstr "{fa}"'
        if old_pattern in content:
            content = content.replace(old_pattern, new_pattern, 1)
            translated += 1

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    return translated

if __name__ == '__main__':
    po = 'locale/fa/LC_MESSAGES/django.po'
    print('Translating FINAL batch: goods receipts, reports...')
    count = update_po_final(po)
    print(f'✅ Translated {count} entries')
    print(f'Progress: 647 + {count} = {647 + count} total')
    print()
    
    # Check if we're done
    with open(po, 'r', encoding='utf-8') as f:
        content = f.read()
    untranslated = [s for s in re.findall(r'msgid "([^"]+)"\nmsgstr ""', content) if s and not s.startswith('%')]
    
    if len(untranslated) == 0:
        print('🎉 ALL TRANSLATIONS COMPLETE! 100%')
    else:
        print(f'⚠️  {len(untranslated)} strings still remaining')
