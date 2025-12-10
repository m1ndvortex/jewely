"""
Subscription Enforcement Service for enterprise-grade limit management.

This service provides comprehensive subscription limit checking and enforcement
across all tenant resources. It integrates with views, API endpoints, and
background tasks to ensure subscription limits are properly enforced.

Features:
- Real-time limit checking for all resource types
- Usage tracking and quota management
- Graceful degradation with warning thresholds
- Caching for performance optimization
- Audit logging for compliance
"""

import logging
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple, Union

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Count, Sum
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

if TYPE_CHECKING:
    from apps.core.models import Tenant, TenantSubscription

logger = logging.getLogger(__name__)


class LimitType(Enum):
    """Types of subscription limits that can be enforced."""
    
    # Core Business Limits
    USERS = "users"
    BRANCHES = "branches"
    INVENTORY = "inventory"
    CONTACTS = "contacts"
    PRODUCTS = "products"
    SUPPLIERS = "suppliers"
    CATEGORIES = "categories"
    
    # Sales & POS Limits
    POS_TERMINALS = "pos_terminals"
    SALES_PER_MONTH = "sales_per_month"
    GIFT_CARDS = "gift_cards"
    
    # Monthly Operation Limits
    INVOICES = "invoices"
    TRANSACTIONS = "transactions"
    CUSTOM_ORDERS = "custom_orders"
    REPAIR_ORDERS = "repair_orders"
    PURCHASE_ORDERS = "purchase_orders"
    
    # Marketing & Communication Limits
    EMAIL_CAMPAIGNS = "email_campaigns"
    SMS_CAMPAIGNS = "sms_campaigns"
    EMAILS_PER_MONTH = "emails_per_month"
    SMS_PER_MONTH = "sms_per_month"
    
    # Advanced Features Limits
    API_CALLS = "api_calls"
    REPORTS_PER_MONTH = "reports_per_month"
    PRICING_RULES = "pricing_rules"
    JOURNAL_ENTRIES = "journal_entries"
    LOYALTY_TIERS = "loyalty_tiers"
    
    # System Limits
    STORAGE = "storage"
    BACKUP_RETENTION = "backup_retention"
    CONCURRENT_SESSIONS = "concurrent_sessions"
    DOCUMENTS = "documents"
    WEBHOOKS = "webhooks"
    
    CUSTOM = "custom"


class EnforcementResult(Enum):
    """Result of a limit enforcement check."""
    
    ALLOWED = "allowed"  # Action is allowed
    WARNING = "warning"  # Action is allowed but nearing limit
    BLOCKED = "blocked"  # Action is blocked due to limit
    UNLIMITED = "unlimited"  # No limit applies
    NO_SUBSCRIPTION = "no_subscription"  # Tenant has no subscription


@dataclass
class LimitCheckResult:
    """Result of checking a subscription limit."""
    
    result: EnforcementResult
    limit_type: LimitType
    current_usage: int
    limit: int
    remaining: int
    percentage_used: float
    message: str
    
    @property
    def is_allowed(self) -> bool:
        """Check if the action is allowed."""
        return self.result in (EnforcementResult.ALLOWED, EnforcementResult.WARNING, EnforcementResult.UNLIMITED)
    
    @property
    def is_blocked(self) -> bool:
        """Check if the action is blocked."""
        return self.result == EnforcementResult.BLOCKED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "result": self.result.value,
            "limit_type": self.limit_type.value,
            "current_usage": self.current_usage,
            "limit": self.limit if self.limit != -1 else "unlimited",
            "remaining": self.remaining if self.limit != -1 else "unlimited",
            "percentage_used": round(self.percentage_used, 2),
            "message": str(self.message),
        }


