#!/usr/bin/env python3
"""
Translation Hot Reload Watcher for Development

This script watches .po translation files and automatically:
1. Compiles them to .mo files when they change
2. Sends HUP signal to gunicorn to reload Django
3. Logs all compilation and reload events

Used in development with Skaffold file sync for instant translation updates.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer


class TranslationFileHandler(FileSystemEventHandler):
    """Handle .po file changes by compiling and reloading Django"""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.last_compile_time = {}
        self.debounce_seconds = 2  # Prevent duplicate compilations

    def on_modified(self, event):
        """Triggered when a .po file is modified"""
        if event.is_directory or not event.src_path.endswith(".po"):
            return

        po_file = Path(event.src_path)
        current_time = time.time()

        # Debounce: skip if we compiled this file within last 2 seconds
        if po_file in self.last_compile_time:
            if current_time - self.last_compile_time[po_file] < self.debounce_seconds:
                return

        self.last_compile_time[po_file] = current_time

        # Extract language code from path (e.g., locale/fa/LC_MESSAGES/django.po -> fa)
        try:
            parts = po_file.parts
            locale_idx = parts.index("locale")
            language_code = parts[locale_idx + 1]
        except (ValueError, IndexError):
            print(f"❌ Could not extract language code from {po_file}")
            return

        print(f"\n🔄 Translation file changed: {po_file}")
        print(f"📝 Compiling messages for language: {language_code}")

        # Compile messages
        try:
            result = subprocess.run(
                [sys.executable, "manage.py", "compilemessages", "-l", language_code],
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                print(f"✅ Successfully compiled messages for {language_code}")
                # Send HUP signal to gunicorn master process (PID 1 in container)
                try:
                    os.kill(1, signal.SIGHUP)
                    print(f"🔃 Sent reload signal to gunicorn")
                except ProcessLookupError:
                    print(f"⚠️  Could not find gunicorn process (PID 1)")
            else:
                print(f"❌ Compilation failed:")
                print(result.stderr)

        except subprocess.TimeoutExpired:
            print(f"❌ Compilation timed out after 30 seconds")
        except Exception as e:
            print(f"❌ Compilation error: {e}")


def main():
    """Start watching translation files"""
    base_dir = Path(__file__).parent.parent.resolve()
    locale_dir = base_dir / "locale"

    if not locale_dir.exists():
        print(f"❌ Locale directory not found: {locale_dir}")
        sys.exit(1)

    print("🔍 Translation Hot Reload Watcher")
    print(f"📁 Watching: {locale_dir}")
    print(f"⚡ Changes to .po files will trigger automatic compilation and reload")
    print()

    event_handler = TranslationFileHandler(base_dir)
    observer = Observer()
    observer.schedule(event_handler, str(locale_dir), recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹️  Stopping translation watcher...")
        observer.stop()

    observer.join()


if __name__ == "__main__":
    main()
