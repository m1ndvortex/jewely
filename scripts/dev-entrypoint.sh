#!/bin/bash
# Development entrypoint: Run gunicorn with translation hot reload

set -e

echo "🚀 Starting Django development server with hot reload..."

# Start translation watcher in background
python /app/scripts/watch_translations.py &
WATCHER_PID=$!
echo "✅ Translation watcher started (PID: $WATCHER_PID)"

# Trap to cleanup watcher on exit
trap "echo '⏹️  Stopping translation watcher...'; kill $WATCHER_PID 2>/dev/null || true" EXIT

# Start gunicorn with reload (exec replaces this process with gunicorn as PID 1)
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3 \
    --threads 2 \
    --reload \
    --reload-extra-file /app/locale \
    --access-logfile - \
    --error-logfile - \
    --log-level info
