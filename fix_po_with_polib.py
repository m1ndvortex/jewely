#!/usr/bin/env python3
"""
Properly fix the corrupted django.po file by using polib library
"""

import sys

try:
    import polib
except ImportError:
    print("Installing polib...")
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "polib"])
    import polib

from pathlib import Path


def fix_po_file_with_polib():
    """Fix the corrupted .po file using polib which properly handles .po syntax"""
    po_file_path = Path("locale/fa/LC_MESSAGES/django.po")

    if not po_file_path.exists():
        print(f"❌ File not found: {po_file_path}")
        return False

    print("🔍 Loading .po file with polib...")

    try:
        # Try to load the file
        po = polib.pofile(str(po_file_path))
        print(f"✅ Loaded {len(po)} entries")

        # Remove duplicate entries (keep first occurrence)
        seen = {}
        duplicates_removed = 0

        for entry in list(po):
            if entry.msgid in seen:
                po.remove(entry)
                duplicates_removed += 1
                print(f"  🗑️  Removed duplicate: {entry.msgid[:50]}...")
            else:
                seen[entry.msgid] = entry

        print(f"\n✅ Removed {duplicates_removed} duplicate entries")
        print(f"📊 Final entry count: {len(po)}")

        # Save the fixed file
        po.save(str(po_file_path))
        print(f"✅ Saved fixed file: {po_file_path}")

        return True

    except Exception as e:
        print(f"❌ Error loading .po file: {e}")
        print("\n🔧 The file is too corrupted. Will restore from backup and re-add translations...")
        return False


if __name__ == "__main__":
    if fix_po_file_with_polib():
        print("\n🎉 Successfully fixed the .po file!")
    else:
        print("\n❌ Could not fix the .po file automatically")
        sys.exit(1)
