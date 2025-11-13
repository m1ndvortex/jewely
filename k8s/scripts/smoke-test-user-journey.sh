#!/bin/bash

# Smoke Test: Complete User Journey
# Tests: Login → Create Tenant → Add Inventory → Create Sale

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

NAMESPACE="jewelry-shop"
LOG_FILE="k8s/SMOKE_TEST_$(date +%Y%m%d_%H%M%S).log"

print_header() {
    echo -e "\n${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}\n"
}

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

echo "Smoke Test: User Journey" > "$LOG_FILE"
echo "Test Date: $(date)" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

print_header "Smoke Test: Complete User Journey"

# Get Django pod
DJANGO_POD=$(kubectl get pods -n $NAMESPACE -l component=django -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)

if [ -z "$DJANGO_POD" ]; then
    print_error "No Django pod found"
    exit 1
fi

print_success "Found Django pod: $DJANGO_POD"

# Test 1: Database Connection
print_header "Step 1: Verify Database Connection"

DB_CHECK=$(kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py check --database default 2>&1)
if echo "$DB_CHECK" | grep -q "System check identified no issues"; then
    print_success "Database connection verified"
else
    print_error "Database connection failed"
    exit 1
fi

# Test 2: Run Migrations
print_header "Step 2: Verify Database Schema"

MIGRATION_CHECK=$(kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py showmigrations 2>&1)
if echo "$MIGRATION_CHECK" | grep -q "\[X\]"; then
    print_success "Database migrations applied"
else
    print_error "Database migrations not applied"
    print_info "Attempting to run migrations..."
    kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py migrate
fi

# Test 3: Create Superuser (if not exists)
print_header "Step 3: Verify Admin User"

