# Design Document

## Overview

This document outlines the comprehensive design for an enterprise-grade, multi-tenant B2B SaaS platform for gold and jewelry shop management. The system is architected to serve 500-10,000+ jewelry shop tenants with complete data isolation, high availability, and military-grade security.

### Design Principles

1. **Library-First Approach**: Leverage well-maintained Django libraries before writing custom code
2. **Multi-Tenancy by Design**: PostgreSQL Row-Level Security (RLS) for database-level tenant isolation
3. **Security First**: Military-grade encryption, comprehensive audit trails, and defense-in-depth
4. **Scalability**: Horizontal scaling with Kubernetes, stateless application design
5. **Resilience**: Triple-redundant backups, automated disaster recovery, 99.9% uptime target
6. **Developer Experience**: Clear separation of concerns, comprehensive testing, CI/CD automation
7. **User Experience**: Dual-language (English/Persian), dual-theme (light/dark), WCAG 2.1 AA compliance

### Technology Stack

**Backend:**
- Django 4.2+ (Python web framework)
- PostgreSQL 15+ (Database with RLS support)
- Redis 7+ (Caching and message broker)
- Celery (Distributed task queue)

**Frontend:**
- Django Templates (Server-side rendering)
- HTMX (Dynamic interactions without heavy JavaScript)
- Alpine.js (Lightweight reactive components)
- Tailwind CSS + Flowbite (Utility-first styling and components)

**Infrastructure:**
- Docker (Containerization)
- Kubernetes (Orchestration)
- Nginx (Reverse proxy and static file serving)
- Cloudflare R2 + Backblaze B2 (Object storage)

**Key Libraries:**
- django-allauth (Authentication)
- django-argon2 (Password hashing)
- djangorestframework-simplejwt (JWT tokens)
- django-otp (Multi-factor authentication)
- django-hijack (Admin impersonation)
- django-ledger (Double-entry accounting)
- django-fsm (Finite state machines)
- django-guardian (Object-level permissions)
- django-waffle (Feature flags)
- django-prometheus (Metrics)
- drf-spectacular (API documentation)


## Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USERS                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │   Platform   │  │   Jewelry    │  │   Jewelry    │          │
│  │    Admin     │  │  Shop Owner  │  │  Shop Staff  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LOAD BALANCER                               │
│                    (Traefik Ingress)                             │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      NGINX (Reverse Proxy)                       │
│  • SSL Termination  • Static Files  • Rate Limiting             │
└─────────────────────────────────────────────────────────────────┘
                              │
                ┌─────────────┴─────────────┐
                ▼                           ▼
┌───────────────────────────┐   ┌───────────────────────────┐
│   DJANGO APPLICATION      │   │   CELERY WORKERS          │
│   (Multiple Pods)         │   │   (Multiple Pods)         │
│                           │   │                           │
│  • Admin Panel            │   │  • Backup Tasks           │
│  • Tenant Panel           │   │  • Email/SMS Tasks        │
│  • API Endpoints          │   │  • Report Generation      │
│  • Authentication         │   │  • Gold Rate Updates      │
│  • Multi-Tenant Middleware│   │  • WAL Archiving          │
└───────────────────────────┘   └───────────────────────────┘
                │                           │
                └─────────────┬─────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    DATA LAYER                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  PostgreSQL  │  │    Redis     │  │   Storage    │          │
│  │  (Patroni)   │  │  (Sentinel)  │  │  R2 + B2     │          │
│  │  • RLS       │  │  • Cache     │  │  • Backups   │          │
│  │  • PITR      │  │  • Sessions  │  │  • Media     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MONITORING & OBSERVABILITY                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │  Prometheus  │  │   Grafana    │  │    Sentry    │          │
│  │   + Loki     │  │  Dashboards  │  │ Error Track  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### Multi-Tenancy Architecture

**Tenant Isolation Strategy: PostgreSQL Row-Level Security (RLS)**

```sql
-- Enable RLS on all tenant-scoped tables
ALTER TABLE inventory_items ENABLE ROW LEVEL SECURITY;

-- Create RLS policy
CREATE POLICY tenant_isolation_policy ON inventory_items
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- Set tenant context in Django middleware
SELECT set_config('app.current_tenant', 'tenant-uuid-here', false);
```

**Tenant Context Flow:**

```
1. User authenticates → JWT token issued with tenant_id
2. Request arrives → Django middleware extracts tenant_id
3. Middleware sets PostgreSQL session variable
4. All queries automatically filtered by RLS
5. Response returned with only tenant's data
```

**Benefits:**
- Database-level enforcement (cannot be bypassed)
- No application-level filtering needed
- Automatic protection for all queries
- Performance: Uses PostgreSQL indexes efficiently


## Components and Interfaces

### 1. Admin Panel Components

#### 1.1 Admin Dashboard
- **Purpose**: High-level platform health overview
- **Components**:
  - Tenant metrics widget (signups, active, suspended)
  - Revenue metrics widget (MRR, ARR, churn rate)
  - System health widget (CPU, memory, disk, database)
  - Error feed widget (recent errors from Sentry)
  - Real-time charts using Chart.js
- **Technology**: Django views + HTMX for real-time updates

#### 1.2 Tenant Management
- **Purpose**: Full CRUD operations on tenant accounts
- **Components**:
  - Tenant list view with search and filters
  - Tenant detail view with tabs (Info, Users, Subscription, Activity)
  - Tenant creation form with validation
  - Status change modal with confirmation
  - Impersonation button (django-hijack integration)
- **Models**:
  ```python
  class Tenant(models.Model):
      id = models.UUIDField(primary_key=True, default=uuid.uuid4)
      company_name = models.CharField(max_length=255)
      status = models.CharField(choices=STATUS_CHOICES)
      subscription_plan = models.ForeignKey('SubscriptionPlan')
      created_at = models.DateTimeField(auto_now_add=True)
  ```

#### 1.3 Subscription Management
- **Purpose**: Manage plans and tenant subscriptions
- **Components**:
  - Plan CRUD interface
  - Plan configuration form (name, price, limits)
  - Tenant subscription list with filters
  - Manual subscription assignment
  - Limit override interface
- **Models**:
  ```python
  class SubscriptionPlan(models.Model):
      name = models.CharField(max_length=100)
      price = models.DecimalField(max_digits=10, decimal_places=2)
      billing_cycle = models.CharField(choices=CYCLE_CHOICES)
      user_limit = models.IntegerField()
      inventory_limit = models.IntegerField()
      branch_limit = models.IntegerField()
  
  class TenantSubscription(models.Model):
      tenant = models.OneToOneField('Tenant')
      plan = models.ForeignKey('SubscriptionPlan')
      status = models.CharField(choices=STATUS_CHOICES)
      user_limit_override = models.IntegerField(null=True)
  ```

#### 1.4 Backup Management
- **Purpose**: Enterprise backup and disaster recovery interface
- **Components**:
  - Backup dashboard (health status, storage usage, schedules)
  - Manual backup trigger form
  - 4-step restore wizard
  - Backup history table with filters
  - DR runbook execution interface
- **Models**: See Backup System section below

#### 1.5 System Monitoring
- **Purpose**: Real-time platform health monitoring
- **Components**:
  - System metrics dashboard (CPU, memory, disk, network)
  - Service status indicators (Django, PostgreSQL, Redis, Celery, Nginx)
  - Alert configuration interface
  - Alert history and acknowledgment
- **Integration**: Prometheus + Grafana embedded dashboards

#### 1.6 Audit Logs
- **Purpose**: Comprehensive audit trail
- **Components**:
  - Audit log explorer with advanced search
  - Filters (user, action, date range, tenant, IP)
  - Export to CSV functionality
  - Security event dashboard
- **Library**: django-auditlog
- **Models**:
  ```python
  class AuditLog(models.Model):
      user = models.ForeignKey('auth.User')
      action = models.CharField(max_length=100)
      model = models.CharField(max_length=100)
      object_id = models.CharField(max_length=255)
      changes = models.JSONField()
      ip_address = models.GenericIPAddressField()
      timestamp = models.DateTimeField(auto_now_add=True)
  ```

#### 1.7 Feature Flags
- **Purpose**: Control feature rollout
- **Components**:
  - Feature flag list with status
  - Flag configuration form (name, rollout percentage, target tenants)
  - A/B test configuration
  - Metrics dashboard
- **Library**: django-waffle

#### 1.8 Communication System
- **Purpose**: Platform-to-tenant communication
- **Components**:
  - Announcement creation form
  - Announcement scheduling interface
  - Tenant targeting (by plan, region, status)
  - Delivery channel selection (in-app, email, SMS)
  - Communication history
- **Models**:
  ```python
  class Announcement(models.Model):
      title = models.CharField(max_length=255)
      message = models.TextField()
      severity = models.CharField(choices=SEVERITY_CHOICES)
      target_filter = models.JSONField()
      channels = models.JSONField()
      scheduled_at = models.DateTimeField(null=True)
      sent_at = models.DateTimeField(null=True)
  ```


### 2. Tenant Panel Components

#### 2.1 Tenant Dashboard
- **Purpose**: Business overview for jewelry shop
- **Components**:
  - Today's sales widget
  - Inventory value widget
  - Low stock alerts widget
  - Pending orders widget
  - Quick actions (New Sale, Add Product, View Reports)
  - Sales chart (last 30 days)
- **Technology**: Django views + HTMX for live updates

#### 2.2 Inventory Management
- **Purpose**: Track all jewelry items
- **Components**:
  - Product list with search and filters
  - Product detail view with images
  - Product creation/edit form
  - Barcode/QR code generation
  - Stock adjustment interface
  - Inventory valuation report
- **Models**:
  ```python
  class InventoryItem(models.Model):
      tenant = models.ForeignKey('Tenant')
      sku = models.CharField(max_length=100, unique=True)
      name = models.CharField(max_length=255)
      category = models.ForeignKey('ProductCategory')
      karat = models.IntegerField()
      weight_grams = models.DecimalField(max_digits=10, decimal_places=3)
      cost_price = models.DecimalField(max_digits=12, decimal_places=2)
      selling_price = models.DecimalField(max_digits=12, decimal_places=2)
      quantity = models.IntegerField()
      branch = models.ForeignKey('Branch')
      serial_number = models.CharField(max_length=100, null=True)
      lot_number = models.CharField(max_length=100, null=True)
  ```

#### 2.3 Point of Sale (POS)
- **Purpose**: Fast in-store sales processing
- **Components**:
  - Product search with barcode scanner support
  - Cart management
  - Customer selection/creation
  - Payment method selection (cash, card, split)
  - Discount application
  - Receipt generation and printing
  - Offline mode with sync
- **Technology**: Service Workers for offline, IndexedDB for local storage
- **Models**:
  ```python
  class Sale(models.Model):
      tenant = models.ForeignKey('Tenant')
      sale_number = models.CharField(max_length=50, unique=True)
      customer = models.ForeignKey('Customer', null=True)
      branch = models.ForeignKey('Branch')
      terminal = models.ForeignKey('Terminal')
      employee = models.ForeignKey('User')
      subtotal = models.DecimalField(max_digits=12, decimal_places=2)
      tax = models.DecimalField(max_digits=12, decimal_places=2)
      discount = models.DecimalField(max_digits=12, decimal_places=2)
      total = models.DecimalField(max_digits=12, decimal_places=2)
      payment_method = models.CharField(max_length=50)
      status = models.CharField(choices=STATUS_CHOICES)
      created_at = models.DateTimeField(auto_now_add=True)
  
  class SaleItem(models.Model):
      sale = models.ForeignKey('Sale', related_name='items')
      inventory_item = models.ForeignKey('InventoryItem')
      quantity = models.IntegerField()
      unit_price = models.DecimalField(max_digits=12, decimal_places=2)
      subtotal = models.DecimalField(max_digits=12, decimal_places=2)
  ```

