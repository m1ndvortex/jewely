"""
Tests for WCAG 2.1 Level AA Accessibility Features
Per Requirement 29
"""

from django.contrib.auth import get_user_model
from django.template import Context, Template
from django.test import TestCase

import pytest

from apps.core.wcag_compliance import (
    ColorPair,
    calculate_contrast_ratio,
    hex_to_rgb,
    rgb_to_relative_luminance,
    verify_contrast,
)

User = get_user_model()


class WCAGContrastTestCase(TestCase):
    """Test WCAG color contrast compliance"""

    def test_hex_to_rgb_conversion(self):
        """Test hex color to RGB conversion"""
        # Test 6-digit hex
        self.assertEqual(hex_to_rgb("#ffffff"), (255, 255, 255))
        self.assertEqual(hex_to_rgb("#000000"), (0, 0, 0))
        self.assertEqual(hex_to_rgb("#2563eb"), (37, 99, 235))

        # Test 3-digit hex
        self.assertEqual(hex_to_rgb("#fff"), (255, 255, 255))
        self.assertEqual(hex_to_rgb("#000"), (0, 0, 0))

    def test_relative_luminance_calculation(self):
        """Test relative luminance calculation"""
        # White should have luminance of 1
        luminance_white = rgb_to_relative_luminance(255, 255, 255)
        self.assertAlmostEqual(luminance_white, 1.0, places=2)

        # Black should have luminance of 0
        luminance_black = rgb_to_relative_luminance(0, 0, 0)
        self.assertAlmostEqual(luminance_black, 0.0, places=2)

    def test_contrast_ratio_calculation(self):
        """Test contrast ratio calculation"""
        # Black on white should be 21:1 (maximum)
        ratio = calculate_contrast_ratio("#000000", "#ffffff")
        self.assertAlmostEqual(ratio, 21.0, places=1)

        # White on white should be 1:1 (minimum)
        ratio = calculate_contrast_ratio("#ffffff", "#ffffff")
        self.assertAlmostEqual(ratio, 1.0, places=1)

    def test_light_theme_contrast_ratios(self):
        """Test that light theme colors meet WCAG AA standards"""
        # Primary text on white background
        ratio = calculate_contrast_ratio("#111827", "#ffffff")
        self.assertGreaterEqual(ratio, 4.5, "Primary text must have 4.5:1 contrast")

        # Secondary text on white background
        ratio = calculate_contrast_ratio("#6b7280", "#ffffff")
        self.assertGreaterEqual(ratio, 4.5, "Secondary text must have 4.5:1 contrast")

        # Link text on white background
        ratio = calculate_contrast_ratio("#2563eb", "#ffffff")
        self.assertGreaterEqual(ratio, 4.5, "Link text must have 4.5:1 contrast")

    def test_dark_theme_contrast_ratios(self):
        """Test that dark theme colors meet WCAG AA standards"""
        # Primary text on dark background
        ratio = calculate_contrast_ratio("#f9fafb", "#111827")
        self.assertGreaterEqual(ratio, 4.5, "Primary text must have 4.5:1 contrast")

        # Secondary text on dark background
        ratio = calculate_contrast_ratio("#d1d5db", "#111827")
        self.assertGreaterEqual(ratio, 4.5, "Secondary text must have 4.5:1 contrast")

        # Link text on dark background
        ratio = calculate_contrast_ratio("#60a5fa", "#111827")
        self.assertGreaterEqual(ratio, 4.5, "Link text must have 4.5:1 contrast")

    def test_button_contrast_ratios(self):
        """Test that button colors meet WCAG AA standards"""
        # Primary button text on primary button background
        ratio = calculate_contrast_ratio("#ffffff", "#2563eb")
        self.assertGreaterEqual(ratio, 4.5, "Button text must have 4.5:1 contrast")

    def test_verify_contrast_function(self):
        """Test the verify_contrast function"""
        # Create a color pair that should pass
        color_pair = ColorPair(
            name="Test pair",
            foreground="#111827",
            background="#ffffff",
            context="normal-text",
            theme="light",
        )

        result = verify_contrast(color_pair)
        self.assertTrue(result.passes, "High contrast pair should pass")
        self.assertGreaterEqual(result.contrast_ratio, 4.5)

        # Create a color pair that should fail
        color_pair_fail = ColorPair(
            name="Test pair fail",
            foreground="#cccccc",
            background="#ffffff",
            context="normal-text",
            theme="light",
        )

        result_fail = verify_contrast(color_pair_fail)
        self.assertFalse(result_fail.passes, "Low contrast pair should fail")


