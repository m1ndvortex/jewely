"""
Views for documentation and knowledge base management.

This module provides views for:
- Browsing documentation with categories
- Searching documentation
- Creating and editing documentation pages (markdown support)
- Version tracking
- Browsing and managing runbooks
- Creating admin notes

Per Requirement 34 - Knowledge Base and Documentation
"""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from .decorators import platform_admin_required
from .documentation_forms import (
    AdminNoteForm,
    DocumentationPageForm,
    DocumentationSearchForm,
    RunbookForm,
    RunbookSearchForm,
)
from .documentation_models import AdminNote, DocumentationPage, Runbook, RunbookExecution

# Documentation Browser Views


@login_required
@platform_admin_required
def documentation_home(request):
    """
    Documentation home page with category overview.

    Requirement 34.1: Provide documentation of platform architecture and components.
    Requirement 34.2: Provide step-by-step guides for common admin tasks.
    """
    # Get category counts
    categories = []
    for category_code, category_name in DocumentationPage.CATEGORY_CHOICES:
        count = DocumentationPage.objects.filter(
            category=category_code, status=DocumentationPage.PUBLISHED
        ).count()
        categories.append({"code": category_code, "name": category_name, "count": count})

    # Get recently updated pages
    recent_pages = DocumentationPage.objects.filter(status=DocumentationPage.PUBLISHED).order_by(
        "-updated_at"
    )[:10]

    # Get popular pages
    popular_pages = DocumentationPage.objects.filter(status=DocumentationPage.PUBLISHED).order_by(
        "-view_count"
    )[:10]

    context = {
        "categories": categories,
        "recent_pages": recent_pages,
        "popular_pages": popular_pages,
    }

    return render(request, "core/documentation/home.html", context)


