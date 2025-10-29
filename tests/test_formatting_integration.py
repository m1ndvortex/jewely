"""
Integration tests for number and date formatting.

These tests verify the formatting utilities work correctly in a real Django environment
with actual database, translation system, and template rendering.

NO MOCKS - All tests use real Django components.

Per Requirement 2 - Dual-Language Support (English and Persian)
"""

from datetime import date, datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.test import RequestFactory, TestCase
from django.utils import translation

from apps/core.formatting_utils import (
    format_currency,
    format_date,
    format_datetime,
    format_number,
    to_jalali,
    to_persian_numerals,
)

User = get_user_model()


class TestFormattingIntegrationWithDjango(TestCase):
    """Integration tests with Django's translation system."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_number_formatting_switches_with_language(self):
        """Test that number formatting automatically switches with Django's language."""
        number = 1234567.89

        # Test English
        with translation.override("en"):
            result = format_number(number)
            assert "1,234,567.89" in result
            assert "۱" not in result  # No Persian numerals

        # Test Persian
        with translation.override("fa"):
            result = format_number(number)
            assert "۱" in result  # Has Persian numerals
            assert "٬" in result  # Has Persian thousands separator

    def test_currency_formatting_with_real_translation(self):
        """Test currency formatting uses real Django translation."""
        amount = 1234.56

        # Test USD in English
        with translation.override("en"):
            result = format_currency(amount, "USD")
            assert "$" in result
            assert "1,234.56" in result

        # Test USD in Persian
        with translation.override("fa"):
            result = format_currency(amount, "USD")
            assert "دلار" in result
            assert "۱" in result

        # Test IRR (Toman) in Persian
        with translation.override("fa"):
            result = format_currency(1234567, "IRR")
            assert "تومان" in result
            assert "۱" in result

    def test_jalali_calendar_conversion_accuracy(self):
        """Test Jalali calendar conversion with known dates."""
        # Test Persian New Year (Nowruz) - March 20, 2024 = Farvardin 1, 1403
        nowruz_2024 = date(2024, 3, 20)
        jalali = to_jalali(nowruz_2024)

        assert jalali.year == 1403
        assert jalali.month == 1
        assert jalali.day == 1

        # Test another known date - January 1, 2024 = Dey 11, 1402
        jan_1_2024 = date(2024, 1, 1)
        jalali = to_jalali(jan_1_2024)

        assert jalali.year == 1402
        assert jalali.month == 10
        assert jalali.day == 11

    def test_date_formatting_with_jalali_calendar(self):
        """Test date formatting automatically uses Jalali calendar for Persian."""
        test_date = date(2024, 3, 20)  # Nowruz

        # English should use Gregorian
        with translation.override("en"):
            result = format_date(test_date)
            assert "2024" in result

        # Persian should use Jalali
        with translation.override("fa"):
            result = format_date(test_date)
            assert "۱۴۰۳" in result  # Year 1403 in Persian numerals
            # Should be Farvardin 1 (first day of Persian year)

    def test_template_rendering_with_formatting_filters(self):
        """Test that formatting filters work in actual template rendering."""
        template_string = """
        {% load formatting_filters %}
        Number: {{ number|format_number }}
        Currency: {{ amount|format_currency:"USD" }}
        Date: {{ date|format_date }}
        """

        template = Template(template_string)

        # Test in English
        with translation.override("en"):
            context = Context(
                {
                    "number": 1234567.89,
                    "amount": 999.99,
                    "date": date(2024, 1, 15),
                }
            )
            result = template.render(context)

            assert "1,234,567.89" in result
            assert "$999.99" in result
            assert "2024" in result

        # Test in Persian
        with translation.override("fa"):
            context = Context(
                {
                    "number": 1234567.89,
                    "amount": 999.99,
                    "date": date(2024, 1, 15),
                }
            )
            result = template.render(context)

            assert "۱" in result  # Persian numerals
            assert "دلار" in result  # Persian currency name
            assert "۱۴۰۲" in result  # Jalali year

    def test_persian_numerals_in_template_loop(self):
        """Test Persian numerals work correctly in template loops."""
        template_string = """
        {% load formatting_filters %}
        {% for num in numbers %}
        {{ num|persian_numerals }}
        {% endfor %}
        """

        template = Template(template_string)
        context = Context({"numbers": [1, 2, 3, 4, 5]})
        result = template.render(context)

        # Check all Persian numerals are present
        assert "۱" in result
        assert "۲" in result
        assert "۳" in result
        assert "۴" in result
        assert "۵" in result

    def test_datetime_formatting_with_timezone(self):
        """Test datetime formatting handles timezones correctly."""
        test_datetime = datetime(2024, 1, 15, 14, 30, 45)

        # Test English
        with translation.override("en"):
            result = format_datetime(test_datetime)
            assert "2024" in result
            assert any(t in result for t in ["14", "2:30", "PM", "pm"])

        # Test Persian with Jalali calendar
        with translation.override("fa"):
            result = format_datetime(test_datetime)
            assert "۱۴۰۲" in result  # Jalali year
            assert "۱۴" in result  # Hour in Persian numerals
            assert "۳۰" in result  # Minute in Persian numerals


