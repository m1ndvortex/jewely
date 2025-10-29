# Internationalization (i18n) - Locale Files

This directory contains translation files for the jewelry shop SaaS platform.

## Supported Languages

Per Requirement 2 - Dual-Language Support:
- **English (en)**: Default language, LTR layout
- **Persian (fa)**: RTL layout, Persian numerals, Jalali calendar support

## Directory Structure

```
locale/
├── en/
│   └── LC_MESSAGES/
│       ├── django.po      # Translation strings for Python code
│       └── django.mo      # Compiled translation file
└── fa/
    └── LC_MESSAGES/
        ├── django.po      # Translation strings for Python code
        └── django.mo      # Compiled translation file
```

## Generating Translation Files

### 1. Mark strings for translation in code

**In Python code:**
```python
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy

# Use gettext for runtime translation
message = _("Hello, World!")

# Use gettext_lazy for model fields, form labels, etc.
class MyModel(models.Model):
    name = models.CharField(_lazy("Name"), max_length=100)
```

**In Django templates:**
```django
{% load i18n %}

{# Translate simple strings #}
<h1>{% trans "Welcome" %}</h1>

{# Translate strings with variables #}
{% blocktrans with name=user.name %}
Hello, {{ name }}!
{% endblocktrans %}

{# Translate plurals #}
{% blocktrans count counter=items|length %}
There is {{ counter }} item.
{% plural %}
There are {{ counter }} items.
{% endblocktrans %}
```

### 2. Extract translatable strings

Run inside Docker container:
```bash
# Extract strings from all apps
docker-compose exec web python manage.py makemessages -l fa

# Extract strings from specific app
docker-compose exec web python manage.py makemessages -l fa -d django --ignore=venv/*

# Extract strings from JavaScript files
docker-compose exec web python manage.py makemessages -l fa -d djangojs
```

### 3. Translate strings

Edit the `.po` files in `locale/fa/LC_MESSAGES/django.po`:
```po
#: apps/core/models.py:25
msgid "Name"
msgstr "نام"

#: apps/core/views.py:42
msgid "Welcome to Jewelry Shop"
msgstr "به فروشگاه جواهرات خوش آمدید"
```

### 4. Compile translations

Run inside Docker container:
```bash
# Compile all translations
docker-compose exec web python manage.py compilemessages

# Compile specific language
docker-compose exec web python manage.py compilemessages -l fa
```

### 5. Test translations

1. Change language in user profile or use language switcher
2. Verify all strings are translated
3. Check RTL layout for Persian
4. Verify Persian numerals display correctly

## Translation Management

For easier translation management, consider using:
- **django-rosetta**: Web-based translation interface
- **Transifex**: Cloud-based translation platform
- **POEdit**: Desktop application for editing .po files

## Format Localization

Date, time, and number formats are configured in:
- `config/formats/en.py` - English formats
- `config/formats/fa.py` - Persian formats

## Persian-Specific Features

### Persian Numerals
Use template filter to convert to Persian numerals (۰۱۲۳۴۵۶۷۸۹):
```django
{% load persian_filters %}
{{ number|persian_numerals }}
```

### Persian Calendar (Jalali)
Use jdatetime library for Persian calendar conversion:
```python
import jdatetime

# Convert Gregorian to Jalali
jalali_date = jdatetime.date.fromgregorian(date=gregorian_date)

# Format Jalali date
formatted = jalali_date.strftime("%Y/%m/%d")
```

## Best Practices

1. **Always use translation functions**: Never hardcode user-facing strings
2. **Use lazy translation for class-level strings**: Models, forms, etc.
3. **Provide context for translators**: Add comments above msgid in .po files
4. **Test both languages**: Ensure UI works in both LTR and RTL
5. **Keep translations up to date**: Run makemessages regularly
6. **Use meaningful string IDs**: Avoid generic strings like "OK" or "Submit"
7. **Handle plurals correctly**: Use ngettext for plural forms
8. **Consider text expansion**: Translated text may be longer than English

## Troubleshooting

### Translations not showing
1. Check if .mo files are compiled: `docker-compose exec web python manage.py compilemessages`
2. Verify LANGUAGE_CODE in settings matches user's language preference
3. Check if LocaleMiddleware is enabled in MIDDLEWARE
4. Ensure translation strings are marked with gettext/trans tags

### RTL layout issues
1. Verify RTL CSS is loaded for Persian language
2. Check if `dir="rtl"` attribute is set on HTML element
3. Test with Tailwind RTL plugin or custom RTL styles

### Date/number format issues
1. Verify FORMAT_MODULE_PATH is set in settings
2. Check format files in config/formats/
3. Ensure USE_L10N = True in settings

## Resources

- [Django i18n Documentation](https://docs.djangoproject.com/en/4.2/topics/i18n/)
- [Django Translation Documentation](https://docs.djangoproject.com/en/4.2/topics/i18n/translation/)
- [Persian Language Support](https://docs.djangoproject.com/en/4.2/topics/i18n/translation/#how-django-discovers-language-preference)
- [jdatetime Documentation](https://github.com/slashmili/python-jalali)
