#!/bin/bash

# Simple Smoke Test: Core Functionality Only
# Tests: Database → Tenant → User → Inventory

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

NAMESPACE="jewelry-shop"
LOG_FILE="k8s/SMOKE_TEST_SIMPLE_$(date +%Y%m%d_%H%M%S).log"

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
    echo "✅ $1" >> "$LOG_FILE"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
    echo "❌ $1" >> "$LOG_FILE"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
    echo "ℹ️  $1" >> "$LOG_FILE"
}

echo "Simple Smoke Test" > "$LOG_FILE"
echo "Test Date: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

echo ""
echo "========================================="
echo "Simple Smoke Test: Core Functionality"
echo "========================================="
echo ""

# Get Django pod
DJANGO_POD=$(kubectl get pods -n $NAMESPACE -l component=django -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$DJANGO_POD" ]; then
    print_error "No Django pod found"
    exit 1
fi

print_success "Found Django pod: $DJANGO_POD"

# Test 1: Database Connection
print_info "Test 1: Database Connection"
DB_CHECK=$(kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py check --database default 2>&1)
if echo "$DB_CHECK" | grep -q "System check identified no issues"; then
    print_success "Database connection works"
else
    print_error "Database connection failed"
    exit 1
fi

# Test 2: Create Tenant
print_info "Test 2: Create Tenant"
TENANT_RESULT=$(timeout 30 kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py shell -c "
from apps.core.models import Tenant
from django.utils.text import slugify

tenant_name = 'Simple Test Shop'
tenant_slug = slugify(tenant_name)

tenant, created = Tenant.objects.get_or_create(
    slug=tenant_slug,
    defaults={'company_name': tenant_name, 'status': 'ACTIVE'}
)
print(f'TENANT:{tenant.id}:{\"CREATED\" if created else \"EXISTS\"}')
" 2>&1)

if echo "$TENANT_RESULT" | grep -q "TENANT:"; then
    TENANT_ID=$(echo "$TENANT_RESULT" | grep "TENANT:" | cut -d':' -f2)
    print_success "Tenant ready: $TENANT_ID"
else
    print_error "Tenant creation failed"
    echo "$TENANT_RESULT"
    exit 1
fi

# Test 3: Create User
print_info "Test 3: Create Tenant User"
USER_RESULT=$(timeout 30 kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py shell -c "
from django.contrib.auth import get_user_model
from apps.core.models import Tenant

User = get_user_model()
tenant = Tenant.objects.get(id='$TENANT_ID')

user, created = User.objects.get_or_create(
    username='test_owner',
    tenant=tenant,
    defaults={
        'email': 'test@shop.com',
        'role': 'TENANT_OWNER'
    }
)
if created:
    user.set_password('testpass123')
    user.save()

print(f'USER:{user.id}:{\"CREATED\" if created else \"EXISTS\"}')
" 2>&1)

if echo "$USER_RESULT" | grep -q "USER:"; then
    print_success "User created successfully"
else
    print_error "User creation failed"
    echo "$USER_RESULT"
    exit 1
fi

# Test 4: Create Inventory Item
print_info "Test 4: Create Inventory Item"
ITEM_RESULT=$(timeout 30 kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py shell -c "
from apps.inventory.models import InventoryItem, ProductCategory
from apps.core.models import Tenant, Branch
from decimal import Decimal

tenant = Tenant.objects.get(id='$TENANT_ID')

# Create branch
branch, _ = Branch.objects.get_or_create(
    tenant=tenant,
    name='Main Branch',
    defaults={'address': '123 Test St', 'is_active': True}
)

# Create category
category, _ = ProductCategory.objects.get_or_create(
    tenant=tenant,
    name='Test Rings',
    defaults={}
)

# Create item
item, created = InventoryItem.objects.get_or_create(
    tenant=tenant,
    sku='SIMPLE-TEST-001',
    defaults={
        'name': 'Simple Test Ring',
        'category': category,
        'karat': 18,
        'weight_grams': Decimal('5.0'),
        'cost_price': Decimal('500.00'),
        'selling_price': Decimal('750.00'),
        'quantity': 10,
        'branch': branch,
        'is_active': True
    }
)

print(f'ITEM:{item.id}:{\"CREATED\" if created else \"EXISTS\"}')
" 2>&1)

if echo "$ITEM_RESULT" | grep -q "ITEM:"; then
    print_success "Inventory item created successfully"
else
    print_error "Inventory item creation failed"
    echo "$ITEM_RESULT"
    exit 1
fi

# Summary
echo ""
echo "========================================="
echo "SIMPLE SMOKE TEST RESULTS"
echo "========================================="
echo ""
echo "✅ Database Connection: PASS" | tee -a "$LOG_FILE"
echo "✅ Tenant Creation: PASS" | tee -a "$LOG_FILE"
echo "✅ User Creation: PASS" | tee -a "$LOG_FILE"
echo "✅ Inventory Creation: PASS" | tee -a "$LOG_FILE"
echo ""
print_success "ALL TESTS PASSED! ✅"
echo ""
echo "Log file: $LOG_FILE"

exit 0
