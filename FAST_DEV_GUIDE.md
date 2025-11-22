# 🚀 FAST DEVELOPMENT WORKFLOW - SIMPLE & EFFECTIVE

## ✅ What We've Set Up

1. **Cleaned Docker images**: Freed 36GB of disk space
2. **Scaled to 1 pod**: Faster iterations  
3. **File sync script**: `dev-sync.sh` watches and syncs changes instantly

## 📝 How To Use

### Start Development Mode

```bash
# In one terminal - run the file sync watcher
./dev-sync.sh
```

This script watches for changes in your code and **instantly syncs** them to the running pod.

### Make Changes and See Them Live

**Python Code:**
```bash
# Edit any .py file
vim accounting/views.py

# Save - dev-sync.sh automatically:
# 1. Copies file to pod (1-2 seconds)
# 2. Gunicorn detects change and reloads (2-3 seconds)
# 3. Total: 3-5 seconds to see changes ✅
```

**Templates:**
```bash
# Edit HTML
vim templates/accounting/dashboard.html

# Save - Syncs instantly, refresh browser
```

**Translations:**
```bash
# Edit .po file
vim locale/fa/LC_MESSAGES/django.po

# Save - Script automatically:
# 1. Syncs .po file
# 2. Runs compilemessages in pod
# 3. Restarts gunicorn
# Total: 5-7 seconds
```

**CSS/JS:**
```bash
# Edit static files
vim static/css/custom.css

# Save - Syncs instantly, hard refresh browser (Ctrl+F5)
```

## 📊 Speed Comparison

### Before:
```
Edit code → docker build (500s) → k3d import (150s) → deploy (60s) = 11 MINUTES ❌
```

### Now with dev-sync.sh:
```
Edit code → Auto-sync (1-2s) → Auto-reload (2-3s) = 3-5 SECONDS ✅
```

## 🛠️ What dev-sync.sh Does

- **Watches** all code directories with `inotifywait`
- **Auto-syncs** changed files to running pod via `kubectl cp`
- **Auto-compiles** translations when .po files change
- **Skips** junk files (`__pycache__`, `.pyc`, `.git`, etc.)
- **Real-time feedback** with colored console output

## 💡 Tips

1. **Keep dev-sync.sh running** in a dedicated terminal
2. **Watch the output** to see files syncing in real-time
3. **For new dependencies** (requirements.txt changes):
   ```bash
   # Still need to rebuild for dependency changes
   docker build -t jewelry-shop-django:latest -f Dockerfile.prod .
   k3d image import jewelry-shop-django:latest -c jewelry-shop
   kubectl delete pods -n jewelry-shop -l component=django
   ```

4. **For database migrations**:
   ```bash
   kubectl exec -n jewelry-shop $(kubectl get pod -n jewelry-shop -l component=django -o name | head -n 1) -- \
     python manage.py migrate
   ```

5. **Check pod logs** if something doesn't reload:
   ```bash
   kubectl logs -f -n jewelry-shop -l component=django
   ```

## 🎯 Quick Commands

```bash
# Start file sync (main command)
./dev-sync.sh

# Check Django pod
kubectl get pods -n jewelry-shop -l component=django

# View Django logs
kubectl logs -f -n jewelry-shop -l component=django

# Access shell in pod
kubectl exec -it -n jewelry-shop $(kubectl get pod -n jewelry-shop -l component=django -o name | head -n 1) -- /bin/bash

# Manual file sync (if needed)
kubectl cp myfile.py jewelry-shop/$(kubectl get pod -n jewelry-shop -l component=django -o jsonpath='{.items[0].metadata.name}'):/app/myfile.py

# Restart Django manually
kubectl delete pods -n jewelry-shop -l component=django
```

## ✨ Summary

**Goal Achieved:** 
- ✅ Instant code changes (3-5 seconds)
- ✅ No rebuilds for code/template/translation changes
- ✅ Production-like environment (same Docker image, k8s setup)
- ✅ Simple script, no complex tools

**Start developing:**
```bash
# Terminal 1: Run file sync
./dev-sync.sh

# Terminal 2: Edit code
vim accounting/views.py

# Terminal 3: Watch logs (optional)
kubectl logs -f -n jewelry-shop -l component=django
```

**Access app:**
```
https://jewelry-shop.local:8443
```

Happy coding! 🎉
