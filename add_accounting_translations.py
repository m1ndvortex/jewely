#!/usr/bin/env python3
"""
Add accounting translations safely to django.po
"""

import os

# Accounting-specific translations
translations = {
    "Accounting & Finance": "حسابداری و مالی",
    "Accounting Dashboard": "داشبورد حسابداری",
    "Financial Management": "مدیریت مالی",
    "View Reports": "مشاهده گزارش‌ها",
    "Export": "خروجی",
}

# Path to django.po
po_file = "locale/fa/LC_MESSAGES/django.po"

# Read existing translations
with open(po_file, "r", encoding="utf-8") as f:
    content = f.read()

# Extract existing msgids
existing_msgids = set()
lines = content.split("\n")
for i, line in enumerate(lines):
    if line.startswith('msgid "') and not line.startswith('msgid ""'):
        msgid = line[7:-1]  # Extract text between msgid " and "
        existing_msgids.add(msgid)

# Add new translations
new_entries = []
skipped = []

for english, persian in translations.items():
    if english in existing_msgids:
        skipped.append(english)
        continue

    entry = f'\nmsgid "{english}"\nmsgstr "{persian}"'
    new_entries.append(entry)

# Insert new entries before the final empty line
if new_entries:
    # Find the last msgstr line
    insert_pos = content.rfind("\nmsgstr")
    if insert_pos != -1:
        # Find the end of that entry (next blank line or end of file)
        insert_pos = content.find("\n\n", insert_pos)
        if insert_pos == -1:
            insert_pos = len(content)

        # Insert new entries
        new_content = content[:insert_pos] + "\n" + "\n".join(new_entries) + content[insert_pos:]

        # Write back
        with open(po_file, "w", encoding="utf-8") as f:
            f.write(new_content)

        print(f"✅ Added {len(new_entries)} new accounting translations")
    else:
        print("❌ Could not find insertion point")
else:
    print("ℹ️  No new translations to add")

if skipped:
    print(f"\n⏭️  Skipped {len(skipped)} existing translations:")
    for item in skipped:
        print(f"  - {item}")
