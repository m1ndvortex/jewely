"""
Fixed Asset Management Views

Comprehensive views for managing fixed assets, depreciation, and disposals.
Production-ready implementation with proper validation and error handling.
"""

import logging
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from apps.core.decorators import tenant_access_required

from .fixed_asset_models import AssetDisposal, DepreciationSchedule, FixedAsset
from .models import JewelryEntity
from .services import AccountingService

logger = logging.getLogger(__name__)


@login_required
@tenant_access_required
def fixed_asset_list(request):
    """
    List all fixed assets for the tenant with filtering and pagination.
    """
    try:
        # Check if accounting is set up
        jewelry_entity = get_object_or_404(JewelryEntity, tenant=request.user.tenant)
        
        # Get all assets for tenant
        assets = FixedAsset.objects.filter(tenant=request.user.tenant).select_related('tenant')
        
        # Apply filters
        status_filter = request.GET.get('status')
        category_filter = request.GET.get('category')
        search = request.GET.get('search')
        
        if status_filter:
            assets = assets.filter(status=status_filter)
        
        if category_filter:
            assets = assets.filter(category=category_filter)
        
        if search:
            assets = assets.filter(
                Q(asset_name__icontains=search) |
                Q(asset_number__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Calculate summary statistics
        total_acquisition_cost = assets.aggregate(
            total=Sum('acquisition_cost')
        )['total'] or Decimal('0.00')
        
        total_accumulated_depreciation = assets.aggregate(
            total=Sum('accumulated_depreciation')
        )['total'] or Decimal('0.00')
        
        net_book_value = total_acquisition_cost - total_accumulated_depreciation
        
        # Pagination
        paginator = Paginator(assets.order_by('-acquisition_date'), 25)
        page = request.GET.get('page')
        
        try:
            assets_page = paginator.page(page)
        except PageNotAnInteger:
            assets_page = paginator.page(1)
        except EmptyPage:
            assets_page = paginator.page(paginator.num_pages)
        
        context = {
            'assets': assets_page,
            'total_acquisition_cost': total_acquisition_cost,
            'total_accumulated_depreciation': total_accumulated_depreciation,
            'net_book_value': net_book_value,
            'status_choices': FixedAsset.STATUS_CHOICES,
            'category_choices': FixedAsset.CATEGORY_CHOICES,
            'current_status': status_filter,
            'current_category': category_filter,
            'search_query': search,
        }
        
        return render(request, 'accounting/fixed_assets/list.html', context)
        
    except JewelryEntity.DoesNotExist:
        messages.warning(request, "Please initialize the accounting system first.")
        return redirect('accounting:dashboard')
    except Exception as e:
        logger.error(f"Error loading fixed assets: {str(e)}")
        messages.error(request, f"Error loading fixed assets: {str(e)}")
        return redirect('accounting:dashboard')


@login_required
@tenant_access_required
def fixed_asset_detail(request, asset_id):
    """
    Display detailed information about a fixed asset.
    """
    try:
        asset = get_object_or_404(
            FixedAsset,
            id=asset_id,
            tenant=request.user.tenant
        )
        
        # Get depreciation schedule
        depreciation_schedules = DepreciationSchedule.objects.filter(
            fixed_asset=asset
        ).order_by('period_end_date')
        
        # Get disposal information if disposed
        disposal = None
        if asset.status == 'DISPOSED':
            try:
                disposal = AssetDisposal.objects.get(fixed_asset=asset)
            except AssetDisposal.DoesNotExist:
                pass
        
        context = {
            'asset': asset,
            'depreciation_schedules': depreciation_schedules,
            'disposal': disposal,
        }
        
        return render(request, 'accounting/fixed_assets/detail.html', context)
        
    except Exception as e:
        logger.error(f"Error loading asset detail: {str(e)}")
        messages.error(request, f"Error loading asset: {str(e)}")
        return redirect('accounting:fixed_asset_list')


@login_required
@tenant_access_required
def fixed_asset_create(request):
    """
    Create a new fixed asset.
    """
    try:
        # Check if accounting is set up
        jewelry_entity = get_object_or_404(JewelryEntity, tenant=request.user.tenant)
        
        if request.method == 'POST':
            with transaction.atomic():
                # Extract form data
                asset_name = request.POST.get('asset_name')
                asset_number = request.POST.get('asset_number')
                category = request.POST.get('category')
                description = request.POST.get('description', '')
                acquisition_date = request.POST.get('acquisition_date')
                acquisition_cost = Decimal(request.POST.get('acquisition_cost'))
                salvage_value = Decimal(request.POST.get('salvage_value', '0.00'))
                useful_life_years = int(request.POST.get('useful_life_years'))
                depreciation_method = request.POST.get('depreciation_method')
                
                # Validate
                if acquisition_cost <= 0:
                    raise ValueError("Acquisition cost must be greater than zero")
                
                if useful_life_years <= 0:
                    raise ValueError("Useful life must be greater than zero")
                
                if salvage_value < 0:
                    raise ValueError("Salvage value cannot be negative")
                
                if salvage_value >= acquisition_cost:
                    raise ValueError("Salvage value must be less than acquisition cost")
                
                # Create asset
                asset = FixedAsset.objects.create(
                    tenant=request.user.tenant,
                    asset_name=asset_name,
                    asset_number=asset_number,
                    category=category,
                    description=description,
                    acquisition_date=acquisition_date,
                    acquisition_cost=acquisition_cost,
                    salvage_value=salvage_value,
                    useful_life_years=useful_life_years,
                    depreciation_method=depreciation_method,
                    status='ACTIVE'
                )
                
                # Generate depreciation schedule
                asset.generate_depreciation_schedule()
                
                messages.success(request, f"Fixed asset '{asset_name}' created successfully.")
                return redirect('accounting:fixed_asset_detail', asset_id=asset.id)
                
        context = {
            'category_choices': FixedAsset.CATEGORY_CHOICES,
            'depreciation_method_choices': FixedAsset.DEPRECIATION_METHOD_CHOICES,
            'today': date.today().isoformat(),
        }
        
        return render(request, 'accounting/fixed_assets/form.html', context)
        
    except JewelryEntity.DoesNotExist:
        messages.warning(request, "Please initialize the accounting system first.")
        return redirect('accounting:dashboard')
    except ValueError as e:
        messages.error(request, str(e))
        return render(request, 'accounting/fixed_assets/form.html', {
            'category_choices': FixedAsset.CATEGORY_CHOICES,
            'depreciation_method_choices': FixedAsset.DEPRECIATION_METHOD_CHOICES,
        })
    except Exception as e:
        logger.error(f"Error creating fixed asset: {str(e)}")
        messages.error(request, f"Error creating asset: {str(e)}")
        return redirect('accounting:fixed_asset_list')


@login_required
@tenant_access_required
def fixed_asset_dispose(request, asset_id):
    """
    Dispose of a fixed asset.
    """
    try:
        asset = get_object_or_404(
            FixedAsset,
            id=asset_id,
            tenant=request.user.tenant
        )
        
        if asset.status == 'DISPOSED':
            messages.warning(request, "This asset has already been disposed.")
            return redirect('accounting:fixed_asset_detail', asset_id=asset.id)
        
        if request.method == 'POST':
            with transaction.atomic():
                disposal_date = request.POST.get('disposal_date')
                disposal_method = request.POST.get('disposal_method')
                disposal_proceeds = Decimal(request.POST.get('disposal_proceeds', '0.00'))
                notes = request.POST.get('notes', '')
                
                # Create disposal record
                disposal = AssetDisposal.objects.create(
                    tenant=request.user.tenant,
                    fixed_asset=asset,
                    disposal_date=disposal_date,
                    disposal_method=disposal_method,
                    disposal_proceeds=disposal_proceeds,
                    book_value_at_disposal=asset.current_book_value,
                    gain_loss_on_disposal=disposal_proceeds - asset.current_book_value,
                    notes=notes
                )
                
                # Update asset status
                asset.status = 'DISPOSED'
                asset.disposal_date = disposal_date
                asset.save()
                
                messages.success(request, f"Asset '{asset.asset_name}' disposed successfully.")
                return redirect('accounting:fixed_asset_detail', asset_id=asset.id)
        
        context = {
            'asset': asset,
            'today': date.today().isoformat(),
        }
        
        return render(request, 'accounting/fixed_assets/disposal_form.html', context)
        
    except Exception as e:
        logger.error(f"Error disposing asset: {str(e)}")
        messages.error(request, f"Error disposing asset: {str(e)}")
        return redirect('accounting:fixed_asset_detail', asset_id=asset_id)


@login_required
@tenant_access_required
def depreciation_schedule(request):
    """
    Display depreciation schedule for all assets.
    """
    try:
        # Check if accounting is set up
        jewelry_entity = get_object_or_404(JewelryEntity, tenant=request.user.tenant)
        
        # Get all active assets
        assets = FixedAsset.objects.filter(
            tenant=request.user.tenant,
            status='ACTIVE'
        ).prefetch_related('depreciation_schedules')
        
        # Get all depreciation schedules
        schedules = DepreciationSchedule.objects.filter(
            fixed_asset__tenant=request.user.tenant
        ).select_related('fixed_asset').order_by('period_end_date', 'fixed_asset__asset_name')
        
        # Calculate totals
        total_depreciation = schedules.aggregate(
            total=Sum('depreciation_amount')
        )['total'] or Decimal('0.00')
        
        total_accumulated = schedules.aggregate(
            total=Sum('accumulated_depreciation')
        )['total'] or Decimal('0.00')
        
        context = {
            'assets': assets,
            'schedules': schedules,
            'total_depreciation': total_depreciation,
            'total_accumulated': total_accumulated,
        }
        
        return render(request, 'accounting/reports/depreciation_schedule.html', context)
        
    except JewelryEntity.DoesNotExist:
        messages.warning(request, "Please initialize the accounting system first.")
        return redirect('accounting:dashboard')
    except Exception as e:
        logger.error(f"Error loading depreciation schedule: {str(e)}")
        messages.error(request, f"Error loading depreciation schedule: {str(e)}")
        return redirect('accounting:dashboard')
