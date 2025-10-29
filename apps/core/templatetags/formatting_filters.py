"""
Django template filters for number and date formatting.

Usage in templates:
    {% load formatting_filters %}

    {{ number|persian_numerals }}
    {{ number|format_number }}
    {{ amount|format_currency:"USD" }}
    {{ date|format_date }}
    {{ datetime|format_datetime }}

Per Requirement 2 - Dual-Language Support (English and Persian)
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Union

from django import template

from apps.core.formatting_utils import (
    format_currency,
    format_date,
    format_datetime,
    format_number,
    to_persian_numerals,
)

register = template.Library()


@register.filter(name="persian_numerals")
def persian_numerals_filter(value: Union[str, int, float, Decimal]) -> str:
    """
    Convert Western numerals to Persian numerals.

    Usage:
        {{ "123"|persian_numerals }}  -> ۱۲۳
        {{ 456|persian_numerals }}    -> ۴۵۶
    """
    if value is None:
        return ""
    return to_persian_numerals(value)


@register.filter(name="format_number")
def format_number_filter(value: Union[int, float, Decimal], decimal_places: int = None) -> str:
    """
    Format a number according to the current locale.

    Usage:
        {{ 1234567.89|format_number }}     -> 1,234,567.89 (en) or ۱٬۲۳۴٬۵۶۷٫۸۹ (fa)
        {{ 1234567.89|format_number:2 }}   -> 1,234,567.89 (en) or ۱٬۲۳۴٬۵۶۷٫۸۹ (fa)
    """
    if value is None:
        return ""

    try:
        return format_number(value, decimal_places=decimal_places)
    except (ValueError, TypeError):
        return str(value)


@register.filter(name="format_currency")
def format_currency_filter(value: Union[int, float, Decimal], currency: str = "USD") -> str:
    """
    Format a currency amount according to the current locale.

    Usage:
        {{ 1234.56|format_currency:"USD" }}  -> $1,234.56 (en) or ۱٬۲۳۴٫۵۶ دلار (fa)
        {{ 1234567|format_currency:"IRR" }}  -> 1,234,567 IRR (en) or ۱٬۲۳۴٬۵۶۷ ریال (fa)
    """
    if value is None:
        return ""

    try:
        return format_currency(value, currency=currency)
    except (ValueError, TypeError):
        return str(value)


@register.filter(name="format_date")
def format_date_filter(value: Union[date, datetime], format_string: str = None) -> str:
    """
    Format a date according to the current locale.

    For Persian locale, converts to Jalali calendar.

    Usage:
        {{ date_obj|format_date }}              -> Jan. 1, 2024 (en) or ۱۴۰۲/۱۰/۱۱ (fa)
        {{ date_obj|format_date:"%Y-%m-%d" }}   -> 2024-01-01 (en) or ۱۴۰۲-۱۰-۱۱ (fa)
    """
    if value is None:
        return ""

    try:
        return format_date(value, format_string=format_string)
    except (ValueError, TypeError, AttributeError):
        return str(value)


@register.filter(name="format_datetime")
def format_datetime_filter(value: datetime, format_string: str = None) -> str:
    """
    Format a datetime according to the current locale.

    For Persian locale, converts to Jalali calendar.

    Usage:
        {{ datetime_obj|format_datetime }}                    -> Jan. 1, 2024, 2:30 PM (en) or ۱۴۰۲/۱۰/۱۱، ۱۴:۳۰ (fa)
        {{ datetime_obj|format_datetime:"%Y-%m-%d %H:%M" }}   -> 2024-01-01 14:30 (en) or ۱۴۰۲-۱۰-۱۱ ۱۴:۳۰ (fa)
    """
    if value is None:
        return ""

    try:
        return format_datetime(value, format_string=format_string)
    except (ValueError, TypeError, AttributeError):
        return str(value)


@register.simple_tag(takes_context=True)
def format_number_tag(
    context, value: Union[int, float, Decimal], decimal_places: int = None
) -> str:
    """
    Template tag version of format_number for more complex usage.

    Usage:
        {% format_number_tag 1234567.89 %}
        {% format_number_tag 1234567.89 2 %}
    """
    if value is None:
        return ""

    try:
        return format_number(value, decimal_places=decimal_places)
    except (ValueError, TypeError):
        return str(value)


@register.simple_tag(takes_context=True)
def format_currency_tag(context, value: Union[int, float, Decimal], currency: str = "USD") -> str:
    """
    Template tag version of format_currency for more complex usage.

    Usage:
        {% format_currency_tag 1234.56 "USD" %}
        {% format_currency_tag amount "IRR" %}
    """
    if value is None:
        return ""

    try:
        return format_currency(value, currency=currency)
    except (ValueError, TypeError):
        return str(value)


@register.inclusion_tag("core/formatted_number.html", takes_context=True)
def formatted_number(context, value: Union[int, float, Decimal], decimal_places: int = None):
    """
    Inclusion tag for rendering formatted numbers with proper HTML structure.

    Usage:
        {% formatted_number 1234567.89 %}
        {% formatted_number 1234567.89 2 %}
    """
    formatted = ""
    if value is not None:
        try:
            formatted = format_number(value, decimal_places=decimal_places)
        except (ValueError, TypeError):
            formatted = str(value)

    return {
        "value": value,
        "formatted": formatted,
    }


@register.inclusion_tag("core/formatted_currency.html", takes_context=True)
def formatted_currency(context, value: Union[int, float, Decimal], currency: str = "USD"):
    """
    Inclusion tag for rendering formatted currency with proper HTML structure.

    Usage:
        {% formatted_currency 1234.56 "USD" %}
        {% formatted_currency amount "IRR" %}
    """
    formatted = ""
    if value is not None:
        try:
            formatted = format_currency(value, currency=currency)
        except (ValueError, TypeError):
            formatted = str(value)

    return {
        "value": value,
        "currency": currency,
        "formatted": formatted,
    }