@dataclass
class UsageStats:
    """Usage statistics for a tenant's subscription."""
    
    # Core Business Stats
    users: int = 0
    branches: int = 0
    inventory_items: int = 0
    contacts: int = 0
    products: int = 0
    suppliers: int = 0
    categories: int = 0
    
    # Sales & POS Stats
    pos_terminals: int = 0
    sales_this_month: int = 0
    gift_cards: int = 0
    
    # Monthly Operation Stats
    invoices_this_month: int = 0
    transactions_this_month: int = 0
    custom_orders_this_month: int = 0
    repair_orders_this_month: int = 0
    purchase_orders_this_month: int = 0
    
    # Marketing & Communication Stats
    email_campaigns_this_month: int = 0
    sms_campaigns_this_month: int = 0
    emails_sent_this_month: int = 0
    sms_sent_this_month: int = 0
    
    # Advanced Features Stats
    api_calls_this_month: int = 0
    reports_this_month: int = 0
    pricing_rules: int = 0
    journal_entries_this_month: int = 0
    loyalty_tiers: int = 0
    
    # System Stats
    storage_bytes: int = 0
    backup_retention_days: int = 0
    concurrent_sessions: int = 0
    documents: int = 0
    webhooks: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            # Core Business
            "users": self.users,
            "branches": self.branches,
            "inventory_items": self.inventory_items,
            "contacts": self.contacts,
            "products": self.products,
            "suppliers": self.suppliers,
            "categories": self.categories,
            # Sales & POS
            "pos_terminals": self.pos_terminals,
            "sales_this_month": self.sales_this_month,
            "gift_cards": self.gift_cards,
            # Monthly Operations
            "invoices_this_month": self.invoices_this_month,
            "transactions_this_month": self.transactions_this_month,
            "custom_orders_this_month": self.custom_orders_this_month,
            "repair_orders_this_month": self.repair_orders_this_month,
            "purchase_orders_this_month": self.purchase_orders_this_month,
            # Marketing
            "email_campaigns_this_month": self.email_campaigns_this_month,
            "sms_campaigns_this_month": self.sms_campaigns_this_month,
            "emails_sent_this_month": self.emails_sent_this_month,
            "sms_sent_this_month": self.sms_sent_this_month,
            # Advanced
            "api_calls_this_month": self.api_calls_this_month,
            "reports_this_month": self.reports_this_month,
            "pricing_rules": self.pricing_rules,
            "journal_entries_this_month": self.journal_entries_this_month,
            "loyalty_tiers": self.loyalty_tiers,
            # System
            "storage_gb": round(self.storage_bytes / (1024 * 1024 * 1024), 2),
            "concurrent_sessions": self.concurrent_sessions,
            "documents": self.documents,
            "webhooks": self.webhooks,
        }


