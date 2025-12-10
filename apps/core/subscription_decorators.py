"""
Subscription Enforcement Decorators and Mixins.

This module provides decorators for function-based views and mixins for
class-based views to enforce subscription limits and feature access.

Features:
- Function decorators for FBV
- Class-based view mixins for CBV
- API view enforcement
- Graceful error handling with proper HTTP responses
- Support for JSON API responses
"""

import functools
import logging
from typing import Callable, List, Optional, Type, Union

from django.contrib import messages
from django.http import HttpRequest, HttpResponseForbidden, JsonResponse
from django.shortcuts import redirect
from django.utils.translation import gettext_lazy as _

from apps.core.subscription_enforcement import (
    EnforcementResult,
    FeatureNotEnabled,
    LimitCheckResult,
    LimitType,
    SubscriptionEnforcementService,
    SubscriptionLimitExceeded,
)

logger = logging.getLogger(__name__)


# ===== Function-Based View Decorators =====

def enforce_subscription_limit(
    limit_type: Union[LimitType, str],
    increment: int = 1,
    redirect_url: str = None,
    api_response: bool = False,
):
    """
    Decorator to enforce subscription limits on views.
    
    Args:
        limit_type: The type of limit to check (LimitType enum or string)
        increment: Number of resources being added (default 1)
        redirect_url: URL to redirect to if limit exceeded (default: referrer)
        api_response: If True, return JSON response instead of redirect
        
    Usage:
        @enforce_subscription_limit(LimitType.USERS)
        def create_user(request):
            ...
            
        @enforce_subscription_limit("inventory", increment=5)
        def bulk_create_items(request):
            ...
    """
    if isinstance(limit_type, str):
        limit_type = LimitType(limit_type)
    
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            tenant = getattr(request, "tenant", None)
            
            if not tenant:
                logger.warning("No tenant found in request for subscription enforcement")
                if api_response:
                    return JsonResponse(
                        {"error": "No tenant context", "code": "no_tenant"},
                        status=400
                    )
                return HttpResponseForbidden("Tenant context required")
            
            # Check limit
            service = SubscriptionEnforcementService(tenant)
            result = service.check_limit(limit_type, increment)
            
            if result.is_blocked:
                logger.info(
                    f"Subscription limit blocked: tenant={tenant.slug}, "
                    f"limit={limit_type.value}, usage={result.current_usage}/{result.limit}"
                )
                
                if api_response:
                    return JsonResponse(
                        {
                            "error": str(result.message),
                            "code": "subscription_limit_exceeded",
                            "limit_type": limit_type.value,
                            "current_usage": result.current_usage,
                            "limit": result.limit,
                        },
                        status=402  # Payment Required
                    )
                
                messages.error(request, result.message)
                
                if redirect_url:
                    return redirect(redirect_url)
                
                referer = request.META.get("HTTP_REFERER")
                if referer:
                    return redirect(referer)
                
                return redirect("core:tenant_dashboard")
            
            # Add warning message if nearing limit
            if result.result == EnforcementResult.WARNING:
                messages.warning(request, result.message)
            
            # Store result in request for view to access
            request.subscription_limit_result = result
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def require_subscription_feature(
    feature_name: str,
    redirect_url: str = None,
    api_response: bool = False,
):
    """
    Decorator to require a specific subscription feature.
    
    Args:
        feature_name: Name of the required feature
        redirect_url: URL to redirect to if feature not enabled
        api_response: If True, return JSON response instead of redirect
        
    Usage:
        @require_subscription_feature("api_access")
        def api_endpoint(request):
            ...
            
        @require_subscription_feature("advanced_reporting")
        def advanced_report(request):
            ...
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            tenant = getattr(request, "tenant", None)
            
            if not tenant:
                if api_response:
                    return JsonResponse(
                        {"error": "No tenant context", "code": "no_tenant"},
                        status=400
                    )
                return HttpResponseForbidden("Tenant context required")
            
            service = SubscriptionEnforcementService(tenant)
            
            if not service.check_feature(feature_name):
                message = _(
                    f"The '{feature_name}' feature is not available in your current plan. "
                    "Please upgrade to access this feature."
                )
                
                logger.info(
                    f"Feature access denied: tenant={tenant.slug}, feature={feature_name}"
                )
                
                if api_response:
                    return JsonResponse(
                        {
                            "error": str(message),
                            "code": "feature_not_enabled",
                            "feature": feature_name,
                        },
                        status=402
                    )
                
                messages.error(request, message)
                
                if redirect_url:
                    return redirect(redirect_url)
                
                referer = request.META.get("HTTP_REFERER")
                if referer:
                    return redirect(referer)
                
                return redirect("core:tenant_dashboard")
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def require_active_subscription(
    redirect_url: str = None,
    api_response: bool = False,
):
    """
    Decorator to require an active subscription.
    
    Args:
        redirect_url: URL to redirect to if no active subscription
        api_response: If True, return JSON response instead of redirect
        
    Usage:
        @require_active_subscription()
        def premium_feature(request):
            ...
    """
    def decorator(view_func: Callable) -> Callable:
        @functools.wraps(view_func)
        def wrapper(request: HttpRequest, *args, **kwargs):
            tenant = getattr(request, "tenant", None)
            
            if not tenant:
                if api_response:
                    return JsonResponse(
                        {"error": "No tenant context", "code": "no_tenant"},
                        status=400
                    )
                return HttpResponseForbidden("Tenant context required")
            
            service = SubscriptionEnforcementService(tenant)
            
            if not service.has_active_subscription():
                message = _("An active subscription is required to access this feature.")
                
                if api_response:
                    return JsonResponse(
                        {
                            "error": str(message),
                            "code": "no_active_subscription",
                        },
                        status=402
                    )
                
                messages.error(request, message)
                
                if redirect_url:
                    return redirect(redirect_url)
                
                return redirect("core:tenant_dashboard")
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


# ===== Class-Based View Mixins =====

class SubscriptionEnforcementMixin:
    """
    Mixin for class-based views to enforce subscription limits.
    
    Attributes:
        subscription_limit_type: LimitType to check (required)
        subscription_limit_increment: Number of resources being added (default 1)
        subscription_redirect_url: URL to redirect on limit exceeded
        subscription_api_response: Return JSON instead of redirect
        
    Usage:
        class CreateUserView(SubscriptionEnforcementMixin, CreateView):
            subscription_limit_type = LimitType.USERS
            model = User
            ...
    """
    
    subscription_limit_type: Optional[LimitType] = None
    subscription_limit_increment: int = 1
    subscription_redirect_url: Optional[str] = None
    subscription_api_response: bool = False
    
    def dispatch(self, request, *args, **kwargs):
        """Check subscription limit before processing request."""
        if self.subscription_limit_type:
            tenant = getattr(request, "tenant", None)
            
            if not tenant:
                if self.subscription_api_response:
                    return JsonResponse(
                        {"error": "No tenant context", "code": "no_tenant"},
                        status=400
                    )
                return HttpResponseForbidden("Tenant context required")
            
            service = SubscriptionEnforcementService(tenant)
            result = service.check_limit(
                self.subscription_limit_type,
                self.subscription_limit_increment
            )
            
            if result.is_blocked:
                return self._handle_limit_exceeded(request, result)
            
            if result.result == EnforcementResult.WARNING:
                messages.warning(request, result.message)
            
            request.subscription_limit_result = result
        
        return super().dispatch(request, *args, **kwargs)
    
    def _handle_limit_exceeded(self, request, result: LimitCheckResult):
        """Handle limit exceeded response."""
        if self.subscription_api_response:
            return JsonResponse(
                {
                    "error": str(result.message),
                    "code": "subscription_limit_exceeded",
                    "limit_type": result.limit_type.value,
                    "current_usage": result.current_usage,
                    "limit": result.limit,
                },
                status=402
            )
        
        messages.error(request, result.message)
        
        if self.subscription_redirect_url:
            return redirect(self.subscription_redirect_url)
        
        referer = request.META.get("HTTP_REFERER")
        if referer:
            return redirect(referer)
        
        return redirect("core:tenant_dashboard")


class SubscriptionFeatureMixin:
    """
    Mixin for class-based views to require subscription features.
    
    Attributes:
        required_subscription_features: List of required feature names
        subscription_redirect_url: URL to redirect if feature not enabled
        subscription_api_response: Return JSON instead of redirect
        
    Usage:
        class AdvancedReportView(SubscriptionFeatureMixin, TemplateView):
            required_subscription_features = ["advanced_reporting"]
            template_name = "reports/advanced.html"
    """
    
    required_subscription_features: List[str] = []
    subscription_redirect_url: Optional[str] = None
    subscription_api_response: bool = False
    
    def dispatch(self, request, *args, **kwargs):
        """Check subscription features before processing request."""
        if self.required_subscription_features:
            tenant = getattr(request, "tenant", None)
            
            if not tenant:
                if self.subscription_api_response:
                    return JsonResponse(
                        {"error": "No tenant context", "code": "no_tenant"},
                        status=400
                    )
                return HttpResponseForbidden("Tenant context required")
            
            service = SubscriptionEnforcementService(tenant)
            
            for feature in self.required_subscription_features:
                if not service.check_feature(feature):
                    return self._handle_feature_not_enabled(request, feature)
        
        return super().dispatch(request, *args, **kwargs)
    
    def _handle_feature_not_enabled(self, request, feature_name: str):
        """Handle feature not enabled response."""
        message = _(
            f"The '{feature_name}' feature is not available in your current plan. "
            "Please upgrade to access this feature."
        )
        
        if self.subscription_api_response:
            return JsonResponse(
                {
                    "error": str(message),
                    "code": "feature_not_enabled",
                    "feature": feature_name,
                },
                status=402
            )
        
        messages.error(request, message)
        
        if self.subscription_redirect_url:
            return redirect(self.subscription_redirect_url)
        
        referer = request.META.get("HTTP_REFERER")
        if referer:
            return redirect(referer)
        
        return redirect("core:tenant_dashboard")


class ActiveSubscriptionRequiredMixin:
    """
    Mixin for class-based views to require an active subscription.
    
    Attributes:
        subscription_redirect_url: URL to redirect if no active subscription
        subscription_api_response: Return JSON instead of redirect
        
    Usage:
        class PremiumView(ActiveSubscriptionRequiredMixin, TemplateView):
            template_name = "premium/feature.html"
    """
    
    subscription_redirect_url: Optional[str] = None
    subscription_api_response: bool = False
    
    def dispatch(self, request, *args, **kwargs):
        """Check for active subscription before processing request."""
        tenant = getattr(request, "tenant", None)
        
        if not tenant:
            if self.subscription_api_response:
                return JsonResponse(
                    {"error": "No tenant context", "code": "no_tenant"},
                    status=400
                )
            return HttpResponseForbidden("Tenant context required")
        
        service = SubscriptionEnforcementService(tenant)
        
        if not service.has_active_subscription():
            message = _("An active subscription is required to access this feature.")
            
            if self.subscription_api_response:
                return JsonResponse(
                    {
                        "error": str(message),
                        "code": "no_active_subscription",
                    },
                    status=402
                )
            
            messages.error(request, message)
            
            if self.subscription_redirect_url:
                return redirect(self.subscription_redirect_url)
            
            return redirect("core:tenant_dashboard")
        
        return super().dispatch(request, *args, **kwargs)


# ===== API View Decorator =====

def subscription_api_limit(limit_type: Union[LimitType, str], increment: int = 1):
    """
    Decorator specifically for API views to enforce subscription limits.
    
    Always returns JSON responses with appropriate status codes.
    
    Args:
        limit_type: The type of limit to check
        increment: Number of resources being added
        
    Usage:
        @api_view(['POST'])
        @subscription_api_limit(LimitType.INVENTORY)
        def create_item(request):
            ...
    """
    return enforce_subscription_limit(
        limit_type,
        increment=increment,
        api_response=True,
    )


def subscription_api_feature(feature_name: str):
    """
    Decorator specifically for API views to require subscription features.
    
    Always returns JSON responses with appropriate status codes.
    
    Args:
        feature_name: Name of the required feature
        
    Usage:
        @api_view(['GET'])
        @subscription_api_feature("api_access")
        def api_endpoint(request):
            ...
    """
    return require_subscription_feature(
        feature_name,
        api_response=True,
    )
