"""
Pricing views for dynamic pricing management.

Implements Requirement 17: Gold Rate and Dynamic Pricing
- Price calculation interface
- Automatic price recalculation triggers
- Pricing tier display
- Manager approval for price overrides
"""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from apps.core.decorators import tenant_required
from apps.inventory.models import InventoryItem
from apps.pricing.models import (
    GoldRate,
    PriceAlert,
    PriceChangeLog,
    PriceOverrideRequest,
    PricingRule,
)
from apps.pricing.services import (
    PriceOverrideService,
    PriceRecalculationService,
    PricingCalculationEngine,
)


@login_required
@tenant_required
def pricing_dashboard(request):
    """
    Pricing dashboard showing current rates, rules, and recent changes.
    """
    tenant = request.user.tenant

    # Get latest gold rate
    latest_rate = GoldRate.get_latest_rate()

    # Get active pricing rules
    pricing_rules = PricingRule.objects.filter(tenant=tenant, is_active=True).order_by(
        "-priority", "karat", "customer_tier"
    )[:10]

    # Get recent price changes
    recent_changes = PriceChangeLog.objects.filter(tenant=tenant).order_by("-changed_at")[:10]

    # Get pending override requests
    pending_overrides = PriceOverrideRequest.objects.filter(
        tenant=tenant, status=PriceOverrideRequest.PENDING
    ).order_by("-requested_at")[:5]

    # Get active alerts
    active_alerts = PriceAlert.objects.filter(tenant=tenant, is_active=True).order_by(
        "-created_at"
    )[:5]

    context = {
        "latest_rate": latest_rate,
        "pricing_rules": pricing_rules,
        "recent_changes": recent_changes,
        "pending_overrides": pending_overrides,
        "active_alerts": active_alerts,
    }

    return render(request, "pricing/dashboard.html", context)


@login_required
@tenant_required
def calculate_price(request):
    """
    Calculate price for given parameters.
    """
    tenant = request.user.tenant

    if request.method == "POST":
        try:
            # Get parameters from form
            karat = int(request.POST.get("karat"))
            weight_grams = Decimal(request.POST.get("weight_grams"))
            product_type = request.POST.get("product_type") or None
            craftsmanship_level = request.POST.get("craftsmanship_level") or None
            customer_tier = request.POST.get("customer_tier", PricingRule.RETAIL)
            stone_value = Decimal(request.POST.get("stone_value", "0.00"))

            # Calculate price
            engine = PricingCalculationEngine(tenant)
            price_breakdown = engine.calculate_price(
                karat=karat,
                weight_grams=weight_grams,
                product_type=product_type,
                craftsmanship_level=craftsmanship_level,
                customer_tier=customer_tier,
                stone_value=stone_value,
            )

            # Get tiered prices
            tiered_prices = engine.get_tiered_prices(
                karat=karat,
                weight_grams=weight_grams,
                product_type=product_type,
                craftsmanship_level=craftsmanship_level,
                stone_value=stone_value,
            )

            context = {
                "price_breakdown": price_breakdown,
                "tiered_prices": tiered_prices,
                "karat": karat,
                "weight_grams": weight_grams,
                "product_type": product_type,
                "craftsmanship_level": craftsmanship_level,
                "customer_tier": customer_tier,
                "stone_value": stone_value,
            }

            return render(request, "pricing/price_calculation_result.html", context)

        except (ValueError, KeyError) as e:
            messages.error(request, f"Error calculating price: {str(e)}")

    # GET request - show form
    pricing_rules = PricingRule.objects.filter(tenant=tenant, is_active=True)
    latest_rate = GoldRate.get_latest_rate()

    context = {
        "pricing_rules": pricing_rules,
        "latest_rate": latest_rate,
        "product_types": PricingRule.PRODUCT_TYPE_CHOICES,
        "craftsmanship_levels": PricingRule.CRAFTSMANSHIP_CHOICES,
        "customer_tiers": PricingRule.CUSTOMER_TIER_CHOICES,
    }

    return render(request, "pricing/calculate_price.html", context)