class SubscriptionEnforcementService:
    """
    Enterprise-grade subscription enforcement service.
    
    This service is responsible for:
    1. Checking subscription limits before resource creation
    2. Tracking resource usage
    3. Providing usage statistics
    4. Enforcing limits with graceful degradation
    5. Caching for performance
    
    Usage:
        service = SubscriptionEnforcementService(tenant)
        result = service.check_limit(LimitType.USERS)
        if result.is_blocked:
            raise SubscriptionLimitExceeded(result.message)
    """
    
    # Warning threshold - alert when usage exceeds this percentage
    WARNING_THRESHOLD = 80.0
    
    # Cache timeout in seconds
    CACHE_TIMEOUT = 300  # 5 minutes
    
    def __init__(self, tenant: "Tenant"):
        """
        Initialize the enforcement service for a tenant.
        
        Args:
            tenant: The tenant to enforce limits for
        """
        self.tenant = tenant
        self._subscription: Optional["TenantSubscription"] = None
        self._usage_stats: Optional[UsageStats] = None
    
    @property
    def subscription(self) -> Optional["TenantSubscription"]:
        """Get the tenant's subscription (cached)."""
        if self._subscription is None:
            try:
                self._subscription = self.tenant.subscription
            except Exception:
                self._subscription = None
        return self._subscription
    
    def has_active_subscription(self) -> bool:
        """Check if tenant has an active subscription."""
        if not self.subscription:
            return False
        return self.subscription.is_active() or self.subscription.is_trial()
    
    def _get_cache_key(self, suffix: str) -> str:
        """Generate a cache key for this tenant."""
        return f"subscription_enforcement:{self.tenant.id}:{suffix}"
    
    def _invalidate_cache(self):
        """Invalidate all cached data for this tenant."""
        cache.delete(self._get_cache_key("usage_stats"))
        self._usage_stats = None
    
    def get_usage_stats(self, force_refresh: bool = False) -> UsageStats:
        """
        Get current usage statistics for the tenant.
        
        Args:
            force_refresh: If True, bypass cache and recalculate
            
        Returns:
            UsageStats object with current usage
        """
        if not force_refresh:
            cache_key = self._get_cache_key("usage_stats")
            cached = cache.get(cache_key)
            if cached:
                return cached
        
        stats = self._calculate_usage_stats()
        
        # Cache the results
        cache.set(self._get_cache_key("usage_stats"), stats, self.CACHE_TIMEOUT)
        self._usage_stats = stats
        
        return stats
    
    def _calculate_usage_stats(self) -> UsageStats:
        """Calculate current usage statistics from the database."""
        from apps.core.models import Branch, User
        from apps.core.tenant_context import tenant_context
        
        stats = UsageStats()
        
        with tenant_context(self.tenant):
            # Count users
            stats.users = User.objects.filter(tenant=self.tenant).count()
            
            # Count branches
            stats.branches = Branch.objects.filter(tenant=self.tenant).count()
            
            # Count inventory items
            try:
                from apps.inventory.models import InventoryItem
                stats.inventory_items = InventoryItem.objects.filter(tenant=self.tenant).count()
            except ImportError:
                stats.inventory_items = 0
            
            # Count contacts/customers
            try:
                from apps.crm.models import Customer
                stats.contacts = Customer.objects.filter(tenant=self.tenant).count()
            except ImportError:
                stats.contacts = 0
            
            # Count products
            try:
                from apps.inventory.models import Product
                stats.products = Product.objects.filter(tenant=self.tenant).count()
            except ImportError:
                stats.products = 0
            
            # Get monthly usage from subscription
            if self.subscription:
                stats.invoices_this_month = self.subscription.invoices_created_this_month
                stats.transactions_this_month = self.subscription.transactions_this_month
                stats.api_calls_this_month = self.subscription.api_calls_used_this_month
                stats.storage_bytes = self.subscription.storage_used_bytes
        
        return stats
    
    def check_limit(self, limit_type: LimitType, increment: int = 1) -> LimitCheckResult:
        """
        Check if a subscription limit would be exceeded.
        
        Args:
            limit_type: The type of limit to check
            increment: Number of resources being added (default 1)
            
        Returns:
            LimitCheckResult with the check result
        """
        if not self.subscription:
            return LimitCheckResult(
                result=EnforcementResult.NO_SUBSCRIPTION,
                limit_type=limit_type,
                current_usage=0,
                limit=0,
                remaining=0,
                percentage_used=0,
                message=_("No active subscription found. Please subscribe to a plan."),
            )
        
        # Get current usage and limit
        current_usage, limit = self._get_usage_and_limit(limit_type)
        
        # Check for unlimited
        if limit == -1:
            return LimitCheckResult(
                result=EnforcementResult.UNLIMITED,
                limit_type=limit_type,
                current_usage=current_usage,
                limit=-1,
                remaining=-1,
                percentage_used=0,
                message=_("Unlimited usage allowed for this resource."),
            )
        
        # Calculate usage after increment
        new_usage = current_usage + increment
        remaining = max(0, limit - current_usage)
        percentage_used = (current_usage / limit * 100) if limit > 0 else 100
        
        # Check if limit would be exceeded
        if new_usage > limit:
            return LimitCheckResult(
                result=EnforcementResult.BLOCKED,
                limit_type=limit_type,
                current_usage=current_usage,
                limit=limit,
                remaining=remaining,
                percentage_used=percentage_used,
                message=self._get_limit_exceeded_message(limit_type, current_usage, limit),
            )
        
        # Check if nearing limit (warning)
        if percentage_used >= self.WARNING_THRESHOLD:
            return LimitCheckResult(
                result=EnforcementResult.WARNING,
                limit_type=limit_type,
                current_usage=current_usage,
                limit=limit,
                remaining=remaining,
                percentage_used=percentage_used,
                message=self._get_warning_message(limit_type, current_usage, limit),
            )
        
        # All good
        return LimitCheckResult(
            result=EnforcementResult.ALLOWED,
            limit_type=limit_type,
            current_usage=current_usage,
            limit=limit,
            remaining=remaining,
            percentage_used=percentage_used,
            message=_("Action allowed."),
        )
    
    def _get_usage_and_limit(self, limit_type: LimitType) -> Tuple[int, int]:
        """Get current usage and limit for a resource type."""
        stats = self.get_usage_stats()
        
        # Core Business Limits
        limit_mapping = {
            LimitType.USERS: (stats.users, self.subscription.get_user_limit()),
            LimitType.BRANCHES: (stats.branches, self.subscription.get_branch_limit()),
            LimitType.INVENTORY: (stats.inventory_items, self.subscription.get_inventory_limit()),
            LimitType.CONTACTS: (stats.contacts, self.subscription.get_contacts_limit()),
            LimitType.PRODUCTS: (stats.products, self.subscription.get_products_limit()),
            LimitType.SUPPLIERS: (stats.suppliers, self.subscription.get_suppliers_limit()),
            LimitType.CATEGORIES: (stats.categories, self.subscription.get_categories_limit()),
            
            # Sales & POS Limits
            LimitType.POS_TERMINALS: (stats.pos_terminals, self.subscription.get_pos_terminals_limit()),
            LimitType.SALES_PER_MONTH: (stats.sales_this_month, self.subscription.get_sales_per_month_limit()),
            LimitType.GIFT_CARDS: (stats.gift_cards, self.subscription.get_gift_cards_limit()),
            
            # Monthly Operation Limits
            LimitType.INVOICES: (stats.invoices_this_month, self.subscription.get_invoices_limit()),
            LimitType.TRANSACTIONS: (stats.transactions_this_month, self.subscription.get_transactions_limit()),
            LimitType.CUSTOM_ORDERS: (stats.custom_orders_this_month, self.subscription.get_custom_orders_limit()),
            LimitType.REPAIR_ORDERS: (stats.repair_orders_this_month, self.subscription.get_repair_orders_limit()),
            LimitType.PURCHASE_ORDERS: (stats.purchase_orders_this_month, self.subscription.get_purchase_orders_limit()),
            
            # Marketing & Communication Limits
            LimitType.EMAIL_CAMPAIGNS: (stats.email_campaigns_this_month, self.subscription.get_email_campaigns_limit()),
            LimitType.SMS_CAMPAIGNS: (stats.sms_campaigns_this_month, self.subscription.get_sms_campaigns_limit()),
            LimitType.EMAILS_PER_MONTH: (stats.emails_sent_this_month, self.subscription.get_emails_per_month_limit()),
            LimitType.SMS_PER_MONTH: (stats.sms_sent_this_month, self.subscription.get_sms_per_month_limit()),
            
            # Advanced Features Limits
            LimitType.API_CALLS: (stats.api_calls_this_month, self.subscription.get_api_calls_per_month()),
            LimitType.REPORTS_PER_MONTH: (stats.reports_this_month, self.subscription.get_reports_per_month_limit()),
            LimitType.PRICING_RULES: (stats.pricing_rules, self.subscription.get_pricing_rules_limit()),
            LimitType.JOURNAL_ENTRIES: (stats.journal_entries_this_month, self.subscription.get_journal_entries_limit()),
            LimitType.LOYALTY_TIERS: (stats.loyalty_tiers, self.subscription.get_loyalty_tiers_limit()),
            
            # System Limits
            LimitType.STORAGE: (
                int(stats.storage_bytes / (1024 * 1024 * 1024)),  # Convert to GB
                self.subscription.get_storage_limit_gb(),
            ),
            LimitType.BACKUP_RETENTION: (stats.backup_retention_days, self.subscription.get_backup_retention_days()),
            LimitType.CONCURRENT_SESSIONS: (stats.concurrent_sessions, self.subscription.get_concurrent_sessions_limit()),
            LimitType.DOCUMENTS: (stats.documents, self.subscription.get_documents_limit()),
            LimitType.WEBHOOKS: (stats.webhooks, self.subscription.get_webhooks_limit()),
        }
        
        return limit_mapping.get(limit_type, (0, 0))
    
    def _get_limit_exceeded_message(self, limit_type: LimitType, current: int, limit: int) -> str:
        """Get a user-friendly message for limit exceeded."""
        messages = {
            # Core Business
            LimitType.USERS: _("User limit reached ({current}/{limit}). Please upgrade your plan to add more users."),
            LimitType.BRANCHES: _("Branch limit reached ({current}/{limit}). Please upgrade your plan to add more branches."),
            LimitType.INVENTORY: _("Inventory limit reached ({current}/{limit}). Please upgrade your plan to add more items."),
            LimitType.CONTACTS: _("Contact limit reached ({current}/{limit}). Please upgrade your plan to add more contacts."),
            LimitType.PRODUCTS: _("Product limit reached ({current}/{limit}). Please upgrade your plan to add more products."),
            LimitType.SUPPLIERS: _("Supplier limit reached ({current}/{limit}). Please upgrade your plan to add more suppliers."),
            LimitType.CATEGORIES: _("Category limit reached ({current}/{limit}). Please upgrade your plan to add more categories."),
            
            # Sales & POS
            LimitType.POS_TERMINALS: _("POS terminal limit reached ({current}/{limit}). Please upgrade your plan to add more terminals."),
            LimitType.SALES_PER_MONTH: _("Monthly sales limit reached ({current}/{limit}). Please upgrade your plan or wait for the next billing cycle."),
            LimitType.GIFT_CARDS: _("Gift card limit reached ({current}/{limit}). Please upgrade your plan to create more gift cards."),
            
            # Monthly Operations
            LimitType.INVOICES: _("Monthly invoice limit reached ({current}/{limit}). Please upgrade your plan or wait for the next billing cycle."),
            LimitType.TRANSACTIONS: _("Monthly transaction limit reached ({current}/{limit}). Please upgrade your plan or wait for the next billing cycle."),
            LimitType.CUSTOM_ORDERS: _("Monthly custom order limit reached ({current}/{limit}). Please upgrade your plan or wait for the next billing cycle."),
            LimitType.REPAIR_ORDERS: _("Monthly repair order limit reached ({current}/{limit}). Please upgrade your plan or wait for the next billing cycle."),
            LimitType.PURCHASE_ORDERS: _("Monthly purchase order limit reached ({current}/{limit}). Please upgrade your plan or wait for the next billing cycle."),
            
            # Marketing & Communication
            LimitType.EMAIL_CAMPAIGNS: _("Monthly email campaign limit reached ({current}/{limit}). Please upgrade your plan or wait for the next billing cycle."),
            LimitType.SMS_CAMPAIGNS: _("Monthly SMS campaign limit reached ({current}/{limit}). Please upgrade your plan or wait for the next billing cycle."),
            LimitType.EMAILS_PER_MONTH: _("Monthly email limit reached ({current}/{limit}). Please upgrade your plan or wait for the next billing cycle."),
            LimitType.SMS_PER_MONTH: _("Monthly SMS limit reached ({current}/{limit}). Please upgrade your plan or wait for the next billing cycle."),
            
            # Advanced Features
            LimitType.API_CALLS: _("API call limit reached ({current}/{limit}). Please upgrade your plan or wait for the next billing cycle."),
            LimitType.REPORTS_PER_MONTH: _("Monthly report limit reached ({current}/{limit}). Please upgrade your plan or wait for the next billing cycle."),
            LimitType.PRICING_RULES: _("Pricing rule limit reached ({current}/{limit}). Please upgrade your plan to add more rules."),
            LimitType.JOURNAL_ENTRIES: _("Monthly journal entry limit reached ({current}/{limit}). Please upgrade your plan or wait for the next billing cycle."),
            LimitType.LOYALTY_TIERS: _("Loyalty tier limit reached ({current}/{limit}). Please upgrade your plan to add more tiers."),
            
            # System
            LimitType.STORAGE: _("Storage limit reached ({current}GB/{limit}GB). Please upgrade your plan for more storage."),
            LimitType.BACKUP_RETENTION: _("Backup retention limit reached. Please upgrade your plan for longer retention."),
            LimitType.CONCURRENT_SESSIONS: _("Concurrent session limit reached ({current}/{limit}). Please upgrade your plan for more sessions."),
            LimitType.DOCUMENTS: _("Document limit reached ({current}/{limit}). Please upgrade your plan to upload more documents."),
            LimitType.WEBHOOKS: _("Webhook limit reached ({current}/{limit}). Please upgrade your plan to add more webhooks."),
        }
        
        message = messages.get(limit_type, _("Resource limit reached ({current}/{limit}). Please upgrade your plan."))
        return str(message).format(current=current, limit=limit)
    
    def _get_warning_message(self, limit_type: LimitType, current: int, limit: int) -> str:
        """Get a user-friendly warning message."""
        remaining = limit - current
        return str(_("You're using {percent}% of your {resource} limit. {remaining} remaining.")).format(
            percent=int(current / limit * 100),
            resource=limit_type.value,
            remaining=remaining,
        )
    
    def check_feature(self, feature_name: str) -> bool:
        """
        Check if a feature is enabled for this tenant's subscription.
        
        Args:
            feature_name: Name of the feature (e.g., 'multi_branch', 'api_access')
            
        Returns:
            True if feature is enabled, False otherwise
        """
        if not self.subscription:
            return False
        
        feature_mapping = {
            "multi_branch": self.subscription.has_multi_branch_enabled,
            "advanced_reporting": self.subscription.has_advanced_reporting_enabled,
            "api_access": self.subscription.has_api_access_enabled,
            "custom_branding": self.subscription.has_custom_branding_enabled,
            "priority_support": self.subscription.has_priority_support_enabled,
            "export_import": self.subscription.has_export_import_enabled,
            "email_notifications": self.subscription.has_email_notifications_enabled,
            "sms_notifications": self.subscription.has_sms_notifications_enabled,
        }
        
        check_func = feature_mapping.get(feature_name)
        if check_func:
            return check_func()
        
        # Check custom features
        return self.subscription.get_custom_feature(feature_name, False)
    
    def get_all_limits_status(self) -> Dict[str, LimitCheckResult]:
        """
        Get the status of all limits for the tenant.
        
        Returns:
            Dictionary mapping limit type names to their check results
        """
        results = {}
        for limit_type in LimitType:
            if limit_type != LimitType.CUSTOM:
                results[limit_type.value] = self.check_limit(limit_type, increment=0)
        return results
    
    def get_subscription_summary(self) -> Dict[str, Any]:
        """
        Get a complete subscription summary for the tenant.
        
        Returns:
            Dictionary with subscription details, limits, and usage
        """
        if not self.subscription:
            return {
                "has_subscription": False,
                "message": _("No active subscription"),
            }
        
        stats = self.get_usage_stats()
        limits_status = self.get_all_limits_status()
        
        return {
            "has_subscription": True,
            "plan_name": self.subscription.plan.name,
            "plan_price": str(self.subscription.plan.price),
            "plan_price_irr": str(self.subscription.plan.price_irr),
            "billing_cycle": self.subscription.plan.billing_cycle,
            "status": self.subscription.status,
            "is_free": self.subscription.plan.is_free,
            "trial_ends": self.subscription.trial_end.isoformat() if self.subscription.trial_end else None,
            "next_billing": self.subscription.next_billing_date.isoformat() if self.subscription.next_billing_date else None,
            "usage": stats.to_dict(),
            "limits_status": {k: v.to_dict() for k, v in limits_status.items()},
            "features": {
                "multi_branch": self.check_feature("multi_branch"),
                "advanced_reporting": self.check_feature("advanced_reporting"),
                "api_access": self.check_feature("api_access"),
                "custom_branding": self.check_feature("custom_branding"),
                "priority_support": self.check_feature("priority_support"),
                "export_import": self.check_feature("export_import"),
                "email_notifications": self.check_feature("email_notifications"),
                "sms_notifications": self.check_feature("sms_notifications"),
            },
        }
    
    @classmethod
    def reset_monthly_usage_for_all(cls):
        """
        Reset monthly usage counters for all tenants.
        
        This should be called by a scheduled task at the start of each billing cycle.
        """
        from apps.core.models import TenantSubscription
        
        now = timezone.now()
        
        # Find subscriptions that need reset (usage_reset_date is in previous month)
        subscriptions = TenantSubscription.objects.filter(
            status__in=[TenantSubscription.STATUS_ACTIVE, TenantSubscription.STATUS_TRIAL]
        )
        
        for subscription in subscriptions:
            if subscription.usage_reset_date:
                # Check if we're in a new month
                if subscription.usage_reset_date.month != now.month or subscription.usage_reset_date.year != now.year:
                    subscription.reset_monthly_usage()
            else:
                # First time - set reset date
                subscription.reset_monthly_usage()
        
        logger.info(f"Reset monthly usage for {subscriptions.count()} subscriptions")