#### 2.4 Customer Management (CRM)
- **Purpose**: Manage customer relationships
- **Components**:
  - Customer list with search
  - Customer profile with purchase history
  - Customer creation/edit form
  - Loyalty points management
  - Store credit management
  - Communication history
- **Models**:
  ```python
  class Customer(models.Model):
      tenant = models.ForeignKey('Tenant')
      customer_number = models.CharField(max_length=50, unique=True)
      first_name = models.CharField(max_length=100)
      last_name = models.CharField(max_length=100)
      email = models.EmailField(null=True)
      phone = models.CharField(max_length=20)
      loyalty_tier = models.CharField(choices=TIER_CHOICES)
      loyalty_points = models.IntegerField(default=0)
      store_credit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
      total_purchases = models.DecimalField(max_digits=12, decimal_places=2, default=0)
  ```

#### 2.5 Accounting Module
- **Purpose**: Double-entry bookkeeping
- **Library**: django-ledger
- **Components**:
  - Chart of accounts
  - Journal entries
  - General ledger
  - Trial balance
  - Financial reports (Balance Sheet, Income Statement, Cash Flow)
- **Integration**: Automatic journal entries from sales, purchases, payments

#### 2.6 Repair & Custom Orders
- **Purpose**: Service order tracking
- **Components**:
  - Order creation form
  - Order status tracking
  - Photo upload for documentation
  - Work order generation
  - Customer notifications
- **Library**: django-fsm for state management
- **Models**:
  ```python
  class RepairOrder(models.Model):
      tenant = models.ForeignKey('Tenant')
      order_number = models.CharField(max_length=50, unique=True)
      customer = models.ForeignKey('Customer')
      item_description = models.TextField()
      service_type = models.CharField(choices=SERVICE_CHOICES)
      status = FSMField(default='received', choices=STATUS_CHOICES)
      estimated_completion = models.DateField()
      cost_estimate = models.DecimalField(max_digits=10, decimal_places=2)
      
      @transition(field=status, source='received', target='in_progress')
      def start_work(self):
          pass
      
      @transition(field=status, source='in_progress', target='completed')
      def complete_work(self):
          pass
  ```


#### 2.7 Multi-Branch Management
- **Purpose**: Manage multiple shop locations
- **Components**:
  - Branch list and creation
  - Branch configuration (address, hours, manager)
  - Branch performance dashboard
  - Inter-branch transfer interface
  - Transfer approval workflow
- **Models**:
  ```python
  class Branch(models.Model):
      tenant = models.ForeignKey('Tenant')
      name = models.CharField(max_length=255)
      address = models.TextField()
      phone = models.CharField(max_length=20)
      manager = models.ForeignKey('User', null=True)
      opening_hours = models.JSONField()
      is_active = models.BooleanField(default=True)
  
  class InventoryTransfer(models.Model):
      tenant = models.ForeignKey('Tenant')
      transfer_number = models.CharField(max_length=50, unique=True)
      from_branch = models.ForeignKey('Branch', related_name='transfers_out')
      to_branch = models.ForeignKey('Branch', related_name='transfers_in')
      status = FSMField(default='pending', choices=STATUS_CHOICES)
      requested_by = models.ForeignKey('User')
      approved_by = models.ForeignKey('User', null=True)
      created_at = models.DateTimeField(auto_now_add=True)
  ```

#### 2.8 Reporting & Analytics
- **Purpose**: Business intelligence
- **Components**:
  - Report builder interface
  - Pre-built report templates
  - Interactive charts and graphs
  - Report scheduling
  - Export functionality (PDF, Excel, CSV)
- **Library**: django-import-export for exports
- **Charts**: Chart.js or ApexCharts
- **Reports**:
  - Sales reports (daily, by product, by employee, by branch)
  - Inventory reports (valuation, turnover, dead stock)
  - Financial reports (P&L, revenue trends, expense breakdown)
  - Customer reports (top customers, acquisition, loyalty analytics)

#### 2.9 Supplier Management
- **Purpose**: Procurement and supplier relationships
- **Components**:
  - Supplier directory
  - Purchase order creation
  - PO approval workflow
  - Goods receiving interface
  - Three-way matching (PO, receipt, invoice)
- **Models**:
  ```python
  class Supplier(models.Model):
      tenant = models.ForeignKey('Tenant')
      name = models.CharField(max_length=255)
      contact_person = models.CharField(max_length=255)
      email = models.EmailField()
      phone = models.CharField(max_length=20)
      rating = models.IntegerField(default=0)
  
  class PurchaseOrder(models.Model):
      tenant = models.ForeignKey('Tenant')
      po_number = models.CharField(max_length=50, unique=True)
      supplier = models.ForeignKey('Supplier')
      status = FSMField(default='draft', choices=STATUS_CHOICES)
      total_amount = models.DecimalField(max_digits=12, decimal_places=2)
      expected_delivery = models.DateField()
      created_by = models.ForeignKey('User')
  ```

#### 2.10 Gold Rate Management
- **Purpose**: Dynamic pricing based on market rates
- **Components**:
  - Live gold rate display
  - Rate history chart
  - Markup configuration
  - Price recalculation trigger
  - Rate alert configuration
- **Integration**: External APIs (GoldAPI, Metals-API)
- **Models**:
  ```python
  class GoldRate(models.Model):
      rate_per_gram = models.DecimalField(max_digits=10, decimal_places=2)
      rate_per_tola = models.DecimalField(max_digits=10, decimal_places=2)
      rate_per_ounce = models.DecimalField(max_digits=10, decimal_places=2)
      market = models.CharField(max_length=50)
      timestamp = models.DateTimeField(auto_now_add=True)
  
  class PricingRule(models.Model):
      tenant = models.ForeignKey('Tenant')
      karat = models.IntegerField()
      markup_percentage = models.DecimalField(max_digits=5, decimal_places=2)
      customer_tier = models.CharField(choices=TIER_CHOICES, null=True)
  ```

#### 2.11 Loyalty Program
- **Purpose**: Customer retention and rewards
- **Components**:
  - Loyalty tier configuration
  - Points accrual rules
  - Points redemption interface
  - Gift card management
  - Referral tracking
- **Models**:
  ```python
  class LoyaltyTier(models.Model):
      tenant = models.ForeignKey('Tenant')
      name = models.CharField(max_length=100)
      min_spending = models.DecimalField(max_digits=12, decimal_places=2)
      discount_percentage = models.DecimalField(max_digits=5, decimal_places=2)
      points_multiplier = models.DecimalField(max_digits=3, decimal_places=2)
  
  class LoyaltyTransaction(models.Model):
      customer = models.ForeignKey('Customer')
      transaction_type = models.CharField(choices=TYPE_CHOICES)
      points = models.IntegerField()
      description = models.CharField(max_length=255)
      created_at = models.DateTimeField(auto_now_add=True)
  ```

#### 2.12 Notification System
- **Purpose**: Keep users informed
- **Components**:
  - Notification center
  - Email notification templates
  - SMS notification templates
  - Push notification support (HTMX polling or WebSocket)
  - Notification preferences
- **Libraries**: django-anymail (email), Twilio (SMS)
- **Models**:
  ```python
  class Notification(models.Model):
      user = models.ForeignKey('User')
      title = models.CharField(max_length=255)
      message = models.TextField()
      notification_type = models.CharField(choices=TYPE_CHOICES)
      is_read = models.BooleanField(default=False)
      created_at = models.DateTimeField(auto_now_add=True)
  ```


## Data Models

### Core Models

#### Tenant Model
```python
class Tenant(models.Model):
    """Core tenant model for multi-tenancy"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company_name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    status = models.CharField(max_length=20, choices=[
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('PENDING_DELETION', 'Pending Deletion'),
    ], default='ACTIVE')
    subscription_plan = models.ForeignKey('SubscriptionPlan', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tenants'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['slug']),
        ]
```

#### User Model (Extended)
```python
class User(AbstractUser):
    """Extended user model with tenant association"""
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE, null=True)
    role = models.CharField(max_length=50, choices=[
        ('PLATFORM_ADMIN', 'Platform Administrator'),
        ('TENANT_OWNER', 'Shop Owner'),
        ('TENANT_MANAGER', 'Shop Manager'),
        ('TENANT_EMPLOYEE', 'Shop Employee'),
    ])
    branch = models.ForeignKey('Branch', on_delete=models.SET_NULL, null=True)
    language = models.CharField(max_length=10, choices=[('en', 'English'), ('fa', 'Persian')], default='en')
    theme = models.CharField(max_length=10, choices=[('light', 'Light'), ('dark', 'Dark')], default='light')
    phone = models.CharField(max_length=20, null=True)
    is_mfa_enabled = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'users'
        indexes = [
            models.Index(fields=['tenant', 'role']),
        ]
```

### Backup System Models

#### Backup Model
```python
class Backup(models.Model):
    """Track all backup operations"""
    BACKUP_TYPES = [
        ('FULL_DATABASE', 'Full Database Backup'),
        ('TENANT_BACKUP', 'Tenant-Specific Backup'),
        ('WAL_ARCHIVE', 'WAL Archive for PITR'),
        ('CONFIGURATION', 'Configuration Backup'),
    ]
    
    STATUS_CHOICES = [
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('VERIFIED', 'Verified'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    backup_type = models.CharField(max_length=50, choices=BACKUP_TYPES)
    tenant = models.ForeignKey('Tenant', null=True, blank=True, on_delete=models.CASCADE)
    filename = models.CharField(max_length=255)
    size_bytes = models.BigIntegerField()
    checksum = models.CharField(max_length=64)  # SHA-256
    local_path = models.CharField(max_length=500, null=True, blank=True)
    r2_path = models.CharField(max_length=500)
    b2_path = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    backup_job_id = models.UUIDField(null=True, blank=True)
    compression_ratio = models.FloatField(null=True, blank=True)
    backup_duration_seconds = models.IntegerField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey('User', null=True, blank=True, on_delete=models.SET_NULL)
    
    class Meta:
        db_table = 'backups_backup'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['backup_type', '-created_at']),
            models.Index(fields=['tenant', '-created_at']),
            models.Index(fields=['status']),
        ]
```

#### BackupRestoreLog Model
```python
class BackupRestoreLog(models.Model):
    """Track all restore operations"""
    RESTORE_MODES = [
        ('FULL', 'Full Restore (Replace)'),
        ('MERGE', 'Merge Restore (Preserve)'),
        ('PITR', 'Point-in-Time Recovery'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    backup = models.ForeignKey('Backup', on_delete=models.CASCADE)
    initiated_by = models.ForeignKey('User', on_delete=models.SET_NULL, null=True)
    tenant_ids = models.JSONField(null=True, blank=True)
    restore_mode = models.CharField(max_length=20, choices=RESTORE_MODES)
    target_timestamp = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=[
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),
    ])
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    rows_restored = models.BigIntegerField(null=True, blank=True)
    duration_seconds = models.IntegerField(null=True, blank=True)
    reason = models.TextField()
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'backups_restore_log'
        ordering = ['-started_at']
```

### Inventory Models