@login_required
@tenant_required
@require_POST
def recalculate_all_prices(request):
    """
    Trigger automatic recalculation of all inventory prices.
    """
    tenant = request.user.tenant

    # Check if user has permission (manager or owner)
    if request.user.role not in ["TENANT_OWNER", "TENANT_MANAGER"]:
        messages.error(request, "You do not have permission to recalculate prices.")
        return redirect("pricing:dashboard")

    try:
        customer_tier = request.POST.get("customer_tier", PricingRule.RETAIL)

        # Recalculate prices
        service = PriceRecalculationService(tenant)
        stats = service.recalculate_all_prices(customer_tier=customer_tier)

        messages.success(
            request,
            f"Price recalculation complete. "
            f"Updated: {stats['updated_items']}, "
            f"Skipped: {stats['skipped_items']}, "
            f"Failed: {stats['failed_items']}",
        )

    except Exception as e:
        messages.error(request, f"Error recalculating prices: {str(e)}")

    return redirect("pricing:dashboard")


@login_required
@tenant_required
@require_POST
def recalculate_by_karat(request):
    """
    Trigger recalculation for items of a specific karat.
    """
    tenant = request.user.tenant

    # Check if user has permission
    if request.user.role not in ["TENANT_OWNER", "TENANT_MANAGER"]:
        messages.error(request, "You do not have permission to recalculate prices.")
        return redirect("pricing:dashboard")

    try:
        karat = int(request.POST.get("karat"))
        customer_tier = request.POST.get("customer_tier", PricingRule.RETAIL)

        # Recalculate prices
        service = PriceRecalculationService(tenant)
        stats = service.recalculate_by_karat(karat=karat, customer_tier=customer_tier)

        messages.success(
            request,
            f"Price recalculation for {karat}K items complete. "
            f"Updated: {stats['updated_items']}, "
            f"Skipped: {stats['skipped_items']}, "
            f"Failed: {stats['failed_items']}",
        )

    except (ValueError, KeyError) as e:
        messages.error(request, f"Error recalculating prices: {str(e)}")

    return redirect("pricing:dashboard")


@login_required
@tenant_required
def price_override_list(request):
    """
    List all price override requests.
    """
    tenant = request.user.tenant

    # Filter by status
    status_filter = request.GET.get("status", "")
    overrides = PriceOverrideRequest.objects.filter(tenant=tenant)

    if status_filter:
        overrides = overrides.filter(status=status_filter)

    overrides = overrides.order_by("-requested_at")

    # Pagination
    paginator = Paginator(overrides, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "status_filter": status_filter,
        "status_choices": PriceOverrideRequest.STATUS_CHOICES,
    }

    return render(request, "pricing/override_list.html", context)


@login_required
@tenant_required
def price_override_detail(request, override_id):
    """
    View details of a price override request.
    """
    tenant = request.user.tenant
    override = get_object_or_404(PriceOverrideRequest, id=override_id, tenant=tenant)

    context = {
        "override": override,
    }

    return render(request, "pricing/override_detail.html", context)


@login_required
@tenant_required
@require_POST
def request_price_override(request):
    """
    Request a manual price override for an inventory item.
    """
    tenant = request.user.tenant

    try:
        item_id = request.POST.get("item_id")
        new_price = Decimal(request.POST.get("new_price"))
        reason = request.POST.get("reason", "")

        # Get inventory item
        item = get_object_or_404(InventoryItem, id=item_id, tenant=tenant)

        # Create override request
        service = PriceOverrideService(tenant)
        override_request = service.request_price_override(
            inventory_item=item,
            new_price=new_price,
            reason=reason,
            requested_by=request.user,
        )

        messages.success(
            request,
            f"Price override request created for {item.name}. " f"Awaiting manager approval.",
        )

        return redirect("pricing:override_detail", override_id=override_request.id)

    except (ValueError, KeyError) as e:
        messages.error(request, f"Error creating override request: {str(e)}")
        return redirect("pricing:dashboard")


@login_required
@tenant_required
@require_POST
def approve_price_override(request, override_id):
    """
    Approve a price override request.
    """
    tenant = request.user.tenant
    override = get_object_or_404(PriceOverrideRequest, id=override_id, tenant=tenant)

    try:
        notes = request.POST.get("notes", "")

        # Approve override
        service = PriceOverrideService(tenant)
        service.approve_override(
            override_request=override,
            approved_by=request.user,
            notes=notes,
        )

        messages.success(
            request,
            f"Price override approved for {override.inventory_item.name}. "
            f"New price: {override.requested_price}",
        )

    except ValueError as e:
        messages.error(request, f"Error approving override: {str(e)}")

    return redirect("pricing:override_detail", override_id=override_id)


