"""
WCAG 2.1 Level AA Compliance Verification
Per Requirements 3 and 29

This module provides utilities to verify color contrast ratios
and ensure WCAG 2.1 Level AA compliance for both light and dark themes.

WCAG 2.1 Level AA Requirements:
- Normal text (< 18pt or < 14pt bold): 4.5:1 contrast ratio
- Large text (>= 18pt or >= 14pt bold): 3:1 contrast ratio
- UI components and graphical objects: 3:1 contrast ratio
"""

from dataclasses import dataclass
from typing import List, Tuple


@dataclass
class ColorPair:
    """Represents a foreground/background color pair"""

    name: str
    foreground: str
    background: str
    context: str  # 'normal-text', 'large-text', 'ui-component'
    theme: str  # 'light' or 'dark'


@dataclass
class ContrastResult:
    """Result of a contrast ratio check"""

    color_pair: ColorPair
    contrast_ratio: float
    required_ratio: float
    passes: bool

    def __str__(self):
        status = "✓ PASS" if self.passes else "✗ FAIL"
        return (
            f"{status} [{self.color_pair.theme}] {self.color_pair.name}: "
            f"{self.contrast_ratio:.2f}:1 "
            f"(required: {self.required_ratio}:1)"
        )


def hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """
    Convert hex color to RGB tuple.

    Args:
        hex_color: Hex color string (e.g., '#ffffff' or '#fff')

    Returns:
        Tuple of (r, g, b) values (0-255)
    """
    hex_color = hex_color.lstrip("#")

    # Handle 3-digit hex codes
    if len(hex_color) == 3:
        hex_color = "".join([c * 2 for c in hex_color])

    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def rgb_to_relative_luminance(r: int, g: int, b: int) -> float:
    """
    Calculate relative luminance of an RGB color.

    Per WCAG 2.1 formula:
    https://www.w3.org/WAI/GL/wiki/Relative_luminance

    Args:
        r, g, b: RGB values (0-255)

    Returns:
        Relative luminance (0-1)
    """
    # Convert to 0-1 range
    r, g, b = r / 255.0, g / 255.0, b / 255.0

    # Apply gamma correction
    def adjust(channel):
        if channel <= 0.03928:
            return channel / 12.92
        else:
            return ((channel + 0.055) / 1.055) ** 2.4

    r = adjust(r)
    g = adjust(g)
    b = adjust(b)

    # Calculate luminance
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def calculate_contrast_ratio(color1: str, color2: str) -> float:
    """
    Calculate contrast ratio between two colors.

    Per WCAG 2.1 formula:
    (L1 + 0.05) / (L2 + 0.05)
    where L1 is the lighter color and L2 is the darker color

    Args:
        color1: First color (hex format)
        color2: Second color (hex format)

    Returns:
        Contrast ratio (1-21)
    """
    # Convert to RGB
    rgb1 = hex_to_rgb(color1)
    rgb2 = hex_to_rgb(color2)

    # Calculate luminance
    l1 = rgb_to_relative_luminance(*rgb1)
    l2 = rgb_to_relative_luminance(*rgb2)

    # Ensure L1 is the lighter color
    if l1 < l2:
        l1, l2 = l2, l1

    # Calculate contrast ratio
    return (l1 + 0.05) / (l2 + 0.05)


def get_required_contrast_ratio(context: str) -> float:
    """
    Get required contrast ratio for a given context.

    Args:
        context: One of 'normal-text', 'large-text', 'ui-component'

    Returns:
        Required contrast ratio
    """
    ratios = {
        "normal-text": 4.5,
        "large-text": 3.0,
        "ui-component": 3.0,
    }
    return ratios.get(context, 4.5)


def verify_contrast(color_pair: ColorPair) -> ContrastResult:
    """
    Verify if a color pair meets WCAG contrast requirements.

    Args:
        color_pair: ColorPair to verify

    Returns:
        ContrastResult with verification details
    """
    contrast_ratio = calculate_contrast_ratio(color_pair.foreground, color_pair.background)
    required_ratio = get_required_contrast_ratio(color_pair.context)
    passes = contrast_ratio >= required_ratio

    return ContrastResult(
        color_pair=color_pair,
        contrast_ratio=contrast_ratio,
        required_ratio=required_ratio,
        passes=passes,
    )


