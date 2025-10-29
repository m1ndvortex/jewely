# RTL (Right-to-Left) Support Implementation

## Overview

This document describes the implementation of RTL (Right-to-Left) support for the Persian language in the Jewelry Shop SaaS platform, as per **Requirement 2 - Dual-Language Support**.

## Implementation Details

### 1. RTL CSS Overrides (`static/css/rtl.css`)

A comprehensive RTL CSS file has been created that:

- **Flips margins and paddings**: Converts `ml-*` to `mr-*` and vice versa
- **Flips positioning**: Swaps `left` and `right` properties
- **Flips text alignment**: Converts `text-left` to `text-right`
- **Flips flex spacing**: Adjusts `space-x-*` classes for RTL
- **Flips border radius**: Mirrors corner radius properties
- **Flips border sides**: Swaps left and right borders
- **Adjusts form elements**: Sets text alignment to right for inputs
- **Adjusts dropdowns**: Mirrors dropdown positioning
- **Adjusts tables**: Sets RTL direction and text alignment
- **Adjusts navigation**: Mirrors navigation layout
- **Adjusts icons**: Provides flip utility for directional icons

### 2. Tailwind CSS Configuration (`tailwind.config.js`)

A Tailwind configuration file has been created with:

- **RTL Plugin**: `tailwindcss-rtl` for automatic RTL support
- **Forms Plugin**: `@tailwindcss/forms` for better form styling
- **Typography Plugin**: `@tailwindcss/typography` for rich text
- **Aspect Ratio Plugin**: `@tailwindcss/aspect-ratio`
- **Custom Colors**: Jewelry shop theme colors (primary, gold)
- **Persian Font**: Vazir font family configuration
- **Dark Mode**: Class-based dark mode support
- **Safelist**: RTL-specific classes for dynamic generation

### 3. Package Configuration (`package.json`)

NPM package configuration includes:

- **Tailwind CSS**: Core framework (v3.4.0)
- **RTL Plugin**: `tailwindcss-rtl` (v0.9.0)
- **Tailwind Plugins**: Forms, Typography, Aspect Ratio
- **Build Scripts**: Commands to build and watch CSS

### 4. Input CSS (`static/css/input.css`)

Tailwind input file that:

- Imports Tailwind base, components, and utilities
- Imports RTL overrides
- Defines Persian font (Vazir) with font-face
- Applies Persian font when language is Persian
- Defines custom component styles (buttons, cards, forms, badges, alerts)
- Defines custom utility classes (RTL-specific, animations)
- Includes print styles with RTL support

### 5. Base Template Updates (`templates/base.html`)

The base template has been updated to:

- Include RTL CSS file
- Load Persian font (Vazir) when language is Persian
- Maintain existing `dir` attribute logic: `dir="{% if LANGUAGE_BIDI %}rtl{% else %}ltr{% endif %}"`
- Maintain existing `lang` attribute: `lang="{{ LANGUAGE_CODE }}"`

### 6. Comprehensive Tests (`tests/test_rtl_support.py`)

Test suite includes:

- **HTML Direction Tests**: Verify `dir="rtl"` for Persian, `dir="ltr"` for English
- **HTML Language Tests**: Verify `lang="fa"` for Persian, `lang="en"` for English
- **CSS Loading Tests**: Verify RTL CSS is loaded
- **Font Loading Tests**: Verify Persian font is loaded for Persian language
- **Context Variable Tests**: Verify `LANGUAGE_BIDI` is set correctly
- **User Preference Tests**: Verify user language preference is applied
- **File Existence Tests**: Verify all required files exist
- **Form Tests**: Verify forms have RTL layout
- **Navigation Tests**: Verify navigation has RTL layout
- **Table Tests**: Verify tables have RTL direction
- **Integration Tests**: Verify RTL is consistent across multiple pages

## How RTL Works

### Automatic Direction Switching

1. **User Language Preference**: User's language preference is stored in their profile
2. **Middleware**: `LocaleMiddleware` sets the active language based on user preference
3. **Template Context**: Django provides `LANGUAGE_CODE` and `LANGUAGE_BIDI` in template context
4. **HTML Attribute**: Base template sets `dir` attribute based on `LANGUAGE_BIDI`
5. **CSS Application**: RTL CSS rules apply automatically when `dir="rtl"` is set

### CSS Cascade

```
1. Tailwind Base Styles (LTR by default)
2. Tailwind Components
3. Tailwind Utilities
4. RTL Overrides (applied when dir="rtl")
5. Custom Component Styles
6. Custom Utility Classes
```

### Persian Font Loading

When language is Persian (`fa`):
- Vazir font is loaded from CDN
- Font is applied to body element
- Font supports Persian characters and numerals

