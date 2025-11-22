#!/usr/bin/env python3
"""
Extract all English strings from templates that are NOT wrapped in {% trans %}
This will help us find all missing translations
"""

import re
import os
from pathlib import Path

# Patterns to match HTML text content that should be translated
# Excludes: already translated ({% trans %}), URLs, variables, technical terms


def extract_text_from_html(file_path):
    """Extract translatable strings from HTML file"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except:
        return []

    untranslated = []

    # Find text in common patterns that are NOT already in {% trans %}
    patterns = [
        # Headings
        r"<h[1-6][^>]*>([^{<]+)</h[1-6]>",
        # Labels
        r"<label[^>]*>([^{<]+)</label>",
        # Buttons (excluding already translated)
        r"<button[^>]*>(?!.*{%\s*trans)([^{<]+)</button>",
        # Spans with text
        r"<span[^>]*>(?!.*{%\s*trans)([^{<]+)</span>",
        # Paragraphs
        r"<p[^>]*>(?!.*{%\s*trans)([^{<]+)</p>",
        # TD cells
        r"<td[^>]*>(?!.*{%\s*trans)([^{<]+)</td>",
        # TH headers
        r"<th[^>]*>(?!.*{%\s*trans)([^{<]+)</th>",
        # Divs with simple text
        r"<div[^>]*>\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*</div>",
        # Option values
        r"<option[^>]*>([^{<]+)</option>",
        # Placeholder attributes
        r'placeholder="([^"]+)"',
        # Title attributes
        r'title="([^"]+)"',
    ]

    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)
        for match in matches:
            text = match.strip()
            # Filter out non-translatable content
            if (
                text
                and len(text) > 1
                and not text.startswith("{{")
                and not text.startswith("{%")
                and not text.startswith("http")
                and not text.startswith("/")
                and not text.startswith("#")
                and not text.isdigit()
                and not re.match(r"^[\d\s\-\+\(\)]+$", text)  # Not just numbers/symbols
                and not re.match(r"^\$[\d\.]+$", text)  # Not currency
                and re.search(r"[a-zA-Z]{2,}", text)
            ):  # Has at least one word
                untranslated.append(text)

    return list(set(untranslated))


# Scan all template directories
template_dirs = [
    "templates",
    "apps/core/templates",
]

all_strings = set()
file_count = 0

for template_dir in template_dirs:
    template_path = Path(template_dir)
    if template_path.exists():
        for html_file in template_path.rglob("*.html"):
            strings = extract_text_from_html(html_file)
            if strings:
                all_strings.update(strings)
                file_count += 1

# Sort and print
sorted_strings = sorted(all_strings)

print(f"Found {len(sorted_strings)} potentially untranslated strings in {file_count} files\n")
print("=" * 80)

# Group by category (heuristic)
categories = {"UI Actions": [], "Labels/Fields": [], "Messages": [], "Headings": [], "Other": []}

for s in sorted_strings:
    # Categorize
    if any(
        word in s.lower()
        for word in [
            "add",
            "edit",
            "delete",
            "save",
            "cancel",
            "submit",
            "create",
            "update",
            "view",
            "back",
            "next",
            "previous",
        ]
    ):
        categories["UI Actions"].append(s)
    elif any(
        word in s.lower()
        for word in [
            "name",
            "email",
            "phone",
            "address",
            "date",
            "code",
            "number",
            "type",
            "status",
            "amount",
            "price",
        ]
    ):
        categories["Labels/Fields"].append(s)
    elif any(
        word in s.lower()
        for word in ["successfully", "error", "warning", "please", "required", "invalid", "confirm"]
    ):
        categories["Messages"].append(s)
    elif s[0].isupper() and len(s.split()) <= 5:
        categories["Headings"].append(s)
    else:
        categories["Other"].append(s)

for category, items in categories.items():
    if items:
        print(f"\n{category} ({len(items)}):")
        print("-" * 80)
        for item in sorted(items)[:30]:  # Show first 30
            print(f"  {item}")
        if len(items) > 30:
            print(f"  ... and {len(items) - 30} more")
