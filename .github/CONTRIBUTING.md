# Contributing to Jewelry Shop Management Platform

Thank you for contributing! This guide will help you understand our CI/CD pipeline and development workflow.

## Quick Start

1. **Fork and Clone**
   ```bash
   git clone https://github.com/YOUR_USERNAME/jewelry-shop.git
   cd jewelry-shop
   ```

2. **Create Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make Changes**
   - Write code following our style guide
   - Add tests for new functionality
   - Update documentation

4. **Run Tests Locally**
   ```bash
   docker compose exec web pytest
   ```

5. **Check Code Quality**
   ```bash
   docker compose exec web black apps/ config/ tests/
   docker compose exec web isort apps/ config/ tests/
   docker compose exec web flake8 apps/ config/ tests/
   docker compose exec web mypy apps/ config/
   ```

6. **Commit and Push**
   ```bash
   git add .
   git commit -m "feat: add new feature"
   git push origin feature/your-feature-name
   ```

7. **Create Pull Request**
   - Go to GitHub and create PR
   - Wait for CI checks to pass
   - Request review from maintainers

## CI/CD Pipeline

When you push code or create a PR, our automated pipeline runs:

### 1. Code Quality Checks (5-7 min)
- ✅ Black (formatting)
- ✅ isort (imports)
- ✅ Flake8 (linting)
- ✅ MyPy (type checking)
- ✅ Bandit (security)
- ✅ Safety (dependencies)

### 2. Tests & Coverage (8-12 min)
- ✅ Full test suite with pytest
- ✅ Code coverage report
- ✅ Coverage must be ≥75%
- ✅ PR comment with coverage details

### 3. Build Docker Image (5-8 min)
- ✅ Multi-stage build
- ✅ Push to registry
- ✅ Tagged with branch name

### 4. Security Scan (3-5 min)
- ✅ Container vulnerability scan
- ✅ Results in GitHub Security tab

## Code Style Guide

### Python Code Style

We use **Black** for formatting and **isort** for import sorting:

```python
# Good
from typing import List, Optional

from django.db import models
from django.utils import timezone

from apps.core.models import BaseModel


class Product(BaseModel):
    """Product model for inventory management."""
    
    name: str = models.CharField(max_length=255)
    price: Decimal = models.DecimalField(max_digits=10, decimal_places=2)
    
    def calculate_discount(self, percentage: float) -> Decimal:
        """Calculate discounted price."""
        return self.price * (1 - percentage / 100)
```

### Commit Message Format

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**
```bash
feat(inventory): add barcode scanning support
fix(pos): resolve payment calculation error
docs(api): update authentication documentation
test(crm): add customer loyalty tests
```

## Testing Guidelines

### Writing Tests

```python
# tests/test_inventory.py
import pytest
from django.test import TestCase

from apps.inventory.models import Product


class TestProduct(TestCase):
    """Test Product model."""
    
    def setUp(self):
        """Set up test data."""
        self.product = Product.objects.create(
            name="Gold Ring",
            sku="GR-001",
            price=299.99
        )
    
    def test_product_creation(self):
        """Test product is created correctly."""
        assert self.product.name == "Gold Ring"
        assert self.product.sku == "GR-001"
    
    def test_calculate_discount(self):
        """Test discount calculation."""
        discounted = self.product.calculate_discount(10)
        assert discounted == 269.99
```

### Running Tests

```bash
# Run all tests
docker compose exec web pytest

# Run specific test file
docker compose exec web pytest tests/test_inventory.py

# Run with coverage
docker compose exec web pytest --cov=apps --cov-report=html

# Run specific test
docker compose exec web pytest tests/test_inventory.py::TestProduct::test_product_creation
```

## Pre-commit Hooks

We use pre-commit hooks to ensure code quality:

```bash
# Install pre-commit hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

Hooks will automatically:
- Format code with Black
- Sort imports with isort
- Check for common issues
- Lint with Flake8

## Pull Request Process

1. **Create PR**
   - Use descriptive title
   - Fill out PR template
   - Link related issues

2. **Wait for CI**
   - All checks must pass
   - Coverage must be ≥75%
   - No security issues

3. **Code Review**
   - Address reviewer comments
   - Push updates to same branch
   - CI will re-run automatically

4. **Merge**
   - Squash and merge (preferred)
   - Delete branch after merge

## Common Issues

### Tests Failing in CI

**Problem:** Tests pass locally but fail in CI

**Solution:**
- Check service versions (PostgreSQL, Redis)
- Verify environment variables
- Review CI logs for details

### Coverage Below Threshold

**Problem:** Coverage drops below 75%

**Solution:**
- Add tests for new code
- Check coverage report: `htmlcov/index.html`
- Focus on untested lines

### Linting Errors

**Problem:** Flake8 or Black errors

**Solution:**
```bash
# Auto-fix formatting
docker compose exec web black apps/ config/ tests/
docker compose exec web isort apps/ config/ tests/

# Check remaining issues
docker compose exec web flake8 apps/ config/ tests/
```

### Type Checking Warnings

**Problem:** MyPy type errors

**Solution:**
- Add type hints to functions
- Use `typing` module for complex types
- Check MyPy documentation

## Security

### Reporting Vulnerabilities

**DO NOT** create public issues for security vulnerabilities.

Instead:
1. Email security@jewelry-shop.example.com
2. Include detailed description
3. Wait for response before disclosure

### Security Scanning

Our pipeline automatically scans for:
- Code vulnerabilities (Bandit)
- Dependency vulnerabilities (Safety, pip-audit)
- Container vulnerabilities (Trivy)
- Exposed secrets (Gitleaks)

## Getting Help

- **Documentation:** Check `.github/workflows/README.md`
- **Issues:** Search existing issues first
- **Discussions:** Use GitHub Discussions for questions
- **Slack:** Join our development channel

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Help others learn and grow
- Follow our code of conduct

## License

By contributing, you agree that your contributions will be licensed under the project's license.

## Thank You!

Your contributions make this project better for everyone. We appreciate your time and effort! 🙏