class SubscriptionLimitExceeded(Exception):
    """Exception raised when a subscription limit is exceeded."""
    
    def __init__(self, result: LimitCheckResult):
        self.result = result
        super().__init__(result.message)


class FeatureNotEnabled(Exception):
    """Exception raised when a feature is not enabled for the subscription."""
    
    def __init__(self, feature_name: str, message: str = None):
        self.feature_name = feature_name
        self.message = message or f"Feature '{feature_name}' is not enabled for your subscription plan."
        super().__init__(self.message)


# ===== Utility Functions =====

def get_enforcement_service(request: HttpRequest) -> Optional[SubscriptionEnforcementService]:
    """
    Get the enforcement service for the current request.
    
    Args:
        request: The HTTP request
        
    Returns:
        SubscriptionEnforcementService or None if no tenant
    """
    tenant = getattr(request, "tenant", None)
    if not tenant:
        return None
    return SubscriptionEnforcementService(tenant)


def check_subscription_limit(tenant: "Tenant", limit_type: LimitType, increment: int = 1) -> LimitCheckResult:
    """
    Convenience function to check a subscription limit.
    
    Args:
        tenant: The tenant to check
        limit_type: The type of limit to check
        increment: Number of resources being added
        
    Returns:
        LimitCheckResult
    """
    service = SubscriptionEnforcementService(tenant)
    return service.check_limit(limit_type, increment)


def check_subscription_feature(tenant: "Tenant", feature_name: str) -> bool:
    """
    Convenience function to check if a feature is enabled.
    
    Args:
        tenant: The tenant to check
        feature_name: Name of the feature
        
    Returns:
        True if feature is enabled
    """
    service = SubscriptionEnforcementService(tenant)
    return service.check_feature(feature_name)