```python
class ProductCategory(models.Model):
    """Product categories for inventory"""
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE)
    
    class Meta:
        db_table = 'inventory_categories'
        unique_together = [['tenant', 'name']]

class InventoryItem(models.Model):
    """Main inventory tracking"""
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE)
    sku = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    category = models.ForeignKey('ProductCategory', on_delete=models.PROTECT)
    karat = models.IntegerField()
    weight_grams = models.DecimalField(max_digits=10, decimal_places=3)
    cost_price = models.DecimalField(max_digits=12, decimal_places=2)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.IntegerField()
    branch = models.ForeignKey('Branch', on_delete=models.PROTECT)
    serial_number = models.CharField(max_length=100, null=True, blank=True)
    lot_number = models.CharField(max_length=100, null=True, blank=True)
    barcode = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'inventory_items'
        unique_together = [['tenant', 'sku']]
        indexes = [
            models.Index(fields=['tenant', 'branch']),
            models.Index(fields=['tenant', 'category']),
            models.Index(fields=['barcode']),
        ]
```

### Sales Models

```python
class Sale(models.Model):
    """Sales transactions"""
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE)
    sale_number = models.CharField(max_length=50)
    customer = models.ForeignKey('Customer', null=True, blank=True, on_delete=models.SET_NULL)
    branch = models.ForeignKey('Branch', on_delete=models.PROTECT)
    terminal = models.ForeignKey('Terminal', on_delete=models.PROTECT)
    employee = models.ForeignKey('User', on_delete=models.PROTECT)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    tax = models.DecimalField(max_digits=12, decimal_places=2)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    status = models.CharField(max_length=20, choices=[
        ('COMPLETED', 'Completed'),
        ('REFUNDED', 'Refunded'),
        ('CANCELLED', 'Cancelled'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'sales'
        unique_together = [['tenant', 'sale_number']]
        indexes = [
            models.Index(fields=['tenant', '-created_at']),
            models.Index(fields=['customer', '-created_at']),
        ]

class SaleItem(models.Model):
    """Line items for sales"""
    sale = models.ForeignKey('Sale', related_name='items', on_delete=models.CASCADE)
    inventory_item = models.ForeignKey('InventoryItem', on_delete=models.PROTECT)
    quantity = models.IntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)
    
    class Meta:
        db_table = 'sale_items'
```


## Error Handling

### Error Handling Strategy

**Principles:**
1. **Fail Fast**: Detect errors early and fail explicitly
2. **Graceful Degradation**: Provide fallback functionality when possible
3. **User-Friendly Messages**: Show clear, actionable error messages
4. **Comprehensive Logging**: Log all errors with context for debugging
5. **Monitoring**: Track error rates and alert on anomalies

### Error Categories

#### 1. Validation Errors
- **Handling**: Django form validation, DRF serializers
- **Response**: 400 Bad Request with field-specific errors
- **User Message**: "Please correct the highlighted fields"
- **Example**:
  ```python
  {
      "email": ["Enter a valid email address."],
      "phone": ["This field is required."]
  }
  ```

#### 2. Authentication Errors
- **Handling**: Django authentication, JWT validation
- **Response**: 401 Unauthorized
- **User Message**: "Invalid credentials" or "Session expired"
- **Action**: Redirect to login page

#### 3. Authorization Errors
- **Handling**: Django permissions, RLS policies
- **Response**: 403 Forbidden
- **User Message**: "You don't have permission to perform this action"
- **Logging**: Log unauthorized access attempts

#### 4. Not Found Errors
- **Handling**: Django get_object_or_404
- **Response**: 404 Not Found
- **User Message**: "The requested resource was not found"
- **Action**: Show 404 page with navigation options

#### 5. Business Logic Errors
- **Handling**: Custom exceptions
- **Response**: 422 Unprocessable Entity
- **User Message**: Specific business rule violation
- **Example**: "Insufficient inventory to complete sale"

#### 6. External Service Errors
- **Handling**: Try-except with retries
- **Response**: 503 Service Unavailable
- **User Message**: "Service temporarily unavailable, please try again"
- **Action**: Queue for retry with Celery

#### 7. Database Errors
- **Handling**: Django database exception handling
- **Response**: 500 Internal Server Error
- **User Message**: "An error occurred, please try again"
- **Logging**: Full stack trace to Sentry
- **Action**: Rollback transaction

### Error Handling Implementation

```python
# Custom exception classes
class BusinessLogicError(Exception):
    """Base class for business logic errors"""
    pass

class InsufficientInventoryError(BusinessLogicError):
    """Raised when inventory is insufficient for operation"""
    pass

class TenantSuspendedError(BusinessLogicError):
    """Raised when tenant account is suspended"""
    pass

# Middleware for error handling
class ErrorHandlingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except BusinessLogicError as e:
            logger.warning(f"Business logic error: {e}", extra={'request': request})
            return JsonResponse({'error': str(e)}, status=422)
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True, extra={'request': request})
            # Send to Sentry
            sentry_sdk.capture_exception(e)
            return JsonResponse({'error': 'An unexpected error occurred'}, status=500)

# View-level error handling
def create_sale(request):
    try:
        with transaction.atomic():
            sale = Sale.objects.create(...)
            # Deduct inventory
            for item in sale_items:
                inventory = InventoryItem.objects.select_for_update().get(id=item.id)
                if inventory.quantity < item.quantity:
                    raise InsufficientInventoryError(
                        f"Insufficient inventory for {inventory.name}"
                    )
                inventory.quantity -= item.quantity
                inventory.save()
            return JsonResponse({'success': True, 'sale_id': sale.id})
    except InsufficientInventoryError as e:
        return JsonResponse({'error': str(e)}, status=422)
```

### Sentry Integration

```python
# settings.py
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.celery import CeleryIntegration

sentry_sdk.init(
    dsn=os.getenv('SENTRY_DSN'),
    integrations=[
        DjangoIntegration(),
        CeleryIntegration(),
    ],
    traces_sample_rate=0.1,  # 10% of transactions
    send_default_pii=False,  # Don't send PII
    environment=os.getenv('ENVIRONMENT', 'production'),
)
```

### User-Facing Error Pages

**404 Page:**
- Friendly message: "Page not found"
- Search box to find what they're looking for
- Links to common pages (Dashboard, Help)

**500 Page:**
- Friendly message: "Something went wrong"
- Error ID for support reference
- Link to status page
- Contact support button

**503 Page:**
- Friendly message: "We're performing maintenance"
- Estimated time to completion
- Subscribe to status updates


## Testing Strategy

### Testing Pyramid

```
                    ┌─────────────┐
                    │   E2E Tests │  (10%)
                    │  Playwright │
                    └─────────────┘
                  ┌───────────────────┐
                  │ Integration Tests │  (30%)
                  │  API, Workflows   │
                  └───────────────────┘
              ┌─────────────────────────────┐
              │       Unit Tests            │  (60%)
              │  Models, Services, Utils    │
              └─────────────────────────────┘
```

### 1. Unit Tests (60% of tests)

**Scope**: Individual functions, methods, and classes
**Framework**: pytest with pytest-django
**Coverage Target**: 90%+ for business logic

**What to Test:**
- Model methods and properties
- Service layer business logic
- Utility functions
- Form validation
- Serializer validation
- Custom template tags and filters

**Example:**
```python
# tests/test_models.py
import pytest
from decimal import Decimal
from inventory.models import InventoryItem

@pytest.mark.django_db
class TestInventoryItem:
    def test_calculate_selling_price_with_markup(self):
        """Test automatic selling price calculation"""
        item = InventoryItem.objects.create(
            tenant=tenant,
            sku='TEST-001',
            cost_price=Decimal('100.00'),
            markup_percentage=Decimal('20.00')
        )
        assert item.selling_price == Decimal('120.00')
    
    def test_insufficient_quantity_raises_error(self):
        """Test that selling more than available raises error"""
        item = InventoryItem.objects.create(
            tenant=tenant,
            quantity=5
        )
        with pytest.raises(InsufficientInventoryError):
            item.deduct_quantity(10)
```

### 2. Integration Tests (30% of tests)

**Scope**: Multiple components working together
**Framework**: pytest with pytest-django
**Coverage Target**: All critical workflows

**What to Test:**
- API endpoints (full request/response cycle)
- Database queries with RLS
- Celery tasks
- Complete business workflows
- External service integrations (mocked)

**Example:**
```python
# tests/test_api.py
import pytest
from rest_framework.test import APIClient

@pytest.mark.django_db
class TestSalesAPI:
    def test_create_sale_deducts_inventory(self, api_client, tenant, inventory_item):
        """Test that creating a sale deducts inventory"""
        initial_quantity = inventory_item.quantity
        
        response = api_client.post('/api/sales/', {
            'items': [
                {'inventory_item_id': inventory_item.id, 'quantity': 2}
            ],
            'payment_method': 'cash'
        })
        
        assert response.status_code == 201
        inventory_item.refresh_from_database()
        assert inventory_item.quantity == initial_quantity - 2
    
    def test_tenant_isolation_in_sales(self, api_client, tenant1, tenant2):
        """Test that tenants cannot see each other's sales"""
        # Create sale for tenant1
        sale1 = Sale.objects.create(tenant=tenant1, ...)
        
        # Login as tenant2
        api_client.force_authenticate(user=tenant2.owner)
        
        # Try to access tenant1's sale
        response = api_client.get(f'/api/sales/{sale1.id}/')
        assert response.status_code == 404  # RLS prevents access
```

### 3. End-to-End Tests (10% of tests)

**Scope**: Complete user journeys
**Framework**: Playwright
**Coverage Target**: Critical user flows

**What to Test:**
- User registration and login
- Complete sale process (search product → add to cart → checkout → receipt)
- Inventory management workflow
- Report generation
- Multi-language switching
- Theme switching

**Example:**
```python
# tests/e2e/test_pos_flow.py
def test_complete_sale_flow(page, tenant_user):
    """Test complete POS sale flow"""
    # Login
    page.goto('/login/')
    page.fill('#username', tenant_user.username)
    page.fill('#password', 'password')
    page.click('button[type="submit"]')
    
    # Navigate to POS
    page.click('text=Point of Sale')
    
    # Search and add product
    page.fill('#product-search', 'Gold Ring')
    page.click('text=24K Gold Ring')
    page.click('button:has-text("Add to Cart")')
    
    # Select payment method
    page.click('text=Cash')
    
    # Complete sale
    page.click('button:has-text("Complete Sale")')
    
    # Verify receipt displayed
    assert page.is_visible('text=Sale Completed')
    assert page.is_visible('text=Receipt')
```

### 4. RLS (Row-Level Security) Tests

**Critical**: Test tenant isolation at database level

```python
@pytest.mark.django_db
class TestRLSPolicies:
    def test_tenant_cannot_access_other_tenant_data(self, tenant1, tenant2):
        """Test RLS prevents cross-tenant data access"""
        # Create inventory for tenant1
        item1 = InventoryItem.objects.create(tenant=tenant1, sku='T1-001')
        
        # Set tenant2 context
        with tenant_context(tenant2):
            # Try to query all inventory
            items = InventoryItem.objects.all()
            
            # Should not see tenant1's item
            assert item1 not in items
            assert items.filter(tenant=tenant1).count() == 0
```

### 5. Performance Tests

**Framework**: Locust
**Target**: Ensure system meets performance requirements

