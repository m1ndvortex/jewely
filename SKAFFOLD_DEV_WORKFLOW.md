# 🚀 Fast Development Workflow with Skaffold

## Quick Start

### 1. First Time Setup (Already Done)
```bash
✅ Skaffold installed: v2.17.0
✅ Pods scaled to 1 replica
✅ Docker images cleaned (36GB freed)
```

### 2. Start Development Mode

```bash
# Start Skaffold in development mode
skaffold dev

# Or run in background and tail logs
skaffold dev --port-forward &
```

**What happens:**
- Skaffold watches for file changes
- When you edit code, templates, translations, or static files
- Files are **synced directly to running pod** (no rebuild!)
- Gunicorn auto-reloads the application
- Changes appear in **~2-5 seconds** ✨

### 3. Make Changes and See Them Instantly

**Python Code:**
```bash
# Edit any .py file
vim accounting/views.py
# Save - Skaffold syncs → Gunicorn reloads → Live in 2-3 seconds
```

**Templates:**
```bash
# Edit HTML templates
vim templates/accounting/dashboard.html
# Save - Instant sync → No reload needed
```

**Translations:**
```bash
# Edit .po file
vim locale/fa/LC_MESSAGES/django.po
# Compile
make compilemessages  # Or: msgfmt -o django.mo django.po
# Save - Skaffold syncs .mo → Gunicorn reloads → Live immediately
```

**Static Files (CSS/JS):**
```bash
# Edit CSS or JavaScript
vim static/css/custom.css
# Save - Instant sync → Refresh browser
```

### 4. Access Your App

```bash
# Skaffold auto port-forwards
https://jewelry-shop.local:8443
```

### 5. Stop Development Mode

```bash
# Press Ctrl+C in the skaffold dev terminal
# Or if running in background:
pkill -f "skaffold dev"
```

## What Gets Synced Instantly (No Rebuild)

✅ **Python files** (`**/*.py`)
✅ **Templates** (`templates/**/*`)
✅ **Translations** (`locale/**/*`)
✅ **Static files** (`static/**/*`)
✅ **CSS/JS** (`.css`, `.js`)
✅ **HTML** (`.html`)

## What Requires Rebuild

❌ **Dependencies** (`requirements.txt` changes)
❌ **Dockerfile** changes
❌ **System packages** (`apt install`)
❌ **Environment variables** in k8s manifests

## Development Workflow

### Traditional (Before):
```
Edit code → docker build (500s) → k3d import (150s) → deploy (60s) = 11 minutes ❌
```

### With Skaffold (Now):
```
Edit code → Skaffold syncs (1-2s) → Gunicorn reloads (2-3s) = 3-5 seconds ✅
```

## Tips for Maximum Speed

1. **Keep Skaffold Running:**
   ```bash
   # Run in a dedicated terminal
   skaffold dev
   ```

2. **Watch the Logs:**
   ```bash
   # Skaffold shows real-time sync and reload events
   [django] Watching for file changes with StatReloader
   [django] File synced: /app/accounting/views.py
   [django] Worker reloading: /app/accounting/views.py changed
   ```

3. **Compile Translations in Container:**
   ```bash
   # If you edit .po files, compile in the running pod
   kubectl exec -n jewelry-shop $(kubectl get pod -n jewelry-shop -l component=django -o name) -- \
     python manage.py compilemessages
   ```

4. **For Static Files (CSS/JS):**
   - Changes sync instantly
   - Just refresh browser (Ctrl+F5 for hard refresh)
   - No collectstatic needed during development

5. **For Database Migrations:**
   ```bash
   # Still need to run migrations manually
   kubectl exec -n jewelry-shop $(kubectl get pod -n jewelry-shop -l component=django -o name) -- \
     python manage.py migrate
   ```

## Troubleshooting

### Files Not Syncing?
```bash
# Check Skaffold is watching
skaffold dev --verbosity=debug

# Verify file patterns in skaffold.yaml
cat skaffold.yaml | grep -A 20 "sync:"
```

### Gunicorn Not Reloading?
```bash
# Check pod logs
kubectl logs -n jewelry-shop -l component=django -f

# Verify --reload flag in deployment
kubectl get deployment django -n jewelry-shop -o yaml | grep reload
```

### Need to Rebuild?
```bash
# Force rebuild (for dependency changes)
skaffold dev --force-deploy

# Or rebuild specific artifact
skaffold build --file-output=build.json
```

## Production Deployment

When ready for production, use the original deployment:

```bash
# Build production image
docker build -t jewelry-shop-django:latest -f Dockerfile.prod .

# Import to k3d
k3d image import jewelry-shop-django:latest -c jewelry-shop

# Deploy with production config
kubectl apply -f k8s/django-deployment.yaml

# Scale to 3 replicas
kubectl scale deployment django --replicas=3 -n jewelry-shop
```

## Summary

🎯 **Goal Achieved:** Change code → See results in 3-5 seconds  
🚫 **No more:** 11-minute build/deploy cycles  
✨ **Benefits:** 
- Instant feedback
- Production-like environment (k8s + Docker)
- File sync = no rebuilds
- Auto-reload on code changes
- Same stack as production
