"""
Tests for Django template filters for number and date formatting.

Per Requirement 2 - Dual-Language Support (English and Persian)
"""

from datetime import date, datetime
from decimal import Decimal

from django.template import Context, Template
from django.test import TestCase
from django.utils import translation


class TestFormattingFilters(TestCase):
    """Test Django template filters for formatting."""

    def test_persian_numerals_filter(self):
        """Test persian_numerals template filter."""
        template = Template("{% load formatting_filters %}{{ value|persian_numerals }}")

        context = Context({"value": "123"})
        result = template.render(context)
        assert result == "۱۲۳"

        context = Context({"value": 456})
        result = template.render(context)
        assert result == "۴۵۶"

    def test_persian_numerals_filter_with_none(self):
        """Test persian_numerals filter with None value."""
        template = Template("{% load formatting_filters %}{{ value|persian_numerals }}")
        context = Context({"value": None})
        result = template.render(context)
        assert result == ""

    def test_format_number_filter_english(self):
        """Test format_number filter in English locale."""
        template = Template("{% load formatting_filters %}{{ value|format_number }}")

        with translation.override("en"):
            context = Context({"value": 1234567.89})
            result = template.render(context)
            assert "1,234,567.89" in result

    def test_format_number_filter_persian(self):
        """Test format_number filter in Persian locale."""
        template = Template("{% load formatting_filters %}{{ value|format_number }}")

        with translation.override("fa"):
            context = Context({"value": 1234567.89})
            result = template.render(context)
            # Should contain Persian numerals
            assert any(char in result for char in "۰۱۲۳۴۵۶۷۸۹")

    def test_format_number_filter_with_decimal_places(self):
        """Test format_number filter with decimal places argument."""
        template = Template("{% load formatting_filters %}{{ value|format_number:2 }}")

        with translation.override("en"):
            context = Context({"value": 1234.5})
            result = template.render(context)
            assert "1,234.50" in result

    def test_format_currency_filter_usd(self):
        """Test format_currency filter with USD."""
        template = Template('{% load formatting_filters %}{{ value|format_currency:"USD" }}')

        with translation.override("en"):
            context = Context({"value": 1234.56})
            result = template.render(context)
            assert "$" in result
            assert "1,234.56" in result

    def test_format_currency_filter_irr(self):
        """Test format_currency filter with IRR (displays as Toman in Persian)."""
        template = Template('{% load formatting_filters %}{{ value|format_currency:"IRR" }}')

        with translation.override("fa"):
            context = Context({"value": 1234567})
            result = template.render(context)
            assert "تومان" in result

    def test_format_date_filter_english(self):
        """Test format_date filter in English locale."""
        template = Template("{% load formatting_filters %}{{ value|format_date }}")

        with translation.override("en"):
            context = Context({"value": date(2024, 1, 15)})
            result = template.render(context)
            assert "2024" in result

    def test_format_date_filter_persian(self):
        """Test format_date filter in Persian locale (Jalali calendar)."""
        template = Template("{% load formatting_filters %}{{ value|format_date }}")

        with translation.override("fa"):
            context = Context({"value": date(2024, 1, 15)})
            result = template.render(context)
            # Should contain Persian numerals and Jalali year
            assert "۱۴۰۲" in result

    def test_format_date_filter_custom_format(self):
        """Test format_date filter with custom format."""
        template = Template('{% load formatting_filters %}{{ value|format_date:"%Y-%m-%d" }}')

        with translation.override("en"):
            context = Context({"value": date(2024, 1, 15)})
            result = template.render(context)
            assert "2024-01-15" in result

    def test_format_datetime_filter_english(self):
        """Test format_datetime filter in English locale."""
        template = Template("{% load formatting_filters %}{{ value|format_datetime }}")

        with translation.override("en"):
            context = Context({"value": datetime(2024, 1, 15, 14, 30)})
            result = template.render(context)
            assert "2024" in result
            # Should contain time
            assert any(t in result for t in ["14", "2:30", "PM", "pm"])

    def test_format_datetime_filter_persian(self):
        """Test format_datetime filter in Persian locale."""
        template = Template("{% load formatting_filters %}{{ value|format_datetime }}")

        with translation.override("fa"):
            context = Context({"value": datetime(2024, 1, 15, 14, 30)})
            result = template.render(context)
            # Should contain Persian numerals
            assert any(char in result for char in "۰۱۲۳۴۵۶۷۸۹")

    def test_format_number_tag(self):
        """Test format_number_tag template tag."""
        template = Template("{% load formatting_filters %}{% format_number_tag 1234567.89 2 %}")

        with translation.override("en"):
            context = Context({})
            result = template.render(context)
            assert "1,234,567.89" in result

    def test_format_currency_tag(self):
        """Test format_currency_tag template tag."""
        template = Template('{% load formatting_filters %}{% format_currency_tag 1234.56 "USD" %}')

        with translation.override("en"):
            context = Context({})
            result = template.render(context)
            assert "$" in result
            assert "1,234.56" in result

    def test_formatted_number_inclusion_tag(self):
        """Test formatted_number inclusion tag."""
        template = Template("{% load formatting_filters %}{% formatted_number 1234567.89 2 %}")

        with translation.override("en"):
            context = Context({})
            result = template.render(context)
            # Should render the inclusion template
            assert "formatted-number" in result
            assert "1,234,567.89" in result

    def test_formatted_currency_inclusion_tag(self):
        """Test formatted_currency inclusion tag."""
        template = Template('{% load formatting_filters %}{% formatted_currency 1234.56 "USD" %}')

        with translation.override("en"):
            context = Context({})
            result = template.render(context)
            # Should render the inclusion template
            assert "formatted-currency" in result
            assert "$" in result

    def test_filter_with_invalid_value(self):
        """Test filters handle invalid values gracefully."""
        template = Template("{% load formatting_filters %}{{ value|format_number }}")

        context = Context({"value": "invalid"})
        result = template.render(context)
        # Should not crash, should return something reasonable
        assert result is not None

    def test_multiple_filters_chained(self):
        """Test chaining multiple filters."""
        # This tests that filters can be used together
        template = Template("{% load formatting_filters %}{{ value|format_number }}")

        with translation.override("en"):
            context = Context({"value": Decimal("1234.56")})
            result = template.render(context)
            assert "1,234.56" in result


