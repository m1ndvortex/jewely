#!/usr/bin/env python
"""
Bulk translate untranslated strings using Google Translate API
or manually via CSV file.

Usage:
1. Export untranslated to CSV:
   python bulk_translate_untranslated.py --export

2. Manually translate the CSV file

3. Import translations back:
   python bulk_translate_untranslated.py --import translations.csv
"""

import argparse
import csv
import polib


def export_untranslated_to_csv(po_file, csv_file):
    """Export all untranslated strings to CSV for manual translation."""
    po = polib.pofile(po_file)

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["English", "Persian", "Context", "File"])

        for entry in po:
            if not entry.msgstr and not entry.obsolete:
                # Get file occurrences
                files = ", ".join([f"{occ[0]}:{occ[1]}" for occ in entry.occurrences[:3]])
                if len(entry.occurrences) > 3:
                    files += f" ... ({len(entry.occurrences) - 3} more)"

                writer.writerow(
                    [entry.msgid, "", entry.comment or "", files]  # Empty Persian - to be filled
                )

    print(
        f"✓ Exported {sum(1 for e in po if not e.msgstr and not e.obsolete)} untranslated strings to {csv_file}"
    )
    print(f"\nNext steps:")
    print(f"1. Open {csv_file} in Excel/Google Sheets")
    print(f"2. Fill in the 'Persian' column")
    print(f"3. Run: python {__file__} --import {csv_file}")


def import_translations_from_csv(po_file, csv_file):
    """Import translations from CSV back to .po file."""
    po = polib.pofile(po_file)

    imported = 0
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            english = row["English"]
            persian = row["Persian"].strip()

            if not persian:
                continue

            # Find entry by msgid
            entry = po.find(english)
            if entry:
                entry.msgstr = persian
                imported += 1

    po.save()
    print(f"✓ Imported {imported} translations into {po_file}")
    print(f"\nNext steps:")
    print(f"1. Compile: docker-compose exec web python manage.py compilemessages -l fa")
    print(f"2. Restart: docker-compose restart web")


def export_fuzzy_to_csv(po_file, csv_file):
    """Export fuzzy translations to CSV for review."""
    po = polib.pofile(po_file)

    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["English", "Current Persian", "Corrected Persian", "Context", "File"])

        for entry in po:
            if "fuzzy" in entry.flags:
                files = ", ".join([f"{occ[0]}:{occ[1]}" for occ in entry.occurrences[:3]])
                if len(entry.occurrences) > 3:
                    files += f" ... ({len(entry.occurrences) - 3} more)"

                writer.writerow(
                    [
                        entry.msgid,
                        entry.msgstr,
                        "",  # Corrected Persian - to be filled
                        entry.comment or "",
                        files,
                    ]
                )

    fuzzy_count = sum(1 for e in po if "fuzzy" in e.flags)
    print(f"✓ Exported {fuzzy_count} fuzzy translations to {csv_file}")
    print(f"\nThese are translations that need review because the English text changed slightly.")


def import_fuzzy_corrections_from_csv(po_file, csv_file):
    """Import corrected fuzzy translations from CSV."""
    po = polib.pofile(po_file)

    imported = 0
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            english = row["English"]
            corrected = row["Corrected Persian"].strip()

            if not corrected:
                continue

            entry = po.find(english)
            if entry and "fuzzy" in entry.flags:
                entry.msgstr = corrected
                entry.flags.remove("fuzzy")  # Remove fuzzy flag
                imported += 1

    po.save()
    print(f"✓ Imported {imported} fuzzy corrections into {po_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bulk translation tool for django.po")
    parser.add_argument("--export", action="store_true", help="Export untranslated strings to CSV")
    parser.add_argument(
        "--export-fuzzy", action="store_true", help="Export fuzzy translations to CSV"
    )
    parser.add_argument("--import", dest="import_file", help="Import translations from CSV")
    parser.add_argument(
        "--import-fuzzy", dest="import_fuzzy_file", help="Import fuzzy corrections from CSV"
    )
    parser.add_argument(
        "--po-file", default="locale/fa/LC_MESSAGES/django.po", help="Path to .po file"
    )

    args = parser.parse_args()

    if args.export:
        export_untranslated_to_csv(args.po_file, "untranslated_strings.csv")
    elif args.export_fuzzy:
        export_fuzzy_to_csv(args.po_file, "fuzzy_translations.csv")
    elif args.import_file:
        import_translations_from_csv(args.po_file, args.import_file)
    elif args.import_fuzzy_file:
        import_fuzzy_corrections_from_csv(args.po_file, args.import_fuzzy_file)
    else:
        parser.print_help()