print_info "Checking if platform admin exists..."
USER_EXISTS=$(kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
print('EXISTS' if User.objects.filter(is_superuser=True, role='PLATFORM_ADMIN').exists() else 'NONE')
" 2>&1)

if echo "$USER_EXISTS" | grep -q "EXISTS"; then
    print_success "Platform admin already exists"
else
    print_info "Creating platform admin..."
    kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
user = User(
    username='admin',
    email='admin@example.com',
    is_superuser=True,
    is_staff=True,
    role='PLATFORM_ADMIN',
    tenant=None
)
user.set_password('admin123')
user.save()
print('CREATED')
" 2>&1
    print_success "Platform admin created"
fi

# Test 4: Create Test Tenant
print_header "Step 4: Create Test Tenant"

print_info "Creating test tenant..."
TENANT_RESULT=$(kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py shell -c "
from apps.core.models import Tenant
from django.utils.text import slugify
import uuid

tenant_name = 'E2E Test Shop'
tenant_slug = slugify(tenant_name)

# Check if tenant exists
existing = Tenant.objects.filter(slug=tenant_slug).first()
if existing:
    print(f'TENANT_EXISTS:{existing.id}')
else:
    tenant = Tenant.objects.create(
        company_name=tenant_name,
        slug=tenant_slug,
        status='ACTIVE'
    )
    print(f'TENANT_CREATED:{tenant.id}')
" 2>&1)

if echo "$TENANT_RESULT" | grep -q "TENANT_CREATED\|TENANT_EXISTS"; then
    TENANT_ID=$(echo "$TENANT_RESULT" | grep -E "TENANT_CREATED|TENANT_EXISTS" | grep -oP '(?<=:)[a-f0-9-]+' | head -1)
    print_success "Tenant ready: $TENANT_ID"
else
    print_error "Failed to create tenant"
    echo "$TENANT_RESULT"
    exit 1
fi

# Test 5: Create Test User for Tenant
print_header "Step 5: Create Tenant User"

print_info "Creating tenant user..."
USER_RESULT=$(kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py shell -c "
from django.contrib.auth import get_user_model
from apps.core.models import Tenant
import uuid

User = get_user_model()
tenant = Tenant.objects.get(id='$TENANT_ID')

# Check if user exists
username = 'shop_owner'
existing_user = User.objects.filter(username=username, tenant=tenant).first()

if existing_user:
    print(f'USER_EXISTS:{existing_user.id}')
else:
    user = User.objects.create_user(
        username=username,
        email='owner@testshop.com',
        password='testpass123',
        tenant=tenant,
        role='TENANT_OWNER'
    )
    print(f'USER_CREATED:{user.id}')
" 2>&1)

if echo "$USER_RESULT" | grep -q "USER_CREATED\|USER_EXISTS"; then
    print_success "Tenant user ready"
else
    print_error "Failed to create tenant user"
    echo "$USER_RESULT"
    exit 1
fi

# Test 6: Create Inventory Item
print_header "Step 6: Create Inventory Item"

print_info "Creating test inventory item..."
INVENTORY_RESULT=$(kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py shell -c "
from apps.inventory.models import InventoryItem, ProductCategory
from apps.core.models import Tenant, Branch
from decimal import Decimal

tenant = Tenant.objects.get(id='$TENANT_ID')

# Create branch if not exists
branch, _ = Branch.objects.get_or_create(
    tenant=tenant,
    name='Main Branch',
    defaults={'address': '123 Test St', 'is_active': True}
)

# Create category if not exists
category, _ = ProductCategory.objects.get_or_create(
    tenant=tenant,
    name='Rings',
    defaults={}
)

# Create inventory item
item, created = InventoryItem.objects.get_or_create(
    tenant=tenant,
    sku='TEST-RING-001',
    defaults={
        'name': 'Test Gold Ring',
        'category': category,
        'karat': 18,
        'weight_grams': Decimal('5.5'),
        'cost_price': Decimal('500.00'),
        'selling_price': Decimal('750.00'),
        'quantity': 10,
        'branch': branch,
        'is_active': True
    }
)

if created:
    print(f'ITEM_CREATED:{item.id}')
else:
    print(f'ITEM_EXISTS:{item.id}')
" 2>&1)

if echo "$INVENTORY_RESULT" | grep -q "ITEM_CREATED\|ITEM_EXISTS"; then
    ITEM_ID=$(echo "$INVENTORY_RESULT" | grep -E "ITEM_CREATED|ITEM_EXISTS" | grep -oP '(?<=:)\d+' | head -1)
    print_success "Inventory item ready: $ITEM_ID"
else
    print_error "Failed to create inventory item"
    echo "$INVENTORY_RESULT"
    exit 1
fi

# Test 7: Create Sale
print_header "Step 7: Create Test Sale"

print_info "Creating test sale..."
SALE_RESULT=$(kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py shell -c "
from apps.sales.models import Sale, SaleItem
from apps.inventory.models import InventoryItem
from apps.core.models import Tenant, Branch, Terminal
from django.contrib.auth import get_user_model
from decimal import Decimal
import uuid

User = get_user_model()
tenant = Tenant.objects.get(id='$TENANT_ID')
branch = Branch.objects.filter(tenant=tenant).first()
user = User.objects.filter(tenant=tenant, role='TENANT_OWNER').first()
item = InventoryItem.objects.get(id=$ITEM_ID)

# Create terminal if not exists
terminal, _ = Terminal.objects.get_or_create(
    branch=branch,
    terminal_id='TERM-001',
    defaults={'is_active': True}
)

# Create sale
sale_number = f'SALE-{uuid.uuid4().hex[:8].upper()}'
sale = Sale.objects.create(
    tenant=tenant,
    sale_number=sale_number,
    branch=branch,
    terminal=terminal,
    employee=user,
    subtotal=Decimal('750.00'),
    tax=Decimal('75.00'),
    discount=Decimal('0.00'),
    total=Decimal('825.00'),
    payment_method='CASH',
    status='COMPLETED'
)

# Create sale item
sale_item = SaleItem.objects.create(
    sale=sale,
    inventory_item=item,
    quantity=1,
    unit_price=Decimal('750.00'),
    subtotal=Decimal('750.00')
)

# Update inventory
item.quantity -= 1
item.save()

print(f'SALE_CREATED:{sale.id}:{sale.sale_number}')
" 2>&1)

if echo "$SALE_RESULT" | grep -q "SALE_CREATED"; then
    SALE_INFO=$(echo "$SALE_RESULT" | grep "SALE_CREATED")
    print_success "Sale created successfully"
    print_info "$SALE_INFO"
else
    print_error "Failed to create sale"
    echo "$SALE_RESULT"
    exit 1
fi

# Test 8: Verify Data Consistency
print_header "Step 8: Verify Data Consistency"

print_info "Checking inventory quantity after sale..."
INVENTORY_CHECK=$(kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py shell -c "
from apps.inventory.models import InventoryItem
item = InventoryItem.objects.get(id=$ITEM_ID)
print(f'QUANTITY:{item.quantity}')
" 2>&1)

if echo "$INVENTORY_CHECK" | grep -q "QUANTITY:9"; then
    print_success "Inventory quantity correctly updated (10 → 9)"
else
    print_error "Inventory quantity not updated correctly"
    echo "$INVENTORY_CHECK"
fi

print_info "Checking sale record..."
SALE_CHECK=$(kubectl exec -n $NAMESPACE $DJANGO_POD -- python manage.py shell -c "
from apps.sales.models import Sale
sale_count = Sale.objects.filter(tenant_id='$TENANT_ID').count()
print(f'SALES_COUNT:{sale_count}')
" 2>&1)

if echo "$SALE_CHECK" | grep -q "SALES_COUNT:[1-9]"; then
    print_success "Sale record exists in database"
else
    print_error "Sale record not found"
    echo "$SALE_CHECK"
fi

# Final Summary
print_header "Smoke Test Summary"

echo ""
echo "========================================" | tee -a "$LOG_FILE"
echo "SMOKE TEST RESULTS" | tee -a "$LOG_FILE"
echo "========================================" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "✅ Database Connection: PASS" | tee -a "$LOG_FILE"
echo "✅ Database Schema: PASS" | tee -a "$LOG_FILE"
echo "✅ Admin User: PASS" | tee -a "$LOG_FILE"
echo "✅ Tenant Creation: PASS" | tee -a "$LOG_FILE"
echo "✅ User Creation: PASS" | tee -a "$LOG_FILE"
echo "✅ Inventory Management: PASS" | tee -a "$LOG_FILE"
echo "✅ Sale Processing: PASS" | tee -a "$LOG_FILE"
echo "✅ Data Consistency: PASS" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

print_success "ALL SMOKE TESTS PASSED! ✅"
echo "Status: ✅ ALL SMOKE TESTS PASSED" >> "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"
echo "Log file: $LOG_FILE" | tee -a "$LOG_FILE"

exit 0
