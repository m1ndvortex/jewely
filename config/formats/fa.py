"""
Persian (fa) format localization.
Per Requirement 2 - Dual-Language Support (English and Persian)

Note: This file defines format patterns for Persian locale.
For Persian calendar (Jalali) support, use jdatetime library in application code.
"""

# Date and time formats (using Gregorian calendar by default)
# Persian calendar conversion will be handled by jdatetime in views/templates
DATE_FORMAT = "Y/m/d"  # e.g., "1403/10/11" (Persian calendar) or "2024/01/01" (Gregorian)
TIME_FORMAT = "H:i"  # e.g., "14:30" (24-hour format is standard in Iran)
DATETIME_FORMAT = "Y/m/d، H:i"  # e.g., "1403/10/11، 14:30"
YEAR_MONTH_FORMAT = "F Y"  # e.g., "دی 1403"
MONTH_DAY_FORMAT = "j F"  # e.g., "11 دی"
SHORT_DATE_FORMAT = "Y/m/d"  # e.g., "1403/10/11"
SHORT_DATETIME_FORMAT = "Y/m/d H:i"  # e.g., "1403/10/11 14:30"

# Date input formats (for form fields)
# Accept both Persian and Gregorian calendar formats
DATE_INPUT_FORMATS = [
    "%Y/%m/%d",  # '1403/10/11' or '2024/01/01'
    "%Y-%m-%d",  # '1403-10-11' or '2024-01-01'
    "%d/%m/%Y",  # '11/10/1403' or '01/01/2024'
    "%d-%m-%Y",  # '11-10-1403' or '01-01-2024'
]

# Time input formats (for form fields)
TIME_INPUT_FORMATS = [
    "%H:%M:%S",  # '14:30:59'
    "%H:%M:%S.%f",  # '14:30:59.000200'
    "%H:%M",  # '14:30'
]

# Datetime input formats (for form fields)
DATETIME_INPUT_FORMATS = [
    "%Y/%m/%d %H:%M:%S",  # '1403/10/11 14:30:59'
    "%Y/%m/%d %H:%M:%S.%f",  # '1403/10/11 14:30:59.000200'
    "%Y/%m/%d %H:%M",  # '1403/10/11 14:30'
    "%Y-%m-%d %H:%M:%S",  # '1403-10-11 14:30:59'
    "%Y-%m-%d %H:%M:%S.%f",  # '1403-10-11 14:30:59.000200'
    "%Y-%m-%d %H:%M",  # '1403-10-11 14:30'
]

# Number formatting
# Persian uses Eastern Arabic numerals (۰۱۲۳۴۵۶۷۸۹)
# Conversion will be handled by template filters and utility functions
DECIMAL_SEPARATOR = "٫"  # Persian decimal separator (U+066B)
THOUSAND_SEPARATOR = "٬"  # Persian thousands separator (U+066C)
NUMBER_GROUPING = 3

# First day of week (6 = Saturday, which is the first day in Iran)
FIRST_DAY_OF_WEEK = 6  # Saturday