class TestFormattingWithRealData(TestCase):
    """Integration tests with realistic data scenarios."""

    def test_format_large_inventory_value(self):
        """Test formatting large numbers like inventory values."""
        inventory_value = Decimal("9876543.21")

        with translation.override("en"):
            result = format_number(inventory_value, decimal_places=2)
            assert "9,876,543.21" in result

        with translation.override("fa"):
            result = format_number(inventory_value, decimal_places=2)
            assert "۹" in result
            assert "٬" in result

    def test_format_jewelry_prices(self):
        """Test formatting jewelry prices in different currencies."""
        gold_ring_price = Decimal("2499.99")

        # USD
        with translation.override("en"):
            result = format_currency(gold_ring_price, "USD")
            assert "$2,499.99" in result

        with translation.override("fa"):
            result = format_currency(gold_ring_price, "USD")
            assert "دلار" in result
            assert "۲" in result

        # Iranian Toman
        toman_price = 125000000  # 125 million Toman
        with translation.override("fa"):
            result = format_currency(toman_price, "IRR")
            assert "تومان" in result
            assert "۱۲۵" in result

    def test_format_transaction_dates(self):
        """Test formatting transaction dates in both calendars."""
        transaction_date = date(2024, 2, 14)  # Valentine's Day

        # English - Gregorian
        with translation.override("en"):
            result = format_date(transaction_date, "%Y-%m-%d")
            assert result == "2024-02-14"

        # Persian - Jalali
        with translation.override("fa"):
            result = format_date(transaction_date)
            # Should contain Jalali year
            assert "۱۴۰۲" in result

    def test_format_invoice_with_multiple_items(self):
        """Test formatting a complete invoice with multiple items."""
        template_string = """
        {% load formatting_filters %}
        <table>
        {% for item in items %}
        <tr>
            <td>{{ item.name }}</td>
            <td>{{ item.quantity|format_number }}</td>
            <td>{{ item.price|format_currency:"USD" }}</td>
            <td>{{ item.total|format_currency:"USD" }}</td>
        </tr>
        {% endfor %}
        </table>
        Date: {{ date|format_date }}
        """

        template = Template(template_string)

        items = [
            {"name": "Gold Ring", "quantity": 2, "price": 1500.00, "total": 3000.00},
            {"name": "Silver Necklace", "quantity": 1, "price": 750.50, "total": 750.50},
            {"name": "Diamond Earrings", "quantity": 1, "price": 5000.00, "total": 5000.00},
        ]

        # Test in English
        with translation.override("en"):
            context = Context(
                {
                    "items": items,
                    "date": date(2024, 1, 15),
                }
            )
            result = template.render(context)

            assert "$1,500.00" in result
            assert "$750.50" in result
            assert "$5,000.00" in result
            assert "2024" in result

        # Test in Persian
        with translation.override("fa"):
            context = Context(
                {
                    "items": items,
                    "date": date(2024, 1, 15),
                }
            )
            result = template.render(context)

            assert "دلار" in result
            assert "۱" in result  # Persian numerals
            assert "۱۴۰۲" in result  # Jalali year


class TestFormattingEdgeCasesIntegration(TestCase):
    """Integration tests for edge cases and error handling."""

    def test_formatting_with_none_values(self):
        """Test that formatting handles None values gracefully."""
        template_string = """
        {% load formatting_filters %}
        Number: {{ number|format_number }}
        Currency: {{ amount|format_currency:"USD" }}
        Date: {{ date|format_date }}
        """

        template = Template(template_string)
        context = Context(
            {
                "number": None,
                "amount": None,
                "date": None,
            }
        )

        # Should not crash
        result = template.render(context)
        assert result is not None

    def test_formatting_with_zero_values(self):
        """Test formatting zero values."""
        with translation.override("en"):
            assert format_number(0) == "0"
            assert format_currency(0, "USD") == "$0.00"

        with translation.override("fa"):
            assert format_number(0) == "۰"
            result = format_currency(0, "IRR")
            assert "۰" in result
            assert "تومان" in result

    def test_formatting_negative_numbers(self):
        """Test formatting negative numbers."""
        with translation.override("en"):
            result = format_number(-1234.56)
            assert "-1,234.56" in result

        with translation.override("fa"):
            result = format_number(-1234.56)
            assert "-" in result or "۱" in result

    def test_formatting_very_large_numbers(self):
        """Test formatting very large numbers (billions)."""
        large_number = 9999999999.99

        with translation.override("en"):
            result = format_number(large_number)
            assert "9,999,999,999.99" in result

        with translation.override("fa"):
            result = format_number(large_number)
            assert "۹" in result
            assert "٬" in result

    def test_formatting_very_small_decimals(self):
        """Test formatting very small decimal numbers."""
        small_number = 0.00001

        with translation.override("en"):
            result = format_number(small_number, decimal_places=5)
            assert "0.00001" in result

        with translation.override("fa"):
            result = format_number(small_number, decimal_places=5)
            assert "۰" in result
            assert "٫" in result


