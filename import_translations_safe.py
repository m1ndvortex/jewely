#!/usr/bin/env python
"""
Safe translation importer that preserves .po file format correctly.
Uses polib to handle multiline strings and special formatting.
"""
import csv
import polib
import sys
import os
import django

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")
django.setup()


def import_translations_safe(csv_file, po_file_path="/app/locale/fa/LC_MESSAGES/django.po"):
    """
    Import translations from CSV into .po file while preserving format.
    Handles both regular and fuzzy CSV formats.
    """
    po = polib.pofile(po_file_path)

    # Read CSV
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Detect CSV format
    is_fuzzy = "Corrected Persian" in rows[0] if rows else False
    persian_column = "Corrected Persian" if is_fuzzy else "Persian"

    updated = 0
    skipped = 0

    print(f"📝 Importing from {csv_file}...")
    print(f"   Format: {'Fuzzy corrections' if is_fuzzy else 'New translations'}")
    print(f"   Total rows: {len(rows)}")

    # Create lookup dictionary for faster matching
    translations_dict = {}
    for row in rows:
        english = row["English"].strip()
        persian = row[persian_column].strip() if row[persian_column] else ""
        if persian:  # Only add if there's a translation
            translations_dict[english] = persian

    # Update .po entries
    for entry in po:
        # Skip entries with no msgid
        if not entry.msgid:
            continue

        # Clean msgid for matching (remove newlines/extra spaces from multiline)
        msgid_clean = entry.msgid.replace("\n", " ").replace("  ", " ").strip()

        # Try exact match first, then cleaned match
        if entry.msgid in translations_dict:
            new_translation = translations_dict[entry.msgid]
        elif msgid_clean in translations_dict:
            new_translation = translations_dict[msgid_clean]
        else:
            if not entry.msgstr:
                skipped += 1
            continue

        if new_translation:
            # Preserve multiline format: if msgid is multiline, keep msgstr single-line
            # polib will handle the formatting correctly
            entry.msgstr = new_translation

            # Remove fuzzy flag if set
            if "fuzzy" in entry.flags:
                entry.flags.remove("fuzzy")
            updated += 1
        else:
            skipped += 1

    # Save the .po file
    po.save(po_file_path)

    print(f"\n✅ Import complete!")
    print(f"   Updated: {updated} entries")
    print(f"   Skipped: {skipped} entries")
    print(f"   Output: {po_file_path}")
    print(f"\nNext steps:")
    print(f"1. Compile: docker-compose exec web python manage.py compilemessages -l fa")
    print(f"2. Restart: docker-compose restart web")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_translations_safe.py <csv_file>")
        sys.exit(1)

    csv_file = sys.argv[1]
    import_translations_safe(csv_file)
