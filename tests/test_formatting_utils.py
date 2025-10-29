"""
Tests for number and date formatting utilities.

Per Requirement 2 - Dual-Language Support (English and Persian)
Tests cover:
- Persian numeral conversion
- Number formatting with locale support
- Currency formatting
- Jalali calendar conversion
- Date and datetime formatting
"""

from datetime import date, datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import translation

import jdatetime
import pytest

from apps.core.formatting_utils import (
    format_currency,
    format_date,
    format_datetime,
    format_number,
    get_jalali_month_name,
    get_jalali_weekday_name,
    parse_persian_number,
    to_gregorian,
    to_jalali,
    to_persian_numerals,
    to_western_numerals,
)


class TestPersianNumeralConversion(TestCase):
    """Test Persian numeral conversion utilities."""

    def test_to_persian_numerals_string(self):
        """Test converting string with Western numerals to Persian."""
        assert to_persian_numerals("123") == "۱۲۳"
        assert to_persian_numerals("0123456789") == "۰۱۲۳۴۵۶۷۸۹"
        assert to_persian_numerals("Price: 1234.56") == "Price: ۱۲۳۴.۵۶"

    def test_to_persian_numerals_integer(self):
        """Test converting integer to Persian numerals."""
        assert to_persian_numerals(123) == "۱۲۳"
        assert to_persian_numerals(0) == "۰"
        assert to_persian_numerals(999) == "۹۹۹"

    def test_to_persian_numerals_float(self):
        """Test converting float to Persian numerals."""
        assert to_persian_numerals(12.34) == "۱۲.۳۴"
        assert to_persian_numerals(0.5) == "۰.۵"

    def test_to_persian_numerals_decimal(self):
        """Test converting Decimal to Persian numerals."""
        assert to_persian_numerals(Decimal("123.45")) == "۱۲۳.۴۵"

    def test_to_western_numerals(self):
        """Test converting Persian numerals to Western."""
        assert to_western_numerals("۱۲۳") == "123"
        assert to_western_numerals("۰۱۲۳۴۵۶۷۸۹") == "0123456789"
        assert to_western_numerals("قیمت: ۱۲۳۴٫۵۶") == "قیمت: 1234.56"

    def test_roundtrip_conversion(self):
        """Test that conversion is reversible."""
        original = "123456789"
        persian = to_persian_numerals(original)
        western = to_western_numerals(persian)
        assert western == original


class TestNumberFormatting(TestCase):
    """Test number formatting with locale support."""

    def test_format_number_english(self):
        """Test number formatting in English locale."""
        with translation.override("en"):
            assert format_number(1234567.89) == "1,234,567.89"
            assert format_number(1234567) == "1,234,567"
            assert format_number(123) == "123"

    def test_format_number_persian(self):
        """Test number formatting in Persian locale."""
        with translation.override("fa"):
            result = format_number(1234567.89)
            assert "۱" in result
            assert "٬" in result  # Persian thousands separator
            assert "٫" in result  # Persian decimal separator

    def test_format_number_decimal_places(self):
        """Test number formatting with specific decimal places."""
        with translation.override("en"):
            assert format_number(1234.5, decimal_places=2) == "1,234.50"
            assert format_number(1234.567, decimal_places=1) == "1,234.6"
            assert format_number(1234, decimal_places=0) == "1,234"

    def test_format_number_no_grouping(self):
        """Test number formatting without thousand separators."""
        with translation.override("en"):
            assert format_number(1234567, use_grouping=False) == "1234567"

    def test_format_number_zero(self):
        """Test formatting zero."""
        with translation.override("en"):
            assert format_number(0) == "0"
        with translation.override("fa"):
            assert format_number(0) == "۰"

    def test_format_number_negative(self):
        """Test formatting negative numbers."""
        with translation.override("en"):
            assert format_number(-1234.56) == "-1,234.56"