@login_required
@tenant_required
@require_POST
def reject_price_override(request, override_id):
    """
    Reject a price override request.
    """
    tenant = request.user.tenant
    override = get_object_or_404(PriceOverrideRequest, id=override_id, tenant=tenant)

    try:
        rejection_reason = request.POST.get("rejection_reason", "")

        if not rejection_reason:
            messages.error(request, "Please provide a reason for rejection.")
            return redirect("pricing:override_detail", override_id=override_id)

        # Reject override
        service = PriceOverrideService(tenant)
        service.reject_override(
            override_request=override,
            rejected_by=request.user,
            rejection_reason=rejection_reason,
        )

        messages.success(
            request,
            f"Price override rejected for {override.inventory_item.name}.",
        )

    except ValueError as e:
        messages.error(request, f"Error rejecting override: {str(e)}")

    return redirect("pricing:override_detail", override_id=override_id)


@login_required
@tenant_required
def price_change_history(request):
    """
    View price change history with filters.
    """
    tenant = request.user.tenant

    # Get filters
    item_id = request.GET.get("item_id")
    search = request.GET.get("search", "")

    # Build query
    changes = PriceChangeLog.objects.filter(tenant=tenant)

    if item_id:
        changes = changes.filter(inventory_item_id=item_id)

    if search:
        changes = changes.filter(
            Q(inventory_item__sku__icontains=search)
            | Q(inventory_item__name__icontains=search)
            | Q(reason__icontains=search)
        )

    changes = changes.order_by("-changed_at")

    # Pagination
    paginator = Paginator(changes, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "search": search,
        "item_id": item_id,
    }

    return render(request, "pricing/change_history.html", context)


@login_required
@tenant_required
def gold_rate_widget(request):
    """
    Live gold rate widget for dashboard display.
    """
    # Get latest rates for different markets
    markets = [
        GoldRate.INTERNATIONAL,
        GoldRate.LOCAL,
        GoldRate.LONDON,
        GoldRate.NEW_YORK,
        GoldRate.DUBAI,
    ]

    rates = {}
    for market in markets:
        rate = GoldRate.get_latest_rate(market=market)
        if rate:
            # Get previous rate for comparison
            previous_rate = GoldRate.objects.filter(
                market=market, currency=rate.currency, timestamp__lt=rate.timestamp
            ).first()

            change_percentage = Decimal("0.00")
            if previous_rate:
                change_percentage = rate.calculate_percentage_change(previous_rate)

            rates[market] = {
                "rate": rate,
                "change_percentage": change_percentage,
                "is_increase": change_percentage > 0,
                "is_decrease": change_percentage < 0,
            }

    context = {
        "rates": rates,
        "markets": GoldRate.MARKET_CHOICES,
    }

    return render(request, "pricing/gold_rate_widget.html", context)


@login_required
@tenant_required
def gold_rate_history(request):
    """
    Gold rate history with charts and trend analysis.
    """
    # Get parameters
    market = request.GET.get("market", GoldRate.INTERNATIONAL)
    days = int(request.GET.get("days", 30))

    # Get historical rates
    rates = GoldRate.get_rate_history(market=market, days=days)

    # Prepare chart data
    chart_data = []
    for rate in rates.reverse():  # Reverse to get chronological order
        chart_data.append(
            {
                "date": rate.timestamp.strftime("%Y-%m-%d %H:%M"),
                "rate_per_gram": float(rate.rate_per_gram),
                "rate_per_tola": float(rate.rate_per_tola),
                "rate_per_ounce": float(rate.rate_per_ounce),
            }
        )

    # Calculate statistics
    if rates:
        latest_rate = rates.first()
        oldest_rate = rates.last()

        total_change = latest_rate.rate_per_gram - oldest_rate.rate_per_gram
        total_change_percentage = (
            (total_change / oldest_rate.rate_per_gram * 100)
            if oldest_rate.rate_per_gram > 0
            else Decimal("0.00")
        )

        # Calculate min/max
        rates_list = list(rates)
        min_rate = min(rates_list, key=lambda r: r.rate_per_gram)
        max_rate = max(rates_list, key=lambda r: r.rate_per_gram)

        stats = {
            "latest_rate": latest_rate,
            "oldest_rate": oldest_rate,
            "total_change": total_change,
            "total_change_percentage": total_change_percentage,
            "min_rate": min_rate,
            "max_rate": max_rate,
            "is_trending_up": total_change > 0,
        }
    else:
        stats = None

    context = {
        "market": market,
        "days": days,
        "rates": rates,
        "chart_data": chart_data,
        "stats": stats,
        "markets": GoldRate.MARKET_CHOICES,
    }

    return render(request, "pricing/gold_rate_history.html", context)


