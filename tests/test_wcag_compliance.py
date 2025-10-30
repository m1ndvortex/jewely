"""
WCAG 2.1 Level AA Compliance Tests
Per Requirements 3 and 29

Tests to verify color contrast ratios and accessibility compliance
for both light and dark themes.
"""

import pytest

from apps.core.wcag_compliance import (
    ColorPair,
    calculate_contrast_ratio,
    get_required_contrast_ratio,
    get_theme_color_pairs,
    hex_to_rgb,
    rgb_to_relative_luminance,
    verify_all_color_pairs,
    verify_contrast,
)


class TestColorConversion:
    """Test color conversion utilities"""

    def test_hex_to_rgb_6_digit(self):
        """Test conversion of 6-digit hex colors"""
        assert hex_to_rgb("#ffffff") == (255, 255, 255)
        assert hex_to_rgb("#000000") == (0, 0, 0)
        assert hex_to_rgb("#ff0000") == (255, 0, 0)
        assert hex_to_rgb("#00ff00") == (0, 255, 0)
        assert hex_to_rgb("#0000ff") == (0, 0, 255)

    def test_hex_to_rgb_3_digit(self):
        """Test conversion of 3-digit hex colors"""
        assert hex_to_rgb("#fff") == (255, 255, 255)
        assert hex_to_rgb("#000") == (0, 0, 0)
        assert hex_to_rgb("#f00") == (255, 0, 0)

    def test_hex_to_rgb_without_hash(self):
        """Test conversion without # prefix"""
        assert hex_to_rgb("ffffff") == (255, 255, 255)
        assert hex_to_rgb("000000") == (0, 0, 0)

    def test_relative_luminance_white(self):
        """Test luminance calculation for white"""
        luminance = rgb_to_relative_luminance(255, 255, 255)
        assert luminance == pytest.approx(1.0, rel=0.01)

    def test_relative_luminance_black(self):
        """Test luminance calculation for black"""
        luminance = rgb_to_relative_luminance(0, 0, 0)
        assert luminance == pytest.approx(0.0, rel=0.01)

    def test_relative_luminance_gray(self):
        """Test luminance calculation for gray"""
        luminance = rgb_to_relative_luminance(128, 128, 128)
        assert 0.2 < luminance < 0.3  # Gray should be in middle range


class TestContrastRatio:
    """Test contrast ratio calculations"""

    def test_contrast_ratio_black_white(self):
        """Test maximum contrast (black on white)"""
        ratio = calculate_contrast_ratio("#000000", "#ffffff")
        assert ratio == pytest.approx(21.0, rel=0.01)

    def test_contrast_ratio_white_black(self):
        """Test maximum contrast (white on black)"""
        ratio = calculate_contrast_ratio("#ffffff", "#000000")
        assert ratio == pytest.approx(21.0, rel=0.01)

    def test_contrast_ratio_same_color(self):
        """Test minimum contrast (same color)"""
        ratio = calculate_contrast_ratio("#ffffff", "#ffffff")
        assert ratio == pytest.approx(1.0, rel=0.01)

    def test_contrast_ratio_known_values(self):
        """Test known contrast ratios"""
        # Dark gray on white should be around 7:1
        ratio = calculate_contrast_ratio("#595959", "#ffffff")
        assert 6.5 < ratio < 7.5

        # Medium gray on white should be around 4.5:1
        ratio = calculate_contrast_ratio("#767676", "#ffffff")
        assert 4.0 < ratio < 5.0


class TestRequiredRatios:
    """Test required contrast ratio retrieval"""

    def test_normal_text_ratio(self):
        """Test required ratio for normal text"""
        assert get_required_contrast_ratio("normal-text") == 4.5

    def test_large_text_ratio(self):
        """Test required ratio for large text"""
        assert get_required_contrast_ratio("large-text") == 3.0

    def test_ui_component_ratio(self):
        """Test required ratio for UI components"""
        assert get_required_contrast_ratio("ui-component") == 3.0

    def test_unknown_context_defaults_to_normal(self):
        """Test that unknown context defaults to normal text ratio"""
        assert get_required_contrast_ratio("unknown") == 4.5