class TestFormattingConsistency(TestCase):
    """Test consistency of formatting across different contexts."""

    def test_same_number_formats_consistently(self):
        """Test that the same number formats the same way every time."""
        number = 12345.67

        with translation.override("en"):
            result1 = format_number(number)
            result2 = format_number(number)
            assert result1 == result2

        with translation.override("fa"):
            result1 = format_number(number)
            result2 = format_number(number)
            assert result1 == result2

    def test_roundtrip_numeral_conversion(self):
        """Test that numeral conversion is reversible."""
        from apps.core.formatting_utils import to_western_numerals

        original = "1234567890"
        persian = to_persian_numerals(original)
        western = to_western_numerals(persian)

        assert western == original

    def test_roundtrip_calendar_conversion(self):
        """Test that calendar conversion is reversible."""
        from apps.core.formatting_utils import to_gregorian

        original_date = date(2024, 3, 20)
        jalali = to_jalali(original_date)
        gregorian = to_gregorian(jalali)

        assert gregorian == original_date

    def test_formatting_with_different_decimal_types(self):
        """Test formatting works with int, float, and Decimal."""
        value_int = 1234
        value_float = 1234.56
        value_decimal = Decimal("1234.56")

        with translation.override("en"):
            result_int = format_number(value_int)
            result_float = format_number(value_float)
            result_decimal = format_number(value_decimal)

            assert "1,234" in result_int
            assert "1,234.56" in result_float
            assert "1,234.56" in result_decimal


class TestFormattingPerformance(TestCase):
    """Test that formatting performs well with realistic loads."""

    def test_format_many_numbers_quickly(self):
        """Test formatting many numbers doesn't cause performance issues."""
        import time

        numbers = [i * 1.5 for i in range(1000)]

        start_time = time.time()
        with translation.override("fa"):
            for num in numbers:
                format_number(num)
        end_time = time.time()

        # Should complete in reasonable time (< 1 second for 1000 numbers)
        elapsed = end_time - start_time
        assert elapsed < 1.0, f"Formatting 1000 numbers took {elapsed:.2f}s"

    def test_format_many_dates_quickly(self):
        """Test formatting many dates doesn't cause performance issues."""
        import time
        from datetime import timedelta

        base_date = date(2024, 1, 1)
        dates = [base_date + timedelta(days=i) for i in range(365)]

        start_time = time.time()
        with translation.override("fa"):
            for d in dates:
                format_date(d)
        end_time = time.time()

        # Should complete in reasonable time (< 2 seconds for 365 dates)
        elapsed = end_time - start_time
        assert elapsed < 2.0, f"Formatting 365 dates took {elapsed:.2f}s"


class TestFormattingWithRealTemplates(TestCase):
    """Test formatting in realistic template scenarios."""

    def test_dashboard_summary_template(self):
        """Test formatting in a dashboard summary template."""
        template_string = """
        {% load formatting_filters %}
        <div class="dashboard">
            <h1>Dashboard</h1>
            <div class="stats">
                <div class="stat">
                    <span class="label">Total Sales:</span>
                    <span class="value">{{ total_sales|format_currency:"USD" }}</span>
                </div>
                <div class="stat">
                    <span class="label">Items Sold:</span>
                    <span class="value">{{ items_sold|format_number }}</span>
                </div>
                <div class="stat">
                    <span class="label">Last Updated:</span>
                    <span class="value">{{ last_updated|format_datetime }}</span>
                </div>
            </div>
        </div>
        """

        template = Template(template_string)

        with translation.override("fa"):
            context = Context(
                {
                    "total_sales": 1234567.89,
                    "items_sold": 456,
                    "last_updated": datetime(2024, 1, 15, 14, 30),
                }
            )
            result = template.render(context)

            # Verify Persian formatting
            assert "۱" in result
            assert "دلار" in result
            assert "۱۴۰۲" in result

    def test_product_list_template(self):
        """Test formatting in a product list template."""
        template_string = """
        {% load formatting_filters %}
        <table class="product-list">
            <thead>
                <tr>
                    <th>Product</th>
                    <th>Price</th>
                    <th>Stock</th>
                </tr>
            </thead>
            <tbody>
            {% for product in products %}
                <tr>
                    <td>{{ product.name }}</td>
                    <td>{{ product.price|format_currency:"IRR" }}</td>
                    <td>{{ product.stock|format_number }}</td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
        """

        template = Template(template_string)

        products = [
            {"name": "Gold Ring 18K", "price": 50000000, "stock": 12},
            {"name": "Silver Bracelet", "price": 5000000, "stock": 25},
            {"name": "Diamond Pendant", "price": 150000000, "stock": 3},
        ]

        with translation.override("fa"):
            context = Context({"products": products})
            result = template.render(context)

            # Verify Persian formatting
            assert "تومان" in result
            assert "۱" in result or "۲" in result or "۳" in result