@login_required
@tenant_required
def gold_rate_comparison(request):
    """
    Compare gold rates across different markets.
    """
    # Get latest rates for all markets
    markets = [choice[0] for choice in GoldRate.MARKET_CHOICES]

    comparison_data = []
    base_rate = None

    for market in markets:
        rate = GoldRate.get_latest_rate(market=market)
        if rate:
            # Use first rate as base for comparison
            if base_rate is None:
                base_rate = rate.rate_per_gram

            # Calculate difference from base
            difference = rate.rate_per_gram - base_rate
            difference_percentage = (
                (difference / base_rate * 100) if base_rate > 0 else Decimal("0.00")
            )

            comparison_data.append(
                {
                    "market": market,
                    "market_display": dict(GoldRate.MARKET_CHOICES)[market],
                    "rate": rate,
                    "difference": difference,
                    "difference_percentage": difference_percentage,
                    "is_higher": difference > 0,
                    "is_lower": difference < 0,
                }
            )

    # Sort by rate (highest first)
    comparison_data.sort(key=lambda x: x["rate"].rate_per_gram, reverse=True)

    context = {
        "comparison_data": comparison_data,
        "base_market": comparison_data[0]["market"] if comparison_data else None,
    }

    return render(request, "pricing/gold_rate_comparison.html", context)


@login_required
@tenant_required
@require_http_methods(["GET"])
def api_gold_rates(request):
    """
    API endpoint to get current gold rates for HTMX updates.
    """
    market = request.GET.get("market", GoldRate.INTERNATIONAL)

    rate = GoldRate.get_latest_rate(market=market)
    if not rate:
        return JsonResponse({"success": False, "error": "No rate found"}, status=404)

    # Get previous rate for comparison
    previous_rate = GoldRate.objects.filter(
        market=market, currency=rate.currency, timestamp__lt=rate.timestamp
    ).first()

    change_percentage = Decimal("0.00")
    if previous_rate:
        change_percentage = rate.calculate_percentage_change(previous_rate)

    return JsonResponse(
        {
            "success": True,
            "rate": {
                "rate_per_gram": str(rate.rate_per_gram),
                "rate_per_tola": str(rate.rate_per_tola),
                "rate_per_ounce": str(rate.rate_per_ounce),
                "market": rate.market,
                "currency": rate.currency,
                "timestamp": rate.timestamp.isoformat(),
                "change_percentage": str(change_percentage),
                "is_increase": change_percentage > 0,
                "is_decrease": change_percentage < 0,
            },
        }
    )


@login_required
@tenant_required
@require_http_methods(["GET"])
def api_calculate_item_price(request, item_id):
    """
    API endpoint to calculate price for an inventory item.

    Returns JSON with price breakdown and tiered prices.
    """
    tenant = request.user.tenant

    try:
        # Get inventory item
        item = get_object_or_404(InventoryItem, id=item_id, tenant=tenant)

        # Get parameters
        customer_tier = request.GET.get("customer_tier", PricingRule.RETAIL)
        stone_value = Decimal(request.GET.get("stone_value", "0.00"))

        # Calculate price
        engine = PricingCalculationEngine(tenant)
        price_breakdown = engine.calculate_item_price(
            inventory_item=item,
            customer_tier=customer_tier,
            stone_value=stone_value,
        )

        # Get tiered prices
        tiered_prices = engine.get_tiered_prices(
            karat=item.karat,
            weight_grams=item.weight_grams,
            product_type=item.category.name if item.category else None,
            craftsmanship_level=item.craftsmanship_level,
            stone_value=stone_value,
        )

        # Convert Decimal to string for JSON serialization
        def decimal_to_str(obj):
            if isinstance(obj, Decimal):
                return str(obj)
            elif isinstance(obj, dict):
                return {k: decimal_to_str(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [decimal_to_str(item) for item in obj]
            return obj

        return JsonResponse(
            {
                "success": True,
                "item": {
                    "id": str(item.id),
                    "sku": item.sku,
                    "name": item.name,
                    "current_price": str(item.selling_price),
                },
                "price_breakdown": decimal_to_str(price_breakdown),
                "tiered_prices": decimal_to_str(tiered_prices),
            }
        )

    except (ValueError, KeyError) as e:
        return JsonResponse({"success": False, "error": str(e)}, status=400)