class TestCurrencyFormatting(TestCase):
    """Test currency formatting with locale support."""

    def test_format_currency_usd_english(self):
        """Test USD formatting in English."""
        with translation.override("en"):
            assert format_currency(1234.56, "USD") == "$1,234.56"

    def test_format_currency_usd_persian(self):
        """Test USD formatting in Persian."""
        with translation.override("fa"):
            result = format_currency(1234.56, "USD")
            assert "دلار" in result
            assert "۱" in result

    def test_format_currency_irr_english(self):
        """Test IRR formatting in English (no decimals)."""
        with translation.override("en"):
            assert format_currency(1234567, "IRR") == "1,234,567 IRR"

    def test_format_currency_irr_persian(self):
        """Test IRR formatting in Persian (displays as Toman)."""
        with translation.override("fa"):
            result = format_currency(1234567, "IRR")
            assert "تومان" in result
            assert "۱" in result

    def test_format_currency_eur(self):
        """Test EUR formatting."""
        with translation.override("en"):
            assert format_currency(1234.56, "EUR") == "€1,234.56"

    def test_format_currency_gbp(self):
        """Test GBP formatting."""
        with translation.override("en"):
            assert format_currency(1234.56, "GBP") == "£1,234.56"


class TestJalaliCalendarConversion(TestCase):
    """Test Jalali (Persian) calendar conversion."""

    def test_to_jalali_basic(self):
        """Test basic Gregorian to Jalali conversion."""
        gregorian = date(2024, 1, 1)
        jalali = to_jalali(gregorian)
        assert isinstance(jalali, jdatetime.date)
        assert jalali.year == 1402
        assert jalali.month == 10
        assert jalali.day == 11

    def test_to_jalali_from_datetime(self):
        """Test conversion from datetime object."""
        gregorian_dt = datetime(2024, 1, 1, 12, 30)
        jalali = to_jalali(gregorian_dt)
        assert isinstance(jalali, jdatetime.date)
        assert jalali.year == 1402

    def test_to_gregorian_basic(self):
        """Test basic Jalali to Gregorian conversion."""
        jalali = jdatetime.date(1402, 10, 11)
        gregorian = to_gregorian(jalali)
        assert isinstance(gregorian, date)
        assert gregorian.year == 2024
        assert gregorian.month == 1
        assert gregorian.day == 1

    def test_roundtrip_calendar_conversion(self):
        """Test that calendar conversion is reversible."""
        original = date(2024, 3, 20)  # Persian New Year
        jalali = to_jalali(original)
        gregorian = to_gregorian(jalali)
        assert gregorian == original

    def test_jalali_new_year(self):
        """Test conversion of Persian New Year (Nowruz)."""
        # March 20, 2024 is Farvardin 1, 1403
        gregorian = date(2024, 3, 20)
        jalali = to_jalali(gregorian)
        assert jalali.year == 1403
        assert jalali.month == 1
        assert jalali.day == 1


class TestDateFormatting(TestCase):
    """Test date formatting with locale support."""

    def test_format_date_english_default(self):
        """Test default date formatting in English."""
        test_date = date(2024, 1, 15)
        with translation.override("en"):
            result = format_date(test_date)
            assert "2024" in result
            assert "Jan" in result or "15" in result

    def test_format_date_persian_default(self):
        """Test default date formatting in Persian (Jalali calendar)."""
        test_date = date(2024, 1, 15)
        with translation.override("fa"):
            result = format_date(test_date)
            # Should contain Persian numerals
            assert any(char in result for char in "۰۱۲۳۴۵۶۷۸۹")
            # Should be in Jalali calendar (1402)
            assert "۱۴۰۲" in result

    def test_format_date_custom_format_english(self):
        """Test custom date format in English."""
        test_date = date(2024, 1, 15)
        with translation.override("en"):
            result = format_date(test_date, "%Y-%m-%d")
            assert result == "2024-01-15"

    def test_format_date_custom_format_persian(self):
        """Test custom date format in Persian."""
        test_date = date(2024, 1, 15)
        with translation.override("fa"):
            result = format_date(test_date, "%Y/%m/%d")
            # Should contain Persian numerals and be in Jalali calendar
            assert "۱۴۰۲" in result

    def test_format_date_from_datetime(self):
        """Test formatting date from datetime object."""
        test_datetime = datetime(2024, 1, 15, 14, 30)
        with translation.override("en"):
            result = format_date(test_datetime)
            assert "2024" in result


