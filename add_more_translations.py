#!/usr/bin/env python3
"""
Add Persian translations for SMS, campaigns, and remaining common strings.
"""
import re

TRANSLATIONS = {
    # SMS Related
    "Email Templates": "قالب‌های ایمیل",
    "Queued": "در صف",
    "Undelivered": "تحویل نشده",
    "Alert": "هشدار",
    "User who received this SMS": "کاربری که این پیامک را دریافت کرد",
    "SMS message content": "محتوای پیام پیامک",
    "Recipient phone number": "شماره تلفن گیرنده",
    "Sender phone number": "شماره تلفن فرستنده",
    "SMS template used": "قالب پیامک استفاده شده",
    "Type of SMS": "نوع پیامک",
    "Twilio message SID": "شناسه پیام توییلیو",
    "Twilio error code if applicable": "کد خطای توییلیو در صورت وجود",
    "When to send this SMS (for scheduled SMS)": "زمان ارسال این پیامک (برای پیامک‌های زمان‌بندی شده)",
    "Campaign ID for marketing SMS": "شناسه کمپین برای پیامک‌های بازاریابی",
    "Cost of sending this SMS": "هزینه ارسال این پیامک",
    "Currency unit for price": "واحد ارز برای قیمت",
    "SMS Notification": "اعلان پیامکی",
    "SMS Notifications": "اعلان‌های پیامکی",
    "Unique name for this SMS template": "نام یکتا برای این قالب پیامک",
    "SMS message template (supports Django template syntax)": "قالب پیام پیامک (پشتیبانی از سینتکس قالب جنگو)",
    "Type of SMS this template is for": "نوع پیامکی که این قالب برای آن است",
    "SMS Template": "قالب پیامک",
    "SMS Templates": "قالب‌های پیامک",
    "User who opted out of SMS": "کاربری که از پیامک انصراف داد",
    "When the user opted out": "زمان انصراف کاربر",
    "Reason for opting out": "دلیل انصراف",
    "Opted out of transactional SMS": "انصراف از پیامک تراکنشی",
    "Opted out of marketing SMS (default: True)": "انصراف از پیامک بازاریابی (پیش‌فرض: بله)",
    "Opted out of system SMS": "انصراف از پیامک سیستمی",
    "Opted out of alert SMS": "انصراف از پیامک هشدار",
    "SMS Opt-out": "انصراف از پیامک",
    "SMS Opt-outs": "انصرافات از پیامک",
    
    # Campaign Related
    "Campaign": "کمپین",
    "Campaigns": "کمپین‌ها",
    "Campaign name": "نام کمپین",
    "Campaign description": "توضیحات کمپین",
    "Campaign type": "نوع کمپین",
    "Start date": "تاریخ شروع",
    "End date": "تاریخ پایان",
    "Target audience": "مخاطبان هدف",
    "Campaign status": "وضعیت کمپین",
    "Total recipients": "مجموع گیرندگان",
    "Successful deliveries": "تحویل‌های موفق",
    "Failed deliveries": "تحویل‌های ناموفق",
    "Click-through rate": "نرخ کلیک",
    "Conversion rate": "نرخ تبدیل",
    "Budget": "بودجه",
    "Spent": "خرج شده",
    "ROI": "بازگشت سرمایه",
    
    # More UI strings
    "Language switcher": "تغییر دهنده زبان",
    "Toggle navigation": "تغییر ناوبری",
    "Toggle sidebar": "تغییر نوار کناری",
    "Toggle fullscreen": "تغییر تمام صفحه",
    "Expand all": "گسترش همه",
    "Collapse all": "جمع کردن همه",
    "Select all": "انتخاب همه",
    "Deselect all": "لغو انتخاب همه",
    "Bulk actions": "اقدامات گروهی",
    "Apply to selected": "اعمال به انتخاب شده‌ها",
    "Are you sure?": "آیا مطمئن هستید؟",
    "Yes, delete": "بله، حذف کن",
    "No, cancel": "خیر، لغو کن",
    "Confirm deletion": "تأیید حذف",
    "This action is irreversible": "این عمل غیرقابل بازگشت است",
    "Proceed": "ادامه",
    "Go back": "بازگشت",
    "Skip": "رد شدن",
    "Finish": "پایان",
    "Done": "انجام شد",
    "Loading": "در حال بارگیری",
    "Processing": "در حال پردازش",
    "Saving": "در حال ذخیره",
    "Deleting": "در حال حذف",
    "Uploading": "در حال بارگذاری",
    "Downloading": "در حال دانلود",
    "Syncing": "در حال همگام‌سازی",
    "Connecting": "در حال اتصال",
    "Disconnecting": "در حال قطع اتصال",
    "Refreshing": "در حال بارگیری مجدد",
    
    # Common messages
    "No items found": "موردی یافت نشد",
    "No records to display": "رکوردی برای نمایش وجود ندارد",
    "Empty list": "لیست خالی",
    "Start by adding items": "با افزودن موارد شروع کنید",
    "Nothing here yet": "هنوز چیزی اینجا نیست",
    "Try a different filter": "فیلتر دیگری امتحان کنید",
    "Clear filters": "پاک کردن فیلترها",
    "Reset to default": "بازنشانی به پیش‌فرض",
    "Restore defaults": "بازگردانی پیش‌فرض‌ها",
    "Show filters": "نمایش فیلترها",
    "Hide filters": "پنهان کردن فیلترها",
    "Advanced filters": "فیلترهای پیشرفته",
    "Quick filters": "فیلترهای سریع",
    
    # Table/Grid
    "Show entries": "نمایش رکوردها",
    "Showing": "نمایش",
    "of": "از",
    "entries": "رکورد",
    "First": "اول",
    "Last": "آخر",
    "Page": "صفحه",
    "Go to page": "رفتن به صفحه",
    "Per page": "در هر صفحه",
    "Rows per page": "ردیف در هر صفحه",
    "No data": "داده‌ای وجود ندارد",
    "Sort ascending": "مرتب‌سازی صعودی",
    "Sort descending": "مرتب‌سازی نزولی",
    "Sort by": "مرتب‌سازی بر اساس",
    "Group by": "گروه‌بندی بر اساس",
    
    # Form validation
    "Please fill out this field": "لطفاً این فیلد را پر کنید",
    "Please select an option": "لطفاً یک گزینه انتخاب کنید",
    "Please enter a number": "لطفاً یک عدد وارد کنید",
    "Please enter a valid date": "لطفاً یک تاریخ معتبر وارد کنید",
    "Please enter a valid URL": "لطفاً یک آدرس معتبر وارد کنید",
    "Minimum length": "حداقل طول",
    "Maximum length": "حداکثر طول",
    "characters": "کاراکتر",
    "Must be at least": "باید حداقل",
    "Must not exceed": "نباید بیشتر از",
    "Invalid input": "ورودی نامعتبر",
    "Required field": "فیلد الزامی",
    
    # Dates
    "Start Date": "تاریخ شروع",
    "End Date": "تاریخ پایان",
    "Created At": "ایجاد شده در",
    "Updated At": "به‌روزرسانی شده در",
    "Deleted At": "حذف شده در",
    "Last Modified": "آخرین تغییر",
    "Last Login": "آخرین ورود",
    "Expires": "منقضی می‌شود",
    "Expired": "منقضی شده",
    "Never": "هرگز",
    "Always": "همیشه",
    "Custom": "سفارشی",
    "Custom Date Range": "بازه زمانی سفارشی",
    "Select Date": "انتخاب تاریخ",
    "Select Time": "انتخاب زمان",
    "Date and Time": "تاریخ و زمان",
    
    # Numbers and currency
    "Amount": "مقدار",
    "Total Amount": "مقدار کل",
    "Balance": "مانده",
    "Credit": "اعتبار",
    "Debit": "بدهی",
    "Percentage": "درصد",
    "Rate": "نرخ",
    "Count": "تعداد",
    "Average": "میانگین",
    "Minimum": "حداقل",
    "Maximum": "حداکثر",
    "Sum": "مجموع",
    
    # Actions
    "Create New": "ایجاد جدید",
    "Add New": "افزودن جدید",
    "Edit Item": "ویرایش مورد",
    "Delete Item": "حذف مورد",
    "View Details": "مشاهده جزئیات",
    "Duplicate Item": "تکثیر مورد",
    "Archive": "بایگانی",
    "Restore": "بازگردانی",
    "Activate": "فعال‌سازی",
    "Deactivate": "غیرفعال‌سازی",
    "Enable": "فعال کردن",
    "Disable": "غیرفعال کردن",
    "Publish": "انتشار",
    "Unpublish": "لغو انتشار",
    "Lock": "قفل کردن",
    "Unlock": "باز کردن قفل",
    "Pin": "سنجاق کردن",
    "Unpin": "برداشتن سنجاق",
    "Star": "ستاره دار کردن",
    "Unstar": "برداشتن ستاره",
    "Bookmark": "نشانه‌گذاری",
    "Unbookmark": "برداشتن نشانه",
    "Flag": "پرچم‌گذاری",
    "Unflag": "برداشتن پرچم",
}


def update_po(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    translated = 0
    for en, fa in TRANSLATIONS.items():
        esc = re.escape(en)
        pattern = rf'(msgid "{esc}"\nmsgstr ")(")'
        new, count = re.subn(pattern, rf'\1{fa}\2', content)
        if count:
            content = new
            translated += count
            print(f"✓ {en[:60]:60s} → {fa[:40]}")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"\n✅ Translated {translated} entries")
    return translated

if __name__ == '__main__':
    po = 'locale/fa/LC_MESSAGES/django.po'
    print('='*80)
    print('ADDING SMS, CAMPAIGNS, AND UI TRANSLATIONS')
    print('='*80 + '\n')
    count = update_po(po)
    print(f'\nTotal added: {count}')
    print('Run compilemessages and restart.')
