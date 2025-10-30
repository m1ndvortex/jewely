#!/usr/bin/env python3
"""
Add Persian translations to the django.po file.
This script updates msgstr values with Persian translations.
"""

import re

# Comprehensive Persian translations dictionary
TRANSLATIONS = {
    # Navigation and UI
    "Platform Admin": "مدیریت پلتفرم",
    "Jewelry Shop": "فروشگاه جواهرات",
    "Dashboard": "داشبورد",
    "Tenants": "مستأجران",
    "Subscriptions": "اشتراک‌ها",
    "Monitoring": "نظارت",
    "Audit Logs": "گزارش‌های حسابرسی",
    "More": "بیشتر",
    "POS": "صندوق فروش",
    "Customers": "مشتریان",
    "Accounting": "حسابداری",
    "Repairs": "تعمیرات",
    "Procurement": "خریداری",
    "Branches": "شعب",
    "Reports": "گزارش‌ها",
    "Settings": "تنظیمات",
    "Backups": "پشتیبان‌ها",
    "Security": "امنیت",
    "Feature Flags": "پرچم‌های ویژگی",
    "Announcements": "اعلانیه‌ها",
    
    # User Menu
    "Notifications": "اعلان‌ها",
    "Notification Settings": "تنظیمات اعلان",
    "Profile": "پروفایل",
    "Sign out": "خروج",
    "View notifications": "مشاهده اعلان‌ها",
    "Open user menu": "باز کردن منوی کاربر",
    
    # Impersonation
    "Stop Impersonating": "توقف انتحال هویت",
    "You are viewing this account as a platform administrator. All actions are logged.": "شما این حساب را به عنوان مدیر پلتفرم مشاهده می‌کنید. تمام اقدامات ثبت می‌شود.",
    
    # Admin Dashboard
    "Admin Dashboard - Platform Management": "داشبورد مدیریت - مدیریت پلتفرم",
    "Platform Admin Dashboard": "داشبورد مدیریت پلتفرم",
    "Monitor platform health, tenant metrics, and system performance": "نظارت بر سلامت پلتفرم، معیارهای مستأجران و عملکرد سیستم",
    "Quick Actions": "اقدامات سریع",
    "Manage Tenants": "مدیریت مستأجران",
    "View and manage all tenants": "مشاهده و مدیریت تمام مستأجران",
    "Create Tenant": "ایجاد مستأجر",
    "Add a new tenant account": "افزودن حساب مستأجر جدید",
    "Coming in Task 20": "در وظیفه 20 می‌آید",
    
    # Tenant Metrics
    "Tenant Metrics": "معیارهای مستأجر",
    "Total Tenants": "مجموع مستأجران",
    "Active Tenants": "مستأجران فعال",
    "Suspended": "معلق شده",
    "Pending Deletion": "در انتظار حذف",
    "Requires attention": "نیاز به توجه دارد",
    "Scheduled for removal": "برنامه‌ریزی شده برای حذف",
    
    # Revenue Metrics
    "Revenue Metrics": "معیارهای درآمد",
    "Monthly Recurring Revenue (MRR)": "درآمد متکرر ماهانه (MRR)",
    
    # Tenant Dashboard
    "Dashboard - Jewelry Shop": "داشبورد - فروشگاه جواهرات",
    "Welcome back! Here's what's happening with your jewelry shop today.": "خوش آمدید! این اتفاقات امروز در فروشگاه جواهرات شماست.",
    "Refresh": "بارگیری مجدد",
    "Today's Sales": "فروش امروز",
    "Increased": "افزایش یافت",
    "Decreased": "کاهش یافت",
    "by": "به میزان",
    
    # Count translations
    "%(count)s new in last 30 days": "%(count)s مورد جدید در 30 روز گذشته",
    "%(count)s new today": "%(count)s مورد جدید امروز",
    
    # Status and messages
    "Completed": "تکمیل شد",
    "Pending": "در انتظار",
    "Cancelled": "لغو شد",
    "This field is required.": "این فیلد الزامی است.",
    "Please enter a valid email address.": "لطفاً یک آدرس ایمیل معتبر وارد کنید.",
    "Please enter a valid phone number.": "لطفاً یک شماره تلفن معتبر وارد کنید.",
    "Insufficient stock available.": "موجودی کافی نیست.",
    "Invalid username or password.": "نام کاربری یا رمز عبور نامعتبر است.",
    "You do not have permission to perform this action.": "شما اجازه انجام این عمل را ندارید.",
    "The requested item was not found.": "مورد درخواستی یافت نشد.",
    "An item with this information already exists.": "موردی با این اطلاعات قبلاً وجود دارد.",
    "Item created successfully.": "مورد با موفقیت ایجاد شد.",
    "Item updated successfully.": "مورد با موفقیت به‌روزرسانی شد.",
    "Item deleted successfully.": "مورد با موفقیت حذف شد.",
    "Sale completed successfully.": "فروش با موفقیت تکمیل شد.",
    "Customer added successfully.": "مشتری با موفقیت اضافه شد.",
    "Email sent successfully.": "ایمیل با موفقیت ارسال شد.",
    "Settings saved successfully.": "تنظیمات با موفقیت ذخیره شد.",
    
    # Confirmation messages
    "Are you sure you want to delete this item?": "آیا مطمئن هستید که می‌خواهید این مورد را حذف کنید؟",
    "Are you sure you want to delete this customer?": "آیا مطمئن هستید که می‌خواهید این مشتری را حذف کنید؟",
    "Are you sure you want to cancel this sale?": "آیا مطمئن هستید که می‌خواهید این فروش را لغو کنید؟",
    "Are you sure you want to log out?": "آیا مطمئن هستید که می‌خواهید خارج شوید؟",
    
    # Login/Auth
    "Platform Admin Login": "ورود مدیر پلتفرم",
    "Please use your admin credentials to access this area.": "لطفاً از اعتبارنامه مدیریتی خود برای دسترسی به این بخش استفاده کنید.",
    "Username and password are required.": "نام کاربری و رمز عبور الزامی است.",
    "Access denied. This login is for platform administrators only.": "دسترسی رد شد. این ورود فقط برای مدیران پلتفرم است.",
    "This account has been disabled.": "این حساب غیرفعال شده است.",
    "Invalid username or password. Please try again.": "نام کاربری یا رمز عبور نامعتبر است. لطفاً دوباره تلاش کنید.",
    "You have been successfully logged out.": "شما با موفقیت خارج شدید.",
    
    # Common
    "Welcome back, %(name)s!": "خوش آمدید، %(name)s!",
    "%(start)s to %(end)s": "%(start)s تا %(end)s",
    "%(amount)s %(currency)s": "%(amount)s %(currency)s",
}

def update_po_file(filepath):
    """Update the .po file with Persian translations."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Track translations
    translated_count = 0
    
    for english, persian in TRANSLATIONS.items():
        # Escape special characters for regex
        escaped_english = re.escape(english)
        
        # Pattern to match msgid followed by empty msgstr
        # This handles both simple strings and those with variables
        pattern = rf'(msgid "{escaped_english}"\nmsgstr ")(")'
        
        # Replace empty msgstr with Persian translation
        new_content, count = re.subn(pattern, rf'\1{persian}\2', content)
        
        if count > 0:
            content = new_content
            translated_count += count
            print(f"✓ Translated: {english[:50]}...")
    
    # Write updated content
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n✅ Total translations added: {translated_count}")
    return translated_count

if __name__ == '__main__':
    po_file = 'locale/fa/LC_MESSAGES/django.po'
    print(f"Updating {po_file} with Persian translations...\n")
    update_po_file(po_file)
    print("\n✅ Translation file updated successfully!")
    print("Next step: Run 'python manage.py compilemessages' to compile the translations")