```python
# locustfile.py
from locust import HttpUser, task, between

class JewelryShopUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Login before starting tasks"""
        self.client.post('/api/auth/login/', {
            'username': 'testuser',
            'password': 'testpass'
        })
    
    @task(3)
    def view_dashboard(self):
        """View dashboard (most common action)"""
        self.client.get('/dashboard/')
    
    @task(2)
    def search_inventory(self):
        """Search inventory"""
        self.client.get('/api/inventory/?search=gold')
    
    @task(1)
    def create_sale(self):
        """Create a sale"""
        self.client.post('/api/sales/', {
            'items': [{'inventory_item_id': 1, 'quantity': 1}],
            'payment_method': 'cash'
        })
```

### Test Fixtures

```python
# conftest.py
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.fixture
def tenant(db):
    """Create a test tenant"""
    return Tenant.objects.create(
        company_name='Test Jewelry Shop',
        slug='test-shop',
        status='ACTIVE'
    )

@pytest.fixture
def tenant_owner(db, tenant):
    """Create a tenant owner user"""
    return User.objects.create_user(
        username='owner',
        password='testpass',
        tenant=tenant,
        role='TENANT_OWNER'
    )

@pytest.fixture
def api_client(tenant_owner):
    """Create authenticated API client"""
    from rest_framework.test import APIClient
    client = APIClient()
    client.force_authenticate(user=tenant_owner)
    return client

@pytest.fixture
def inventory_item(db, tenant):
    """Create a test inventory item"""
    return InventoryItem.objects.create(
        tenant=tenant,
        sku='TEST-001',
        name='Test Gold Ring',
        karat=24,
        weight_grams=10.5,
        cost_price=1000,
        selling_price=1200,
        quantity=10
    )
```

### Continuous Testing

**Pre-commit Hooks:**
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest-check
        name: pytest-check
        entry: pytest tests/ -x
        language: system
        pass_filenames: false
        always_run: true
```

**CI Pipeline:**
```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-django pytest-cov
      - name: Run tests
        run: pytest --cov=. --cov-report=xml --cov-report=html
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```


## Security Architecture

### Defense in Depth

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: Network Security                                       │
│  • Firewall rules                                               │
│  • DDoS protection                                              │
│  • VPN for admin access                                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 2: Application Firewall                                   │
│  • WAF (ModSecurity or Cloudflare)                              │
│  • Rate limiting                                                │
│  • IP blocking                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 3: Application Security                                   │
│  • Input validation                                             │
│  • CSRF protection                                              │
│  • XSS prevention                                               │
│  • SQL injection prevention (ORM + parameterized queries)       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 4: Authentication & Authorization                         │
│  • Strong password policy                                       │
│  • MFA (django-otp)                                             │
│  • JWT tokens with short expiration                             │
│  • Role-based access control                                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 5: Data Security                                          │
│  • RLS for tenant isolation                                     │
│  • Encryption at rest (AES-256)                                 │
│  • Encryption in transit (TLS 1.3)                              │
│  • Sensitive data masking in logs                               │
└─────────────────────────────────────────────────────────────────┘
```

### Authentication Flow

```
┌──────────┐
│  User    │
└────┬─────┘
     │ 1. POST /api/auth/login/
     │    {username, password}
     ▼
┌────────────────┐
│  Django Auth   │
└────┬───────────┘
     │ 2. Verify credentials
     │    (Argon2 hash)
     ▼
┌────────────────┐
│  MFA Check     │
└────┬───────────┘
     │ 3. If MFA enabled,
     │    request OTP
     ▼
┌────────────────┐
│  JWT Token     │
│  Generation    │
└────┬───────────┘
     │ 4. Generate tokens
     │    {access_token, refresh_token}
     ▼
┌────────────────┐
│  Response      │
│  + Set Cookies │
└────────────────┘
```

### Authorization Flow

```
┌──────────┐
│  Request │
└────┬─────┘
     │ 1. Extract JWT from header/cookie
     ▼
┌────────────────┐
│  JWT Verify    │
└────┬───────────┘
     │ 2. Verify signature & expiration
     ▼
┌────────────────┐
│  Extract User  │
│  & Tenant      │
└────┬───────────┘
     │ 3. Load user and tenant from token
     ▼
┌────────────────┐
│  Set Tenant    │
│  Context       │
└────┬───────────┘
     │ 4. SET app.current_tenant = 'tenant-uuid'
     ▼
┌────────────────┐
│  Check         │
│  Permissions   │
└────┬───────────┘
     │ 5. Verify user has required permission
     ▼
┌────────────────┐
│  Execute View  │
└────┬───────────┘
     │ 6. RLS automatically filters queries
     ▼
┌────────────────┐
│  Response      │
└────────────────┘
```

### Password Security

```python
# settings.py
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',  # Primary
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',  # Fallback
]

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {'min_length': 12}
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]
```

### Multi-Factor Authentication

```python
# Using django-otp
from django_otp.decorators import otp_required
from django_otp.plugins.otp_totp.models import TOTPDevice

@otp_required
def sensitive_view(request):
    """View that requires MFA"""
    pass

# Enable MFA for user
def enable_mfa(user):
    device = TOTPDevice.objects.create(
        user=user,
        name='default',
        confirmed=True
    )
    return device.config_url  # QR code URL for authenticator app
```

### CSRF Protection

```python
# All POST/PUT/DELETE requests require CSRF token
# Django automatically includes in forms

# For AJAX requests
<script>
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

const csrftoken = getCookie('csrftoken');

fetch('/api/endpoint/', {
    method: 'POST',
    headers: {
        'X-CSRFToken': csrftoken,
        'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
});
</script>
```

### XSS Prevention

```python
# Django templates auto-escape by default
{{ user_input }}  # Automatically escaped

# For HTML content (use with caution)
{{ trusted_html|safe }}

# In JavaScript
<script>
const userInput = "{{ user_input|escapejs }}";
</script>
```

### SQL Injection Prevention

```python
# ALWAYS use ORM or parameterized queries
# GOOD:
InventoryItem.objects.filter(sku=user_input)

# GOOD (raw SQL with parameters):
cursor.execute("SELECT * FROM inventory WHERE sku = %s", [user_input])

# BAD (vulnerable to SQL injection):
cursor.execute(f"SELECT * FROM inventory WHERE sku = '{user_input}'")
```

### Rate Limiting

```python
# Using django-ratelimit
from django_ratelimit.decorators import ratelimit

@ratelimit(key='ip', rate='5/m', method='POST')
def login_view(request):
    """Limit login attempts to 5 per minute per IP"""
    pass

@ratelimit(key='user', rate='100/h')
def api_endpoint(request):
    """Limit API calls to 100 per hour per user"""
    pass
```

### Security Headers

```python
# settings.py
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = 31536000  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Strict'
CSRF_COOKIE_SAMESITE = 'Strict'

# Content Security Policy
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "cdn.jsdelivr.net")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "cdn.jsdelivr.net")
CSP_IMG_SRC = ("'self'", "data:", "https:")
CSP_FONT_SRC = ("'self'", "cdn.jsdelivr.net")
```

### Secrets Management

```python
# Use environment variables for secrets
# NEVER commit secrets to version control

# .env (encrypted, not in git)
SECRET_KEY=your-secret-key-here
DATABASE_PASSWORD=your-db-password
BACKUP_ENCRYPTION_KEY=your-backup-key
CLOUDFLARE_R2_SECRET_KEY=your-r2-key

# settings.py
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY')
DATABASES = {
    'default': {
        'PASSWORD': os.getenv('DATABASE_PASSWORD'),
    }
}

# For Kubernetes, use Secrets
# kubectl create secret generic app-secrets \
#   --from-literal=secret-key=your-secret-key \
#   --from-literal=db-password=your-db-password
```

### Audit Logging

```python
# Log all security-relevant events
import logging

security_logger = logging.getLogger('security')

def login_view(request):
    if authenticate(username, password):
        security_logger.info(
            f"Successful login: user={username}, ip={request.META['REMOTE_ADDR']}"
        )
    else:
        security_logger.warning(
            f"Failed login attempt: user={username}, ip={request.META['REMOTE_ADDR']}"
        )
```


## Deployment Architecture

### Docker Configuration

#### Dockerfile (Multi-stage build)

```dockerfile
# Stage 1: Build dependencies
FROM python:3.11-slim as builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH

# Copy application code
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD python manage.py health_check || exit 1

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "60", "config.wsgi:application"]
```

#### docker-compose.yml (Development)

```yaml
version: '3.8'

services:
  db:
    image: postgres:15
    environment:
      POSTGRES_DB: jewelry_shop
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/jewelry_shop
      - REDIS_URL=redis://redis:6379/0
      - DEBUG=True
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  celery_worker:
    build: .
    command: celery -A config worker -l info
    volumes:
      - .:/app
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/jewelry_shop
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

  celery_beat:
    build: .
    command: celery -A config beat -l info
    volumes:
      - .:/app
    environment:
      - DATABASE_URL=postgresql://postgres:postgres@db:5432/jewelry_shop
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

volumes:
  postgres_data:
```

### Kubernetes Configuration

#### Deployment (Django Application)

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: django-app
  namespace: jewelry-shop
spec:
  replicas: 3
  selector:
    matchLabels:
      app: django
  template:
    metadata:
      labels:
        app: django
    spec:
      containers:
      - name: django
        image: jewelry-shop/django:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: app-secrets
              key: database-url
        - name: REDIS_URL
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: redis-url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health/live/
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready/
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: v1
kind: Service
metadata:
  name: django-service
  namespace: jewelry-shop
spec:
  selector:
    app: django
  ports:
  - protocol: TCP
    port: 80
    targetPort: 8000
  type: ClusterIP
```

#### Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: django-hpa
  namespace: jewelry-shop
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: django-app
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

#### PostgreSQL with Patroni

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres-patroni
  namespace: jewelry-shop
spec:
  serviceName: postgres
  replicas: 3
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15
        ports:
        - containerPort: 5432
        env:
        - name: POSTGRES_PASSWORD
          valueFrom:
            secretKeyRef:
              name: postgres-secret
              key: password
        volumeMounts:
        - name: postgres-data
          mountPath: /var/lib/postgresql/data
  volumeClaimTemplates:
  - metadata:
      name: postgres-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 100Gi
```

#### Ingress (Traefik)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: jewelry-shop-ingress
  namespace: jewelry-shop
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod
    traefik.ingress.kubernetes.io/router.middlewares: default-ratelimit@kubernetescrd
spec:
  ingressClassName: traefik
  tls:
  - hosts:
    - jewelry-shop.com
    - www.jewelry-shop.com
    secretName: jewelry-shop-tls
  rules:
  - host: jewelry-shop.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: nginx-service
            port:
              number: 80