class AccessibilityTemplateTagsTestCase(TestCase):
    """Test accessibility template tags"""

    def test_skip_link_tag(self):
        """Test skip link generation"""
        template = Template(
            "{% load accessibility_tags %}{% skip_link 'main-content' 'Skip to main' %}"
        )
        rendered = template.render(Context({}))

        self.assertIn('href="#main-content"', rendered)
        self.assertIn("Skip to main", rendered)
        self.assertIn("skip-link", rendered)

    def test_aria_label_tag(self):
        """Test ARIA label generation"""
        template = Template('{% load accessibility_tags %}{% aria_describedby "input" "help" %}')
        rendered = template.render(Context({}))

        self.assertIn('aria-describedby="help"', rendered)

    def test_aria_live_tag(self):
        """Test ARIA live region generation"""
        template = Template('{% load accessibility_tags %}{% aria_live "assertive" %}')
        rendered = template.render(Context({}))

        self.assertIn('aria-live="assertive"', rendered)

    def test_aria_expanded_tag(self):
        """Test ARIA expanded attribute"""
        template = Template("{% load accessibility_tags %}{% aria_expanded True %}")
        rendered = template.render(Context({}))

        self.assertIn('aria-expanded="true"', rendered)

        template = Template("{% load accessibility_tags %}{% aria_expanded False %}")
        rendered = template.render(Context({}))

        self.assertIn('aria-expanded="false"', rendered)

    def test_sr_only_tag(self):
        """Test screen reader only text"""
        template = Template('{% load accessibility_tags %}{% sr_only "Hidden text" %}')
        rendered = template.render(Context({}))

        self.assertIn("sr-only", rendered)
        self.assertIn("Hidden text", rendered)

    def test_landmark_tag(self):
        """Test landmark generation"""
        template = Template('{% load accessibility_tags %}{% landmark "navigation" "Main nav" %}')
        rendered = template.render(Context({}))

        self.assertIn('role="navigation"', rendered)
        self.assertIn('aria-label="Main nav"', rendered)

    def test_accessible_button_tag(self):
        """Test accessible button generation"""
        template = Template(
            '{% load accessibility_tags %}{% accessible_button "Submit" button_type="submit" %}'
        )
        rendered = template.render(Context({}))

        self.assertIn('type="submit"', rendered)
        self.assertIn("Submit", rendered)
        self.assertIn("<button", rendered)

    def test_accessible_link_tag(self):
        """Test accessible link generation"""
        template = Template(
            '{% load accessibility_tags %}{% accessible_link "/test/" "Test Link" %}'
        )
        rendered = template.render(Context({}))

        self.assertIn('href="/test/"', rendered)
        self.assertIn("Test Link", rendered)

    def test_external_link_indicator(self):
        """Test external link with new tab indicator"""
        template = Template(
            '{% load accessibility_tags %}{% accessible_link "https://example.com" "External" external=True %}'
        )
        rendered = template.render(Context({}))

        self.assertIn('target="_blank"', rendered)
        self.assertIn('rel="noopener noreferrer"', rendered)
        self.assertIn("opens in new tab", rendered)


class SemanticHTMLTestCase(TestCase):
    """Test semantic HTML structure in templates"""

    def test_base_template_structure(self):
        """Test that base template has proper semantic HTML structure"""
        # Read the base template file directly
        import os

        from django.conf import settings

        base_template_path = os.path.join(settings.BASE_DIR, "templates", "base.html")

        with open(base_template_path, "r") as f:
            content = f.read()

        # Check for skip link template tag usage
        self.assertIn("skip_link", content)
        self.assertIn("Skip to main content", content)

        # Check for semantic nav element
        self.assertIn("<nav", content)
        self.assertIn('role="navigation"', content)
        self.assertIn("aria-label=", content)

        # Check for semantic main element
        self.assertIn("<main", content)
        self.assertIn('role="main"', content)
        self.assertIn('id="main-content"', content)


class KeyboardAccessibilityTestCase(TestCase):
    """Test keyboard accessibility features"""

    def test_no_div_buttons_in_templates(self):
        """Test that templates don't use divs as buttons (anti-pattern)"""
        # Check base template for anti-patterns
        import os
        import re

        from django.conf import settings

        base_template_path = os.path.join(settings.BASE_DIR, "templates", "base.html")

        with open(base_template_path, "r") as f:
            content = f.read()

        # Check that we're not using divs as buttons (anti-pattern)
        div_buttons = re.findall(r"<div[^>]*onclick[^>]*>", content)
        self.assertEqual(
            len(div_buttons),
            0,
            "Found divs with onclick in base template - use proper button elements instead",
        )


class FocusIndicatorTestCase(TestCase):
    """Test focus indicator styles"""

    def test_accessibility_css_exists(self):
        """Test that accessibility CSS file exists and is loaded"""
        import os

        from django.conf import settings

        css_path = os.path.join(settings.BASE_DIR, "static", "css", "accessibility.css")
        self.assertTrue(os.path.exists(css_path), "Accessibility CSS file should exist")

    def test_accessibility_css_has_focus_styles(self):
        """Test that accessibility CSS includes focus indicator styles"""
        import os

        from django.conf import settings

        css_path = os.path.join(settings.BASE_DIR, "static", "css", "accessibility.css")

        with open(css_path, "r") as f:
            css_content = f.read()

        # Check for focus-visible styles
        self.assertIn(":focus-visible", css_content)
        self.assertIn("outline:", css_content)

        # Check for skip-link styles
        self.assertIn(".skip-link", css_content)

        # Check for sr-only styles
        self.assertIn(".sr-only", css_content)


@pytest.mark.django_db
class AccessibilityIntegrationTest:
    """Integration tests for accessibility features"""

    def test_wcag_compliance_report_generation(self):
        """Test that WCAG compliance report can be generated"""
        from apps.core.wcag_compliance import generate_compliance_report

        report = generate_compliance_report()

        assert "WCAG 2.1 Level AA Compliance Report" in report
        assert "Total color pairs tested:" in report
        assert "Passing:" in report

    def test_all_color_pairs_pass_wcag_aa(self):
        """Test that all defined color pairs pass WCAG AA standards"""
        from apps.core.wcag_compliance import verify_all_color_pairs

        passing, failing = verify_all_color_pairs()

        # All color pairs should pass
        assert (
            len(failing) == 0
        ), f"Found {len(failing)} failing color pairs: {[str(f) for f in failing]}"
        assert len(passing) > 0, "Should have at least some passing color pairs"
