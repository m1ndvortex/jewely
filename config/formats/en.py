"""
English (en) format localization.
Per Requirement 2 - Dual-Language Support (English and Persian)
"""

# Date and time formats
DATE_FORMAT = "N j, Y"  # e.g., "Jan. 1, 2024"
TIME_FORMAT = "P"  # e.g., "1:30 p.m."
DATETIME_FORMAT = "N j, Y, P"  # e.g., "Jan. 1, 2024, 1:30 p.m."
YEAR_MONTH_FORMAT = "F Y"  # e.g., "January 2024"
MONTH_DAY_FORMAT = "F j"  # e.g., "January 1"
SHORT_DATE_FORMAT = "m/d/Y"  # e.g., "01/01/2024"
SHORT_DATETIME_FORMAT = "m/d/Y P"  # e.g., "01/01/2024 1:30 p.m."

# Date input formats (for form fields)
DATE_INPUT_FORMATS = [
    "%Y-%m-%d",  # '2024-01-01'
    "%m/%d/%Y",  # '01/01/2024'
    "%m/%d/%y",  # '01/01/24'
    "%b %d %Y",  # 'Jan 01 2024'
    "%b %d, %Y",  # 'Jan 01, 2024'
    "%d %b %Y",  # '01 Jan 2024'
    "%d %b, %Y",  # '01 Jan, 2024'
    "%B %d %Y",  # 'January 01 2024'
    "%B %d, %Y",  # 'January 01, 2024'
    "%d %B %Y",  # '01 January 2024'
    "%d %B, %Y",  # '01 January, 2024'
]

# Time input formats (for form fields)
TIME_INPUT_FORMATS = [
    "%H:%M:%S",  # '14:30:59'
    "%H:%M:%S.%f",  # '14:30:59.000200'
    "%H:%M",  # '14:30'
    "%I:%M:%S %p",  # '02:30:59 PM'
    "%I:%M %p",  # '02:30 PM'
]

# Datetime input formats (for form fields)
DATETIME_INPUT_FORMATS = [
    "%Y-%m-%d %H:%M:%S",  # '2024-01-01 14:30:59'
    "%Y-%m-%d %H:%M:%S.%f",  # '2024-01-01 14:30:59.000200'
    "%Y-%m-%d %H:%M",  # '2024-01-01 14:30'
    "%m/%d/%Y %H:%M:%S",  # '01/01/2024 14:30:59'
    "%m/%d/%Y %H:%M:%S.%f",  # '01/01/2024 14:30:59.000200'
    "%m/%d/%Y %H:%M",  # '01/01/2024 14:30'
    "%m/%d/%y %H:%M:%S",  # '01/01/24 14:30:59'
    "%m/%d/%y %H:%M:%S.%f",  # '01/01/24 14:30:59.000200'
    "%m/%d/%y %H:%M",  # '01/01/24 14:30'
]

# Number formatting
DECIMAL_SEPARATOR = "."
THOUSAND_SEPARATOR = ","
NUMBER_GROUPING = 3

# First day of week (0 = Sunday, 1 = Monday, etc.)
FIRST_DAY_OF_WEEK = 0  # Sunday