class TestColorPairVerification:
    """Test individual color pair verification"""

    def test_passing_color_pair(self):
        """Test a color pair that should pass"""
        pair = ColorPair(
            name="Black on white",
            foreground="#000000",
            background="#ffffff",
            context="normal-text",
            theme="light",
        )
        result = verify_contrast(pair)
        assert result.passes is True
        assert result.contrast_ratio > 4.5

    def test_failing_color_pair(self):
        """Test a color pair that should fail"""
        pair = ColorPair(
            name="Light gray on white",
            foreground="#cccccc",
            background="#ffffff",
            context="normal-text",
            theme="light",
        )
        result = verify_contrast(pair)
        assert result.passes is False
        assert result.contrast_ratio < 4.5

    def test_large_text_passes_with_lower_ratio(self):
        """Test that large text passes with 3:1 ratio"""
        pair = ColorPair(
            name="Medium gray on white (large text)",
            foreground="#949494",
            background="#ffffff",
            context="large-text",
            theme="light",
        )
        result = verify_contrast(pair)
        # This should pass for large text (3:1) but fail for normal text (4.5:1)
        assert result.passes is True
        assert 3.0 <= result.contrast_ratio < 4.5


class TestLightThemeCompliance:
    """Test WCAG compliance for light theme"""

    def test_light_theme_primary_text(self):
        """Test primary text on light backgrounds"""
        pair = ColorPair(
            name="Primary text on primary background",
            foreground="#111827",
            background="#ffffff",
            context="normal-text",
            theme="light",
        )
        result = verify_contrast(pair)
        assert (
            result.passes is True
        ), f"Light theme primary text failed: {result.contrast_ratio:.2f}:1"

    def test_light_theme_secondary_text(self):
        """Test secondary text on light backgrounds"""
        pair = ColorPair(
            name="Secondary text on primary background",
            foreground="#6b7280",
            background="#ffffff",
            context="normal-text",
            theme="light",
        )
        result = verify_contrast(pair)
        assert (
            result.passes is True
        ), f"Light theme secondary text failed: {result.contrast_ratio:.2f}:1"

    def test_light_theme_links(self):
        """Test link colors on light backgrounds"""
        pair = ColorPair(
            name="Link text",
            foreground="#2563eb",
            background="#ffffff",
            context="normal-text",
            theme="light",
        )
        result = verify_contrast(pair)
        assert result.passes is True, f"Light theme links failed: {result.contrast_ratio:.2f}:1"

    def test_light_theme_primary_button(self):
        """Test primary button text"""
        pair = ColorPair(
            name="Primary button",
            foreground="#ffffff",
            background="#2563eb",
            context="normal-text",
            theme="light",
        )
        result = verify_contrast(pair)
        assert (
            result.passes is True
        ), f"Light theme primary button failed: {result.contrast_ratio:.2f}:1"


class TestDarkThemeCompliance:
    """Test WCAG compliance for dark theme"""

    def test_dark_theme_primary_text(self):
        """Test primary text on dark backgrounds"""
        pair = ColorPair(
            name="Primary text on primary background",
            foreground="#f9fafb",
            background="#111827",
            context="normal-text",
            theme="dark",
        )
        result = verify_contrast(pair)
        assert (
            result.passes is True
        ), f"Dark theme primary text failed: {result.contrast_ratio:.2f}:1"

    def test_dark_theme_secondary_text(self):
        """Test secondary text on dark backgrounds"""
        pair = ColorPair(
            name="Secondary text on primary background",
            foreground="#d1d5db",
            background="#111827",
            context="normal-text",
            theme="dark",
        )
        result = verify_contrast(pair)
        assert (
            result.passes is True
        ), f"Dark theme secondary text failed: {result.contrast_ratio:.2f}:1"

    def test_dark_theme_links(self):
        """Test link colors on dark backgrounds"""
        pair = ColorPair(
            name="Link text",
            foreground="#60a5fa",
            background="#111827",
            context="normal-text",
            theme="dark",
        )
        result = verify_contrast(pair)
        assert result.passes is True, f"Dark theme links failed: {result.contrast_ratio:.2f}:1"

    def test_dark_theme_primary_button(self):
        """Test primary button text"""
        pair = ColorPair(
            name="Primary button",
            foreground="#ffffff",
            background="#2563eb",
            context="normal-text",
            theme="dark",
        )
        result = verify_contrast(pair)
        assert (
            result.passes is True
        ), f"Dark theme primary button failed: {result.contrast_ratio:.2f}:1"


