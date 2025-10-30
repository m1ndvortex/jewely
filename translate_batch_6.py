#!/usr/bin/env python3
"""
Translate gold rates, price overrides, goods receipt, and inventory terms
"""

TRANSLATIONS = {
    # Time periods
    "Time Period": "دوره زمانی",
    "Last 7 days": "7 روز گذشته",
    "Last 30 days": "30 روز گذشته",
    "Last 90 days": "90 روز گذشته",
    # Rate information
    "Current Rate": "نرخ فعلی",
    "Period Change": "تغییر دوره",
    "Highest Rate": "بالاترین نرخ",
    "Lowest Rate": "پایین‌ترین نرخ",
    "Rate Trend": "روند نرخ",
    "Historical Data": "داده‌های تاریخی",
    "Date & Time": "تاریخ و زمان",
    "No Historical Data": "داده تاریخی وجود ندارد",
    "No gold rate data available for the selected market and time period.": "داده نرخ طلا برای بازار و دوره زمانی انتخاب شده موجود نیست.",
    "Rate (USD)": "نرخ (دلار)",
    # Live gold rates
    "Live Gold Rates": "نرخ‌های زنده طلا",
    "Compare": "مقایسه",
    "No change": "بدون تغییر",
    "Tola": "تولا",
    "Oz": "اونس",
    "No gold rates available": "نرخ طلا موجود نیست",
    "Rates will appear when data is fetched from external APIs": "نرخ‌ها هنگامی نمایش داده می‌شوند که داده از APIهای خارجی دریافت شود",
    "Auto-refreshes every 30 seconds": "تازه‌سازی خودکار هر 30 ثانیه",
    # Price override requests
    "Price Override Requests": "درخواست‌های نادیده‌گیری قیمت",
    "Current Price": "قیمت فعلی",
    "Requested Price": "قیمت درخواستی",
    "Deviation": "انحراف",
    "Requested By": "درخواست شده توسط",
    "No price override requests found.": "درخواست نادیده‌گیری قیمتی یافت نشد.",
    # Price calculation
    "Price Calculation Result": "نتیجه محاسبه قیمت",
    "Calculate Another": "محاسبه دیگری",
    "Calculation Details": "جزئیات محاسبه",
    "Craftsmanship": "صنعتگری",
    "Gold Rate": "نرخ طلا",
    "Rule Applied": "قانون اعمال شده",
    "Price Breakdown": "تفکیک قیمت",
    "Gold Value": "ارزش طلا",
    "Markup Amount": "مقدار افزایش قیمت",
    "Fixed Markup": "افزایش قیمت ثابت",
    "Total Price": "قیمت کل",
    "Pricing by Customer Tier": "قیمت‌گذاری بر اساس رده مشتری",
    "Selected": "انتخاب شده",
    # Goods receipt completion
    "Complete Goods Receipt": "تکمیل رسید کالا",
    "Back to Receipt": "بازگشت به رسید",
    "Completion Confirmation": "تأیید تکمیل",
    "What happens when you complete this receipt?": "هنگام تکمیل این رسید چه اتفاقی می‌افتد؟",
    "Inventory levels will be updated for all accepted items": "سطوح موجودی برای تمام اقلام پذیرفته شده به‌روزرسانی می‌شود",
    "New inventory items will be created if they don't exist": "اقلام موجودی جدید در صورت عدم وجود ایجاد می‌شوند",
    "Purchase order status will be updated": "وضعیت سفارش خرید به‌روزرسانی می‌شود",
    "The receipt status will be marked as completed": "وضعیت رسید به عنوان تکمیل شده علامت‌گذاری می‌شود",
    # Warnings
    "Three-Way Matching Warning": "هشدار تطبیق سه‌طرفه",
    "Discrepancy Warning": "هشدار عدم تطابق",
    # Inventory items
    "Items to be Added to Inventory": "اقلامی که به موجودی اضافه می‌شوند",
    "Quantity Accepted": "تعداد پذیرفته شده",
    "Unit Price": "قیمت واحد",
    "Total Value": "ارزش کل",
    "Update Existing": "به‌روزرسانی موجود",
    "No items to add to inventory": "موردی برای افزودن به موجودی وجود ندارد",
    # Receipt summary
    "Receipt Summary": "خلاصه رسید",
    "Receipt Number": "شماره رسید",
    "Received Date": "تاریخ دریافت",
    "Purchase Order": "سفارش خرید",
    "Supplier": "تأمین‌کننده",
    "Total Items": "مجموع اقلام",
    "Total Quantity": "مجموع تعداد",
    "Total Amount": "مبلغ کل",
    "Receipt Status": "وضعیت رسید",
    "Created By": "ایجاد شده توسط",
    "Last Modified": "آخرین تغییر",
    # Inventory management
    "Inventory Management": "مدیریت موجودی",
    "Add to Inventory": "افزودن به موجودی",
    "Remove from Inventory": "حذف از موجودی",
    "Transfer Inventory": "انتقال موجودی",
    "Adjust Inventory": "تنظیم موجودی",
    "Inventory Count": "شمارش موجودی",
    "Physical Count": "شمارش فیزیکی",
    "System Count": "شمارش سیستم",
    "Variance": "واریانس",
    "Adjustment Reason": "دلیل تنظیم",
    "Damaged": "آسیب دیده",
    "Lost": "گم شده",
    "Stolen": "سرقت شده",
    "Expired": "منقضی شده",
    "Obsolete": "منسوخ شده",
    "Correction": "اصلاح",
    "Return to Supplier": "بازگشت به تأمین‌کننده",
    "Sample": "نمونه",
    "Promotion": "تبلیغات",
    "Gift": "هدیه",
    # Warehouse management
    "Warehouse": "انبار",
    "Location": "مکان",
    "Bin": "محفظه",
    "Shelf": "قفسه",
    "Aisle": "راهرو",
    "Zone": "ناحیه",
    "Section": "بخش",
    "Storage Type": "نوع ذخیره‌سازی",
    "Temperature Controlled": "کنترل دما",
    "Secure Storage": "ذخیره‌سازی امن",
    "Bulk Storage": "ذخیره‌سازی انبوه",
    "High Value Storage": "ذخیره‌سازی با ارزش بالا",
    # Stock movements
    "Stock Movement": "جابجایی موجودی",
    "Movement Type": "نوع جابجایی",
    "Inbound": "ورودی",
    "Outbound": "خروجی",
    "Transfer": "انتقال",
    "Adjustment": "تنظیم",
    "From Location": "از مکان",
    "To Location": "به مکان",
    "Movement Date": "تاریخ جابجایی",
    "Reference Number": "شماره مرجع",
    "Reason": "دلیل",
    # Purchase orders
    "Purchase Order Number": "شماره سفارش خرید",
    "Order Date": "تاریخ سفارش",
    "Expected Delivery": "تحویل مورد انتظار",
    "Delivery Address": "آدرس تحویل",
    "Payment Terms": "شرایط پرداخت",
    "Net 30": "خالص 30",
    "Net 60": "خالص 60",
    "Net 90": "خالص 90",
    "Due on Receipt": "سررسید در دریافت",
    "Advance Payment": "پیش‌پرداخت",
    "Cash on Delivery": "پرداخت در محل",
    "Letter of Credit": "اعتبار اسنادی",
    # Supplier management
    "Supplier Details": "جزئیات تأمین‌کننده",
    "Supplier Name": "نام تأمین‌کننده",
    "Supplier Code": "کد تأمین‌کننده",
    "Contact Person": "فرد تماس",
    "Contact Number": "شماره تماس",
    "Contact Email": "ایمیل تماس",
    "Supplier Address": "آدرس تأمین‌کننده",
    "Payment Method": "روش پرداخت",
    "Credit Limit": "محدودیت اعتبار",
    "Outstanding Balance": "مانده معوق",
    "Rating": "امتیاز",
    "Active Supplier": "تأمین‌کننده فعال",
    "Preferred Supplier": "تأمین‌کننده ترجیحی",
    "Blocked Supplier": "تأمین‌کننده مسدود شده",
    # Quality control
    "Quality Control": "کنترل کیفیت",
    "Inspection": "بازرسی",
    "Inspection Date": "تاریخ بازرسی",
    "Inspector": "بازرس",
    "Pass": "قبول",
    "Fail": "رد",
    "Conditional Pass": "قبول مشروط",
    "Pending Inspection": "در انتظار بازرسی",
    "Inspection Notes": "یادداشت‌های بازرسی",
    "Defect Type": "نوع نقص",
    "Defect Quantity": "تعداد نقص",
    "Action Required": "اقدام مورد نیاز",
    "Rework": "کار مجدد",
    "Scrap": "ضایعات",
    "Return": "بازگشت",
    "Accept with Discount": "پذیرش با تخفیف",
}


def update_po_batch(filepath):
    """Apply batch translations."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    translated = 0
    for en, fa in TRANSLATIONS.items():
        old_pattern = f'msgid "{en}"\nmsgstr ""'
        new_pattern = f'msgid "{en}"\nmsgstr "{fa}"'
        if old_pattern in content:
            content = content.replace(old_pattern, new_pattern, 1)
            translated += 1

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return translated


if __name__ == "__main__":
    po = "locale/fa/LC_MESSAGES/django.po"
    print("Translating batch 6: gold rates, inventory, suppliers...")
    count = update_po_batch(po)
    print(f"✅ Translated {count} entries")
    print(f"Progress: 585 + {count} = {585 + count} total")