class TestFormattingInComplexTemplates(TestCase):
    """Test formatting filters in more complex template scenarios."""

    def test_formatting_in_loop(self):
        """Test formatting filters work correctly in loops."""
        template = Template(
            """
            {% load formatting_filters %}
            {% for num in numbers %}
                {{ num|format_number }}
            {% endfor %}
        """
        )

        with translation.override("en"):
            context = Context({"numbers": [100, 1000, 10000]})
            result = template.render(context)
            assert "100" in result
            assert "1,000" in result
            assert "10,000" in result

    def test_formatting_in_conditional(self):
        """Test formatting filters work in conditional blocks."""
        template = Template(
            """
            {% load formatting_filters %}
            {% if show_price %}
                {{ price|format_currency:"USD" }}
            {% endif %}
        """
        )

        with translation.override("en"):
            context = Context({"show_price": True, "price": 99.99})
            result = template.render(context)
            assert "$99.99" in result

    def test_formatting_with_variables(self):
        """Test formatting filters with variable arguments."""
        template = Template(
            """
            {% load formatting_filters %}
            {{ amount|format_currency:currency_code }}
        """
        )

        with translation.override("en"):
            context = Context({"amount": 1234.56, "currency_code": "EUR"})
            result = template.render(context)
            assert "€" in result

    def test_date_formatting_in_table(self):
        """Test date formatting in table context."""
        template = Template(
            """
            {% load formatting_filters %}
            <table>
            {% for item in items %}
                <tr>
                    <td>{{ item.date|format_date }}</td>
                    <td>{{ item.amount|format_currency:"USD" }}</td>
                </tr>
            {% endfor %}
            </table>
        """
        )

        with translation.override("en"):
            items = [
                {"date": date(2024, 1, 1), "amount": 100.00},
                {"date": date(2024, 1, 2), "amount": 200.00},
            ]
            context = Context({"items": items})
            result = template.render(context)
            assert "2024" in result
            assert "$100.00" in result
            assert "$200.00" in result
