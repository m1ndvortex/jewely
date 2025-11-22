#!/usr/bin/env python
"""
Fix Python format string placeholders in Persian translations.
Ensures all %(variable)s placeholders in msgid are preserved in msgstr.
"""
import polib
import re
import sys


def fix_format_strings(po_file_path="/app/locale/fa/LC_MESSAGES/django.po"):
    """Fix format string placeholders in translations."""
    po = polib.pofile(po_file_path)

    fixed = 0
    errors_found = []

    for entry in po:
        if not entry.msgstr or not entry.msgid:
            continue

        # Find all format placeholders in msgid
        msgid_placeholders = set(re.findall(r"%\([a-zA-Z_][a-zA-Z0-9_]*\)[sd]", entry.msgid))
        msgstr_placeholders = set(re.findall(r"%\([a-zA-Z_][a-zA-Z0-9_]*\)[sd]", entry.msgstr))

        # Check for translated placeholders (Persian characters in variable names)
        persian_placeholders = re.findall(r"%\([^)]*[\u0600-\u06FF][^)]*\)[sd]", entry.msgstr)

        if persian_placeholders:
            errors_found.append(
                {
                    "line": entry.linenum,
                    "msgid": entry.msgid[:80],
                    "issue": f"Translated placeholders: {persian_placeholders}",
                    "expected": list(msgid_placeholders),
                }
            )

        # Check for missing placeholders
        missing = msgid_placeholders - msgstr_placeholders
        extra = msgstr_placeholders - msgid_placeholders

        if missing or extra or persian_placeholders:
            print(f"\n⚠️  Line {entry.linenum}:")
            print(f"   msgid: {entry.msgid[:80]}")
            if missing:
                print(f"   Missing in msgstr: {missing}")
            if extra:
                print(f"   Extra in msgstr: {extra}")
            if persian_placeholders:
                print(f"   Translated (WRONG): {persian_placeholders}")
                # Try to fix by replacing Persian placeholders with correct ones
                # This is tricky - we'll need to regenerate the translation
                entry.msgstr = ""  # Clear broken translation
                entry.flags.append("fuzzy")
                fixed += 1
                print(f"   ❌ Cleared broken translation, marked fuzzy")

    if errors_found:
        print(f"\n\n📋 Summary of format string errors:")
        for err in errors_found:
            print(f"\nLine {err['line']}: {err['msgid']}")
            print(f"  Issue: {err['issue']}")
            print(f"  Expected: {err['expected']}")

    if fixed > 0:
        po.save(po_file_path)
        print(f"\n\n✅ Fixed {fixed} format string errors (marked as fuzzy for retranslation)")
    else:
        print(f"\n\n✅ No fixable format string errors")

    return fixed


if __name__ == "__main__":
    po_path = sys.argv[1] if len(sys.argv) > 1 else "/app/locale/fa/LC_MESSAGES/django.po"
    fix_format_strings(po_path)