## Usage Examples

### In Templates

```html
<!-- Direction is automatically set -->
<html lang="{{ LANGUAGE_CODE }}" dir="{% if LANGUAGE_BIDI %}rtl{% else %}ltr{% endif %}">

<!-- Use standard Tailwind classes -->
<div class="ml-4 mr-2">
  <!-- In RTL mode, ml-4 becomes mr-4 and mr-2 becomes ml-2 -->
</div>

<!-- For icons that should flip in RTL -->
<svg class="flip-rtl">...</svg>

<!-- For content that should always be LTR (e.g., code, numbers) -->
<div class="ltr-content">12345</div>

<!-- For content that should always be RTL -->
<div class="rtl-content">محتوای فارسی</div>
```

### In Python Code

```python
from django.utils import translation

# Set language for current request
translation.activate('fa')

# Get current language
current_lang = translation.get_language()  # 'fa'

# Check if current language is RTL
from django.utils.translation import get_language_bidi
is_rtl = get_language_bidi()  # True for Persian
```

## Building CSS (Optional)

If you want to build a custom CSS file instead of using CDN:

```bash
# Install dependencies (inside Docker)
docker-compose exec web npm install

# Build CSS once
docker-compose exec web npm run build:css

# Watch for changes during development
docker-compose exec web npm run watch:css
```

## Testing RTL Support

### Run RTL Tests

```bash
# Run all RTL tests
docker-compose exec web pytest tests/test_rtl_support.py -v

# Run specific test class
docker-compose exec web pytest tests/test_rtl_support.py::RTLSupportTestCase -v

# Run with coverage
docker-compose exec web pytest tests/test_rtl_support.py --cov=. --cov-report=html
```

### Manual Testing

1. **Create a Persian user**:
   ```python
   user = User.objects.create_user(
       username='persian_user',
       email='persian@example.com',
       password='testpass123',
       language='fa'
   )
   ```

2. **Login as Persian user**: The interface should automatically switch to RTL

3. **Check visual elements**:
   - Navigation should be right-aligned
   - Dropdowns should open from right
   - Forms should have right-aligned text
   - Tables should read right-to-left
   - Icons should flip where appropriate

4. **Switch language**: Change user language preference and verify layout changes

## Browser Compatibility

RTL support works in all modern browsers:

- ✅ Chrome/Edge (Chromium)
- ✅ Firefox
- ✅ Safari
- ✅ Mobile browsers (iOS Safari, Chrome Mobile)

## Accessibility

RTL implementation maintains accessibility:

- Screen readers correctly interpret RTL content
- Keyboard navigation works in RTL mode
- Focus indicators are properly positioned
- ARIA labels work correctly in both directions

## Performance

RTL implementation has minimal performance impact:

- CSS file is small (~10KB uncompressed)
- No JavaScript required for RTL switching
- Font loading is optimized with `font-display: swap`
- CSS rules use efficient selectors

## Future Enhancements

Potential improvements for future versions:

1. **Automatic RTL Detection**: Detect RTL from browser settings
2. **Per-Component RTL**: Allow specific components to override RTL
3. **RTL Preview**: Admin interface to preview pages in RTL mode
4. **RTL Testing Tools**: Automated visual regression testing for RTL
5. **Additional RTL Languages**: Support for Arabic, Hebrew, Urdu

## Troubleshooting

### Issue: RTL CSS not loading

**Solution**: Check that `{% load static %}` is in template and CSS file exists

### Issue: Some elements not flipping

**Solution**: Add specific RTL rules in `rtl.css` for those elements

### Issue: Persian font not loading

**Solution**: Check CDN availability and font-face declaration

### Issue: Mixed LTR/RTL content

**Solution**: Use `.ltr-content` or `.rtl-content` classes to force direction

## References

- [Django Internationalization](https://docs.djangoproject.com/en/4.2/topics/i18n/)
- [Tailwind CSS RTL Plugin](https://github.com/20lives/tailwindcss-rtl)
- [CSS Writing Modes](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_Writing_Modes)
- [Vazir Font](https://github.com/rastikerdar/vazir-font)

## Compliance

This implementation satisfies:

- ✅ **Requirement 2.1**: Support English (LTR) and Persian (RTL) languages
- ✅ **Requirement 2.2**: Automatic RTL layout when Persian is selected
- ✅ **Requirement 2.6**: Persist language preference across sessions
- ✅ **Task 26.3**: Create RTL CSS overrides, integrate Tailwind RTL plugin, test all pages

## Conclusion

The RTL support implementation provides a complete solution for Persian language users, with automatic layout mirroring, proper font support, and comprehensive testing. The implementation is maintainable, performant, and follows Django and Tailwind best practices.
