"""
Accessibility Template Tags for WCAG 2.1 Level AA Compliance
Per Requirement 29

This module provides template tags and filters to help create
accessible HTML content that meets WCAG 2.1 Level AA standards.
"""

import re

from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def aria_label(value, label_text=None):
    """
    Add ARIA label to a value.

    Usage:
        {{ "Button text"|aria_label:"Descriptive label" }}
    """
    if label_text:
        return mark_safe(f'aria-label="{label_text}"')
    return ""


@register.simple_tag
def skip_link(target_id, text="Skip to main content"):
    """
    Generate a skip navigation link for keyboard users.

    Usage:
        {% skip_link "main-content" "Skip to main content" %}

    Args:
        target_id: ID of the target element to skip to
        text: Link text (default: "Skip to main content")

    Returns:
        HTML for skip link
    """
    return format_html(
        '<a href="#{}" class="skip-link sr-only focus:not-sr-only focus:absolute focus:top-0 focus:left-0 '
        'focus:z-50 focus:bg-blue-600 focus:text-white focus:px-4 focus:py-2 focus:m-2 focus:rounded">{}</a>',
        target_id,
        text,
    )


@register.simple_tag
def aria_describedby(element_id, description_id):
    """
    Generate aria-describedby attribute.

    Usage:
        {% aria_describedby "input-field" "help-text" %}

    Returns:
        aria-describedby attribute
    """
    return format_html('aria-describedby="{}"', description_id)


@register.simple_tag
def aria_labelledby(element_id, label_id):
    """
    Generate aria-labelledby attribute.

    Usage:
        {% aria_labelledby "dialog" "dialog-title" %}

    Returns:
        aria-labelledby attribute
    """
    return format_html('aria-labelledby="{}"', label_id)


@register.simple_tag
def aria_live(politeness="polite"):
    """
    Generate aria-live attribute for dynamic content.

    Usage:
        {% aria_live "assertive" %}

    Args:
        politeness: "polite", "assertive", or "off"

    Returns:
        aria-live attribute
    """
    valid_values = ["polite", "assertive", "off"]
    if politeness not in valid_values:
        politeness = "polite"
    return format_html('aria-live="{}"', politeness)


@register.simple_tag
def aria_expanded(is_expanded):
    """
    Generate aria-expanded attribute for expandable elements.

    Usage:
        {% aria_expanded True %}
        {% aria_expanded False %}

    Returns:
        aria-expanded attribute
    """
    return format_html('aria-expanded="{}"', "true" if is_expanded else "false")


@register.simple_tag
def aria_hidden(is_hidden):
    """
    Generate aria-hidden attribute.

    Usage:
        {% aria_hidden True %}

    Returns:
        aria-hidden attribute
    """
    return format_html('aria-hidden="{}"', "true" if is_hidden else "false")


@register.simple_tag
def aria_current(current_type="page"):
    """
    Generate aria-current attribute for navigation.

    Usage:
        {% aria_current "page" %}
        {% aria_current "step" %}

    Args:
        current_type: "page", "step", "location", "date", "time", or "true"

    Returns:
        aria-current attribute
    """
    valid_types = ["page", "step", "location", "date", "time", "true"]
    if current_type not in valid_types:
        current_type = "page"
    return format_html('aria-current="{}"', current_type)


@register.simple_tag
def role(role_name):
    """
    Generate role attribute.

    Usage:
        {% role "navigation" %}
        {% role "main" %}

    Returns:
        role attribute
    """
    return format_html('role="{}"', role_name)


@register.filter
def add_alt_text(image_html, alt_text):
    """
    Add alt text to an image tag if it doesn't have one.

    Usage:
        {{ image_tag|add_alt_text:"Description of image" }}

    Args:
        image_html: HTML string containing img tag
        alt_text: Alt text to add

    Returns:
        Image HTML with alt text
    """
    if not image_html or not alt_text:
        return image_html

    # Check if alt attribute already exists
    if "alt=" in str(image_html):
        return image_html

    # Add alt attribute before the closing >
    modified = str(image_html).replace(">", f' alt="{alt_text}">', 1)
    return mark_safe(modified)