def get_theme_color_pairs() -> List[ColorPair]:
    """
    Get all color pairs to verify for both themes.

    Returns:
        List of ColorPair objects to verify
    """
    color_pairs = []

    # Light Theme Color Pairs
    light_theme_pairs = [
        # Primary text on backgrounds
        ColorPair(
            name="Primary text on primary background",
            foreground="#111827",  # --color-text-primary
            background="#ffffff",  # --color-bg-primary
            context="normal-text",
            theme="light",
        ),
        ColorPair(
            name="Primary text on secondary background",
            foreground="#111827",
            background="#f9fafb",  # --color-bg-secondary
            context="normal-text",
            theme="light",
        ),
        ColorPair(
            name="Primary text on tertiary background",
            foreground="#111827",
            background="#f3f4f6",  # --color-bg-tertiary
            context="normal-text",
            theme="light",
        ),
        # Secondary text on backgrounds
        ColorPair(
            name="Secondary text on primary background",
            foreground="#6b7280",  # --color-text-secondary
            background="#ffffff",
            context="normal-text",
            theme="light",
        ),
        ColorPair(
            name="Secondary text on secondary background",
            foreground="#6b7280",
            background="#f9fafb",
            context="normal-text",
            theme="light",
        ),
        # Links
        ColorPair(
            name="Link text on primary background",
            foreground="#2563eb",  # --color-text-link
            background="#ffffff",
            context="normal-text",
            theme="light",
        ),
        # Buttons
        ColorPair(
            name="Primary button text",
            foreground="#ffffff",  # --color-button-primary-text
            background="#2563eb",  # --color-button-primary-bg
            context="normal-text",
            theme="light",
        ),
        ColorPair(
            name="Secondary button text",
            foreground="#374151",  # --color-button-secondary-text
            background="#ffffff",  # --color-button-secondary-bg
            context="normal-text",
            theme="light",
        ),
        # Status colors on light backgrounds
        ColorPair(
            name="Success text on light background",
            foreground="#047857",  # --color-success-dark
            background="#d1fae5",  # --color-success-light
            context="normal-text",
            theme="light",
        ),
        ColorPair(
            name="Warning text on light background",
            foreground="#b45309",  # --color-warning-dark
            background="#fef3c7",  # --color-warning-light
            context="normal-text",
            theme="light",
        ),
        ColorPair(
            name="Danger text on light background",
            foreground="#b91c1c",  # --color-danger-dark
            background="#fee2e2",  # --color-danger-light
            context="normal-text",
            theme="light",
        ),
        # Navigation
        ColorPair(
            name="Navigation text",
            foreground="#111827",  # --color-nav-text
            background="#ffffff",  # --color-nav-bg
            context="normal-text",
            theme="light",
        ),
        # Table headers
        ColorPair(
            name="Table header text",
            foreground="#111827",
            background="#f9fafb",  # --color-table-header-bg
            context="normal-text",
            theme="light",
        ),
        # Tooltips
        ColorPair(
            name="Tooltip text",
            foreground="#ffffff",  # --color-tooltip-text
            background="#1f2937",  # --color-tooltip-bg
            context="normal-text",
            theme="light",
        ),
        # Badges
        ColorPair(
            name="Badge text",
            foreground="#374151",  # --color-badge-text
            background="#f3f4f6",  # --color-badge-bg
            context="normal-text",
            theme="light",
        ),
    ]

    # Dark Theme Color Pairs
    dark_theme_pairs = [
        # Primary text on backgrounds
        ColorPair(
            name="Primary text on primary background",
            foreground="#f9fafb",  # --color-text-primary
            background="#111827",  # --color-bg-primary
            context="normal-text",
            theme="dark",
        ),
        ColorPair(
            name="Primary text on secondary background",
            foreground="#f9fafb",
            background="#1f2937",  # --color-bg-secondary
            context="normal-text",
            theme="dark",
        ),
        ColorPair(
            name="Primary text on tertiary background",
            foreground="#f9fafb",
            background="#374151",  # --color-bg-tertiary
            context="normal-text",
            theme="dark",
        ),
        # Secondary text on backgrounds
        ColorPair(
            name="Secondary text on primary background",
            foreground="#d1d5db",  # --color-text-secondary
            background="#111827",
            context="normal-text",
            theme="dark",
        ),
        ColorPair(
            name="Secondary text on secondary background",
            foreground="#d1d5db",
            background="#1f2937",
            context="normal-text",
            theme="dark",
        ),
        # Links
        ColorPair(
            name="Link text on primary background",
            foreground="#60a5fa",  # --color-text-link
            background="#111827",
            context="normal-text",
            theme="dark",
        ),
        # Buttons
        ColorPair(
            name="Primary button text",
            foreground="#ffffff",  # --color-button-primary-text
            background="#2563eb",  # --color-button-primary-bg
            context="normal-text",
            theme="dark",
        ),
        ColorPair(
            name="Secondary button text",
            foreground="#f9fafb",  # --color-button-secondary-text
            background="#374151",  # --color-button-secondary-bg
            context="normal-text",
            theme="dark",
        ),
        # Status colors on dark backgrounds
        ColorPair(
            name="Success text on dark background",
            foreground="#6ee7b7",  # --color-success-dark
            background="#064e3b",  # --color-success-light
            context="normal-text",
            theme="dark",
        ),
        ColorPair(
            name="Warning text on dark background",
            foreground="#fcd34d",  # --color-warning-dark
            background="#78350f",  # --color-warning-light
            context="normal-text",
            theme="dark",
        ),
        ColorPair(
            name="Danger text on dark background",
            foreground="#fca5a5",  # --color-danger-dark
            background="#7f1d1d",  # --color-danger-light
            context="normal-text",
            theme="dark",
        ),
        # Navigation
        ColorPair(
            name="Navigation text",
            foreground="#f9fafb",  # --color-nav-text
            background="#1f2937",  # --color-nav-bg
            context="normal-text",
            theme="dark",
        ),
        # Table headers
        ColorPair(
            name="Table header text",
            foreground="#f9fafb",
            background="#1f2937",  # --color-table-header-bg
            context="normal-text",
            theme="dark",
        ),
        # Tooltips
        ColorPair(
            name="Tooltip text",
            foreground="#111827",  # --color-tooltip-text
            background="#f3f4f6",  # --color-tooltip-bg
            context="normal-text",
            theme="dark",
        ),
        # Badges
        ColorPair(
            name="Badge text",
            foreground="#f3f4f6",  # --color-badge-text
            background="#374151",  # --color-badge-bg
            context="normal-text",
            theme="dark",
        ),
    ]

    color_pairs.extend(light_theme_pairs)
    color_pairs.extend(dark_theme_pairs)

    return color_pairs


