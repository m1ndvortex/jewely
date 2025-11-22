# Improved Translation Workflow for 3000+ Translations

## The Proper Django Way (Recommended)

### Step 1: Wrap ALL English text in templates with {% trans %}
```django
{# Before #}
<h1>Accounting Dashboard</h1>

{# After #}
{% load i18n %}
<h1>{% trans "Accounting Dashboard" %}</h1>
```

### Step 2: Use Django's makemessages command
This automatically extracts ALL translatable strings from your templates:

```bash
docker-compose exec web python manage.py makemessages -l fa --ignore=venv --ignore=staticfiles
```

**What this does:**
- Scans all templates for `{% trans %}` and `{% blocktrans %}` tags
- Automatically adds NEW strings to locale/fa/LC_MESSAGES/django.po
- Preserves EXISTING translations (never duplicates)
- Updates line numbers and file references
- Handles pluralization automatically

### Step 3: Translate in the .po file
Open `locale/fa/LC_MESSAGES/django.po` and translate:

```po
#: templates/accounting/dashboard.html:15
msgid "Accounting Dashboard"
msgstr "داشبورد حسابداری"

#: templates/accounting/dashboard.html:20
msgid "Total Revenue"
msgstr "کل درآمد"
```

### Step 4: Compile messages
```bash
docker-compose exec web python manage.py compilemessages -l fa
```

## Why This Is Better:

✅ **No duplicates** - Django handles deduplication automatically
✅ **Context preservation** - Shows which file/line each string comes from
✅ **Incremental updates** - Only adds new strings, keeps existing translations
✅ **Handles 3000+ strings** - Designed for large projects
✅ **Pluralization support** - Handles singular/plural automatically
✅ **Comments support** - Can add translator notes

## Alternative: Use Translation Management Tools

### Option A: Django Rosetta (Web UI)
Already installed in your project! Access at `/rosetta/`

**Advantages:**
- Web-based translation interface
- Search and filter strings
- See context (which template uses the string)
- Mark strings as fuzzy/needs review
- Export/import functionality

**How to use:**
1. Add to urls.py (if not already):
```python
if settings.DEBUG:
    urlpatterns += [path('rosetta/', include('rosetta.urls'))]
```

2. Access: http://test.localhost:8000/rosetta/
3. Translate in the web UI
4. Auto-saves to django.po

### Option B: POEdit (Desktop App)
Free tool: https://poedit.net/

**Advantages:**
- Better UI than text editor
- Translation memory (suggests previously used translations)
- Spell checking
- Validates format strings
- Shows context

### Option C: Bulk Import from CSV/Excel

Create a script to import translations from spreadsheet:

```python
# bulk_import_translations.py
import polib
import pandas as pd

# Read your Excel/CSV with columns: english, persian
df = pd.read_excel('translations.xlsx')

# Load existing .po file
po = polib.pofile('locale/fa/LC_MESSAGES/django.po')

# Add translations
for _, row in df.iterrows():
    entry = po.find(row['english'])
    if entry:
        entry.msgstr = row['persian']
    else:
        po.append(polib.POEntry(
            msgid=row['english'],
            msgstr=row['persian']
        ))

po.save()
```

## Recommended Workflow for Your 3000+ Translations:

### Phase 1: Template Preparation (1-2 days)
```bash
# Create a script to find all untranslated strings
grep -r ">" templates/ | grep -v "{% trans" | grep -v "{%" > untranslated.txt
```

Go through templates and wrap English text in `{% trans %}` tags.

### Phase 2: Extract Strings (5 minutes)
```bash
docker-compose exec web python manage.py makemessages -l fa
```

This gives you ONE file with ALL strings, no duplicates.

### Phase 3: Translation (bulk approach)
**Option 1 - Use Rosetta web UI** (recommended for review)
**Option 2 - Export to Excel, translate, import back**

```bash
# Export .po to CSV
msgcat locale/fa/LC_MESSAGES/django.po --no-wrap | \
  grep -E "^(msgid|msgstr)" > translations.csv

# After translation in Excel, import back
# Use bulk_import_translations.py script above
```

**Option 3 - AI-assisted translation**
```python
# ai_translate.py
import polib
from openai import OpenAI  # or any translation API

po = polib.pofile('locale/fa/LC_MESSAGES/django.po')

for entry in po:
    if not entry.msgstr:  # Only translate empty strings
        # Call translation API
        entry.msgstr = translate_to_persian(entry.msgid)
        
po.save()
```

### Phase 4: Compile and Test
```bash
docker-compose exec web python manage.py compilemessages -l fa
docker-compose restart web
```

## Migration Strategy from Current Approach:

### Step 1: Keep your existing translations
Your current django.po has ~107 translations - these are fine!

### Step 2: Add {% trans %} to all templates
- accounting/dashboard.html
- All other templates
- Forms, buttons, labels, help text

### Step 3: Run makemessages
```bash
docker-compose exec web python manage.py makemessages -l fa
```

This will:
- Keep your existing 107 translations
- Add ~2900 new entries (empty msgstr)
- Mark any changed strings as "fuzzy"

### Step 4: Translate the new entries
Use Rosetta or bulk import method.

## Comparison Table:

| Method | Speed | Duplicates | Maintenance | Best For |
|--------|-------|------------|-------------|----------|
| **Your current way** (manual .po edit) | Slow | Yes, manual checks needed | Hard | Small projects |
| **makemessages** (recommended) | Fast | Never | Easy | All projects |
| **Rosetta web UI** | Medium | Never | Easy | Teams, review |
| **POEdit desktop** | Fast | Never | Easy | Solo developers |
| **Bulk CSV import** | Very fast | Never | Medium | Large existing translations |

## My Recommendation for You:

1. **Use Django's makemessages** - It's built for this exact problem
2. **Use Rosetta for reviewing** - Nice web UI to verify translations
3. **For bulk work** - Export to Excel, use Google Translate API or hire translator, import back

This will handle 3000+ translations without ANY duplication issues, and future updates will be automatic.

Would you like me to:
1. Set up the Rosetta web interface for you?
2. Create a bulk import script from Excel/CSV?
3. Run makemessages now to show you how it finds all untranslated strings?