@register.simple_tag
def accessible_button(text, button_type="button", css_class="", aria_label=None, **kwargs):
    """
    Generate an accessible button with proper ARIA attributes.

    Usage:
        {% accessible_button "Submit" button_type="submit" css_class="btn-primary" %}
        {% accessible_button "Close" aria_label="Close dialog" %}

    Args:
        text: Button text
        button_type: "button", "submit", or "reset"
        css_class: CSS classes to apply
        aria_label: Optional ARIA label if button text is not descriptive
        **kwargs: Additional attributes (e.g., id="my-button")

    Returns:
        HTML for accessible button
    """
    attrs = []
    attrs.append(f'type="{button_type}"')

    if css_class:
        attrs.append(f'class="{css_class}"')

    if aria_label:
        attrs.append(f'aria-label="{aria_label}"')

    for key, value in kwargs.items():
        attrs.append(f'{key}="{value}"')

    attrs_str = " ".join(attrs)
    return format_html("<button {}>{}</button>", mark_safe(attrs_str), text)


@register.simple_tag
def accessible_link(url, text, css_class="", aria_label=None, external=False, **kwargs):
    """
    Generate an accessible link with proper ARIA attributes.

    Usage:
        {% accessible_link "/dashboard/" "Dashboard" %}
        {% accessible_link "https://example.com" "External Site" external=True %}

    Args:
        url: Link URL
        text: Link text
        css_class: CSS classes to apply
        aria_label: Optional ARIA label if link text is not descriptive
        external: Whether link opens in new tab
        **kwargs: Additional attributes

    Returns:
        HTML for accessible link
    """
    attrs = []
    attrs.append(f'href="{url}"')

    if css_class:
        attrs.append(f'class="{css_class}"')

    if aria_label:
        attrs.append(f'aria-label="{aria_label}"')

    if external:
        attrs.append('target="_blank"')
        attrs.append('rel="noopener noreferrer"')
        # Add visual indicator for screen readers
        text = f'{text} <span class="sr-only">(opens in new tab)</span>'

    for key, value in kwargs.items():
        attrs.append(f'{key}="{value}"')

    attrs_str = " ".join(attrs)
    return format_html("<a {}>{}</a>", mark_safe(attrs_str), mark_safe(text))


@register.simple_tag
def keyboard_shortcut(key, description):
    """
    Generate keyboard shortcut hint for accessibility.

    Usage:
        {% keyboard_shortcut "Ctrl+S" "Save" %}

    Returns:
        HTML for keyboard shortcut hint
    """
    return format_html(
        '<span class="keyboard-shortcut" aria-label="Keyboard shortcut: {}">'
        '<kbd class="px-2 py-1 text-xs font-semibold text-gray-800 bg-gray-100 border border-gray-200 rounded-lg '
        'dark:bg-gray-600 dark:text-gray-100 dark:border-gray-500">{}</kbd>'
        '<span class="sr-only">{}</span>'
        "</span>",
        f"{key} for {description}",
        key,
        description,
    )


@register.simple_tag
def focus_trap(container_id):
    """
    Generate JavaScript for focus trap in modals/dialogs.

    Usage:
        {% focus_trap "modal-dialog" %}

    Returns:
        JavaScript to trap focus within container
    """
    script = f"""
    <script>
    (function() {{
        const container = document.getElementById('{container_id}');
        if (!container) return;

        const focusableElements = container.querySelectorAll(
            'a[href], button:not([disabled]), textarea:not([disabled]), ' +
            'input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])'
        );

        if (focusableElements.length === 0) return;

        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];

        container.addEventListener('keydown', function(e) {{
            if (e.key !== 'Tab') return;

            if (e.shiftKey) {{
                if (document.activeElement === firstElement) {{
                    e.preventDefault();
                    lastElement.focus();
                }}
            }} else {{
                if (document.activeElement === lastElement) {{
                    e.preventDefault();
                    firstElement.focus();
                }}
            }}
        }});

        // Focus first element when container is shown
        firstElement.focus();
    }})();
    </script>
    """
    return mark_safe(script)


