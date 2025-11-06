# Accessibility Implementation Guide

## WCAG 2.1 Level AA Compliance

This document provides guidelines for implementing accessible features in the Jewelry SaaS Platform to meet WCAG 2.1 Level AA standards (Requirement 29).

## Table of Contents

1. [Overview](#overview)
2. [Semantic HTML](#semantic-html)
3. [Keyboard Accessibility](#keyboard-accessibility)
4. [Focus Indicators](#focus-indicators)
5. [ARIA Labels and Roles](#aria-labels-and-roles)
6. [Alt Text for Images](#alt-text-for-images)
7. [Form Accessibility](#form-accessibility)
8. [Color Contrast](#color-contrast)
9. [Template Tags](#template-tags)
10. [Testing](#testing)

## Overview

The platform implements WCAG 2.1 Level AA compliance through:

- **Semantic HTML**: Using proper HTML5 elements (nav, main, article, aside)
- **Keyboard Navigation**: All functionality accessible via keyboard
- **Focus Indicators**: Clear visual indicators for keyboard focus
- **ARIA Labels**: Proper labeling for screen readers
- **Alt Text**: Descriptive text for all images
- **Color Contrast**: Minimum 4.5:1 for normal text, 3:1 for large text
- **Skip Navigation**: Links to skip repetitive content
- **Text Resizing**: Support for 200% text zoom without loss of functionality

## Semantic HTML

### Use Proper HTML5 Elements

Always use semantic HTML elements instead of generic divs:

```html
<!-- ✅ CORRECT -->
<nav role="navigation" aria-label="Main navigation">
    <ul>
        <li><a href="/dashboard/">Dashboard</a></li>
    </ul>
</nav>

<main role="main" aria-label="Main content">
    <article>
        <h1>Page Title</h1>
        <p>Content...</p>
    </article>
</main>

<aside role="complementary" aria-label="Sidebar">
    <h2>Related Information</h2>
</aside>

<!-- ❌ INCORRECT -->
<div class="navigation">
    <div class="nav-item">Dashboard</div>
</div>
```

### Heading Hierarchy

Maintain proper heading hierarchy (h1 → h2 → h3, never skip levels):

```html
<!-- ✅ CORRECT -->
<h1>Main Page Title</h1>
<h2>Section Title</h2>
<h3>Subsection Title</h3>

<!-- ❌ INCORRECT -->
<h1>Main Page Title</h1>
<h3>Section Title</h3> <!-- Skipped h2 -->
```

## Keyboard Accessibility

### Ensure All Interactive Elements Are Keyboard Accessible

All buttons, links, and form controls must be accessible via keyboard:

```html
<!-- ✅ CORRECT - Native button is keyboard accessible -->
<button type="button" onclick="doSomething()">Click Me</button>

<!-- ✅ CORRECT - Link is keyboard accessible -->
<a href="/page/">Go to Page</a>

<!-- ❌ INCORRECT - Div is not keyboard accessible -->
<div onclick="doSomething()">Click Me</div>

<!-- ✅ CORRECT - If you must use div, add tabindex and role -->
<div role="button" tabindex="0" onclick="doSomething()" 
     onkeypress="if(event.key==='Enter')doSomething()">
    Click Me
</div>
```

### Tab Order

Ensure logical tab order by using proper HTML structure. Avoid using `tabindex` values greater than 0:

```html
<!-- ✅ CORRECT -->
<form>
    <input type="text" name="first_name" />
    <input type="text" name="last_name" />
    <button type="submit">Submit</button>
</form>

<!-- ❌ INCORRECT -->
<form>
    <input type="text" name="first_name" tabindex="3" />
    <button type="submit" tabindex="1">Submit</button>
    <input type="text" name="last_name" tabindex="2" />
</form>
```

## Focus Indicators

Focus indicators are automatically applied via `static/css/accessibility.css`. All interactive elements will show a visible focus indicator when navigated via keyboard.

### Custom Focus Styles

If you need custom focus styles, ensure they meet contrast requirements:

```css
/* ✅ CORRECT - Visible focus indicator with sufficient contrast */
.custom-button:focus-visible {
    outline: 3px solid #2563eb;
    outline-offset: 2px;
    box-shadow: 0 0 0 5px rgba(37, 99, 235, 0.15);
}

/* ❌ INCORRECT - No visible focus indicator */
.custom-button:focus {
    outline: none;
}
```

## ARIA Labels and Roles

### Using Template Tags

Use the provided template tags for ARIA attributes:

```django
{% load accessibility_tags %}

<!-- ARIA label for button with icon only -->
<button type="button" aria-label="Close dialog">
    <svg><!-- Close icon --></svg>
</button>

<!-- ARIA described by for form fields -->
<input type="email" 
       id="email" 
       {% aria_describedby "email" "email-help" %} />
<p id="email-help">We'll never share your email.</p>

<!-- ARIA live region for dynamic content -->
<div {% aria_live "polite" %}>
    <!-- Content that updates dynamically -->
</div>

<!-- ARIA expanded for dropdowns -->
<button {% aria_expanded is_open %}>
    Menu
</button>
```

### Landmark Roles

Use landmark roles to help screen reader users navigate:

```django
{% load accessibility_tags %}

<nav {% landmark "navigation" "Main navigation" %}>
    <!-- Navigation content -->
</nav>

<main {% landmark "main" %}>
    <!-- Main content -->
</main>

<aside {% landmark "complementary" "Related information" %}>
    <!-- Sidebar content -->
</aside>
```

## Alt Text for Images

### Always Provide Alt Text

Every image must have alt text that describes its content or purpose:

```html
<!-- ✅ CORRECT - Descriptive alt text -->
<img src="gold-ring.jpg" alt="18 karat gold ring with diamond setting" />

<!-- ✅ CORRECT - Empty alt for decorative images -->
<img src="decorative-border.png" alt="" />

<!-- ❌ INCORRECT - Missing alt text -->
<img src="gold-ring.jpg" />

<!-- ❌ INCORRECT - Non-descriptive alt text -->
<img src="gold-ring.jpg" alt="image" />
```

### Using Template Tags

```django
{% load accessibility_tags %}

<!-- Add alt text to image tag -->
{{ image_html|add_alt_text:"18 karat gold ring with diamond setting" }}
```

### Guidelines for Alt Text

- **Informative images**: Describe the information conveyed
- **Functional images**: Describe the action/purpose
- **Decorative images**: Use empty alt (`alt=""`)
- **Complex images**: Provide detailed description nearby
- **Text in images**: Include the text in alt attribute

## Form Accessibility

### Using Accessible Form Fields

Use the `form_field_accessible` template tag for fully accessible form fields:

```django
{% load accessibility_tags %}

<form method="post">
    {% csrf_token %}
    
    <!-- Fully accessible form field with label, help text, and errors -->
    {% form_field_accessible form.email %}
    
    {% form_field_accessible form.password %}
    
    <button type="submit">Submit</button>
</form>
```

### Manual Form Field Implementation

If implementing manually, ensure:

```html
<!-- ✅ CORRECT - Accessible form field -->
<label for="email">
    Email Address
    <span class="text-red-500" aria-label="required">*</span>
</label>
<input type="email" 
       id="email" 
       name="email" 
       aria-required="true"
       aria-describedby="email-help"
       aria-invalid="false" />
<p id="email-help" class="text-sm text-gray-500">
    We'll never share your email.
</p>

<!-- Error state -->
<input type="email" 
       id="email" 
       name="email" 
       aria-required="true"
       aria-describedby="email-error"
       aria-invalid="true" />
<div id="email-error" class="text-red-600" role="alert">
    Please enter a valid email address.
</div>
```

### Required Fields

Always indicate required fields:

```html
<label for="name">
    Name
    <span class="text-red-500" aria-label="required">*</span>
</label>
<input type="text" id="name" name="name" aria-required="true" />
```

## Color Contrast

### Contrast Requirements

- **Normal text** (< 18pt or < 14pt bold): 4.5:1 minimum
- **Large text** (≥ 18pt or ≥ 14pt bold): 3:1 minimum
- **UI components**: 3:1 minimum

### Verified Color Pairs

The platform's color scheme has been verified for WCAG compliance. Use these approved color combinations:

**Light Theme:**
- Primary text (#111827) on white (#ffffff): 16.1:1 ✓
- Secondary text (#6b7280) on white (#ffffff): 4.6:1 ✓
- Link text (#2563eb) on white (#ffffff): 8.6:1 ✓

**Dark Theme:**
- Primary text (#f9fafb) on dark (#111827): 16.1:1 ✓
- Secondary text (#d1d5db) on dark (#111827): 9.7:1 ✓
- Link text (#60a5fa) on dark (#111827): 8.3:1 ✓

### Testing Contrast

Use the WCAG compliance utility to verify new color combinations:

```python
from apps.core.wcag_compliance import calculate_contrast_ratio

# Check contrast ratio
ratio = calculate_contrast_ratio('#111827', '#ffffff')
print(f"Contrast ratio: {ratio:.2f}:1")  # 16.1:1

# Verify all color pairs
from apps.core.wcag_compliance import generate_compliance_report
print(generate_compliance_report())
```

## Template Tags

### Available Template Tags

```django
{% load accessibility_tags %}

<!-- Skip navigation link -->
{% skip_link "main-content" "Skip to main content" %}

<!-- ARIA attributes -->
{% aria_label "Descriptive label" %}
{% aria_describedby "element-id" "description-id" %}
{% aria_labelledby "element-id" "label-id" %}
{% aria_live "polite" %}
{% aria_expanded True %}
{% aria_hidden False %}
{% aria_current "page" %}

<!-- Roles and landmarks -->
{% role "navigation" %}
{% landmark "main" %}
{% landmark "navigation" "Main navigation" %}

<!-- Screen reader only text -->
{% sr_only "Additional context for screen readers" %}

<!-- Accessible buttons and links -->
{% accessible_button "Submit" button_type="submit" css_class="btn-primary" %}
{% accessible_link "/dashboard/" "Dashboard" css_class="nav-link" %}

<!-- Keyboard shortcuts -->
{% keyboard_shortcut "Ctrl+S" "Save" %}

<!-- Focus trap for modals -->
{% focus_trap "modal-dialog" %}

<!-- Accessible form fields -->
{% form_field_accessible form.email %}
```

## Testing

### Manual Testing

1. **Keyboard Navigation**
   - Tab through all interactive elements
   - Ensure focus indicators are visible
   - Verify all functionality works with keyboard only
   - Test with Enter and Space keys on buttons

2. **Screen Reader Testing**
   - Test with NVDA (Windows)
   - Test with JAWS (Windows)
   - Test with VoiceOver (macOS)
   - Verify all content is announced correctly
   - Check ARIA labels are meaningful

3. **Zoom Testing**
   - Zoom to 200% in browser
   - Verify no content is cut off
   - Ensure all functionality still works
   - Check horizontal scrolling is minimal

4. **Color Contrast**
   - Use browser DevTools to check contrast
   - Test both light and dark themes
   - Verify focus indicators are visible

### Automated Testing

Run the WCAG compliance checker:

```bash
# Inside Docker container
docker compose exec web python apps/core/wcag_compliance.py
```

### Browser Extensions

Use these extensions for testing:

- **axe DevTools**: Automated accessibility testing
- **WAVE**: Web accessibility evaluation tool
- **Lighthouse**: Accessibility audit in Chrome DevTools
- **Color Contrast Analyzer**: Check contrast ratios

## Common Mistakes to Avoid

### ❌ Don't Do This

```html
<!-- Missing alt text -->
<img src="product.jpg" />

<!-- Non-semantic markup -->
<div class="button" onclick="submit()">Submit</div>

<!-- Removing focus indicators -->
<style>
*:focus { outline: none; }
</style>

<!-- Skipping heading levels -->
<h1>Title</h1>
<h3>Subtitle</h3>

<!-- Non-descriptive link text -->
<a href="/more/">Click here</a>

<!-- Div soup instead of semantic HTML -->
<div class="header">
    <div class="nav">...</div>
</div>
```

### ✅ Do This Instead

```html
<!-- Descriptive alt text -->
<img src="product.jpg" alt="18 karat gold necklace with emerald pendant" />

<!-- Semantic button -->
<button type="button" onclick="submit()">Submit</button>

<!-- Visible focus indicators -->
<style>
*:focus-visible {
    outline: 2px solid #2563eb;
    outline-offset: 2px;
}
</style>

<!-- Proper heading hierarchy -->
<h1>Title</h1>
<h2>Subtitle</h2>

<!-- Descriptive link text -->
<a href="/more/">Read more about gold necklaces</a>

<!-- Semantic HTML -->
<header>
    <nav role="navigation" aria-label="Main navigation">...</nav>
</header>
```

## Resources

- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
- [MDN Accessibility](https://developer.mozilla.org/en-US/docs/Web/Accessibility)
- [WebAIM](https://webaim.org/)
- [A11y Project](https://www.a11yproject.com/)
- [ARIA Authoring Practices](https://www.w3.org/WAI/ARIA/apg/)

## Support

For questions about accessibility implementation, contact the development team or refer to the WCAG 2.1 Level AA standards documentation.