```

### CI/CD Pipeline

#### GitHub Actions Workflow

```yaml
name: CI/CD Pipeline

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
      redis:
        image: redis:7
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Cache dependencies
        uses: actions/cache@v3
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements.txt') }}
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-django pytest-cov
      
      - name: Run linters
        run: |
          flake8 .
          black --check .
          isort --check-only .
          mypy .
      
      - name: Run tests
        env:
          DATABASE_URL: postgresql://postgres:postgres@localhost:5432/test_db
          REDIS_URL: redis://localhost:6379/0
        run: |
          pytest --cov=. --cov-report=xml --cov-report=html
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
      
      - name: Security scan
        run: |
          pip install bandit safety
          bandit -r .
          safety check

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2
      
      - name: Login to Docker Registry
        uses: docker/login-action@v2
        with:
          registry: ${{ secrets.DOCKER_REGISTRY }}
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}
      
      - name: Build and push
        uses: docker/build-push-action@v4
        with:
          context: .
          push: true
          tags: |
            ${{ secrets.DOCKER_REGISTRY }}/jewelry-shop:latest
            ${{ secrets.DOCKER_REGISTRY }}/jewelry-shop:${{ github.sha }}
          cache-from: type=gha
          cache-to: type=gha,mode=max

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Deploy to staging
        uses: azure/k8s-deploy@v4
        with:
          manifests: |
            k8s/staging/deployment.yaml
            k8s/staging/service.yaml
          images: |
            ${{ secrets.DOCKER_REGISTRY }}/jewelry-shop:${{ github.sha }}
          kubeconfig: ${{ secrets.KUBE_CONFIG_STAGING }}

  deploy-production:
    needs: deploy-staging
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    environment:
      name: production
      url: https://jewelry-shop.com
    steps:
      - name: Deploy to production
        uses: azure/k8s-deploy@v4
        with:
          manifests: |
            k8s/production/deployment.yaml
            k8s/production/service.yaml
          images: |
            ${{ secrets.DOCKER_REGISTRY }}/jewelry-shop:${{ github.sha }}
          kubeconfig: ${{ secrets.KUBE_CONFIG_PRODUCTION }}
      
      - name: Run database migrations
        run: |
          kubectl exec -n jewelry-shop deployment/django-app -- python manage.py migrate
      
      - name: Notify deployment
        uses: 8398a7/action-slack@v3
        with:
          status: ${{ job.status }}
          text: 'Deployment to production completed'
          webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

### Monitoring Setup

#### Prometheus Configuration

```yaml
# prometheus-config.yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'django'
    static_configs:
      - targets: ['django-service:8000']
    metrics_path: '/metrics'
  
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
  
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
  
  - job_name: 'nginx'
    static_configs:
      - targets: ['nginx-exporter:9113']
  
  - job_name: 'celery'
    static_configs:
      - targets: ['celery-exporter:9808']
```


## Internationalization (i18n) Design

### Language Support

**Supported Languages:**
- English (en) - LTR
- Persian/Farsi (fa) - RTL

### Translation Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Translation Flow                              │
└─────────────────────────────────────────────────────────────────┘

User selects language
        ↓
Django sets LANGUAGE_CODE in session
        ↓
Middleware activates language
        ↓
Templates use {% trans %} and {% blocktrans %}
        ↓
Django looks up translation in .po files
        ↓
Returns translated text
        ↓
RTL CSS applied if Persian selected
```

### Translation Files Structure

```
locale/
├── en/
│   └── LC_MESSAGES/
│       ├── django.po
│       └── django.mo
└── fa/
    └── LC_MESSAGES/
        ├── django.po
        └── django.mo
```

### Template Translation

```django
{% load i18n %}

