"""
Number and date formatting utilities for multi-language support.

This module provides utilities for:
- Persian numeral conversion (۰۱۲۳۴۵۶۷۸۹)
- Persian calendar (Jalali) support using jdatetime
- Locale-specific number and date formatting

Per Requirement 2 - Dual-Language Support (English and Persian)
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Union

from django.utils import translation

import jdatetime

# Persian numeral mapping
PERSIAN_NUMERALS = {
    "0": "۰",
    "1": "۱",
    "2": "۲",
    "3": "۳",
    "4": "۴",
    "5": "۵",
    "6": "۶",
    "7": "۷",
    "8": "۸",
    "9": "۹",
}

# Reverse mapping for parsing
ARABIC_NUMERALS = {v: k for k, v in PERSIAN_NUMERALS.items()}


def to_persian_numerals(text: Union[str, int, float, Decimal]) -> str:
    """
    Convert Western numerals (0-9) to Persian numerals (۰-۹).

    Args:
        text: String, integer, float, or Decimal containing Western numerals

    Returns:
        String with Persian numerals

    Examples:
        >>> to_persian_numerals("123")
        '۱۲۳'
        >>> to_persian_numerals(456)
        '۴۵۶'
        >>> to_persian_numerals(12.34)
        '۱۲.۳۴'
    """
    text_str = str(text)
    for western, persian in PERSIAN_NUMERALS.items():
        text_str = text_str.replace(western, persian)
    return text_str


def to_western_numerals(text: str) -> str:
    """
    Convert Persian numerals (۰-۹) to Western numerals (0-9).
    Also converts Persian separators to Western equivalents.

    Args:
        text: String containing Persian numerals

    Returns:
        String with Western numerals

    Examples:
        >>> to_western_numerals("۱۲۳")
        '123'
        >>> to_western_numerals("۱۲.۳۴")
        '12.34'
    """
    # Convert Persian numerals to Western
    for persian, western in ARABIC_NUMERALS.items():
        text = text.replace(persian, western)

    # Convert Persian separators to Western
    text = text.replace("٬", ",")  # Persian thousands separator to comma
    text = text.replace("٫", ".")  # Persian decimal separator to period

    return text


def format_number(
    number: Union[int, float, Decimal],
    decimal_places: Optional[int] = None,
    use_grouping: bool = True,
    locale: Optional[str] = None,
) -> str:
    """
    Format a number according to the current or specified locale.

    Args:
        number: Number to format
        decimal_places: Number of decimal places (None for automatic)
        use_grouping: Whether to use thousand separators
        locale: Locale code ('en' or 'fa'), defaults to current language

    Returns:
        Formatted number string

    Examples:
        >>> format_number(1234567.89, locale='en')
        '1,234,567.89'
        >>> format_number(1234567.89, locale='fa')
        '۱٬۲۳۴٬۵۶۷٫۸۹'
    """
    if locale is None:
        locale = translation.get_language() or "en"

    # Convert to string with appropriate decimal places
    if decimal_places is not None:
        formatted = f"{number:.{decimal_places}f}"
    else:
        formatted = str(number)

    # Split into integer and decimal parts
    if "." in formatted:
        integer_part, decimal_part = formatted.split(".")
    else:
        integer_part = formatted
        decimal_part = None

    # Add thousand separators if requested
    if use_grouping and len(integer_part) > 3:
        # Group digits from right to left
        groups = []
        for i in range(len(integer_part), 0, -3):
            start = max(0, i - 3)
            groups.insert(0, integer_part[start:i])
        integer_part = ",".join(groups)

    # Reconstruct the number
    if decimal_part:
        formatted = f"{integer_part}.{decimal_part}"
    else:
        formatted = integer_part

    # Apply locale-specific formatting
    if locale == "fa":
        # Replace separators with Persian equivalents
        formatted = formatted.replace(",", "٬")  # Persian thousands separator
        formatted = formatted.replace(".", "٫")  # Persian decimal separator
        # Convert to Persian numerals
        formatted = to_persian_numerals(formatted)

    return formatted


def format_currency(
    amount: Union[int, float, Decimal],
    currency: str = "USD",
    locale: Optional[str] = None,
) -> str:
    """
    Format a currency amount according to the current or specified locale.

    Args:
        amount: Amount to format
        currency: Currency code (e.g., 'USD', 'IRR')
        locale: Locale code ('en' or 'fa'), defaults to current language

    Returns:
        Formatted currency string

    Examples:
        >>> format_currency(1234.56, 'USD', locale='en')
        '$1,234.56'
        >>> format_currency(1234567, 'IRR', locale='fa')
        '۱٬۲۳۴٬۵۶۷ ریال'
    """
    if locale is None:
        locale = translation.get_language() or "en"

    # Determine decimal places based on currency
    decimal_places = 2 if currency != "IRR" else 0  # Iranian Rial has no decimals

    # Format the number
    formatted_amount = format_number(amount, decimal_places=decimal_places, locale=locale)

    # Add currency symbol/name
    if locale == "fa":
        currency_names = {
            "USD": "دلار",
            "EUR": "یورو",
            "GBP": "پوند",
            "IRR": "تومان",  # Iranian Toman is the primary currency
            "IRT": "تومان",  # Alias for Iranian Toman
        }
        currency_name = currency_names.get(currency, currency)
        return f"{formatted_amount} {currency_name}"
    else:
        currency_symbols = {
            "USD": "$",
            "EUR": "€",
            "GBP": "£",
            "IRR": "IRR",  # Iranian Rial (official but Toman is used in practice)
            "IRT": "IRT",  # Iranian Toman
        }
        symbol = currency_symbols.get(currency, currency)
        if currency in ["USD", "EUR", "GBP"]:
            return f"{symbol}{formatted_amount}"
        else:
            return f"{formatted_amount} {symbol}"


def to_jalali(gregorian_date: Union[date, datetime]) -> jdatetime.date:
    """
    Convert Gregorian date to Jalali (Persian) calendar.

    Args:
        gregorian_date: Gregorian date or datetime object

    Returns:
        jdatetime.date object representing the Jalali date

    Examples:
        >>> from datetime import date
        >>> gregorian = date(2024, 1, 1)
        >>> jalali = to_jalali(gregorian)
        >>> jalali.year, jalali.month, jalali.day
        (1402, 10, 11)
    """
    if isinstance(gregorian_date, datetime):
        gregorian_date = gregorian_date.date()

    return jdatetime.date.fromgregorian(date=gregorian_date)


def to_gregorian(jalali_date: jdatetime.date) -> date:
    """
    Convert Jalali (Persian) calendar date to Gregorian.

    Args:
        jalali_date: jdatetime.date object

    Returns:
        datetime.date object representing the Gregorian date

    Examples:
        >>> jalali = jdatetime.date(1402, 10, 11)
        >>> gregorian = to_gregorian(jalali)
        >>> gregorian.year, gregorian.month, gregorian.day
        (2024, 1, 1)
    """
    return jalali_date.togregorian()


def format_date(
    date_obj: Union[date, datetime],
    format_string: Optional[str] = None,
    locale: Optional[str] = None,
) -> str:
    """
    Format a date according to the current or specified locale.

    For Persian locale, converts to Jalali calendar and uses Persian numerals.

    Args:
        date_obj: Date or datetime object to format
        format_string: Custom format string (uses locale default if None)
        locale: Locale code ('en' or 'fa'), defaults to current language

    Returns:
        Formatted date string

    Examples:
        >>> from datetime import date
        >>> d = date(2024, 1, 1)
        >>> format_date(d, locale='en')
        'Jan. 1, 2024'
        >>> format_date(d, locale='fa')
        '۱۴۰۲/۱۰/۱۱'
    """
    if locale is None:
        locale = translation.get_language() or "en"

    if isinstance(date_obj, datetime):
        date_obj = date_obj.date()

    if locale == "fa":
        # Convert to Jalali calendar
        jalali_date = to_jalali(date_obj)

        # Use default Persian format if not specified
        if format_string is None:
            format_string = "%Y/%m/%d"

        # Format using jdatetime
        formatted = jalali_date.strftime(format_string)

        # Convert to Persian numerals
        formatted = to_persian_numerals(formatted)

        return formatted
    else:
        # Use standard Python date formatting
        if format_string is None:
            format_string = "%b. %-d, %Y"  # e.g., "Jan. 1, 2024"

        return date_obj.strftime(format_string)


def format_datetime(
    datetime_obj: datetime,
    format_string: Optional[str] = None,
    locale: Optional[str] = None,
) -> str:
    """
    Format a datetime according to the current or specified locale.

    For Persian locale, converts to Jalali calendar and uses Persian numerals.

    Args:
        datetime_obj: Datetime object to format
        format_string: Custom format string (uses locale default if None)
        locale: Locale code ('en' or 'fa'), defaults to current language

    Returns:
        Formatted datetime string

    Examples:
        >>> from datetime import datetime
        >>> dt = datetime(2024, 1, 1, 14, 30)
        >>> format_datetime(dt, locale='en')
        'Jan. 1, 2024, 2:30 p.m.'
        >>> format_datetime(dt, locale='fa')
        '۱۴۰۲/۱۰/۱۱، ۱۴:۳۰'
    """
    if locale is None:
        locale = translation.get_language() or "en"

    if locale == "fa":
        # Convert to Jalali calendar
        jalali_datetime = jdatetime.datetime.fromgregorian(datetime=datetime_obj)

        # Use default Persian format if not specified
        if format_string is None:
            format_string = "%Y/%m/%d، %H:%M"

        # Format using jdatetime
        formatted = jalali_datetime.strftime(format_string)

        # Convert to Persian numerals
        formatted = to_persian_numerals(formatted)

        return formatted
    else:
        # Use standard Python datetime formatting
        if format_string is None:
            format_string = "%b. %-d, %Y, %-I:%M %p"  # e.g., "Jan. 1, 2024, 2:30 PM"

        return datetime_obj.strftime(format_string)


def parse_persian_number(text: str) -> Union[int, float]:
    """
    Parse a number string that may contain Persian numerals and separators.

    Args:
        text: String containing Persian or Western numerals

    Returns:
        Parsed number (int or float)

    Examples:
        >>> parse_persian_number("۱۲۳")
        123
        >>> parse_persian_number("۱۲.۳۴")
        12.34
        >>> parse_persian_number("۱٬۲۳۴٬۵۶۷")
        1234567
    """
    # Convert Persian numerals and separators to Western
    western_text = to_western_numerals(text)

    # Remove thousands separators (both Persian and Western)
    western_text = western_text.replace(",", "")  # Remove Western thousands separator

    # Parse as int or float
    if "." in western_text:
        return float(western_text)
    else:
        return int(western_text)


def get_jalali_month_name(month: int, locale: str = "fa") -> str:
    """
    Get the name of a Jalali calendar month.

    Args:
        month: Month number (1-12)
        locale: Locale code ('en' or 'fa')

    Returns:
        Month name in the specified locale

    Examples:
        >>> get_jalali_month_name(1, 'fa')
        'فروردین'
        >>> get_jalali_month_name(1, 'en')
        'Farvardin'
    """
    if locale == "fa":
        month_names = [
            "فروردین",
            "اردیبهشت",
            "خرداد",
            "تیر",
            "مرداد",
            "شهریور",
            "مهر",
            "آبان",
            "آذر",
            "دی",
            "بهمن",
            "اسفند",
        ]
    else:
        month_names = [
            "Farvardin",
            "Ordibehesht",
            "Khordad",
            "Tir",
            "Mordad",
            "Shahrivar",
            "Mehr",
            "Aban",
            "Azar",
            "Dey",
            "Bahman",
            "Esfand",
        ]

    if 1 <= month <= 12:
        return month_names[month - 1]
    else:
        raise ValueError(f"Invalid month number: {month}. Must be between 1 and 12.")


def get_jalali_weekday_name(weekday: int, locale: str = "fa") -> str:
    """
    Get the name of a weekday in Jalali calendar.

    Args:
        weekday: Weekday number (0=Saturday, 1=Sunday, ..., 6=Friday)
        locale: Locale code ('en' or 'fa')

    Returns:
        Weekday name in the specified locale

    Examples:
        >>> get_jalali_weekday_name(0, 'fa')
        'شنبه'
        >>> get_jalali_weekday_name(0, 'en')
        'Saturday'
    """
    if locale == "fa":
        weekday_names = [
            "شنبه",  # Saturday
            "یکشنبه",  # Sunday
            "دوشنبه",  # Monday
            "سه‌شنبه",  # Tuesday
            "چهارشنبه",  # Wednesday
            "پنج‌شنبه",  # Thursday
            "جمعه",  # Friday
        ]
    else:
        weekday_names = [
            "Saturday",
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
        ]

    if 0 <= weekday <= 6:
        return weekday_names[weekday]
    else:
        raise ValueError(f"Invalid weekday number: {weekday}. Must be between 0 and 6.")