@login_required
@platform_admin_required
def documentation_list(request):
    """
    List documentation pages with search and filtering.

    Requirement 34: Knowledge Base and Documentation - browser with categories.
    """
    form = DocumentationSearchForm(request.GET)
    pages = DocumentationPage.objects.all()

    # Apply filters
    if form.is_valid():
        query = form.cleaned_data.get("query")
        category = form.cleaned_data.get("category")
        status = form.cleaned_data.get("status")

        if query:
            # Use PostgreSQL full-text search
            search_vector = SearchVector("title", weight="A") + SearchVector("content", weight="B")
            search_query = SearchQuery(query)
            pages = (
                pages.annotate(search=search_vector, rank=SearchRank(search_vector, search_query))
                .filter(search=search_query)
                .order_by("-rank")
            )
        else:
            pages = pages.order_by("category", "order", "title")

        if category:
            pages = pages.filter(category=category)

        if status:
            pages = pages.filter(status=status)
        else:
            # Default to published pages
            pages = pages.filter(status=DocumentationPage.PUBLISHED)

    # Pagination
    paginator = Paginator(pages, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {"form": form, "page_obj": page_obj}

    return render(request, "core/documentation/list.html", context)


@login_required
@platform_admin_required
def documentation_category(request, category):
    """
    List documentation pages in a specific category.

    Requirement 34: Knowledge Base and Documentation - browser with categories.
    """
    # Validate category
    valid_categories = dict(DocumentationPage.CATEGORY_CHOICES)
    if category not in valid_categories:
        messages.error(request, "Invalid category")
        return redirect("core:documentation_home")

    # Get pages in category
    pages = DocumentationPage.objects.filter(
        category=category, status=DocumentationPage.PUBLISHED
    ).order_by("order", "title")

    # Build hierarchy
    root_pages = pages.filter(parent__isnull=True)

    context = {
        "category": category,
        "category_name": valid_categories[category],
        "root_pages": root_pages,
    }

    return render(request, "core/documentation/category.html", context)


@login_required
@platform_admin_required
def documentation_detail(request, slug):
    """
    View a documentation page with version history.

    Requirement 34: Knowledge Base and Documentation - version tracking.
    """
    page = get_object_or_404(DocumentationPage, slug=slug)

    # Increment view count
    page.increment_view_count()

    # Get breadcrumbs
    breadcrumbs = page.get_breadcrumbs()

    # Get child pages
    children = page.children.filter(status=DocumentationPage.PUBLISHED).order_by("order", "title")

    # Get related admin notes
    notes = page.admin_notes.all().order_by("-is_pinned", "-created_at")

    context = {
        "page": page,
        "breadcrumbs": breadcrumbs,
        "children": children,
        "notes": notes,
    }

    return render(request, "core/documentation/detail.html", context)


@login_required
@platform_admin_required
def documentation_create(request):
    """
    Create a new documentation page.

    Requirement 34.2: Provide step-by-step guides for common admin tasks.
    """
    if request.method == "POST":
        form = DocumentationPageForm(request.POST)
        if form.is_valid():
            page = form.save(commit=False)
            page.created_by = request.user
            page.updated_by = request.user
            page.save()

            messages.success(request, f"Documentation page '{page.title}' created successfully")
            return redirect("core:documentation:detail", slug=page.slug)
    else:
        form = DocumentationPageForm()

    context = {"form": form, "action": "Create"}

    return render(request, "core/documentation/form.html", context)


@login_required
@platform_admin_required
def documentation_edit(request, slug):
    """
    Edit a documentation page with version tracking.

    Requirement 34: Knowledge Base and Documentation - version tracking.
    """
    page = get_object_or_404(DocumentationPage, slug=slug)

    if request.method == "POST":
        form = DocumentationPageForm(request.POST, instance=page)
        if form.is_valid():
            page = form.save(commit=False)
            page.updated_by = request.user
            page.save()

            messages.success(request, f"Documentation page '{page.title}' updated successfully")
            return redirect("core:documentation:detail", slug=page.slug)
    else:
        # Convert tags list to comma-separated string for form
        initial_data = {}
        if page.tags:
            initial_data["tags"] = ", ".join(page.tags)
        form = DocumentationPageForm(instance=page, initial=initial_data)

    context = {"form": form, "page": page, "action": "Edit"}

    return render(request, "core/documentation/form.html", context)


@login_required
@platform_admin_required
@require_http_methods(["POST"])
def documentation_publish(request, slug):
    """
    Publish a documentation page.

    Requirement 34: Knowledge Base and Documentation.
    """
    page = get_object_or_404(DocumentationPage, slug=slug)
    page.publish()

    messages.success(request, f"Documentation page '{page.title}' published successfully")
    return redirect("core:documentation:detail", slug=page.slug)


@login_required
@platform_admin_required
@require_http_methods(["POST"])
def documentation_archive(request, slug):
    """
    Archive a documentation page.

    Requirement 34: Knowledge Base and Documentation.
    """
    page = get_object_or_404(DocumentationPage, slug=slug)
    page.archive()

    messages.success(request, f"Documentation page '{page.title}' archived successfully")
    return redirect("core:documentation:list")


# Runbook Views


@login_required
@platform_admin_required
def runbook_list(request):
    """
    List runbooks with search and filtering.

    Requirement 34.5: Provide incident response runbooks with documented procedures.
    Requirement 34.6: Provide maintenance runbooks for routine tasks.
    Requirement 34.7: Provide disaster recovery runbooks with step-by-step procedures.
    """
    form = RunbookSearchForm(request.GET)
    runbooks = Runbook.objects.all()

    # Apply filters
    if form.is_valid():
        query = form.cleaned_data.get("query")
        runbook_type = form.cleaned_data.get("runbook_type")
        priority = form.cleaned_data.get("priority")
        status = form.cleaned_data.get("status")

        if query:
            # Use PostgreSQL full-text search
            search_vector = SearchVector("title", weight="A") + SearchVector(
                "description", weight="B"
            )
            search_query = SearchQuery(query)
            runbooks = (
                runbooks.annotate(
                    search=search_vector, rank=SearchRank(search_vector, search_query)
                )
                .filter(search=search_query)
                .order_by("-rank")
            )
        else:
            runbooks = runbooks.order_by("-priority", "runbook_type", "title")

        if runbook_type:
            runbooks = runbooks.filter(runbook_type=runbook_type)

        if priority:
            runbooks = runbooks.filter(priority=priority)

        if status:
            runbooks = runbooks.filter(status=status)
        else:
            # Default to active runbooks
            runbooks = runbooks.filter(status=Runbook.ACTIVE)

    # Pagination
    paginator = Paginator(runbooks, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {"form": form, "page_obj": page_obj}

    return render(request, "core/documentation/runbook_list.html", context)


@login_required
@platform_admin_required
def runbook_detail(request, slug):
    """
    View a runbook with execution history.

    Requirement 34.8: Track runbook versions and updates.
    """
    runbook = get_object_or_404(Runbook, slug=slug)

    # Get recent executions
    recent_executions = runbook.executions.all().order_by("-started_at")[:10]

    # Get related admin notes
    notes = runbook.admin_notes.all().order_by("-is_pinned", "-created_at")

    # Calculate success rate
    success_rate = runbook.get_success_rate()
    if success_rate is not None:
        success_rate_percent = int(success_rate * 100)
    else:
        success_rate_percent = None

    context = {
        "runbook": runbook,
        "recent_executions": recent_executions,
        "notes": notes,
        "success_rate_percent": success_rate_percent,
    }

    return render(request, "core/documentation/runbook_detail.html", context)


@login_required
@platform_admin_required
def runbook_create(request):
    """
    Create a new runbook.

    Requirement 34.5: Provide incident response runbooks with documented procedures.
    """
    if request.method == "POST":
        form = RunbookForm(request.POST)
        if form.is_valid():
            runbook = form.save(commit=False)
            runbook.created_by = request.user
            runbook.updated_by = request.user
            runbook.save()

            messages.success(request, f"Runbook '{runbook.title}' created successfully")
            return redirect("core:documentation:runbook_detail", slug=runbook.slug)
    else:
        form = RunbookForm()

    context = {"form": form, "action": "Create"}

    return render(request, "core/documentation/runbook_form.html", context)


@login_required
@platform_admin_required
def runbook_edit(request, slug):
    """
    Edit a runbook with version tracking.

    Requirement 34.8: Track runbook versions and updates.
    """
    runbook = get_object_or_404(Runbook, slug=slug)

    if request.method == "POST":
        form = RunbookForm(request.POST, instance=runbook)
        if form.is_valid():
            runbook = form.save(commit=False)
            runbook.updated_by = request.user
            runbook.save()

            messages.success(request, f"Runbook '{runbook.title}' updated successfully")
            return redirect("core:documentation:runbook_detail", slug=runbook.slug)
    else:
        # Convert tags list to comma-separated string for form
        initial_data = {}
        if runbook.tags:
            initial_data["tags"] = ", ".join(runbook.tags)
        # Convert JSON fields to strings for form
        if runbook.steps:
            initial_data["steps"] = json.dumps(runbook.steps, indent=2)
        if runbook.verification_steps:
            initial_data["verification_steps"] = json.dumps(runbook.verification_steps, indent=2)
        if runbook.rollback_steps:
            initial_data["rollback_steps"] = json.dumps(runbook.rollback_steps, indent=2)

        form = RunbookForm(instance=runbook, initial=initial_data)

    context = {"form": form, "runbook": runbook, "action": "Edit"}

    return render(request, "core/documentation/runbook_form.html", context)


@login_required
@platform_admin_required
@require_http_methods(["POST"])
def runbook_execute(request, slug):
    """
    Start a runbook execution.

    Requirement 34.5: Provide incident response runbooks with documented procedures.
    """
    runbook = get_object_or_404(Runbook, slug=slug)

    # Create execution record
    execution = RunbookExecution.objects.create(
        runbook=runbook,
        runbook_version=runbook.version,
        executed_by=request.user,
        status=RunbookExecution.IN_PROGRESS,
    )

    messages.success(
        request,
        f"Started execution of runbook '{runbook.title}'. Track progress in execution history.",
    )
    return redirect("core:documentation:runbook_execution_detail", execution_id=execution.id)


@login_required
@platform_admin_required
def runbook_execution_detail(request, execution_id):
    """
    View runbook execution details.

    Requirement 34.8: Track runbook versions and updates.
    """
    execution = get_object_or_404(RunbookExecution, id=execution_id)

    context = {"execution": execution}

    return render(request, "core/documentation/runbook_execution_detail.html", context)


# Admin Notes Views


def _get_admin_note_initial_data(request):
    """Helper to get initial data for admin note form."""
    initial = {}
    doc_slug = request.GET.get("doc")
    runbook_slug = request.GET.get("runbook")

    if doc_slug:
        try:
            doc = DocumentationPage.objects.get(slug=doc_slug)
            initial["documentation_page"] = doc
        except DocumentationPage.DoesNotExist:
            pass

    if runbook_slug:
        try:
            runbook = Runbook.objects.get(slug=runbook_slug)
            initial["runbook"] = runbook
        except Runbook.DoesNotExist:
            pass

    return initial


def _get_admin_note_redirect(note):
    """Helper to determine redirect after creating admin note."""
    if note.documentation_page:
        return redirect("core:documentation:detail", slug=note.documentation_page.slug)
    elif note.runbook:
        return redirect("core:documentation:runbook_detail", slug=note.runbook.slug)
    else:
        return redirect("core:documentation:home")


@login_required
@platform_admin_required
def admin_note_create(request):
    """
    Create an admin note.

    Requirement 34.9: Allow admins to add notes and tips for other admins.
    """
    if request.method == "POST":
        form = AdminNoteForm(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.created_by = request.user
            note.save()

            messages.success(request, "Admin note created successfully")
            return _get_admin_note_redirect(note)
    else:
        initial = _get_admin_note_initial_data(request)
        form = AdminNoteForm(initial=initial)

    context = {"form": form}
    return render(request, "core/documentation/admin_note_form.html", context)


@login_required
@platform_admin_required
@require_http_methods(["POST"])
def admin_note_helpful(request, note_id):
    """
    Mark an admin note as helpful.

    Requirement 34.9: Allow admins to add notes and tips for other admins.
    """
    note = get_object_or_404(AdminNote, id=note_id)
    note.mark_helpful()

    return JsonResponse({"success": True, "helpful_count": note.helpful_count})


# Search API


@login_required
@platform_admin_required
def documentation_search_api(request):
    """
    API endpoint for documentation search (for autocomplete).

    Requirement 34: Knowledge Base and Documentation - search functionality.
    """
    query = request.GET.get("q", "").strip()

    if not query or len(query) < 2:
        return JsonResponse({"results": []})

    # Search documentation pages
    search_vector = SearchVector("title", weight="A") + SearchVector("content", weight="B")
    search_query = SearchQuery(query)

    pages = (
        DocumentationPage.objects.filter(status=DocumentationPage.PUBLISHED)
        .annotate(search=search_vector, rank=SearchRank(search_vector, search_query))
        .filter(search=search_query)
        .order_by("-rank")[:10]
    )

    results = []
    for page in pages:
        results.append(
            {
                "type": "documentation",
                "title": page.title,
                "category": page.get_category_display(),
                "url": f"/admin/documentation/{page.slug}/",
                "summary": page.summary[:200] if page.summary else "",
            }
        )

    # Search runbooks
    runbooks = (
        Runbook.objects.filter(status=Runbook.ACTIVE)
        .annotate(search=search_vector, rank=SearchRank(search_vector, search_query))
        .filter(search=search_query)
        .order_by("-rank")[:10]
    )

    for runbook in runbooks:
        results.append(
            {
                "type": "runbook",
                "title": runbook.title,
                "category": runbook.get_runbook_type_display(),
                "url": f"/admin/runbooks/{runbook.slug}/",
                "summary": runbook.description[:200] if runbook.description else "",
            }
        )

    return JsonResponse({"results": results})