{# Simple translation #}
<h1>{% trans "Welcome to Jewelry Shop" %}</h1>

{# Translation with variables #}
{% blocktrans with name=user.name %}
Hello {{ name }}, welcome back!
{% endblocktrans %}

{# Pluralization #}
{% blocktrans count counter=items|length %}
You have {{ counter }} item in your cart.
{% plural %}
You have {{ counter }} items in your cart.
{% endblocktrans %}

{# Context-specific translation #}
{% trans "Open" context "shop_status" %}
```

### Python Code Translation

```python
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy as _lazy
from django.utils.translation import ngettext

# In views
def my_view(request):
    message = _("Sale completed successfully")
    return JsonResponse({'message': message})

# In models (use lazy)
class InventoryItem(models.Model):
    name = models.CharField(
        max_length=255,
        verbose_name=_lazy("Product Name"),
        help_text=_lazy("Enter the product name")
    )

# Pluralization
def cart_summary(item_count):
    message = ngettext(
        "You have %(count)d item",
        "You have %(count)d items",
        item_count
    ) % {'count': item_count}
    return message
```

### RTL Support

#### CSS for RTL

```css
/* Base styles (LTR) */
.sidebar {
    float: left;
    margin-right: 20px;
}

/* RTL overrides */
[dir="rtl"] .sidebar {
    float: right;
    margin-right: 0;
    margin-left: 20px;
}

/* Using logical properties (preferred) */
.sidebar {
    float: inline-start;
    margin-inline-end: 20px;
}
```

#### Tailwind CSS RTL Plugin

```javascript
// tailwind.config.js
module.exports = {
  plugins: [
    require('tailwindcss-rtl'),
  ],
}
```

```html
<!-- Automatic RTL support -->
<div class="ml-4 rtl:mr-4 rtl:ml-0">
    Content
</div>

<!-- Using logical properties -->
<div class="ms-4">  <!-- margin-inline-start -->
    Content
</div>
```

### Number Formatting

```python
from django.utils.formats import number_format
from django.utils.translation import get_language

def format_price(amount):
    """Format price according to current language"""
    lang = get_language()
    
    if lang == 'fa':
        # Persian numerals: ۰۱۲۳۴۵۶۷۸۹
        formatted = number_format(amount, decimal_pos=2)
        # Convert to Persian numerals
        persian_digits = '۰۱۲۳۴۵۶۷۸۹'
        for i, digit in enumerate('0123456789'):
            formatted = formatted.replace(digit, persian_digits[i])
        return formatted
    else:
        # Western numerals: 0123456789
        return number_format(amount, decimal_pos=2)
```

### Date Formatting

```python
from django.utils import timezone
from django.utils.translation import get_language
import jdatetime  # Persian calendar library

def format_date(date):
    """Format date according to current language"""
    lang = get_language()
    
    if lang == 'fa':
        # Convert to Persian calendar
        jalali_date = jdatetime.date.fromgregorian(
            year=date.year,
            month=date.month,
            day=date.day
        )
        return jalali_date.strftime('%Y/%m/%d')
    else:
        # Gregorian calendar
        return date.strftime('%Y-%m-%d')
```

### Language Switcher Component

```django
{# language_switcher.html #}
{% load i18n %}

<div class="language-switcher">
    <form action="{% url 'set_language' %}" method="post">
        {% csrf_token %}
        <input name="next" type="hidden" value="{{ request.path }}">
        <select name="language" onchange="this.form.submit()">
            {% get_current_language as LANGUAGE_CODE %}
            {% get_available_languages as LANGUAGES %}
            {% for lang_code, lang_name in LANGUAGES %}
                <option value="{{ lang_code }}"
                        {% if lang_code == LANGUAGE_CODE %}selected{% endif %}>
                    {{ lang_name }}
                </option>
            {% endfor %}
        </select>
    </form>
</div>
```

### Translation Management

**Using django-rosetta for translation management:**

```python
# settings.py
INSTALLED_APPS = [
    ...
    'rosetta',
]

# urls.py
urlpatterns = [
    ...
    path('rosetta/', include('rosetta.urls')),
]
```

**Translation Workflow:**

1. Developer marks strings for translation in code
2. Run `python manage.py makemessages -l fa` to extract strings
3. Translator uses Rosetta web interface to translate
4. Run `python manage.py compilemessages` to compile .po to .mo
5. Deploy updated translations

### Settings Configuration

```python
# settings.py
from django.utils.translation import gettext_lazy as _

# Internationalization
LANGUAGE_CODE = 'en'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ('en', _('English')),
    ('fa', _('Persian')),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# Format localization
FORMAT_MODULE_PATH = [
    'config.formats',
]
```

### Format Files

```python
# config/formats/fa/formats.py
DATE_FORMAT = 'Y/m/d'
TIME_FORMAT = 'H:i'
DATETIME_FORMAT = 'Y/m/d H:i'
YEAR_MONTH_FORMAT = 'Y/m'
MONTH_DAY_FORMAT = 'm/d'
SHORT_DATE_FORMAT = 'y/m/d'
SHORT_DATETIME_FORMAT = 'y/m/d H:i'
FIRST_DAY_OF_WEEK = 6  # Saturday

DECIMAL_SEPARATOR = '٫'
THOUSAND_SEPARATOR = '٬'
NUMBER_GROUPING = 3
```


## Performance Optimization

### Caching Strategy

#### Cache Layers

```
┌─────────────────────────────────────────────────────────────────┐
│ Layer 1: Browser Cache (Static Assets)                          │
│  • CSS, JS, Images: 30 days                                     │
│  • Cache-Control: public, max-age=2592000                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 2: CDN Cache (Cloudflare)                                 │
│  • Static files: 7 days                                         │
│  • API responses: No cache                                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 3: Redis Cache (Application)                              │
│  • Database queries: 5-60 minutes                               │
│  • Session data: 2 weeks                                        │
│  • API responses: 1-5 minutes                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Layer 4: Database Query Cache (PostgreSQL)                      │
│  • Shared buffers: 25% of RAM                                   │
│  • Effective cache size: 75% of RAM                             │
└─────────────────────────────────────────────────────────────────┘
```

#### Django Cache Configuration

```python
# settings.py
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/1'),
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'CONNECTION_POOL_CLASS_KWARGS': {
                'max_connections': 50,
                'retry_on_timeout': True,
            },
            'SOCKET_CONNECT_TIMEOUT': 5,
            'SOCKET_TIMEOUT': 5,
            'COMPRESSOR': 'django_redis.compressors.zlib.ZlibCompressor',
            'IGNORE_EXCEPTIONS': True,  # Don't fail if Redis is down
        },
        'KEY_PREFIX': 'jewelry_shop',
        'TIMEOUT': 300,  # 5 minutes default
    }
}

# Session cache
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
```

#### Cache Usage Examples

```python
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator

# Function-based view caching
@cache_page(60 * 5)  # Cache for 5 minutes
def product_list(request):
    products = InventoryItem.objects.all()
    return render(request, 'products.html', {'products': products})

# Manual caching
def get_gold_rate():
    """Get current gold rate with caching"""
    cache_key = 'gold_rate_current'
    rate = cache.get(cache_key)
    
    if rate is None:
        # Fetch from external API
        rate = fetch_gold_rate_from_api()
        # Cache for 5 minutes
        cache.set(cache_key, rate, 60 * 5)
    
    return rate

# Query result caching
def get_top_customers(tenant_id):
    """Get top customers with caching"""
    cache_key = f'top_customers_{tenant_id}'
    customers = cache.get(cache_key)
    
    if customers is None:
        customers = Customer.objects.filter(
            tenant_id=tenant_id
        ).order_by('-total_purchases')[:10]
        # Cache for 1 hour
        cache.set(cache_key, list(customers), 60 * 60)
    
    return customers

# Cache invalidation
def create_sale(sale_data):
    """Create sale and invalidate related caches"""
    sale = Sale.objects.create(**sale_data)
    
    # Invalidate customer cache
    cache.delete(f'customer_purchases_{sale.customer_id}')
    cache.delete(f'top_customers_{sale.tenant_id}')
    
    return sale
```

### Database Optimization

#### Query Optimization

```python
# BAD: N+1 query problem
sales = Sale.objects.all()
for sale in sales:
    print(sale.customer.name)  # Queries database for each sale

# GOOD: Use select_related for foreign keys
sales = Sale.objects.select_related('customer', 'branch', 'employee').all()
for sale in sales:
    print(sale.customer.name)  # No additional queries

# BAD: N+1 for reverse foreign keys
customers = Customer.objects.all()
for customer in customers:
    print(customer.sales.count())  # Queries for each customer

# GOOD: Use prefetch_related for reverse foreign keys
customers = Customer.objects.prefetch_related('sales').all()
for customer in customers:
    print(customer.sales.count())  # No additional queries

# GOOD: Use only() to fetch specific fields
products = InventoryItem.objects.only('id', 'name', 'selling_price')

# GOOD: Use defer() to exclude heavy fields
products = InventoryItem.objects.defer('description', 'image')

# GOOD: Use values() for dictionaries (lighter than model instances)
product_names = InventoryItem.objects.values('id', 'name')

# GOOD: Use aggregate for calculations
from django.db.models import Sum, Avg, Count
stats = Sale.objects.aggregate(
    total_sales=Sum('total'),
    avg_sale=Avg('total'),
    sale_count=Count('id')
)
```

#### Database Indexes

```python
class InventoryItem(models.Model):
    tenant = models.ForeignKey('Tenant', on_delete=models.CASCADE)
    sku = models.CharField(max_length=100)
    name = models.CharField(max_length=255)
    category = models.ForeignKey('ProductCategory', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            # Composite index for common query
            models.Index(fields=['tenant', 'category']),
            # Index for search
            models.Index(fields=['name']),
            # Index for sorting
            models.Index(fields=['-created_at']),
            # Unique constraint
            models.Index(fields=['tenant', 'sku'], name='unique_tenant_sku'),
        ]
        # Full-text search index (PostgreSQL)
        indexes += [
            GinIndex(fields=['name'], name='name_gin_idx', opclasses=['gin_trgm_ops']),
        ]
```

#### Connection Pooling

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASSWORD'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT', '5432'),
        'CONN_MAX_AGE': 600,  # Keep connections alive for 10 minutes
        'OPTIONS': {
            'connect_timeout': 10,
            'options': '-c statement_timeout=30000',  # 30 second query timeout
        },
    }
}

# Use PgBouncer for connection pooling
# PgBouncer config:
# [databases]
# jewelry_shop = host=localhost port=5432 dbname=jewelry_shop
# [pgbouncer]
# pool_mode = transaction
# max_client_conn = 1000
# default_pool_size = 25
```

### Frontend Optimization

#### Asset Optimization

```python
# settings.py
STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.ManifestStaticFilesStorage'

# Compress static files
INSTALLED_APPS += ['compressor']
COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True
COMPRESS_CSS_FILTERS = [
    'compressor.filters.css_default.CssAbsoluteFilter',
    'compressor.filters.cssmin.rCSSMinFilter',
]
COMPRESS_JS_FILTERS = [
    'compressor.filters.jsmin.JSMinFilter',
]
```

#### Template Fragment Caching

```django
{% load cache %}

{# Cache expensive template fragment for 10 minutes #}
{% cache 600 sidebar request.user.id %}
    <div class="sidebar">
        {# Expensive database queries or calculations #}
        {% for item in expensive_query %}
            {{ item.name }}
        {% endfor %}
    </div>
{% endcache %}
```

#### Lazy Loading Images

```html
<!-- Lazy load images -->
<img src="placeholder.jpg" 
     data-src="actual-image.jpg" 
     loading="lazy"
     alt="Product">

<script>
// Intersection Observer for lazy loading
const images = document.querySelectorAll('img[data-src]');
const imageObserver = new IntersectionObserver((entries, observer) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const img = entry.target;
            img.src = img.dataset.src;
            img.removeAttribute('data-src');
            observer.unobserve(img);
        }
    });
});

images.forEach(img => imageObserver.observe(img));
</script>
```

### API Optimization

#### Pagination

```python
from rest_framework.pagination import PageNumberPagination

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 100

# In viewset
class InventoryViewSet(viewsets.ModelViewSet):
    pagination_class = StandardResultsSetPagination
```

#### Response Compression

```python
# settings.py
MIDDLEWARE = [
    'django.middleware.gzip.GZipMiddleware',  # Add at top
    ...
]
```

#### API Throttling

```python
# settings.py
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    }
}
```

### Celery Task Optimization

```python
# Use task routing for different queues
CELERY_TASK_ROUTES = {
    'backups.tasks.*': {'queue': 'backups'},
    'reports.tasks.*': {'queue': 'reports'},
    'notifications.tasks.*': {'queue': 'notifications'},
}

# Task result backend
CELERY_RESULT_BACKEND = 'redis://localhost:6379/2'
CELERY_RESULT_EXPIRES = 3600  # 1 hour

# Task optimization
CELERY_TASK_ACKS_LATE = True  # Acknowledge after task completion
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Fetch one task at a time
CELERY_TASK_COMPRESSION = 'gzip'  # Compress task messages
```

### Monitoring Performance

```python
# Django Debug Toolbar (development only)
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']

# django-silk for profiling
INSTALLED_APPS += ['silk']
MIDDLEWARE += ['silk.middleware.SilkyMiddleware']

# Prometheus metrics
INSTALLED_APPS += ['django_prometheus']
MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    ...
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]
```


## Enterprise Backup & Disaster Recovery System

### Triple Storage Redundancy Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    BACKUP PROCESSING PIPELINE                    │
└─────────────────────────────────────────────────────────────────┘

Original Data
    ↓
Compress (gzip level 9) → 70-90% size reduction
    ↓
Encrypt (AES-256 Fernet) → Military-grade encryption
    ↓
Calculate Checksum (SHA-256) → Integrity verification
    ↓
Upload to 3 locations simultaneously
    ├─→ Local Storage (/var/backups/jewelry-shop/)
    ├─→ Cloudflare R2 (b7900eeee7c415345d86ea859c9dad47.r2.cloudflarestorage.com)
    └─→ Backblaze B2 (s3.us-east-005.backblazeb2.com)
    ↓
Verify checksums match across all locations
    ↓
Record metadata in database
    ↓
Cleanup temporary files
    ↓
DONE: Backup stored in 3 locations with verified integrity
```

### Storage Configuration

#### 1. Local Storage
- **Retention**: 30 days
- **Purpose**: Fast access for quick restores
- **Location**: `/var/backups/jewelry-shop/`
- **Auto-cleanup**: Files older than 30 days automatically deleted
- **Directory Structure**:
  ```
  /var/backups/jewelry-shop/
  ├── database/
  │   ├── full_backup_20251021_020000.sql.gz.enc
  │   └── full_backup_20251022_020000.sql.gz.enc
  ├── tenants/
  │   ├── tenant_uuid1_20251021_030000.sql.gz.enc
  │   └── tenant_uuid2_20251021_030000.sql.gz.enc
  ├── wal/
  │   ├── 000000010000000000000001.gz
  │   └── 000000010000000000000002.gz
  └── config/
      └── config_backup_20251021_040000.tar.gz.enc
  ```

#### 2. Cloudflare R2 (Primary Cloud)
- **Retention**: 1 year
- **Purpose**: Primary cloud storage with zero egress fees
- **Account ID**: `b7900eeee7c415345d86ea859c9dad47`
- **Bucket**: `securesyntax`
- **Endpoint**: `https://b7900eeee7c415345d86ea859c9dad47.r2.cloudflarestorage.com`
- **Access Key**: `3f3dfdd35d139a687d4d00d75da96c76`
- **Configuration**:
  ```python
  CLOUDFLARE_R2_CONFIG = {
      'account_id': 'b7900eeee7c415345d86ea859c9dad47',
      'bucket': 'securesyntax',
      'endpoint': 'https://b7900eeee7c415345d86ea859c9dad47.r2.cloudflarestorage.com',
      'access_key': '3f3dfdd35d139a687d4d00d75da96c76',
      'secret_key': os.getenv('CLOUDFLARE_R2_SECRET_KEY'),
      'retention_days': 365,
  }
  ```

#### 3. Backblaze B2 (Secondary Cloud)
- **Retention**: 1 year
- **Purpose**: Secondary cloud backup for redundancy
- **Bucket**: `securesyntax`
- **Region**: `us-east-005`
- **Endpoint**: `https://s3.us-east-005.backblazeb2.com`
- **Access Key**: `005acba9882c2b80000000001`
- **Bucket ID**: `2a0cfb4aa9f8f8f29c820b18`
- **Configuration**:
  ```python
  BACKBLAZE_B2_CONFIG = {
      'bucket': 'securesyntax',
      'bucket_id': '2a0cfb4aa9f8f8f29c820b18',
      'region': 'us-east-005',
      'endpoint': 'https://s3.us-east-005.backblazeb2.com',
      'access_key': '005acba9882c2b80000000001',
      'secret_key': os.getenv('BACKBLAZE_B2_SECRET_KEY'),
      'retention_days': 365,
  }
  ```

### Backup Types and Schedules

#### 1. Daily Full Database Backup (2:00 AM)

```python
@shared_task
def daily_full_backup():
    """
    Schedule: Every day at 2:00 AM
    Type: Complete PostgreSQL database dump
    Retention: 30 days local, 1 year cloud
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"full_backup_{timestamp}.sql"
    
    # Step 1: Create PostgreSQL dump with custom format
    dump_command = [
        'pg_dump',
        '-h', settings.DATABASES['default']['HOST'],
        '-U', settings.DATABASES['default']['USER'],
        '-d', settings.DATABASES['default']['NAME'],
        '-F', 'c',  # Custom format for faster restore
        '-f', f'/tmp/{backup_filename}'
    ]
    subprocess.run(dump_command, check=True)
    
    # Step 2: Compress with gzip level 9
    with open(f'/tmp/{backup_filename}', 'rb') as f_in:
        with gzip.open(f'/tmp/{backup_filename}.gz', 'wb', compresslevel=9) as f_out:
            f_out.writelines(f_in)
    
    # Step 3: Encrypt with AES-256 (Fernet)
    fernet = Fernet(settings.BACKUP_ENCRYPTION_KEY)
    with open(f'/tmp/{backup_filename}.gz', 'rb') as f:
        encrypted_data = fernet.encrypt(f.read())
    
    encrypted_filename = f'{backup_filename}.gz.enc'
    with open(f'/tmp/{encrypted_filename}', 'wb') as f:
        f.write(encrypted_data)
    
    # Step 4: Calculate SHA-256 checksum
    with open(f'/tmp/{encrypted_filename}', 'rb') as f:
        checksum = hashlib.sha256(f.read()).hexdigest()
    
    # Step 5: Upload to all three storage locations
    local_path = upload_to_local(f'/tmp/{encrypted_filename}', 'database')
    r2_path = upload_to_r2(f'/tmp/{encrypted_filename}', 'database')
    b2_path = upload_to_b2(f'/tmp/{encrypted_filename}', 'database')
    
    # Step 6: Verify checksums across all locations
    verify_backup_integrity(local_path, r2_path, b2_path, checksum)
    
    # Step 7: Record metadata in database
    Backup.objects.create(
        backup_type='FULL_DATABASE',
        filename=encrypted_filename,
        size_bytes=os.path.getsize(f'/tmp/{encrypted_filename}'),
        checksum=checksum,
        local_path=local_path,
        r2_path=r2_path,
        b2_path=b2_path,
        status='COMPLETED',
        compression_ratio=calculate_compression_ratio(backup_filename, encrypted_filename),
        backup_duration_seconds=int((datetime.now() - start_time).total_seconds())
    )
    
    # Step 8: Cleanup temporary files
    os.remove(f'/tmp/{backup_filename}')
    os.remove(f'/tmp/{backup_filename}.gz')
    os.remove(f'/tmp/{encrypted_filename}')
```

#### 2. Weekly Per-Tenant Backup (Sunday 3:00 AM)

```python
@shared_task
def weekly_tenant_backup():
    """
    Schedule: Every Sunday at 3:00 AM
    Type: Isolated tenant-specific data export
    Retention: 30 days local, 1 year cloud
    """
    for tenant in Tenant.objects.filter(status='ACTIVE'):
        create_tenant_backup.delay(tenant.id)

@shared_task
def create_tenant_backup(tenant_id):
    """Create backup for specific tenant using RLS-filtered export"""
    tenant = Tenant.objects.get(id=tenant_id)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"tenant_{tenant.id}_{timestamp}.sql"
    
    # Set tenant context for RLS
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT set_config('app.current_tenant', '{tenant.id}', false)")
        
        # Export only tenant's data
        dump_command = [
            'pg_dump',
            '-h', settings.DATABASES['default']['HOST'],
            '-U', settings.DATABASES['default']['USER'],
            '-d', settings.DATABASES['default']['NAME'],
            '-t', 'inventory_*',
            '-t', 'sales_*',
            '-t', 'crm_*',
            '-t', 'accounting_*',
            '--data-only',
            '-f', f'/tmp/{backup_filename}'
        ]
        subprocess.run(dump_command, check=True)
    
    # Compress, encrypt, checksum, and upload (same as daily backup)
    # Tag with tenant_id for easy identification
    Backup.objects.create(
        backup_type='TENANT_BACKUP',
        tenant_id=tenant.id,
        filename=encrypted_filename,
        # ... other fields
    )
```

#### 3. Continuous Point-in-Time Recovery (Every 5 minutes)

```python
@shared_task
def archive_wal_files():
    """
    Schedule: Every 5 minutes
    Type: PostgreSQL Write-Ahead Log (WAL) archiving
    Retention: 7 days local, 30 days cloud
    """
    wal_directory = '/var/lib/postgresql/data/pg_wal'
    
    for wal_file in os.listdir(wal_directory):
        if wal_file.endswith('.ready'):
            wal_path = os.path.join(wal_directory, wal_file.replace('.ready', ''))
            
            # Compress WAL file
            with open(wal_path, 'rb') as f_in:
                with gzip.open(f'{wal_path}.gz', 'wb') as f_out:
                    f_out.writelines(f_in)
            
            # Upload to R2 and B2 (skip local for WAL files to save space)
            r2_path = upload_to_r2(f'{wal_path}.gz', 'wal')
            b2_path = upload_to_b2(f'{wal_path}.gz', 'wal')
            
            # Mark as archived
            os.rename(f'{wal_file}.ready', f'{wal_file}.done')
            
            # Record in database
            Backup.objects.create(
                backup_type='WAL_ARCHIVE',
                filename=os.path.basename(f'{wal_path}.gz'),
                r2_path=r2_path,
                b2_path=b2_path,
                status='COMPLETED'
            )
```

#### 4. Configuration Backup (4:00 AM Daily)

```python
@shared_task
def backup_configuration():
    """
    Schedule: Every day at 4:00 AM
    Type: System configuration files and infrastructure code
    Retention: 30 days local, 1 year cloud
    """
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f"config_backup_{timestamp}.tar.gz"
    
    # Collect configuration files
    config_files = [
        'docker-compose.dev.yml',
        'docker-compose.prod.yml',
        'docker-compose.test.yml',
        '.env',  # Will be encrypted separately
        'nginx/nginx.conf',
        'nginx/conf.d/',
        'ssl/',
        'k8s/',
    ]
    
    # Create tar.gz archive
    with tarfile.open(f'/tmp/{backup_filename}', 'w:gz') as tar:
        for config_file in config_files:
            if os.path.exists(config_file):
                tar.add(config_file)
    
    # Encrypt and upload (same process as database backups)
    # ...
```

### Disaster Recovery Runbook

```python
@shared_task
def execute_disaster_recovery_runbook():
    """
    Automated disaster recovery procedure
    RTO: 1 hour | RPO: 15 minutes
    
    Timeline:
    0:00 - Disaster detected
    0:05 - Download latest backup from R2
    0:10 - Decrypt and decompress
    0:30 - Restore database (pg_restore with 4 parallel jobs)
    0:45 - Restart application pods
    0:50 - Verify health checks
    0:55 - Reroute traffic
    1:00 - System fully operational
    """
    start_time = datetime.now()
    log_dr_event("Disaster detected - initiating DR runbook")
    
    # 0:05 - Download latest backup from R2
    latest_backup = Backup.objects.filter(
        backup_type='FULL_DATABASE',
        status='COMPLETED'
    ).order_by('-created_at').first()
    
    try:
        backup_file = download_from_r2(latest_backup.r2_path)
    except Exception as e:
        # Automatic failover to Backblaze B2
        log_dr_event(f"R2 unavailable: {e}, failing over to B2")
        backup_file = download_from_b2(latest_backup.b2_path)
    
    log_dr_event(f"Downloaded backup: {latest_backup.filename}")
    
    # 0:10 - Decrypt and decompress
    decrypted_file = decrypt_backup(backup_file)
    decompressed_file = decompress_backup(decrypted_file)
    log_dr_event("Backup decrypted and decompressed")
    
    # 0:30 - Restore database using pg_restore
    restore_command = [
        'pg_restore',
        '-h', settings.DATABASES['default']['HOST'],
        '-U', settings.DATABASES['default']['USER'],
        '-d', settings.DATABASES['default']['NAME'],
        '-c',  # Clean (drop) database objects before recreating
        '-j', '4',  # Parallel restore with 4 jobs
        decompressed_file
    ]
    subprocess.run(restore_command, check=True)
    log_dr_event("Database restored successfully")
    
    # 0:45 - Restart application pods
    restart_application_pods()
    log_dr_event("Application pods restarted")
    
    # 0:50 - Verify health checks
    if verify_system_health():
        log_dr_event("Health checks passing")
    else:
        raise Exception("Health checks failed after restore")
    
    # 0:55 - Reroute traffic to healthy nodes
    reroute_traffic_to_healthy_nodes()
    log_dr_event("Traffic rerouted to healthy nodes")
    
    # 1:00 - System fully operational
    end_time = datetime.now()
    recovery_duration = (end_time - start_time).total_seconds() / 60
    
    log_dr_event(f"DR completed in {recovery_duration} minutes")
    send_dr_success_notification(recovery_duration)
    
    return {
        'status': 'SUCCESS',
        'recovery_duration_minutes': recovery_duration,
        'backup_used': latest_backup.filename
    }
```

### Celery Beat Schedule

```python
from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    'daily-full-backup': {
        'task': 'backups.tasks.daily_full_backup',
        'schedule': crontab(hour=2, minute=0),
        'options': {'queue': 'backups', 'priority': 9}
    },
    'weekly-tenant-backup': {
        'task': 'backups.tasks.weekly_tenant_backup',
        'schedule': crontab(hour=3, minute=0, day_of_week=0),  # Sunday
        'options': {'queue': 'backups', 'priority': 8}
    },
    'archive-wal-files': {
        'task': 'backups.tasks.archive_wal_files',
        'schedule': crontab(minute='*/5'),  # Every 5 minutes
        'options': {'queue': 'backups', 'priority': 10}
    },
    'backup-configuration': {
        'task': 'backups.tasks.backup_configuration',
        'schedule': crontab(hour=4, minute=0),
        'options': {'queue': 'backups', 'priority': 7}
    },
    'monthly-test-restore': {
        'task': 'backups.tasks.automated_test_restore',
        'schedule': crontab(hour=3, minute=0, day_of_month=1),  # 1st of month
        'options': {'queue': 'backups', 'priority': 6}
    },
    'cleanup-old-backups': {
        'task': 'backups.tasks.cleanup_old_backups',
        'schedule': crontab(hour=5, minute=0),
        'options': {'queue': 'maintenance', 'priority': 3}
    },
    'verify-storage-integrity': {
        'task': 'backups.tasks.verify_storage_integrity',
        'schedule': crontab(minute=0),  # Every hour
        'options': {'queue': 'backups', 'priority': 5}
    },
}
```

### Storage Backend Implementation

```python
import boto3
from django.conf import settings

class CloudflareR2Storage:
    """Cloudflare R2 storage backend"""
    
    def __init__(self):
        self.client = boto3.client(
            's3',
            endpoint_url=f"https://{settings.CLOUDFLARE_R2_CONFIG['account_id']}.r2.cloudflarestorage.com",
            aws_access_key_id=settings.CLOUDFLARE_R2_CONFIG['access_key'],
            aws_secret_access_key=settings.CLOUDFLARE_R2_CONFIG['secret_key'],
            region_name='auto'
        )
        self.bucket = settings.CLOUDFLARE_R2_CONFIG['bucket']
    
    def upload(self, local_path, remote_path):
        self.client.upload_file(local_path, self.bucket, remote_path)
        return f's3://{self.bucket}/{remote_path}'
    
    def download(self, remote_path, local_path):
        self.client.download_file(self.bucket, remote_path, local_path)
        return local_path

class BackblazeB2Storage:
    """Backblaze B2 storage backend"""
    
    def __init__(self):
        self.client = boto3.client(
            's3',
            endpoint_url=settings.BACKBLAZE_B2_CONFIG['endpoint'],
            aws_access_key_id=settings.BACKBLAZE_B2_CONFIG['access_key'],
            aws_secret_access_key=settings.BACKBLAZE_B2_CONFIG['secret_key'],
            region_name=settings.BACKBLAZE_B2_CONFIG['region']
        )
        self.bucket = settings.BACKBLAZE_B2_CONFIG['bucket']
    
    def upload(self, local_path, remote_path):
        self.client.upload_file(local_path, self.bucket, remote_path)
        return f's3://{self.bucket}/{remote_path}'
    
    def download(self, remote_path, local_path):
        self.client.download_file(self.bucket, remote_path, local_path)
        return local_path
```



## Kubernetes Deployment Architecture with k3d/k3s

### Overview

The application uses **k3d** for local development and **k3s** for production VPS deployment. This approach provides:
- **Lightweight**: k3s uses ~512MB RAM vs 2GB+ for full Kubernetes
- **Fast**: k3d cluster starts in seconds
- **Production-ready**: k3s is CNCF certified Kubernetes
- **Consistent**: Same k3s binary runs locally and in production
- **Self-healing**: Automatic recovery from failures
- **Auto-scaling**: HPA scales pods based on load

### k3d Local Development Cluster

**Configuration: 1 Server + 2 Agents**

```bash
# Create k3d cluster
k3d cluster create jewelry-shop \
  --servers 1 \
  --agents 2 \
  --port "8080:80@loadbalancer" \
  --port "8443:443@loadbalancer" \
  --volume "/var/lib/rancher/k3s/storage:/var/lib/rancher/k3s/storage@all" \
  --k3s-arg "--disable=traefik@server:0"

# Verify cluster
kubectl get nodes
```

### k3s Production VPS Deployment

```bash
# Install k3s on VPS
curl -sfL https://get.k3s.io | sh -

# Verify installation
sudo k3s kubectl get nodes

# Get kubeconfig for remote access
sudo cat /etc/rancher/k3s/k3s.yaml
```

### Zalando Postgres Operator

**Why Zalando Operator:**
- Declarative PostgreSQL cluster management
- Automatic failover and leader election
- Built-in backup and restore
- Connection pooling with PgBouncer
- Monitoring and metrics
- Production-proven (used by Zalando, Zalando SE)

**Installation:**

```bash
# Install operator using Helm
helm repo add postgres-operator-charts https://opensource.zalando.com/postgres-operator/charts/postgres-operator
helm install postgres-operator postgres-operator-charts/postgres-operator

# Verify operator is running
kubectl get pods -n postgres-operator
```



**PostgreSQL Cluster Configuration:**

```yaml
apiVersion: "acid.zalan.do/v1"
kind: postgresql
metadata:
  name: jewelry-shop-postgres
  namespace: jewelry-shop
spec:
  teamId: "jewelry-shop"
  volume:
    size: 100Gi
    storageClass: local-path
  numberOfInstances: 3
  users:
    jewelry_shop_user:
      - superuser
      - createdb
  databases:
    jewelry_shop: jewelry_shop_user
  postgresql:
    version: "15"
    parameters:
      shared_buffers: "2GB"
      effective_cache_size: "6GB"
      maintenance_work_mem: "512MB"
      checkpoint_completion_target: "0.9"
      wal_buffers: "16MB"
      default_statistics_target: "100"
      random_page_cost: "1.1"
      effective_io_concurrency: "200"
      work_mem: "10MB"
      min_wal_size: "1GB"
      max_wal_size: "4GB"
      max_worker_processes: "4"
      max_parallel_workers_per_gather: "2"
      max_parallel_workers: "4"
      max_parallel_maintenance_workers: "2"
  patroni:
    initdb:
      encoding: "UTF8"
      locale: "en_US.UTF-8"
      data-checksums: "true"
    pg_hba:
      - hostssl all all 0.0.0.0/0 md5
      - host all all 0.0.0.0/0 md5
  resources:
    requests:
      cpu: "1000m"
      memory: "2Gi"
    limits:
      cpu: "2000m"
      memory: "4Gi"
  sidecars:
    - name: "exporter"
      image: "quay.io/prometheuscommunity/postgres-exporter:latest"
      ports:
        - name: exporter
          containerPort: 9187
          protocol: TCP
      env:
        - name: "DATA_SOURCE_URI"
          value: "localhost/jewelry_shop?sslmode=require"
```



### Self-Healing and Automation Features

**1. Automatic Pod Restart (Liveness Probes)**

```yaml
livenessProbe:
  httpGet:
    path: /health/live/
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
  timeoutSeconds: 5
  failureThreshold: 3
# If 3 consecutive health checks fail, Kubernetes automatically restarts the pod
```

**2. Automatic Traffic Routing (Readiness Probes)**

```yaml
readinessProbe:
  httpGet:
    path: /health/ready/
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 5
  timeoutSeconds: 3
  failureThreshold: 2
# Unhealthy pods are automatically removed from service endpoints
```

**3. Automatic Scaling (HPA)**

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: django-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: django-app
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
  behavior:
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Percent
        value: 50
        periodSeconds: 60
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
      - type: Pods
        value: 2
        periodSeconds: 15
      selectPolicy: Max
```



**4. Automatic Database Failover (Zalando Operator)**

The Zalando Postgres Operator automatically handles:
- **Leader election**: When master fails, a replica is automatically promoted
- **Replication**: Streaming replication keeps replicas in sync
- **Split-brain prevention**: Uses Patroni's DCS (etcd) for consensus
- **Automatic recovery**: Failed pods are recreated automatically
- **Zero downtime**: Clients reconnect to new master automatically

**Failover Timeline:**
```
0:00 - Master pod crashes
0:05 - Patroni detects master failure
0:10 - Patroni promotes healthiest replica to master
0:15 - Other replicas start replicating from new master
0:20 - Service endpoint updated to point to new master
0:25 - Application reconnects to new master
0:30 - System fully operational
```

**5. Automatic Redis Failover (Sentinel)**

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: redis
spec:
  serviceName: redis
  replicas: 3
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
      - name: redis
        image: redis:7-alpine
        command:
          - redis-server
          - --appendonly yes
          - --save 900 1
          - --save 300 10
          - --save 60 10000
        ports:
        - containerPort: 6379
        volumeMounts:
        - name: redis-data
          mountPath: /data
        livenessProbe:
          exec:
            command:
            - redis-cli
            - ping
          initialDelaySeconds: 30
          periodSeconds: 10
  volumeClaimTemplates:
  - metadata:
      name: redis-data
    spec:
      accessModes: ["ReadWriteOnce"]
      resources:
        requests:
          storage: 10Gi
```



### Chaos Testing and Load Testing

**1. Extreme Load Testing with Locust**

```python
# locustfile.py - Extreme load test
from locust import HttpUser, task, between, events
import random

class JewelryShopUser(HttpUser):
    wait_time = between(0.1, 0.5)  # Aggressive timing
    
    def on_start(self):
        """Login before starting"""
        response = self.client.post('/api/auth/login/', {
            'username': f'testuser{random.randint(1, 1000)}',
            'password': 'testpass'
        })
        self.token = response.json().get('access_token')
        self.client.headers.update({'Authorization': f'Bearer {self.token}'})
    
    @task(10)
    def view_dashboard(self):
        """Most common action - high weight"""
        self.client.get('/dashboard/')
    
    @task(5)
    def search_inventory(self):
        """Search inventory"""
        self.client.get(f'/api/inventory/?search=gold&page={random.randint(1, 10)}')
    
    @task(3)
    def create_sale(self):
        """Create sales - moderate load"""
        self.client.post('/api/sales/', {
            'items': [{'inventory_item_id': random.randint(1, 100), 'quantity': 1}],
            'payment_method': 'cash'
        })
    
    @task(2)
    def generate_report(self):
        """Heavy operation"""
        self.client.post('/api/reports/generate/', {
            'report_type': 'sales_summary',
            'date_range': '30_days'
        })

# Run extreme load test
# locust -f locustfile.py --users 1000 --spawn-rate 50 --run-time 30m --host https://jewelry-shop.com
```

**Expected Behavior:**
- **0-100 users**: All pods handle load easily
- **100-300 users**: CPU reaches 70%, HPA triggers scale-up to 5 pods
- **300-500 users**: Memory reaches 80%, HPA scales to 7 pods
- **500-800 users**: HPA scales to 10 pods (maximum)
- **800-1000 users**: System maintains performance at max capacity
- **Load decreases**: HPA gradually scales down after 5-minute stabilization window



**2. Chaos Testing Scenarios**

```bash
#!/bin/bash
# chaos_test.sh - Automated chaos testing

echo "=== Starting Chaos Testing ==="

# Test 1: Kill PostgreSQL master pod
echo "Test 1: Killing PostgreSQL master pod..."
MASTER_POD=$(kubectl get pods -l application=spilo,cluster-name=jewelry-shop-postgres,spilo-role=master -o name)
kubectl delete $MASTER_POD
echo "Waiting for automatic failover..."
sleep 30
kubectl get pods -l application=spilo
# Expected: New master elected, all pods running

# Test 2: Kill random Django pods
echo "Test 2: Killing random Django pods..."
for i in {1..3}; do
    RANDOM_POD=$(kubectl get pods -l app=django -o name | shuf -n 1)
    kubectl delete $RANDOM_POD
    echo "Killed $RANDOM_POD, waiting 10s..."
    sleep 10
done
kubectl get pods -l app=django
# Expected: Pods automatically recreated, service continues

# Test 3: Kill Redis master
echo "Test 3: Killing Redis master..."
REDIS_MASTER=$(kubectl get pods -l app=redis,role=master -o name)
kubectl delete $REDIS_MASTER
echo "Waiting for Sentinel failover..."
sleep 20
kubectl get pods -l app=redis
# Expected: Sentinel promotes new master

# Test 4: Simulate node failure
echo "Test 4: Cordoning node to simulate failure..."
NODE=$(kubectl get nodes -o name | grep agent | head -n 1)
kubectl cordon $NODE
kubectl drain $NODE --ignore-daemonsets --delete-emptydir-data
echo "Waiting for pods to reschedule..."
sleep 60
kubectl get pods -o wide
# Expected: All pods rescheduled to healthy nodes

# Cleanup
kubectl uncordon $NODE

# Test 5: Network partition simulation
echo "Test 5: Simulating network partition..."
kubectl apply -f - <<EOF
apiVersion: v1
kind: NetworkPolicy
metadata:
  name: isolate-postgres
spec:
  podSelector:
    matchLabels:
      application: spilo
  policyTypes:
  - Ingress
  - Egress
  ingress: []
  egress: []
EOF
echo "Waiting 30s..."
sleep 30
kubectl delete networkpolicy isolate-postgres
# Expected: System detects partition, maintains consistency

echo "=== Chaos Testing Complete ==="
echo "Verifying system health..."
kubectl get pods --all-namespaces
kubectl top nodes
kubectl top pods
```



**3. Automated Validation After Each Step**

```bash
#!/bin/bash
# validate_deployment.sh - Run after each deployment step

validate_step() {
    local step_name=$1
    echo "=== Validating: $step_name ==="
    
    # Check pod status
    echo "Checking pod status..."
    kubectl get pods -n jewelry-shop
    PENDING=$(kubectl get pods -n jewelry-shop --field-selector=status.phase=Pending --no-headers | wc -l)
    FAILED=$(kubectl get pods -n jewelry-shop --field-selector=status.phase=Failed --no-headers | wc -l)
    
    if [ $PENDING -gt 0 ] || [ $FAILED -gt 0 ]; then
        echo "❌ FAILED: Pods not healthy"
        kubectl describe pods -n jewelry-shop | grep -A 10 "Events:"
        return 1
    fi
    echo "✅ All pods running"
    
    # Check service endpoints
    echo "Checking service endpoints..."
    kubectl get endpoints -n jewelry-shop
    
    # Test connectivity
    echo "Testing service connectivity..."
    kubectl run test-pod --image=curlimages/curl:latest --rm -it --restart=Never -- \
        curl -s -o /dev/null -w "%{http_code}" http://django-service.jewelry-shop.svc.cluster.local/health/
    
    # Check logs for errors
    echo "Checking logs for errors..."
    ERROR_COUNT=$(kubectl logs -n jewelry-shop -l app=django --tail=100 | grep -i error | wc -l)
    if [ $ERROR_COUNT -gt 5 ]; then
        echo "⚠️  WARNING: Found $ERROR_COUNT errors in logs"
        kubectl logs -n jewelry-shop -l app=django --tail=20 | grep -i error
    fi
    
    echo "✅ $step_name validation complete"
    return 0
}

# Usage after each deployment step:
# validate_step "Django Deployment"
# validate_step "PostgreSQL Cluster"
# validate_step "Redis Cluster"
```

**4. Continuous Health Monitoring**

```python
# health_check.py - Comprehensive health check endpoint
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
import redis

def health_check_live(request):
    """Liveness probe - is the application running?"""
    return JsonResponse({'status': 'alive'})

def health_check_ready(request):
    """Readiness probe - can the application serve traffic?"""
    checks = {}
    
    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks['database'] = 'healthy'
    except Exception as e:
        checks['database'] = f'unhealthy: {str(e)}'
        return JsonResponse({'status': 'not_ready', 'checks': checks}, status=503)
    
    # Check Redis
    try:
        cache.set('health_check', 'ok', 10)
        assert cache.get('health_check') == 'ok'
        checks['redis'] = 'healthy'
    except Exception as e:
        checks['redis'] = f'unhealthy: {str(e)}'
        return JsonResponse({'status': 'not_ready', 'checks': checks}, status=503)
    
    # Check Celery
    try:
        from celery import current_app
        inspect = current_app.control.inspect()
        stats = inspect.stats()
        if stats:
            checks['celery'] = 'healthy'
        else:
            checks['celery'] = 'no workers'
    except Exception as e:
        checks['celery'] = f'unhealthy: {str(e)}'
    
    return JsonResponse({'status': 'ready', 'checks': checks})
```