class TestDateTimeFormatting(TestCase):
    """Test datetime formatting with locale support."""

    def test_format_datetime_english_default(self):
        """Test default datetime formatting in English."""
        test_datetime = datetime(2024, 1, 15, 14, 30)
        with translation.override("en"):
            result = format_datetime(test_datetime)
            assert "2024" in result
            # Should contain time information
            assert any(t in result for t in ["14", "2:30", "PM", "pm"])

    def test_format_datetime_persian_default(self):
        """Test default datetime formatting in Persian."""
        test_datetime = datetime(2024, 1, 15, 14, 30)
        with translation.override("fa"):
            result = format_datetime(test_datetime)
            # Should contain Persian numerals
            assert any(char in result for char in "۰۱۲۳۴۵۶۷۸۹")
            # Should contain time (14:30 in Persian numerals)
            assert "۱۴" in result and "۳۰" in result

    def test_format_datetime_custom_format(self):
        """Test custom datetime format."""
        test_datetime = datetime(2024, 1, 15, 14, 30, 45)
        with translation.override("en"):
            result = format_datetime(test_datetime, "%Y-%m-%d %H:%M:%S")
            assert result == "2024-01-15 14:30:45"


class TestPersianNumberParsing(TestCase):
    """Test parsing numbers with Persian numerals."""

    def test_parse_persian_integer(self):
        """Test parsing Persian integer."""
        assert parse_persian_number("۱۲۳") == 123
        assert parse_persian_number("۰") == 0

    def test_parse_persian_float(self):
        """Test parsing Persian float."""
        assert parse_persian_number("۱۲٫۳۴") == 12.34
        assert parse_persian_number("۰٫۵") == 0.5

    def test_parse_persian_with_thousands_separator(self):
        """Test parsing Persian number with thousands separator."""
        assert parse_persian_number("۱٬۲۳۴٬۵۶۷") == 1234567
        assert parse_persian_number("۱٬۲۳۴٫۵۶") == 1234.56

    def test_parse_western_number(self):
        """Test parsing Western numerals (should still work)."""
        assert parse_persian_number("123") == 123
        assert parse_persian_number("12.34") == 12.34


class TestJalaliMonthNames(TestCase):
    """Test Jalali month name utilities."""

    def test_get_jalali_month_name_persian(self):
        """Test getting Jalali month names in Persian."""
        assert get_jalali_month_name(1, "fa") == "فروردین"
        assert get_jalali_month_name(7, "fa") == "مهر"
        assert get_jalali_month_name(12, "fa") == "اسفند"

    def test_get_jalali_month_name_english(self):
        """Test getting Jalali month names in English."""
        assert get_jalali_month_name(1, "en") == "Farvardin"
        assert get_jalali_month_name(7, "en") == "Mehr"
        assert get_jalali_month_name(12, "en") == "Esfand"

    def test_get_jalali_month_name_invalid(self):
        """Test invalid month number raises error."""
        with pytest.raises(ValueError):
            get_jalali_month_name(0, "fa")
        with pytest.raises(ValueError):
            get_jalali_month_name(13, "fa")


class TestJalaliWeekdayNames(TestCase):
    """Test Jalali weekday name utilities."""

    def test_get_jalali_weekday_name_persian(self):
        """Test getting weekday names in Persian."""
        assert get_jalali_weekday_name(0, "fa") == "شنبه"  # Saturday
        assert get_jalali_weekday_name(6, "fa") == "جمعه"  # Friday

    def test_get_jalali_weekday_name_english(self):
        """Test getting weekday names in English."""
        assert get_jalali_weekday_name(0, "en") == "Saturday"
        assert get_jalali_weekday_name(6, "en") == "Friday"

    def test_get_jalali_weekday_name_invalid(self):
        """Test invalid weekday number raises error."""
        with pytest.raises(ValueError):
            get_jalali_weekday_name(-1, "fa")
        with pytest.raises(ValueError):
            get_jalali_weekday_name(7, "fa")


class TestEdgeCases(TestCase):
    """Test edge cases and error handling."""

    def test_format_number_with_none(self):
        """Test formatting None values."""
        # Should handle gracefully without crashing
        try:
            result = format_number(None)
            # If it doesn't raise, result should be reasonable
            assert result is not None
        except (ValueError, TypeError):
            # Acceptable to raise error for None
            pass

    def test_format_date_with_none(self):
        """Test formatting None date."""
        try:
            result = format_date(None)
            assert result is not None
        except (ValueError, TypeError, AttributeError):
            # Acceptable to raise error for None
            pass

    def test_very_large_numbers(self):
        """Test formatting very large numbers."""
        with translation.override("en"):
            result = format_number(999999999999.99)
            assert "999,999,999,999.99" in result

    def test_very_small_decimals(self):
        """Test formatting very small decimal numbers."""
        with translation.override("en"):
            result = format_number(0.00001, decimal_places=5)
            assert "0.00001" in result
