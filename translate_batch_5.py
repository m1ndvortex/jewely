#!/usr/bin/env python3
"""
Translate customer segments, price calculator, gold rates, and jewelry-specific terms
"""

TRANSLATIONS = {
    # Customer segment criteria
    "Last Purchase Within (Days)": "آخرین خرید در (روز)",
    "Loyalty Tiers": "سطوح وفاداری",
    "Customer Tags (comma-separated)": "برچسب‌های مشتری (جدا شده با کاما)",
    "Communication Preferences": "ترجیحات ارتباط",
    "Marketing Opt-in": "موافقت با بازاریابی",
    "SMS Opt-in": "موافقت با پیامک",
    "Select Customers": "انتخاب مشتریان",
    "For static segments, manually select customers to include.": "برای بخش‌های ثابت، مشتریان را به صورت دستی انتخاب کنید.",
    "Preview Customers": "پیش‌نمایش مشتریان",
    "Click 'Preview Customers' to see who would be included in this segment.": "روی 'پیش‌نمایش مشتریان' کلیک کنید تا ببینید چه کسانی در این بخش شامل می‌شوند.",
    # Price Calculator
    "Calculate Price": "محاسبه قیمت",
    "Back to Dashboard": "بازگشت به داشبورد",
    "Price Calculator": "ماشین‌حساب قیمت",
    "Current Gold Rate": "نرخ فعلی طلا",
    "Karat": "عیار",
    "Weight (grams)": "وزن (گرم)",
    "Product Type": "نوع محصول",
    "Any Type": "هر نوع",
    "Craftsmanship Level": "سطح صنعتگری",
    "Any Level": "هر سطح",
    "Customer Tier": "رده مشتری",
    "Stone Value": "ارزش سنگ",
    # Pricing Dashboard
    "Active Pricing Rules": "قوانین قیمت‌گذاری فعال",
    "No active pricing rules found. Please configure pricing rules first.": "قانون قیمت‌گذاری فعالی یافت نشد. لطفاً ابتدا قوانین قیمت‌گذاری را پیکربندی کنید.",
    "Pricing Dashboard": "داشبورد قیمت‌گذاری",
    "Recalculate Prices": "محاسبه مجدد قیمت‌ها",
    "Rules configured": "قوانین پیکربندی شده",
    "Pending Overrides": "نادیده‌گیری‌های در انتظار",
    "Awaiting approval": "در انتظار تأیید",
    "Recent Price Changes": "تغییرات اخیر قیمت",
    "View all changes": "مشاهده تمام تغییرات",
    "No recent price changes": "تغییر قیمت اخیری وجود ندارد",
    # Override Requests
    "Pending Override Requests": "درخواست‌های نادیده‌گیری در انتظار",
    "Requested by": "درخواست شده توسط",
    "View all requests": "مشاهده تمام درخواست‌ها",
    "No pending override requests": "درخواست نادیده‌گیری در انتظار وجود ندارد",
    # Customer tiers
    "Retail": "خرده‌فروشی",
    "Wholesale": "عمده‌فروشی",
    "VIP": "وی‌آی‌پی",
    # Gold Rate Comparison
    "Gold Rate Comparison": "مقایسه نرخ طلا",
    "View History": "مشاهده تاریخچه",
    "Highest": "بالاترین",
    "Same as base": "همانند پایه",
    "Per Tola": "به ازای تولا",
    "Per Ounce": "به ازای اونس",
    "Updated": "به‌روزرسانی شده",
    "Source": "منبع",
    "Detailed Comparison": "مقایسه دقیق",
    "All rates compared to": "تمام نرخ‌ها در مقایسه با",
    "market": "بازار",
    "Market": "بازار",
    "Per Gram": "به ازای گرم",
    "Difference": "تفاوت",
    "Base": "پایه",
    "Same": "یکسان",
    "Refresh Rates": "تازه‌سازی نرخ‌ها",
    "No Rate Data Available": "داده نرخی موجود نیست",
    "No gold rate data is currently available for comparison.": "در حال حاضر داده نرخ طلایی برای مقایسه موجود نیست.",
    "Gold Rate History": "تاریخچه نرخ طلا",
    "Compare Markets": "مقایسه بازارها",
    # Jewelry-specific terms
    "Gold": "طلا",
    "Silver": "نقره",
    "Platinum": "پلاتین",
    "Diamond": "الماس",
    "Ring": "انگشتر",
    "Necklace": "گردنبند",
    "Bracelet": "دستبند",
    "Earrings": "گوشواره",
    "Pendant": "آویز",
    "Chain": "زنجیر",
    "Bangle": "النگو",
    "Anklet": "پابند",
    "Brooch": "سنجاق سینه",
    "Cufflinks": "دکمه سردست",
    "Tiara": "تاج",
    "Crown": "تاج سلطنتی",
    # Karat values
    "24 Karat": "24 عیار",
    "22 Karat": "22 عیار",
    "21 Karat": "21 عیار",
    "18 Karat": "18 عیار",
    "14 Karat": "14 عیار",
    "10 Karat": "10 عیار",
    # Craftsmanship levels
    "Basic": "پایه",
    "Standard": "استاندارد",
    "Premium": "ممتاز",
    "Luxury": "لوکس",
    "Handcrafted": "دست‌ساز",
    "Machine Made": "ماشینی",
    "Designer": "طراح",
    "Antique": "عتیقه",
    "Modern": "مدرن",
    "Traditional": "سنتی",
    "Contemporary": "معاصر",
    "Vintage": "وینتیج",
    "Custom": "سفارشی",
    # Gemstones
    "Ruby": "یاقوت",
    "Sapphire": "یاقوت کبود",
    "Emerald": "زمرد",
    "Pearl": "مروارید",
    "Topaz": "توپاز",
    "Amethyst": "آمتیست",
    "Garnet": "گارنت",
    "Opal": "اوپال",
    "Turquoise": "فیروزه",
    "Jade": "یشم",
    "Aquamarine": "آکوامارین",
    "Citrine": "سیترین",
    # More jewelry terms
    "Carat Weight": "وزن قیراط",
    "Clarity": "خلوص",
    "Cut": "برش",
    "Color Grade": "درجه رنگ",
    "Setting": "نگین‌کاری",
    "Prong Setting": "نگین‌کاری چنگکی",
    "Bezel Setting": "نگین‌کاری قابی",
    "Pave Setting": "نگین‌کاری پاوه",
    "Channel Setting": "نگین‌کاری کانالی",
    "Polish": "جلا",
    "Finish": "پرداخت",
    "Hallmark": "مهر اصالت",
    "Certificate": "گواهی",
    "Appraisal": "ارزیابی",
    "Warranty": "گارانتی",
    "Authenticity": "اصالت",
    # Pricing terms
    "Base Price": "قیمت پایه",
    "Making Charges": "هزینه ساخت",
    "Stone Charges": "هزینه سنگ",
    "GST": "مالیات",
    "Discount": "تخفیف",
    "Final Price": "قیمت نهایی",
    "Market Price": "قیمت بازار",
    "Selling Price": "قیمت فروش",
    "Purchase Price": "قیمت خرید",
    "Margin": "حاشیه سود",
    "Markup": "افزایش قیمت",
    # Inventory terms
    "Stock Keeping Unit": "واحد نگهداری موجودی",
    "Available Stock": "موجودی موجود",
    "Reserved Stock": "موجودی رزرو شده",
    "Minimum Stock": "حداقل موجودی",
    "Maximum Stock": "حداکثر موجودی",
    "Reorder Level": "سطح سفارش مجدد",
    "Lead Time": "زمان تحویل",
    "Supplier": "تأمین‌کننده",
    "Vendor Code": "کد فروشنده",
    "Purchase Order": "سفارش خرید",
    "Received": "دریافت شده",
    "Pending Receipt": "در انتظار دریافت",
    "Quality Check": "کنترل کیفیت",
    "Approved": "تأیید شده",
    "Rejected": "رد شده",
    # Sales terms
    "Gross Sales": "فروش ناخالص",
    "Net Sales": "فروش خالص",
    "Sales Tax": "مالیات فروش",
    "Commission": "کمیسیون",
    "Exchange": "تعویض",
    "Return": "بازگشت",
    "Store Credit": "اعتبار فروشگاه",
    "Layaway": "پرداخت قسطی",
    "Down Payment": "پیش‌پرداخت",
    "Installment": "قسط",
    "Balance Due": "مانده بدهی",
    "Paid in Full": "پرداخت کامل",
    # Customer service
    "Repair": "تعمیر",
    "Resize": "تغییر سایز",
    "Polish and Clean": "جلا و تمیز کردن",
    "Engraving": "حکاکی",
    "Appraisal Service": "خدمات ارزیابی",
    "Buyback": "خرید مجدد",
    "Trade-in": "معاوضه",
    "Gift Wrap": "بسته‌بندی هدیه",
    "Gift Card": "کارت هدیه",
    "Personalization": "شخصی‌سازی",
}


def update_po_batch(filepath):
    """Apply batch translations."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    translated = 0
    for en, fa in TRANSLATIONS.items():
        # Use simple string replacement for exact matches
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
    print("Translating batch 5: jewelry terms, pricing, gold rates...")
    count = update_po_batch(po)
    print(f"✅ Translated {count} entries")
    print(f"Progress: 520 + {count} = {520 + count} total")
