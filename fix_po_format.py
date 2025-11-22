#!/usr/bin/env python
"""
Fix .po file format issues with multiline strings.
When msgid starts with newline, msgstr must also start with newline.
"""
import polib
import sys


def fix_multiline_format(po_file_path="/app/locale/fa/LC_MESSAGES/django.po"):
    """Fix multiline string formatting in .po file."""
    po = polib.pofile(po_file_path)

    fixed = 0

    for entry in po:
        # Check if msgid starts with newline but msgstr doesn't
        if entry.msgid and entry.msgstr:
            msgid_starts_newline = entry.msgid.startswith("\n")
            msgstr_starts_newline = entry.msgstr.startswith("\n")

            if msgid_starts_newline and not msgstr_starts_newline:
                # Fix: add newline to start of msgstr
                entry.msgstr = "\n" + entry.msgstr
                fixed += 1
                print(f"Fixed line {entry.linenum}: {entry.msgid[:50]}")

    if fixed > 0:
        po.save(po_file_path)
        print(f"\n✅ Fixed {fixed} multiline format issues")
    else:
        print("✅ No format issues found")

    return fixed


if __name__ == "__main__":
    po_path = sys.argv[1] if len(sys.argv) > 1 else "/app/locale/fa/LC_MESSAGES/django.po"
    fix_multiline_format(po_path)
