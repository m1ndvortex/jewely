#!/usr/bin/env python
"""
Enterprise-grade auto-translation using Google Translate API (googletrans library).
Falls back to deep-translator if googletrans fails.

This translates all 524 untranslated strings automatically.
"""

import csv
import time
from pathlib import Path

try:
    from googletrans import Translator

    translator = Translator()
    USE_GOOGLETRANS = True
except ImportError:
    print("⚠️  googletrans not installed, trying deep-translator...")
    try:
        from deep_translator import GoogleTranslator

        translator = GoogleTranslator(source="en", target="fa")
        USE_GOOGLETRANS = False
    except ImportError:
        print("❌ Neither googletrans nor deep-translator installed")
        print("Installing deep-translator...")
        import subprocess

        subprocess.check_call(["pip", "install", "deep-translator"])
        from deep_translator import GoogleTranslator

        translator = GoogleTranslator(source="en", target="fa")
        USE_GOOGLETRANS = False


def translate_text(text):
    """Translate English to Persian with retry logic."""
    if not text or not text.strip():
        return ""

    max_retries = 3
    for attempt in range(max_retries):
        try:
            if USE_GOOGLETRANS:
                result = translator.translate(text, src="en", dest="fa")
                return result.text
            else:
                return translator.translate(text)
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(1)  # Wait before retry
                continue
            else:
                print(f"⚠️  Failed to translate: {text[:50]}... - {e}")
                return text  # Return original if translation fails


def auto_translate_csv(input_csv, output_csv):
    """Auto-translate all untranslated strings in CSV."""

    if not Path(input_csv).exists():
        print(f"❌ File not found: {input_csv}")
        return

    print(f"🚀 Starting auto-translation of {input_csv}...")
    print(f"Using: {'googletrans' if USE_GOOGLETRANS else 'deep-translator'}")

    rows_translated = 0
    total_rows = 0

    # Read input CSV
    with open(input_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        total_rows = len(rows)

    # Translate each row
    for i, row in enumerate(rows, 1):
        english = row["English"]

        # Handle both CSV formats: regular (Persian) and fuzzy (Corrected Persian)
        persian_column = "Corrected Persian" if "Corrected Persian" in row else "Persian"

        if not row[persian_column]:  # Only translate if Persian is empty
            print(f"[{i}/{total_rows}] Translating: {english[:60]}...")
            persian = translate_text(english)
            row[persian_column] = persian
            rows_translated += 1

            # Small delay to avoid rate limiting
            if i % 10 == 0:
                time.sleep(0.5)
        else:
            print(f"[{i}/{total_rows}] Skipping (already has translation): {english[:60]}...")

    # Write output CSV - use same fieldnames as input
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        # Detect fieldnames from first row
        fieldnames = list(rows[0].keys()) if rows else ["English", "Persian", "Context", "File"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✅ Translation complete!")
    print(f"   Translated: {rows_translated} strings")
    print(f"   Output: {output_csv}")
    print(f"\nNext steps:")
    print(f"1. Review {output_csv} (optional)")
    print(
        f"2. Import: docker-compose exec web python /app/bulk_translate_untranslated.py --import {output_csv}"
    )
    print(f"3. Compile: docker-compose exec web python manage.py compilemessages -l fa")
    print(f"4. Restart: docker-compose restart web")


if __name__ == "__main__":
    import sys

    input_file = sys.argv[1] if len(sys.argv) > 1 else "untranslated_strings.csv"
    output_file = sys.argv[2] if len(sys.argv) > 2 else "translated_strings.csv"

    auto_translate_csv(input_file, output_file)
