# 🚀 Development Workflow - Optimized Pre-commit Process

## 📋 Overview

Our pre-commit hooks are designed for **maximum efficiency** with **minimal developer friction**:

<!-- Test comment to trigger pre-commit -->

- ✅ **Auto-fix**: `black` and `isort` automatically fix formatting and import issues
- ❌ **Manual fix**: `flake8` blocks commits until code quality issues are manually resolved
- 🐳 **Docker-based**: All checks run inside Docker containers for consistency

## 🔄 Commit Workflow

### 1. **Make Your Changes**
```bash
# Edit your code
vim apps/myapp/views.py
```

### 2. **Stage Your Changes**
```bash
git add .
```

### 3. **Commit (Auto-fixes Applied)**
```bash
git commit -m "feat: Add new feature"
```

**What Happens Automatically:**
```
🔍 Running pre-commit checks via Docker...
🔧 Auto-fixing code formatting with black...
✅ Black formatting applied!
🔧 Auto-fixing import sorting with isort...
✅ Import sorting applied!
❌ Checking code quality with flake8 (manual fixes required)...
✅ All flake8 checks passed!

🎉 All pre-commit checks passed! Your code is ready to commit.
   ✅ Code formatted with black
   ✅ Imports sorted with isort
   ✅ Code quality verified with flake8
```

### 4. **If Flake8 Issues Found**
```
❌ Checking code quality with flake8 (manual fixes required)...
./apps/myapp/views.py:15:1: F401 'unused_import' imported but unused
./apps/myapp/views.py:42:9: F841 local variable 'unused_var' is assigned to but never used

💡 COMMIT BLOCKED: Please fix the flake8 issues above manually.
   Common fixes:
   - Remove unused imports (F401)
   - Remove unused variables (F841)
   - Fix undefined names (F821)
   - Add missing imports

   After fixing, try committing again.
```

**Fix the issues manually:**
```bash
# Remove unused imports and variables
vim apps/myapp/views.py

# Try committing again
git add .
git commit -m "feat: Add new feature"
```

## 🎯 Benefits of This Approach

### ✅ **Developer Efficiency**
- **No manual formatting**: Never run `black .` or `isort .` manually
- **Focus on logic**: Spend time on code quality, not formatting
- **Instant feedback**: Know immediately if there are issues

### ✅ **Code Quality**
- **Consistent formatting**: All code follows the same style
- **Clean imports**: Properly sorted and organized
- **Quality enforcement**: Flake8 ensures best practices

### ✅ **Team Productivity**
- **No formatting debates**: Tools handle it automatically
- **Reduced review time**: PRs focus on logic, not style
- **Consistent codebase**: Everyone follows the same standards

## 🛠️ Tool Configuration

### Black (Auto-fix)
```yaml
# .pre-commit-config.yaml
- id: black
  name: 🔧 black (auto-fix formatting)
  entry: docker compose exec -T web black
  args: ['--line-length=100']
```

### isort (Auto-fix)
```yaml
# .pre-commit-config.yaml
- id: isort
  name: 🔧 isort (auto-fix imports)
  entry: docker compose exec -T web isort
  args: ['--profile', 'black', '--line-length', '100']
```

### Flake8 (Manual fix required)
```yaml
# .pre-commit-config.yaml
- id: flake8
  name: ❌ flake8 (blocks commit - manual fixes required)
  entry: docker compose exec -T web flake8
  args: ['--max-line-length=100', '--extend-ignore=E203,W503']
```

## 🚨 Common Flake8 Issues & Fixes

### F401: Unused Import
```python
# ❌ Bad
import unused_module
from django.shortcuts import render

def my_view(request):
    return render(request, 'template.html')

# ✅ Good
from django.shortcuts import render

def my_view(request):
    return render(request, 'template.html')
```

### F841: Unused Variable
```python
# ❌ Bad
def process_data():
    result = expensive_calculation()
    return "done"

# ✅ Good
def process_data():
    expensive_calculation()
    return "done"
```

### F821: Undefined Name
```python
# ❌ Bad
def my_view(request):
    return JsonResponse({'data': data})  # 'data' not defined

# ✅ Good
from django.http import JsonResponse

def my_view(request):
    data = {'key': 'value'}
    return JsonResponse({'data': data})
```

## 🔧 Manual Commands (If Needed)

If you need to run tools manually:

```bash
# Format code
docker compose exec web black .

# Sort imports
docker compose exec web isort .

# Check linting
docker compose exec web flake8 .

# Run all checks
docker compose exec web black . && docker compose exec web isort . && docker compose exec web flake8 .
```

## 📝 Summary

This workflow ensures:
- **Zero time spent on formatting** - tools handle it automatically
- **High code quality** - flake8 enforces best practices
- **Consistent codebase** - everyone follows the same standards
- **Fast development** - focus on features, not formatting

**The result**: Clean, consistent, high-quality code with minimal developer effort! 🎉