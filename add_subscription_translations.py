#!/usr/bin/env python
"""
Add Persian translations for subscription feature.
"""

import os

import polib


def add_subscription_translations():
    """Add Persian translations for all subscription-related strings."""

    po_file = "locale/fa/LC_MESSAGES/django.po"

    if not os.path.exists(po_file):
        print(f"Error: {po_file} does not exist")
        return

    po = polib.pofile(po_file)

    # Subscription translations
    translations = {
        # Navigation and general
        "Subscription": "اشتراک",
        "Subscriptions": "اشتراک‌ها",
        "Subscription Dashboard": "داشبورد اشتراک",
        "Subscription Plans": "طرح‌های اشتراک",
        "Subscription Status": "وضعیت اشتراک",
        "Subscription Details": "جزئیات اشتراک",
        "Current Subscription": "اشتراک فعلی",
        "Your Subscription": "اشتراک شما",
        # Plan names and types
        "Free": "رایگان",
        "Basic": "پایه",
        "Professional": "حرفه‌ای",
        "Enterprise": "سازمانی",
        "Starter": "استارتر",
        "Business": "کسب و کار",
        "Premium": "ویژه",
        # Billing periods
        "1 Month": "۱ ماهه",
        "3 Months": "۳ ماهه",
        "6 Months": "۶ ماهه",
        "12 Months": "۱۲ ماهه",
        "1 Year": "۱ ساله",
        "Monthly": "ماهانه",
        "Quarterly": "سه‌ماهه",
        "Semi-Annual": "شش‌ماهه",
        "Annual": "سالانه",
        "Yearly": "سالانه",
        "Billing Period": "دوره صورتحساب",
        "Select Billing Period": "دوره صورتحساب را انتخاب کنید",
        # Pricing and discounts
        "Price": "قیمت",
        "Total Price": "قیمت کل",
        "Original Price": "قیمت اصلی",
        "Discounted Price": "قیمت با تخفیف",
        "Final Price": "قیمت نهایی",
        "Save": "صرفه‌جویی",
        "Discount": "تخفیف",
        "Discounts": "تخفیف‌ها",
        "% off": "% تخفیف",
        "Best Value": "بهترین ارزش",
        "Most Popular": "محبوب‌ترین",
        "Recommended": "پیشنهادی",
        "per month": "در ماه",
        "per year": "در سال",
        "/month": "/ماه",
        "/year": "/سال",
        "Free Trial": "دوره آزمایشی رایگان",
        "No Credit Card Required": "بدون نیاز به کارت اعتباری",
        # Purchase flow
        "Purchase Subscription": "خرید اشتراک",
        "Buy Subscription": "خرید اشتراک",
        "Subscribe Now": "اکنون اشتراک بگیرید",
        "Select Plan": "انتخاب طرح",
        "Choose Plan": "طرح را انتخاب کنید",
        "Continue": "ادامه",
        "Continue to Payment": "ادامه به پرداخت",
        "Review Order": "بررسی سفارش",
        "Confirm Purchase": "تایید خرید",
        "Complete Purchase": "تکمیل خرید",
        "Place Order": "ثبت سفارش",
        "Order Summary": "خلاصه سفارش",
        "Purchase Summary": "خلاصه خرید",
        # Payment
        "Payment": "پرداخت",
        "Payment Method": "روش پرداخت",
        "Select Payment Method": "روش پرداخت را انتخاب کنید",
        "Pay Now": "پرداخت کنید",
        "Process Payment": "پردازش پرداخت",
        "Processing Payment": "در حال پردازش پرداخت",
        "Payment Successful": "پرداخت موفق",
        "Payment Failed": "پرداخت ناموفق",
        "Payment Pending": "پرداخت در انتظار",
        "Payment Cancelled": "پرداخت لغو شد",
        "Payment Processing": "در حال پردازش پرداخت",
        "Payment Gateway": "درگاه پرداخت",
        "Transaction ID": "شناسه تراکنش",
        "Transaction Reference": "مرجع تراکنش",
        "Transaction Date": "تاریخ تراکنش",
        "Transaction Status": "وضعیت تراکنش",
        # Payment methods
        "Credit Card": "کارت اعتباری",
        "Debit Card": "کارت نقدی",
        "Bank Transfer": "انتقال بانکی",
        "Iranian Bank": "بانک ایرانی",
        "Iranian Banks": "بانک‌های ایرانی",
        "PayPal": "پی‌پال",
        "Stripe": "استرایپ",
        "Cryptocurrency": "رمزارز",
        "Crypto": "کریپتو",
        "Bitcoin": "بیت‌کوین",
        "Ethereum": "اتریوم",
        "Coming Soon": "به زودی",
        "Not Available": "در دسترس نیست",
        "Available": "در دسترس",
        # Subscription status
        "Active": "فعال",
        "Inactive": "غیرفعال",
        "Expired": "منقضی شده",
        "Expiring Soon": "به زودی منقضی می‌شود",
        "Cancelled": "لغو شده",
        "Pending": "در انتظار",
        "Trial": "آزمایشی",
        "Grace Period": "مهلت اضافی",
        # Subscription management
        "Manage Subscription": "مدیریت اشتراک",
        "Renew Subscription": "تمدید اشتراک",
        "Renewal": "تمدید",
        "Renew": "تمدید",
        "Renew Now": "اکنون تمدید کنید",
        "Auto-Renewal": "تمدید خودکار",
        "Upgrade Subscription": "ارتقای اشتراک",
        "Upgrade": "ارتقا",
        "Upgrade Now": "اکنون ارتقا دهید",
        "Upgrade to": "ارتقا به",
        "Downgrade": "کاهش رتبه",
        "Cancel Subscription": "لغو اشتراک",
        "Cancel": "لغو",
        "Cancellation": "لغو",
        "Cancel at Period End": "لغو در پایان دوره",
        "Keep Subscription": "حفظ اشتراک",
        # History
        "Purchase History": "تاریخچه خرید",
        "Payment History": "تاریخچه پرداخت",
        "Invoice History": "تاریخچه فاکتور",
        "Invoices": "فاکتورها",
        "Invoice": "فاکتور",
        "Invoice Number": "شماره فاکتور",
        "View Invoice": "مشاهده فاکتور",
        "Download Invoice": "دانلود فاکتور",
        "Receipt": "رسید",
        "View Receipt": "مشاهده رسید",
        "Download Receipt": "دانلود رسید",
        # Dates
        "Start Date": "تاریخ شروع",
        "End Date": "تاریخ پایان",
        "Expiry Date": "تاریخ انقضا",
        "Expires": "منقضی می‌شود",
        "Expires On": "منقضی می‌شود در",
        "Renews On": "تمدید می‌شود در",
        "Next Billing Date": "تاریخ صورتحساب بعدی",
        "Days Remaining": "روز باقی‌مانده",
        "days left": "روز باقی‌مانده",
        "days": "روز",
        # Features
        "Features": "امکانات",
        "Plan Features": "امکانات طرح",
        "Included": "شامل می‌شود",
        "Not Included": "شامل نمی‌شود",
        "Unlimited": "نامحدود",
        "Limited": "محدود",
        "Maximum": "حداکثر",
        "Up to": "تا",
        # Feature descriptions
        "Users": "کاربران",
        "Storage": "فضای ذخیره‌سازی",
        "Branches": "شعب",
        "Products": "محصولات",
        "Transactions": "تراکنش‌ها",
        "Reports": "گزارش‌ها",
        "Support": "پشتیبانی",
        "Priority Support": "پشتیبانی اولویت‌دار",
        "Email Support": "پشتیبانی ایمیل",
        "Phone Support": "پشتیبانی تلفنی",
        "API Access": "دسترسی API",
        "Custom Domain": "دامنه اختصاصی",
        "White Label": "برچسب سفید",
        "Advanced Analytics": "تحلیل پیشرفته",
        "Data Export": "صادرات داده",
        # Messages and alerts
        "Your subscription has expired": "اشتراک شما منقضی شده است",
        "Your subscription will expire soon": "اشتراک شما به زودی منقضی می‌شود",
        "Please renew your subscription": "لطفاً اشتراک خود را تمدید کنید",
        "Subscription renewed successfully": "اشتراک با موفقیت تمدید شد",
        "Subscription upgraded successfully": "اشتراک با موفقیت ارتقا یافت",
        "Subscription cancelled successfully": "اشتراک با موفقیت لغو شد",
        "Purchase completed successfully": "خرید با موفقیت تکمیل شد",
        "Payment successful": "پرداخت موفق",
        "Payment failed. Please try again.": "پرداخت ناموفق. لطفاً دوباره تلاش کنید.",
        "Invalid payment method": "روش پرداخت نامعتبر",
        "An error occurred during payment": "خطایی در هنگام پرداخت رخ داد",
        "Please select a plan": "لطفاً یک طرح انتخاب کنید",
        "Please select a billing period": "لطفاً یک دوره صورتحساب انتخاب کنید",
        "Please select a payment method": "لطفاً یک روش پرداخت انتخاب کنید",
        "No active subscription": "اشتراک فعالی وجود ندارد",
        "You don't have an active subscription": "شما اشتراک فعالی ندارید",
        "Are you sure you want to cancel?": "آیا مطمئن هستید که می‌خواهید لغو کنید؟",
        "This action cannot be undone": "این عمل قابل بازگشت نیست",
        "Contact support for assistance": "برای کمک با پشتیبانی تماس بگیرید",
        # Comparison
        "Compare Plans": "مقایسه طرح‌ها",
        "Plan Comparison": "مقایسه طرح‌ها",
        "Current Plan": "طرح فعلی",
        "New Plan": "طرح جدید",
        "Your Current Plan": "طرح فعلی شما",
        # Misc
        "View Details": "مشاهده جزئیات",
        "View All": "مشاهده همه",
        "Back": "بازگشت",
        "Next": "بعدی",
        "Previous": "قبلی",
        "Step": "مرحله",
        "of": "از",
        "Terms of Service": "شرایط استفاده",
        "Privacy Policy": "سیاست حریم خصوصی",
        "I agree to the terms and conditions": "با شرایط و ضوابط موافقم",
        "Secure Payment": "پرداخت امن",
        "Your payment is secure": "پرداخت شما امن است",
        "SSL Encrypted": "رمزگذاری SSL",
        "Money Back Guarantee": "ضمانت بازگشت وجه",
        "Contact Us": "تماس با ما",
        "Need Help?": "کمک نیاز دارید؟",
        "FAQ": "سوالات متداول",
        "Select": "انتخاب",
        "Selected": "انتخاب شده",
        "Get Started": "شروع کنید",
    }

    existing_msgids = {entry.msgid for entry in po}
    added_count = 0

    for msgid, msgstr in translations.items():
        if msgid not in existing_msgids:
            entry = polib.POEntry(
                msgid=msgid,
                msgstr=msgstr,
            )
            po.append(entry)
            added_count += 1
            print(f"Added: {msgid} -> {msgstr}")
        else:
            # Update existing entry if empty
            for entry in po:
                if entry.msgid == msgid and not entry.msgstr:
                    entry.msgstr = msgstr
                    added_count += 1
                    print(f"Updated: {msgid} -> {msgstr}")
                    break

    po.save()
    print(f"\nTotal: Added/Updated {added_count} translations")
    print(f"Saved to {po_file}")


if __name__ == "__main__":
    add_subscription_translations()
