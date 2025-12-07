"""
Template tags for inventory app.
Provides custom filters and tags for category icons and colors.
"""

from django import template

register = template.Library()


# Category icon mapping - using SVG paths for Heroicons
CATEGORY_ICONS = {
    # Main categories
    "rings": "M12 14l9-5-9-5-9 5 9 5z M12 14l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z",  # Gift/Ring icon
    "necklaces": "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",  # Circle with check (pearl)
    "bracelets": "M12 8v13m0-13V6a2 2 0 112 2h-2zm0 0V5.5A2.5 2.5 0 109.5 8H12zm-7 4h14M5 12a2 2 0 110-4h14a2 2 0 110 4M5 12v7a2 2 0 002 2h10a2 2 0 002-2v-7",  # Bracelet shape
    "earrings": "M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z",  # Sparkle/Star
    "watches": "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",  # Clock/Watch
    "gemstones": "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",  # Lightbulb/Gem
    # Ring subcategories
    "engagement rings": "M12 14l9-5-9-5-9 5 9 5z M12 14l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z",
    "wedding bands": "M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z",  # Heart
    "fashion rings": "M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z",  # Sparkles
    "statement rings": "M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z",  # Badge
    # Necklace subcategories
    "gold chains": "M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1",  # Link
    "pendant necklaces": "M12 14l9-5-9-5-9 5 9 5z M12 14l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14z",
    "chokers": "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",  # Circle
    "statement necklaces": "M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z",
    # Bracelet subcategories
    "bangles": "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
    "chain bracelets": "M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1",
    "charm bracelets": "M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z",
    "tennis bracelets": "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
    # Earring subcategories
    "studs": "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
    "hoops": "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
    "drop earrings": "M19 14l-7 7m0 0l-7-7m7 7V3",  # Arrow down
    "chandelier earrings": "M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z",
    # Watch subcategories
    "men's watches": "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
    "women's watches": "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
    "unisex watches": "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
    # Gemstone subcategories
    "diamonds": "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
    "rubies": "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
    "sapphires": "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
    "emeralds": "M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z",
    "semi-precious": "M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z",
}

# Default icon for unknown categories
DEFAULT_ICON = "M7 7h.01M7 3h5c.512 0 1.024.195 1.414.586l7 7a2 2 0 010 2.828l-7 7a2 2 0 01-2.828 0l-7-7A1.994 1.994 0 013 12V7a4 4 0 014-4z"


# Category color mapping - using Tailwind gradient classes
CATEGORY_COLORS = {
    # Main categories with vibrant gradients
    "rings": "bg-gradient-to-br from-pink-400 to-pink-600 text-white shadow-pink-200 dark:shadow-pink-900",
    "necklaces": "bg-gradient-to-br from-purple-400 to-purple-600 text-white shadow-purple-200 dark:shadow-purple-900",
    "bracelets": "bg-gradient-to-br from-blue-400 to-blue-600 text-white shadow-blue-200 dark:shadow-blue-900",
    "earrings": "bg-gradient-to-br from-yellow-400 to-amber-600 text-white shadow-yellow-200 dark:shadow-yellow-900",
    "watches": "bg-gradient-to-br from-gray-600 to-gray-800 text-white shadow-gray-300 dark:shadow-gray-900",
    "gemstones": "bg-gradient-to-br from-emerald-400 to-emerald-600 text-white shadow-emerald-200 dark:shadow-emerald-900",
    # Ring subcategories
    "engagement rings": "bg-gradient-to-br from-rose-400 to-rose-600 text-white shadow-rose-200 dark:shadow-rose-900",
    "wedding bands": "bg-gradient-to-br from-pink-300 to-pink-500 text-white shadow-pink-200 dark:shadow-pink-900",
    "fashion rings": "bg-gradient-to-br from-fuchsia-400 to-fuchsia-600 text-white shadow-fuchsia-200 dark:shadow-fuchsia-900",
    "statement rings": "bg-gradient-to-br from-violet-400 to-violet-600 text-white shadow-violet-200 dark:shadow-violet-900",
    # Necklace subcategories
    "gold chains": "bg-gradient-to-br from-yellow-500 to-orange-600 text-white shadow-yellow-200 dark:shadow-yellow-900",
    "pendant necklaces": "bg-gradient-to-br from-indigo-400 to-indigo-600 text-white shadow-indigo-200 dark:shadow-indigo-900",
    "chokers": "bg-gradient-to-br from-purple-500 to-purple-700 text-white shadow-purple-200 dark:shadow-purple-900",
    "statement necklaces": "bg-gradient-to-br from-violet-500 to-violet-700 text-white shadow-violet-200 dark:shadow-violet-900",
    # Bracelet subcategories
    "bangles": "bg-gradient-to-br from-cyan-400 to-cyan-600 text-white shadow-cyan-200 dark:shadow-cyan-900",
    "chain bracelets": "bg-gradient-to-br from-blue-500 to-blue-700 text-white shadow-blue-200 dark:shadow-blue-900",
    "charm bracelets": "bg-gradient-to-br from-sky-400 to-sky-600 text-white shadow-sky-200 dark:shadow-sky-900",
    "tennis bracelets": "bg-gradient-to-br from-teal-400 to-teal-600 text-white shadow-teal-200 dark:shadow-teal-900",
    # Earring subcategories
    "studs": "bg-gradient-to-br from-amber-400 to-amber-600 text-white shadow-amber-200 dark:shadow-amber-900",
    "hoops": "bg-gradient-to-br from-orange-400 to-orange-600 text-white shadow-orange-200 dark:shadow-orange-900",
    "drop earrings": "bg-gradient-to-br from-yellow-400 to-yellow-600 text-white shadow-yellow-200 dark:shadow-yellow-900",
    "chandelier earrings": "bg-gradient-to-br from-lime-400 to-lime-600 text-white shadow-lime-200 dark:shadow-lime-900",
    # Watch subcategories
    "men's watches": "bg-gradient-to-br from-slate-600 to-slate-800 text-white shadow-slate-300 dark:shadow-slate-900",
    "women's watches": "bg-gradient-to-br from-zinc-500 to-zinc-700 text-white shadow-zinc-300 dark:shadow-zinc-900",
    "unisex watches": "bg-gradient-to-br from-gray-600 to-gray-800 text-white shadow-gray-300 dark:shadow-gray-900",
    # Gemstone subcategories
    "diamonds": "bg-gradient-to-br from-blue-300 to-blue-500 text-white shadow-blue-200 dark:shadow-blue-900",
    "rubies": "bg-gradient-to-br from-red-400 to-red-600 text-white shadow-red-200 dark:shadow-red-900",
    "sapphires": "bg-gradient-to-br from-blue-500 to-blue-700 text-white shadow-blue-200 dark:shadow-blue-900",
    "emeralds": "bg-gradient-to-br from-green-500 to-green-700 text-white shadow-green-200 dark:shadow-green-900",
    "semi-precious": "bg-gradient-to-br from-teal-500 to-teal-700 text-white shadow-teal-200 dark:shadow-teal-900",
}

