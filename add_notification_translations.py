#!/usr/bin/env python3
"""
Add Persian translations for notification and email template related strings.
This targets the untranslated strings discovered earlier (notification/email/template help text).
"""
import re

TRANSLATIONS = {
    "Welcome back, {}!": "خوش آمدید!",
    "Basic Information": "اطلاعات پایه",
    "Action": "عمل",
    "Timestamps": "نشانه‌های زمانی",
    "Basic Settings": "تنظیمات پایه",
    "Quiet Hours": "ساعات سکوت",
    "Templates": "قالب‌ها",
    "Action Templates": "قالب‌های عمل",
    "Use Django template syntax. Available variables depend on context.": "از سینتکس قالب جنگو استفاده کنید. متغیرهای در دسترس به زمینه بستگی دارد.",
    "Email Details": "جزئیات ایمیل",
    "Status & Tracking": "وضعیت و ردیابی",
    "Scheduling": "زمان‌بندی",
    "Template Details": "جزئیات قالب",
    "Email Content": "محتوای ایمیل",
    "Campaign Details": "جزئیات کمپین",
    "Targeting": "هدف‌گیری",
    "Statistics": "آمار",
    "Delivery Rate": "نرخ تحویل",
    "Open Rate": "نرخ باز شدن",
    "SMS Details": "جزئیات پیامک",
    "Delivery Status": "وضعیت تحویل",
    "Campaign & Cost": "کمپین و هزینه",
    "Message Content": "محتوای پیام",
    "Length": "طول",
    "User": "کاربر",
    "Opt-out Preferences": "ترجیحات انصراف",
    "Information": "اطلاعات",
    "Warning": "هشدار",
    "Low Stock Alert": "هشدار کمبود موجودی",
    "Payment Reminder": "یادآوری پرداخت",
    "Order Status Update": "به‌روزرسانی وضعیت سفارش",
    "System Notification": "اعلان سیستمی",
    "Promotion": "تبلیغ",
    "Appointment Reminder": "یادآوری قرار ملاقات",
    "Transactional Email": "ایمیل تراکنشی",
    "Marketing Email": "ایمیل بازاریابی",
    "User who will receive this notification": "کاربری که این اعلان را دریافت خواهد کرد",
    "Notification title/subject": "عنوان/موضوع اعلان",
    "Notification message content": "محتوای پیام اعلان",
    "Type of notification for styling and filtering": "نوع اعلان برای استایل‌دهی و فیلتر",
    "Whether the user has read this notification": "آیا کاربر این اعلان را خوانده است",
    "When the notification was created": "زمان ایجاد اعلان",
    "When the notification was marked as read": "زمان علامت‌گذاری به عنوان خوانده شده",
    "URL to navigate to when notification is clicked": "آدرس برای هدایت هنگام کلیک بر روی اعلان",
    "When this notification expires and should be hidden": "زمانی که این اعلان منقضی می‌شود و باید پنهان شود",
    "Notification": "اعلان",
    "In-App Notification": "اعلان درون برنامه‌ای",
    "SMS": "پیامک",
    "Push Notification": "اعلان فشار",
    "User these preferences belong to": "این ترجیحات متعلق به چه کاربری است",
    "Type of notification this preference applies to": "نوع اعلان که این ترجیح برای آن اعمال می‌شود",
    "Notification delivery channel": "کانال تحویل اعلان",
    "Whether this notification type is enabled for this channel": "آیا این نوع اعلان برای این کانال فعال است",
    "When this preference was created": "زمان ایجاد این ترجیح",
    "When this preference was last updated": "آخرین زمان به‌روزرسانی این ترجیح",
    "Start of quiet hours (no notifications sent)": "شروع ساعات سکوت (ارسال اعلان انجام نمی‌شود)",
    "End of quiet hours": "پایان ساعات سکوت",
    "Notification Preference": "ترجیح اعلان",
    "Notification Preferences": "ترجیحات اعلان",
    "Unique name for this template": "نام یکتا برای این قالب",
    "Type of notification this template is for": "نوع اعلان که این قالب برای آن است",
    "Template for notification title (supports Django template syntax)": "قالب عنوان اعلان (پشتیبانی از سینتکس قالب جنگو)",
    "Template for notification message (supports Django template syntax)": "قالب پیام اعلان (پشتیبانی از سینتکس قالب جنگو)",
    "Template for action button text": "قالب متن دکمه عمل",
    "Template for action URL": "قالب آدرس دکمه عمل",
    "Whether this template is active and can be used": "آیا این قالب فعال است و می‌توان از آن استفاده کرد",
    "When this template was created": "زمان ایجاد این قالب",
    "When this template was last updated": "آخرین زمان به‌روزرسانی این قالب",
    "Notification Template": "قالب اعلان",
    "Notification Templates": "قالب‌های اعلان",
    "Sent": "ارسال شد",
    "Bounced": "برگشتی",
    "Opened": "باز شده",
    "Clicked": "کلیک شده",
    "Complained": "شاکی",
    "Unsubscribed": "لغو اشتراک شده",
    "Transactional": "تراکنشی",
    "Marketing": "بازاریابی",
    "System": "سیستم",
    "User who received this email": "کاربری که این ایمیل را دریافت کرد",
    "Associated in-app notification": "اعلان درون برنامه‌ای مرتبط",
    "Email subject": "موضوع ایمیل",
    "Recipient email address": "آدرس ایمیل گیرنده",
    "Sender email address": "آدرس ایمیل فرستنده",
    "Email template used": "قالب ایمیل استفاده شده",
    "Type of email": "نوع ایمیل",
    "Current delivery status": "وضعیت فعلی تحویل",
    "Email service provider message ID": "شناسه پیام ارائه‌دهنده سرویس ایمیل",
    "Error message if delivery failed": "پیام خطا در صورت شکست تحویل",
    "Reason for bounce if applicable": "دلیل برگشت در صورت وجود",
    "When to send this email (for scheduled emails)": "زمان ارسال این ایمیل (برای ایمیل‌های زمان‌بندی شده)",
    "Campaign ID for marketing emails": "شناسه کمپین برای ایمیل‌های بازاریابی",
    "Email Notification": "اعلان ایمیلی",
    "Email Notifications": "اعلان‌های ایمیلی",
    "Unique name for this email template": "نام یکتا برای این قالب ایمیل",
    "Template for email subject (supports Django template syntax)": "قالب موضوع ایمیل (پشتیبانی از سینتکس قالب جنگو)",
    "HTML template for email body": "قالب HTML برای بدنه ایمیل",
    "Plain text template for email body (optional)": "قالب متن معمولی برای بدنه ایمیل (اختیاری)",
    "Type of email this template is for": "نوع ایمیلی که این قالب برای آن است",
    "Email Template": "قالب ایمیل",
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
            print(f"Translated: {en}")

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"Done. Translated {translated} entries.")

if __name__ == '__main__':
    po = 'locale/fa/LC_MESSAGES/django.po'
    print('Updating', po)
    update_po(po)
    print('Run compilemessages and restart the web service afterwards.')