@register.simple_tag
def sr_only(text):
    """
    Generate screen reader only text.

    Usage:
        {% sr_only "Additional context for screen readers" %}

    Returns:
        HTML with sr-only class
    """
    return format_html('<span class="sr-only">{}</span>', text)


@register.simple_tag
def landmark(landmark_type, label=None):
    """
    Generate ARIA landmark attributes.

    Usage:
        {% landmark "navigation" "Main navigation" %}
        {% landmark "main" %}

    Args:
        landmark_type: Type of landmark (navigation, main, complementary, etc.)
        label: Optional aria-label for multiple landmarks of same type

    Returns:
        role and aria-label attributes
    """
    attrs = [f'role="{landmark_type}"']
    if label:
        attrs.append(f'aria-label="{label}"')
    return mark_safe(" ".join(attrs))


@register.filter
def ensure_heading_hierarchy(html_content):
    """
    Validate heading hierarchy in HTML content.
    This is a development helper - logs warnings if hierarchy is broken.

    Usage:
        {{ content|ensure_heading_hierarchy }}

    Returns:
        Original HTML (unchanged)
    """
    # Extract heading levels
    headings = re.findall(r"<h([1-6])", str(html_content))

    if headings:
        levels = [int(h) for h in headings]
        prev_level = 0

        for level in levels:
            if prev_level > 0 and level > prev_level + 1:
                # Log warning in development
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(
                    f"Heading hierarchy violation: h{prev_level} followed by h{level}. "
                    f"Headings should not skip levels for accessibility."
                )
            prev_level = level

    return html_content


@register.simple_tag
def form_field_accessible(field, show_label=True, show_help=True):
    """
    Render a form field with full accessibility attributes.

    Usage:
        {% form_field_accessible form.email %}

    Args:
        field: Django form field
        show_label: Whether to show the label
        show_help: Whether to show help text

    Returns:
        HTML for accessible form field
    """
    field_id = field.auto_id or f"id_{field.name}"
    help_id = f"{field_id}_help"
    error_id = f"{field_id}_error"

    # Build aria attributes
    aria_attrs = []
    if field.help_text and show_help:
        aria_attrs.append(f'aria-describedby="{help_id}"')
    if field.errors:
        aria_attrs.append('aria-invalid="true"')
        aria_attrs.append(f'aria-describedby="{error_id}"')
    if field.field.required:
        aria_attrs.append('aria-required="true"')

    aria_str = " ".join(aria_attrs)

    # Build HTML
    html_parts = []

    # Label
    if show_label:
        required_indicator = (
            '<span class="text-red-500" aria-label="required">*</span>'
            if field.field.required
            else ""
        )
        html_parts.append(
            f'<label for="{field_id}" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">'
            f"{field.label}{required_indicator}"
            f"</label>"
        )

    # Field
    field_html = str(field)
    # Add aria attributes to the field
    if aria_str:
        field_html = field_html.replace(">", f" {aria_str}>", 1)
    html_parts.append(field_html)

    # Help text
    if field.help_text and show_help:
        html_parts.append(
            f'<p id="{help_id}" class="mt-1 text-sm text-gray-500 dark:text-gray-400">'
            f"{field.help_text}"
            f"</p>"
        )

    # Errors
    if field.errors:
        html_parts.append(
            f'<div id="{error_id}" class="mt-1 text-sm text-red-600 dark:text-red-400" role="alert">'
        )
        for error in field.errors:
            html_parts.append(f"<p>{error}</p>")
        html_parts.append("</div>")

    return mark_safe("\n".join(html_parts))