def verify_all_color_pairs() -> Tuple[List[ContrastResult], List[ContrastResult]]:
    """
    Verify all color pairs for WCAG compliance.

    Returns:
        Tuple of (passing_results, failing_results)
    """
    color_pairs = get_theme_color_pairs()
    results = [verify_contrast(pair) for pair in color_pairs]

    passing = [r for r in results if r.passes]
    failing = [r for r in results if not r.passes]

    return passing, failing


def generate_compliance_report() -> str:
    """
    Generate a comprehensive WCAG compliance report.

    Returns:
        Formatted report string
    """
    passing, failing = verify_all_color_pairs()
    total = len(passing) + len(failing)

    report = []
    report.append("=" * 80)
    report.append("WCAG 2.1 Level AA Compliance Report")
    report.append("=" * 80)
    report.append("")
    report.append(f"Total color pairs tested: {total}")
    report.append(f"Passing: {len(passing)} ({len(passing)/total*100:.1f}%)")
    report.append(f"Failing: {len(failing)} ({len(failing)/total*100:.1f}%)")
    report.append("")

    if failing:
        report.append("FAILING COLOR PAIRS:")
        report.append("-" * 80)
        for result in failing:
            report.append(str(result))
        report.append("")

    report.append("PASSING COLOR PAIRS:")
    report.append("-" * 80)
    for result in passing:
        report.append(str(result))
    report.append("")

    report.append("=" * 80)
    report.append("WCAG 2.1 Level AA Requirements:")
    report.append("- Normal text: 4.5:1 contrast ratio minimum")
    report.append("- Large text: 3:1 contrast ratio minimum")
    report.append("- UI components: 3:1 contrast ratio minimum")
    report.append("=" * 80)

    return "\n".join(report)


if __name__ == "__main__":
    # Generate and print compliance report
    report = generate_compliance_report()
    print(report)

    # Exit with error code if any tests fail
    _, failing = verify_all_color_pairs()
    if failing:
        exit(1)
