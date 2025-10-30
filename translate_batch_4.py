#!/usr/bin/env python3
"""
Translate campaign tracking, notifications, segments, and UI strings
"""
import re

TRANSLATIONS = {
    # Campaign actions
    "Send Campaign": "ارسال کمپین",
    "Type:": "نوع:",
    "Target:": "هدف:",
    "Ready to send campaign to selected segment.": "آماده برای ارسال کمپین به بخش انتخاب شده.",
    "Track the performance of your email and SMS campaigns.": "عملکرد کمپین‌های ایمیل و پیامک خود را پیگیری کنید.",
    "Total Campaigns": "مجموع کمپین‌ها",
    "Messages Sent": "پیام‌های ارسال شده",
    # Email metrics
    "Email Metrics": "معیارهای ایمیل",
    "Total Opened": "مجموع باز شده",
    "Total Clicked": "مجموع کلیک شده",
    "Total Conversions": "مجموع تبدیل‌ها",
    "Conversion Value": "ارزش تبدیل",
    "Total Cost": "هزینه کل",
    "Recent Campaigns": "کمپین‌های اخیر",
    "No campaigns found for the selected period.": "کمپینی برای دوره انتخاب شده یافت نشد.",
    # Communication history
    "View all customer communications across all channels.": "مشاهده تمام ارتباطات مشتری در تمام کانال‌ها.",
    "Enter customer ID...": "شناسه مشتری را وارد کنید...",
    "Communication Type": "نوع ارتباط",
    "All Types": "تمام انواع",
    "Campaign ID": "شناسه کمپین",
    "Enter campaign ID...": "شناسه کمپین را وارد کنید...",
    "Communication History": "تاریخچه ارتباطات",
    "Direction": "جهت",
    "Subject": "موضوع",
    "Engagement": "تعامل",
    "Converted": "تبدیل شده",
    "No communications found.": "ارتباطی یافت نشد.",
    # Customer segments
    "Create Segment": "ایجاد بخش",
    "All Segments": "تمام بخش‌ها",
    "No customer segments found.": "بخش مشتری یافت نشد.",
    # Notification center
    "Notification Center": "مرکز اعلان‌ها",
    "Manage your notifications and stay updated": "اعلان‌های خود را مدیریت کنید و به‌روز بمانید",
    "Mark All Read": "علامت همه به عنوان خوانده شده",
    "Unread only": "فقط خوانده نشده",
    "All types": "تمام انواع",
    "All notifications read": "تمام اعلان‌ها خوانده شد",
    "notifications": "اعلان‌ها",
    "No notifications": "اعلانی وجود ندارد",
    "You're all caught up! No notifications to display.": "همه چیز به‌روز است! اعلانی برای نمایش وجود ندارد.",
    "Mark all notifications as read?": "علامت‌گذاری تمام اعلان‌ها به عنوان خوانده شده؟",
    "new": "جدید",
    "ago": "پیش",
    "View all notifications": "مشاهده تمام اعلان‌ها",
    "Error:": "خطا:",
    "Showing first %(showing)s of %(total)s": "نمایش %(showing)s اول از %(total)s",
    # Customer fields
    "Total Purchases": "مجموع خریدها",
    "Loyalty Tier": "رده وفاداری",
    "No customers match the current criteria.": "هیچ مشتری با معیارهای فعلی مطابقت ندارد.",
    # Notification preferences
    "Customize how and when you receive notifications": "نحوه و زمان دریافت اعلان‌ها را سفارشی کنید",
    "Back to Notifications": "بازگشت به اعلان‌ها",
    "Notification Types": "انواع اعلان",
    "Choose how you want to receive different types of notifications": "انتخاب کنید که چگونه می‌خواهید انواع مختلف اعلان‌ها را دریافت کنید",
    "Notification Type": "نوع اعلان",
    "Set times when you don't want to receive non-critical notifications": "زمان‌هایی را تنظیم کنید که نمی‌خواهید اعلان‌های غیرحیاتی دریافت کنید",
    "Start Time": "زمان شروع",
    "End Time": "زمان پایان",
    "Save Preferences": "ذخیره ترجیحات",
    # Segmentation
    "Create Customer Segment": "ایجاد بخش مشتری",
    "Segmentation Criteria": "معیارهای بخش‌بندی",
    "Minimum Total Purchases": "حداقل مجموع خریدها",
    "Maximum Total Purchases": "حداکثر مجموع خریدها",
    "Minimum Average Order Value": "حداقل میانگین ارزش سفارش",
    "Maximum Average Order Value": "حداکثر میانگین ارزش سفارش",
    "Minimum Days Since Last Purchase": "حداقل روز از آخرین خرید",
    "Maximum Days Since Last Purchase": "حداکثر روز از آخرین خرید",
    "Minimum Lifetime Value": "حداقل ارزش مادام‌العمر",
    "Maximum Lifetime Value": "حداکثر ارزش مادام‌العمر",
    "Has Made Purchase": "خرید انجام داده",
    "Has Not Made Purchase": "خرید انجام نداده",
    "Include Tags": "شامل برچسب‌ها",
    "Exclude Tags": "بدون برچسب‌ها",
    # More UI strings
    "Calculate Segment": "محاسبه بخش",
    "Segment calculated successfully": "بخش با موفقیت محاسبه شد",
    "Failed to calculate segment": "محاسبه بخش ناموفق بود",
    "customers": "مشتریان",
    "in this segment": "در این بخش",
    "Last calculated": "آخرین محاسبه",
    "Never calculated": "هرگز محاسبه نشده",
    "Recalculate Segment": "محاسبه مجدد بخش",
    "Delete Segment": "حذف بخش",
    "Edit Segment": "ویرایش بخش",
    "Clone Segment": "کلون بخش",
    "Export Segment": "خروجی بخش",
    # Template strings
    "Template": "قالب",
    "Templates": "قالب‌ها",
    "Create Template": "ایجاد قالب",
    "Edit Template": "ویرایش قالب",
    "Delete Template": "حذف قالب",
    "Clone Template": "کلون قالب",
    "Preview Template": "پیش‌نمایش قالب",
    "Test Template": "تست قالب",
    "Send Test": "ارسال تست",
    "Test Email Address": "آدرس ایمیل تست",
    "Test Phone Number": "شماره تلفن تست",
    "Template created successfully": "قالب با موفقیت ایجاد شد",
    "Template updated successfully": "قالب با موفقیت به‌روزرسانی شد",
    "Template deleted successfully": "قالب با موفقیت حذف شد",
    "Test sent successfully": "تست با موفقیت ارسال شد",
    # Notification strings
    "New Order": "سفارش جدید",
    "Order Update": "به‌روزرسانی سفارش",
    "Payment Received": "پرداخت دریافت شد",
    "Low Stock Alert": "هشدار موجودی کم",
    "Customer Message": "پیام مشتری",
    "System Alert": "هشدار سیستم",
    "Security Alert": "هشدار امنیتی",
    "Backup Complete": "پشتیبان تکمیل شد",
    "Backup Failed": "پشتیبان ناموفق بود",
    "Update Available": "به‌روزرسانی موجود است",
    "Maintenance Scheduled": "نگهداری زمان‌بندی شده",
    # Time-related strings
    "minutes": "دقیقه",
    "hours": "ساعت",
    "days": "روز",
    "weeks": "هفته",
    "months": "ماه",
    "years": "سال",
    "second": "ثانیه",
    "seconds": "ثانیه",
    "minute": "دقیقه",
    "hour": "ساعت",
    "day": "روز",
    "week": "هفته",
    "month": "ماه",
    "year": "سال",
    # Action confirmations
    "Are you sure?": "آیا مطمئن هستید؟",
    "This action cannot be undone.": "این عمل قابل بازگشت نیست.",
    "Confirm deletion": "تأیید حذف",
    "Confirm action": "تأیید عمل",
    "Yes, delete": "بله، حذف کن",
    "Yes, continue": "بله، ادامه بده",
    "No, cancel": "نه، لغو کن",
    "Yes": "بله",
    "No": "خیر",
    # Success/Error messages
    "Operation successful": "عملیات موفق",
    "Operation failed": "عملیات ناموفق",
    "Changes saved": "تغییرات ذخیره شد",
    "Changes discarded": "تغییرات لغو شد",
    "Item created": "مورد ایجاد شد",
    "Item updated": "مورد به‌روزرسانی شد",
    "Item deleted": "مورد حذف شد",
    "Items deleted": "موارد حذف شدند",
    "Action completed": "عمل تکمیل شد",
    "Action cancelled": "عمل لغو شد",
    "Request sent": "درخواست ارسال شد",
    "Request received": "درخواست دریافت شد",
    "Request processed": "درخواست پردازش شد",
    "Request failed": "درخواست ناموفق بود",
    # Form validation
    "Required field": "فیلد الزامی",
    "Invalid value": "مقدار نامعتبر",
    "Value too short": "مقدار خیلی کوتاه",
    "Value too long": "مقدار خیلی بلند",
    "Invalid format": "قالب نامعتبر",
    "Invalid date": "تاریخ نامعتبر",
    "Date too early": "تاریخ خیلی زود",
    "Date too late": "تاریخ خیلی دیر",
    "Invalid number": "عدد نامعتبر",
    "Number too small": "عدد خیلی کوچک",
    "Number too large": "عدد خیلی بزرگ",
    "Invalid URL": "آدرس نامعتبر",
    "Invalid phone number": "شماره تلفن نامعتبر",
    "File too large": "فایل خیلی بزرگ",
    "Invalid file type": "نوع فایل نامعتبر",
    "Upload failed": "آپلود ناموفق بود",
    # Pagination and sorting
    "Show": "نمایش",
    "per page": "در هر صفحه",
    "Rows per page": "ردیف در هر صفحه",
    "Page size": "اندازه صفحه",
    "Go to first page": "برو به صفحه اول",
    "Go to last page": "برو به صفحه آخر",
    "Go to previous page": "برو به صفحه قبل",
    "Go to next page": "برو به صفحه بعد",
    "Sort A-Z": "مرتب‌سازی الف-ی",
    "Sort Z-A": "مرتب‌سازی ی-الف",
    "Sort newest first": "مرتب‌سازی جدیدترین",
    "Sort oldest first": "مرتب‌سازی قدیمی‌ترین",
    "Sort by name": "مرتب‌سازی بر اساس نام",
    "Sort by date": "مرتب‌سازی بر اساس تاریخ",
    "Sort by price": "مرتب‌سازی بر اساس قیمت",
    "Sort by popularity": "مرتب‌سازی بر اساس محبوبیت",
}


def update_po_batch(filepath):
    """Apply batch translations."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    translated = 0
    for en, fa in TRANSLATIONS.items():
        esc = re.escape(en)
        pattern = rf'(msgid "{esc}"\nmsgstr ")(")'
        new, count = re.subn(pattern, rf"\1{fa}\2", content)
        if count:
            content = new
            translated += count

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return translated


if __name__ == "__main__":
    po = "locale/fa/LC_MESSAGES/django.po"
    print("Translating batch 4: campaigns, notifications, segments...")
    count = update_po_batch(po)
    print(f"✅ Translated {count} entries")
    print(f"Progress: 459 + {count} = {459 + count} total")