# Default color for unknown categories
DEFAULT_COLOR = (
    "bg-gradient-to-br from-gray-400 to-gray-600 text-white shadow-gray-200 dark:shadow-gray-900"
)


@register.filter
def get_category_icon(category_name):
    """
    Get the SVG path for a category icon based on category name.

    Args:
        category_name: The name of the category (case-insensitive)

    Returns:
        SVG path string for the icon
    """
    if not category_name:
        return DEFAULT_ICON

    # Normalize the category name (lowercase, strip whitespace)
    normalized_name = str(category_name).lower().strip()

    return CATEGORY_ICONS.get(normalized_name, DEFAULT_ICON)


@register.filter
def get_category_color(category_name):
    """
    Get the Tailwind CSS gradient classes for a category based on category name.

    Args:
        category_name: The name of the category (case-insensitive)

    Returns:
        String of Tailwind CSS classes for background gradient and shadow
    """
    if not category_name:
        return DEFAULT_COLOR

    # Normalize the category name (lowercase, strip whitespace)
    normalized_name = str(category_name).lower().strip()

    return CATEGORY_COLORS.get(normalized_name, DEFAULT_COLOR)


@register.filter
def get_category_emoji(category_name):
    """
    Get an emoji for a category based on category name.
    Alternative to SVG icons for a fun, colorful look.

    Args:
        category_name: The name of the category (case-insensitive)

    Returns:
        Emoji string
    """
    CATEGORY_EMOJIS = {
        # Main categories
        "rings": "💍",
        "necklaces": "📿",
        "bracelets": "⚜️",
        "earrings": "💎",
        "watches": "⌚",
        "gemstones": "💠",
        # Ring subcategories
        "engagement rings": "💍",
        "wedding bands": "💑",
        "fashion rings": "✨",
        "statement rings": "👑",
        # Necklace subcategories
        "gold chains": "🔗",
        "pendant necklaces": "📿",
        "chokers": "⭕",
        "statement necklaces": "✨",
        # Bracelet subcategories
        "bangles": "⭕",
        "chain bracelets": "🔗",
        "charm bracelets": "✨",
        "tennis bracelets": "💎",
        # Earring subcategories
        "studs": "💎",
        "hoops": "⭕",
        "drop earrings": "💧",
        "chandelier earrings": "✨",
        # Watch subcategories
        "men's watches": "⌚",
        "women's watches": "⌚",
        "unisex watches": "⌚",
        # Gemstone subcategories
        "diamonds": "💎",
        "rubies": "🔴",
        "sapphires": "🔵",
        "emeralds": "🟢",
        "semi-precious": "✨",
    }

    if not category_name:
        return "🏷️"

    normalized_name = str(category_name).lower().strip()
    return CATEGORY_EMOJIS.get(normalized_name, "🏷️")