class TestAllColorPairs:
    """Test all defined color pairs"""

    def test_all_color_pairs_defined(self):
        """Test that color pairs are defined for both themes"""
        pairs = get_theme_color_pairs()
        assert len(pairs) > 0, "No color pairs defined"

        light_pairs = [p for p in pairs if p.theme == "light"]
        dark_pairs = [p for p in pairs if p.theme == "dark"]

        assert len(light_pairs) > 0, "No light theme pairs defined"
        assert len(dark_pairs) > 0, "No dark theme pairs defined"

    def test_all_color_pairs_pass_wcag(self):
        """Test that all color pairs pass WCAG 2.1 Level AA"""
        passing, failing = verify_all_color_pairs()

        if failing:
            failure_details = "\n".join([str(r) for r in failing])
            pytest.fail(f"{len(failing)} color pairs failed WCAG compliance:\n{failure_details}")

        assert len(passing) > 0, "No passing color pairs found"

    def test_minimum_coverage(self):
        """Test that we have minimum coverage of color combinations"""
        pairs = get_theme_color_pairs()

        # Should have at least 10 pairs per theme
        light_pairs = [p for p in pairs if p.theme == "light"]
        dark_pairs = [p for p in pairs if p.theme == "dark"]

        assert len(light_pairs) >= 10, f"Insufficient light theme coverage: {len(light_pairs)}"
        assert len(dark_pairs) >= 10, f"Insufficient dark theme coverage: {len(dark_pairs)}"

    def test_critical_combinations_covered(self):
        """Test that critical color combinations are covered"""
        pairs = get_theme_color_pairs()
        pair_names = [p.name.lower() for p in pairs]

        # Critical combinations that must be tested
        critical = [
            "primary text",
            "secondary text",
            "link",
            "button",
            "navigation",
        ]

        for critical_name in critical:
            found = any(critical_name in name for name in pair_names)
            assert found, f"Critical combination '{critical_name}' not covered"


class TestStatusColors:
    """Test status color compliance (success, warning, danger)"""

    def test_light_theme_success_colors(self):
        """Test success colors in light theme"""
        pair = ColorPair(
            name="Success",
            foreground="#047857",
            background="#d1fae5",
            context="normal-text",
            theme="light",
        )
        result = verify_contrast(pair)
        assert (
            result.passes is True
        ), f"Light theme success colors failed: {result.contrast_ratio:.2f}:1"

    def test_light_theme_warning_colors(self):
        """Test warning colors in light theme"""
        pair = ColorPair(
            name="Warning",
            foreground="#b45309",
            background="#fef3c7",
            context="normal-text",
            theme="light",
        )
        result = verify_contrast(pair)
        assert (
            result.passes is True
        ), f"Light theme warning colors failed: {result.contrast_ratio:.2f}:1"

    def test_light_theme_danger_colors(self):
        """Test danger colors in light theme"""
        pair = ColorPair(
            name="Danger",
            foreground="#b91c1c",
            background="#fee2e2",
            context="normal-text",
            theme="light",
        )
        result = verify_contrast(pair)
        assert (
            result.passes is True
        ), f"Light theme danger colors failed: {result.contrast_ratio:.2f}:1"

    def test_dark_theme_success_colors(self):
        """Test success colors in dark theme"""
        pair = ColorPair(
            name="Success",
            foreground="#6ee7b7",
            background="#064e3b",
            context="normal-text",
            theme="dark",
        )
        result = verify_contrast(pair)
        assert (
            result.passes is True
        ), f"Dark theme success colors failed: {result.contrast_ratio:.2f}:1"

    def test_dark_theme_warning_colors(self):
        """Test warning colors in dark theme"""
        pair = ColorPair(
            name="Warning",
            foreground="#fcd34d",
            background="#78350f",
            context="normal-text",
            theme="dark",
        )
        result = verify_contrast(pair)
        assert (
            result.passes is True
        ), f"Dark theme warning colors failed: {result.contrast_ratio:.2f}:1"

    def test_dark_theme_danger_colors(self):
        """Test danger colors in dark theme"""
        pair = ColorPair(
            name="Danger",
            foreground="#fca5a5",
            background="#7f1d1d",
            context="normal-text",
            theme="dark",
        )
        result = verify_contrast(pair)
        assert (
            result.passes is True
        ), f"Dark theme danger colors failed: {result.contrast_ratio:.2f}:1"


class TestComplianceReport:
    """Test compliance report generation"""

    def test_report_generation(self):
        """Test that compliance report can be generated"""
        from apps.core.wcag_compliance import generate_compliance_report

        report = generate_compliance_report()
        assert len(report) > 0
        assert "WCAG 2.1 Level AA Compliance Report" in report
        assert "Total color pairs tested:" in report

    def test_report_includes_statistics(self):
        """Test that report includes pass/fail statistics"""
        from apps.core.wcag_compliance import generate_compliance_report

        report = generate_compliance_report()
        assert "Passing:" in report
        assert "Failing:" in report

    def test_report_includes_requirements(self):
        """Test that report includes WCAG requirements"""
        from apps.core.wcag_compliance import generate_compliance_report

        report = generate_compliance_report()
        assert "4.5:1" in report
        assert "3:1" in report
        assert "Normal text" in report
        assert "Large text" in report
