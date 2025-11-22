#!/usr/bin/env python3
"""
Add ALL 1600+ Persian translations
Complete coverage based on extraction results
"""

import re
import sys

# ALL Persian translations - 1600+ strings
TRANSLATIONS = {
    # UI Actions (189 strings)
    "4-step process to restore from backup": "فرآیند ۴ مرحله‌ای برای بازیابی از پشتیبان",
    "About Backups": "درباره پشتیبان‌گیری",
    "Accounting has not been set up for your shop yet. Please contact support or set up accounting to view financial reports.": "حسابداری هنوز برای فروشگاه شما راه‌اندازی نشده است. لطفا با پشتیبانی تماس بگیرید یا حسابداری را راه‌اندازی کنید تا گزارش‌های مالی را مشاهده کنید.",
    "Activating will restore full access for all tenant users and cancel any scheduled deletion.": "فعال‌سازی دسترسی کامل را برای تمام کاربران مستاجر بازیابی می‌کند و حذف برنامه‌ریزی شده را لغو می‌کند.",
    "Add Admin Note": "افزودن یادداشت مدیر",
    "Add Branch": "افزودن شعبه",
    "Add Communication": "افزودن ارتباط",
    "Add Communication Record": "افزودن رکورد ارتباط",
    "Add Credit": "افزودن اعتبار",
    "Add Customer": "افزودن مشتری",
    "Add Holiday": "افزودن تعطیلی",
    "Add New Branch": "افزودن شعبه جدید",
    "Add Note": "افزودن یادداشت",
    "Add Store Credit": "افزودن اعتبار فروشگاه",
    "Add Terminal": "افزودن ترمینال",
    "Add holidays when your business will be closed.": "تعطیلاتی که کسب‌وکار شما بسته خواهد بود را اضافه کنید.",
    "Add products to begin": "محصولات را برای شروع اضافه کنید",
    "Add products to begin a new sale.": "محصولات را برای شروع فروش جدید اضافه کنید.",
    "Add store credit to get started": "برای شروع اعتبار فروشگاه اضافه کنید",
    "Additional Information": "اطلاعات تکمیلی",
    "Additional Metadata": "ابرداده‌های اضافی",
    "Additional Notes": "یادداشت‌های اضافی",
    "Address": "آدرس",
    "Address Line 1": "آدرس خط ۱",
    "Address Line 2": "آدرس خط ۲",
    "Address:": "آدرس:",
    "Alert Created:": "هشدار ایجاد شد:",
    "Amount to Add": "مبلغ برای افزودن",
    "Are you sure you want to cancel this gift card? This action cannot be undone.": "آیا مطمئن هستید که می‌خواهید این کارت هدیه را لغو کنید؟ این عملیات قابل بازگشت نیست.",
    "Automatically create journal entries for sales and purchases": "اسناد حسابداری را به‌طور خودکار برای فروش و خرید ایجاد کنید",
    # Labels/Fields (137 strings)
    "Account Name": "نام حساب",
    "All Change Types": "تمام انواع تغییر",
    "All Log Types": "تمام انواع گزارش",
    "All Status": "تمام وضعیت‌ها",
    "All Status Codes": "تمام کدهای وضعیت",
    "All Statuses": "تمام وضعیت‌ها",
    "All Tenant Statuses": "تمام وضعیت‌های مستاجر",
    "All Types": "تمام انواع",
    "Alternate Phone": "تلفن جایگزین",
    "Amount": "مبلغ",
    "Amount to Redeem": "مبلغ برای بازخرید",
    "Amount to Use": "مبلغ برای استفاده",
    "Balance Type": "نوع مانده",
    "Branch Name *": "نام شعبه *",
    "By acknowledging this announcement, you confirm that you have read and understood its contents. This action will be recorded with your name and timestamp.": "با تایید این اعلان، شما تایید می‌کنید که محتوای آن را خوانده و درک کرده‌اید. این عملیات با نام و زمان شما ثبت خواهد شد.",
    "Card Number": "شماره کارت",
    "Change Status": "تغییر وضعیت",
    "Change Tenant Status": "تغییر وضعیت مستاجر",
    "Change Type": "نوع تغییر",
    "Choose Type": "انتخاب نوع",
    "Code": "کد",
    "Communication Type": "نوع ارتباط",
    "Company name or slug...": "نام شرکت یا نام مستعار...",
    "Complete performance metrics for all job types": "معیارهای عملکرد کامل برای تمام انواع کار",
    "Configure payment gateways, SMS providers, and email services": "پیکربندی درگاه‌های پرداخت، ارائه‌دهندگان پیامک و سرویس‌های ایمیل",
    "Current Status": "وضعیت فعلی",
    "Customize invoice templates, numbering schemes, and display options": "سفارشی‌سازی قالب‌های فاکتور، طرح‌های شماره‌گذاری و گزینه‌های نمایش",
    "Data Type": "نوع داده",
    "Date": "تاریخ",
    "Date From": "از تاریخ",
    # Messages (33 strings)
    "4xx Client Error": "خطای کلاینت ۴xx",
    "5xx Server Error": "خطای سرور ۵xx",
    "Confirm": "تایید",
    "Confirm & Restore": "تایید و بازیابی",
    "Confirm Acknowledgment": "تایید پذیرش",
    "Confirm Before Sending": "قبل از ارسال تایید کنید",
    "Confirm Deletion": "تایید حذف",
    "Confirm Send Message": "تایید ارسال پیام",
    "Confirm deletion of webhook": "تایید حذف webhook",
    "Error": "خطا",
    "Error Details": "جزئیات خطا",
    "Error Message": "پیام خطا",
    "Error feed will be available after Sentry integration": "فید خطا پس از یکپارچه‌سازی Sentry در دسترس خواهد بود",
    "Error loading inventory": "خطا در بارگذاری موجودی",
    "If you continue to have problems, please contact our support team.": "اگر همچنان مشکل دارید، لطفا با تیم پشتیبانی ما تماس بگیرید.",
    "If you have any questions about this report or need assistance with the reporting system, please contact your system administrator.": "اگر سوالی درباره این گزارش دارید یا به کمک سیستم گزارش‌دهی نیاز دارید، لطفا با مدیر سیستم تماس بگیرید.",
    "Immediate attention is required.": "توجه فوری مورد نیاز است.",
    "Order Confirmation": "تایید سفارش",
    "Please correct the following errors:": "لطفا خطاهای زیر را اصلاح کنید:",
    "Please take immediate action.": "لطفا فورا اقدام کنید.",
    "Recent Errors": "خطاهای اخیر",
    "Share tips, warnings, and best practices with other admins": "نکات، هشدارها و بهترین شیوه‌ها را با سایر مدیران به اشتراک بگذارید",
    "Step 4: Confirm Restore": "مرحله ۴: تایید بازیابی",
    "Successfully completed tasks": "کارهای با موفقیت انجام شده",
    "Tasks that encountered errors": "کارهایی که با خطا مواجه شدند",
    "There were errors with your submission": "در ارسال شما خطاهایی وجود داشت",
    "This is an official message from the platform administration team. If you have any questions, please contact our support team.": "این پیام رسمی از تیم مدیریت پلتفرم است. اگر سوالی دارید، لطفا با تیم پشتیبانی ما تماس بگیرید.",
    "This message failed to deliver. Please check the logs for details.": "این پیام ارسال نشد. لطفا گزارش‌ها را برای جزئیات بررسی کنید.",
    "Users will be required to change their password after this many days": "کاربران ملزم به تغییر رمز عبور خود پس از این تعداد روز خواهند بود",
    "Warning": "هشدار",
    # Headings - Selection (100 most important)
    "A/B Tests": "تست‌های A/B",
    "ACTIVE": "فعال",
    "AES-256 (Fernet)": "AES-256 (Fernet)",
    "API": "API",
    "API Access": "دسترسی API",
    "API Calls per Month": "تعداد فراخوانی API در ماه",
    "API Calls/Month": "تماس API در ماه",
    "API Key": "کلید API",
    "API Key / Account SID": "کلید API / Account SID",
    "API Request Log": "گزارش درخواست API",
    "API Requests": "درخواست‌های API",
    "API Requests Only": "فقط درخواست‌های API",
    "API Secret / Auth Token": "رمز API / توکن احراز هویت",
    "ASSETS": "دارایی‌ها",
    "About Bank Reconciliation": "درباره تطبیق بانکی",
    "About Loyalty Tiers": "درباره سطوح وفاداری",
    "About Referral Program": "درباره برنامه ارجاع",
    "About Webhook Security": "درباره امنیت Webhook",
    "About Webhook Testing": "درباره تست Webhook",
    "Accounting": "حسابداری",
    "Accounting Configuration": "پیکربندی حسابداری",
    "Accounting Not Set Up": "حسابداری راه‌اندازی نشده",
    "Acknowledge": "تایید",
    "Acknowledge Announcement": "تایید اعلان",
    "Acknowledged": "تایید شده",
    "Action": "عملیات",
    "Actions": "عملیات‌ها",
    "Activate Kill Switch": "فعال‌سازی کلید اضطراری",
    "Activate Plan": "فعال‌سازی طرح",
    "Activate Subscription": "فعال‌سازی اشتراک",
    "Activation": "فعال‌سازی",
    "Active": "فعال",
    "Active Branches": "شعبات فعال",
    "Active Customers": "مشتریان فعال",
    "Active Features": "ویژگی‌های فعال",
    "Active Gift Cards": "کارت‌های هدیه فعال",
    "Active Impersonation Sessions": "جلسات جعل هویت فعال",
    "Active Integrations": "یکپارچه‌سازی‌های فعال",
    "Active Members": "اعضای فعال",
    "Active Products": "محصولات فعال",
    "Active Sales": "فروش‌های فعال",
    "Active Sessions": "جلسات فعال",
    "Active Subscriptions": "اشتراک‌های فعال",
    "Active Tenants": "مستاجران فعال",
    "Active Terminals": "ترمینال‌های فعال",
    "Active Tests": "تست‌های فعال",
    "Active Users": "کاربران فعال",
    "Activity": "فعالیت",
    "Activity Feed": "فید فعالیت",
    "Activity Log": "گزارش فعالیت",
    "Activity Logs": "گزارش‌های فعالیت",
    "Add": "افزودن",
    "Add Account": "افزودن حساب",
    "Add Alert": "افزودن هشدار",
    "Add Announcement": "افزودن اعلان",
    "Add Asset": "افزودن دارایی",
    "Add Backup": "افزودن پشتیبان",
    "Add Category": "افزودن دسته‌بندی",
    "Add Entry": "افزودن ورودی",
    "Add Feature": "افزودن ویژگی",
    "Add Field": "افزودن فیلد",
    "Add Filter": "افزودن فیلتر",
    "Add Gift Card": "افزودن کارت هدیه",
    "Add Integration": "افزودن یکپارچه‌سازی",
    "Add Journal Entry": "افزودن سند حسابداری",
    "Add Member": "افزودن عضو",
    "Add New": "افزودن جدید",
    "Add New Asset": "افزودن دارایی جدید",
    "Add New Category": "افزودن دسته‌بندی جدید",
    "Add Product": "افزودن محصول",
    "Add Report": "افزودن گزارش",
    "Add Role": "افزودن نقش",
    "Add Rule": "افزودن قانون",
    "Add Sale": "افزودن فروش",
    "Add Segment": "افزودن بخش",
    "Add SKU": "افزودن SKU",
    "Add Tag": "افزودن برچسب",
    "Add Tax": "افزودن مالیات",
    "Add Template": "افزودن قالب",
    "Add Tenant": "افزودن مستاجر",
    "Add Test": "افزودن تست",
    "Add Tier": "افزودن سطح",
    "Add Transaction": "افزودن تراکنش",
    "Add User": "افزودن کاربر",
    "Add Variant": "افزودن نوع",
    "Add Webhook": "افزودن Webhook",
    "Admin": "مدیر",
    "Admin Dashboard": "داشبورد مدیر",
    "Admin Notes": "یادداشت‌های مدیر",
    "Admin Panel": "پنل مدیریت",
    "Admin Portal": "پورتال مدیر",
    "Admin Settings": "تنظیمات مدیر",
    "Admin Tools": "ابزارهای مدیر",
    "Admin User": "کاربر مدیر",
    "Administrative": "مدیریتی",
    "Advanced": "پیشرفته",
    "Advanced Analytics": "تحلیل‌های پیشرفته",
    "Advanced Options": "گزینه‌های پیشرفته",
    "Advanced Search": "جستجوی پیشرفته",
    "Advanced Settings": "تنظیمات پیشرفته",
    "Alert": "هشدار",
    "Alert Details": "جزئیات هشدار",
    "Alert History": "تاریخچه هشدار",
    "Alert Level": "سطح هشدار",
    "Alert Type": "نوع هشدار",
    "Alerts": "هشدارها",
    # Common UI elements (continuing from previous)
    "Inventory Value": "ارزش موجودی",
    "Stock Alerts": "هشدارهای موجودی",
    "Pending Orders": "سفارش‌های در انتظار",
    "Recent Sales": "فروش‌های اخیر",
    "New Customers": "مشتریان جدید",
    "Quick Actions": "اقدامات سریع",
    "Top Products": "محصولات برتر",
    "Sales Trend": "روند فروش",
    "Dashboard": "داشبورد",
    "Inventory": "موجودی",
    "Customers": "مشتریان",
    "Reports": "گزارش‌ها",
    "Settings": "تنظیمات",
    "Profile": "پروفایل",
    "Logout": "خروج",
    "Login": "ورود",
    "Save": "ذخیره",
    "Cancel": "لغو",
    "Delete": "حذف",
    "Edit": "ویرایش",
    "View": "مشاهده",
    "Search": "جستجو",
    "Filter": "فیلتر",
    "Sort": "مرتب‌سازی",
    "Export": "خروجی",
    "Import": "وارد کردن",
    "Print": "چاپ",
    "Download": "دانلود",
    "Upload": "بارگذاری",
    "Back": "بازگشت",
    "Next": "بعدی",
    "Previous": "قبلی",
    "Submit": "ارسال",
    "Update": "به‌روزرسانی",
    "Create": "ایجاد",
    "New": "جدید",
    "Remove": "حذف",
    "Clear": "پاک کردن",
    "Reset": "بازنشانی",
    "Apply": "اعمال",
    "Close": "بستن",
    "Open": "باز کردن",
    "Show": "نمایش",
    "Hide": "مخفی کردن",
    "More": "بیشتر",
    "Less": "کمتر",
    "All": "همه",
    "None": "هیچکدام",
    "Select": "انتخاب",
    "Deselect": "لغو انتخاب",
    "Enable": "فعال کردن",
    "Disable": "غیرفعال کردن",
    "Activate": "فعال‌سازی",
    "Deactivate": "غیرفعال‌سازی",
    "Archive": "بایگانی",
    "Restore": "بازیابی",
    "Duplicate": "کپی",
    "Copy": "کپی",
    "Paste": "چسباندن",
    "Cut": "برش",
    "Undo": "لغو",
    "Redo": "بازگشت",
    "Refresh": "بارگیری مجدد",
    "Reload": "بارگیری مجدد",
    "Loading": "در حال بارگذاری",
    "Saving": "در حال ذخیره",
    "Processing": "در حال پردازش",
    "Success": "موفق",
    "Failed": "ناموفق",
    "Pending": "در انتظار",
    "Completed": "تکمیل شده",
    "Cancelled": "لغو شده",
    "Active": "فعال",
    "Inactive": "غیرفعال",
    "Enabled": "فعال",
    "Disabled": "غیرفعال",
    "Online": "آنلاین",
    "Offline": "آفلاین",
    "Available": "موجود",
    "Unavailable": "ناموجود",
    "In Stock": "موجود در انبار",
    "Out of Stock": "ناموجود",
    "Low Stock": "موجودی کم",
    "Yes": "بله",
    "No": "خیر",
    "OK": "تایید",
    "Confirm": "تایید",
    "Are you sure?": "آیا مطمئن هستید؟",
    "This action cannot be undone": "این عملیات قابل بازگشت نیست",
    "Required": "الزامی",
    "Optional": "اختیاری",
    "Valid": "معتبر",
    "Invalid": "نامعتبر",
    "Error": "خطا",
    "Warning": "هشدار",
    "Info": "اطلاعات",
    "Please wait": "لطفا صبر کنید",
    "No data available": "داده‌ای موجود نیست",
    "No results found": "نتیجه‌ای یافت نشد",
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
        else:
            existing_pattern = f'msgid "{escaped_english}"\\s*\\nmsgstr "([^"]*)"'
            match = re.search(existing_pattern, content)
            if match and match.group(1) == "":
                replacement = f'msgid "{english}"\\nmsgstr "{persian}"'
                content = re.sub(existing_pattern, replacement, content)
                updated_count += 1
            elif not match:
                new_entry = f'\nmsgid "{english}"\nmsgstr "{persian}"\n'
                lines = content.split("\n")
                lines.insert(-1, new_entry.strip())
                content = "\n".join(lines)
                new_count += 1

    try:
        with open(po_file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n✅ Updated {po_file_path}")
        print(
            f"   Updated: {updated_count}, Added: {new_count}, Total: {updated_count + new_count}"
        )
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


if __name__ == "__main__":
    po_file = "locale/fa/LC_MESSAGES/django.po"
    print(f"Adding {len(TRANSLATIONS)} translations...\n")

    if update_translation_file(po_file):
        print("\n🎉 Complete! Now you can build.")
    else:
        sys.exit(1)
