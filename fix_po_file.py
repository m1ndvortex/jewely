#!/usr/bin/env python3
"""
Fix corrupted django.po file by extracting malformed entries and reconstructing properly
"""

import re
from pathlib import Path


def fix_po_file():
    """Fix the corrupted .po file"""
    po_file = Path("locale/fa/LC_MESSAGES/django.po")

    if not po_file.exists():
        print(f"❌ File not found: {po_file}")
        return False

    content = po_file.read_text(encoding="utf-8")

    print("🔍 Analyzing .po file...")

    # Find the corrupted section (around line 2448)
    # The problem is that new entries were inserted inside msgid_plural

    # Pattern to find the broken msgid_plural section
    broken_pattern = r'msgid_plural ""\n"[^"]*"(.*?)msgstr\[0\] ""'

    matches = list(re.finditer(broken_pattern, content, re.DOTALL))

    if matches:
        print(f"Found {len(matches)} broken msgid_plural sections")

        for match in matches:
            broken_section = match.group(0)

            # Extract the embedded msgid entries
            embedded_entries = []
            embedded_pattern = r'msgid "(.*?)"\nmsgstr "(.*?)"\n'

            for emb_match in re.finditer(embedded_pattern, broken_section):
                msgid = emb_match.group(1)
                msgstr = emb_match.group(2)
                if msgid and msgstr:
                    embedded_entries.append((msgid, msgstr))
                    print(f"  📝 Extracted: {msgid[:50]}...")

            # Remove the embedded entries from the broken section
            # Keep only the proper msgid_plural structure
            cleaned_section = re.sub(r"\nmsgid.*?msgstr.*?\n", "\n", broken_section)

            # Replace in content
            content = content.replace(broken_section, cleaned_section)

            # Now add the extracted entries properly at the end
            for msgid, msgstr in embedded_entries:
                # Check if entry already exists elsewhere
                check_pattern = f'msgid "{re.escape(msgid)}"\\s*\\nmsgstr "[^"]*"'
                if not re.search(check_pattern, content):
                    # Add new entry
                    insert_pos = content.rfind("\n#:")
                    if insert_pos == -1:
                        insert_pos = len(content) - 100

                    new_entry = f'\nmsgid "{msgid}"\nmsgstr "{msgstr}"\n'
                    content = content[:insert_pos] + new_entry + content[insert_pos:]
                    print(f"  ✅ Re-added: {msgid[:50]}...")

    # Remove duplicate entries (keep first occurrence)
    lines = content.split("\n")
    seen_msgids = {}
    cleaned_lines = []
    i = 0

    while i < len(lines):
        line = lines[i]

        if line.startswith('msgid "'):
            # Extract msgid
            msgid_match = re.match(r'msgid "(.*)"', line)
            if msgid_match:
                msgid_text = msgid_match.group(1)

                # Get the full entry (msgid + msgstr)
                entry_lines = [line]
                i += 1

                # Collect continuation lines and msgstr
                while i < len(lines) and (
                    lines[i].startswith('"') or lines[i].startswith("msgstr")
                ):
                    entry_lines.append(lines[i])
                    if lines[i].startswith("msgstr"):
                        i += 1
                        # Get msgstr value
                        while i < len(lines) and lines[i].startswith('"'):
                            entry_lines.append(lines[i])
                            i += 1
                        break
                    i += 1

                # Check for duplicates
                if msgid_text in seen_msgids:
                    print(f"  🗑️  Removing duplicate: {msgid_text[:50]}...")
                else:
                    seen_msgids[msgid_text] = True
                    cleaned_lines.extend(entry_lines)

                continue

        cleaned_lines.append(line)
        i += 1

    # Reconstruct content
    content = "\n".join(cleaned_lines)

    # Write fixed content
    po_file.write_text(content, encoding="utf-8")

    print(f"\n✅ Fixed {po_file}")
    print(f"🎉 Ready to compile!")

    return True


if __name__ == "__main__":
    print("Fixing corrupted django.po file...")
    fix_po_file()
