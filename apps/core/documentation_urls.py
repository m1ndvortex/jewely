"""
URL configuration for documentation and knowledge base.

Per Requirement 34 - Knowledge Base and Documentation
"""

from django.urls import path

from . import documentation_views

app_name = "documentation"

urlpatterns = [
    # Documentation pages
    path("", documentation_views.documentation_home, name="home"),
    path("list/", documentation_views.documentation_list, name="list"),
    path("category/<str:category>/", documentation_views.documentation_category, name="category"),
    path("create/", documentation_views.documentation_create, name="create"),
    # Runbooks - must come before <slug:slug>/ patterns
    path("runbooks/", documentation_views.runbook_list, name="runbook_list"),
    path("runbooks/create/", documentation_views.runbook_create, name="runbook_create"),
    path("runbooks/<slug:slug>/", documentation_views.runbook_detail, name="runbook_detail"),
    path("runbooks/<slug:slug>/edit/", documentation_views.runbook_edit, name="runbook_edit"),
    path(
        "runbooks/<slug:slug>/execute/", documentation_views.runbook_execute, name="runbook_execute"
    ),
    path(
        "runbook-executions/<uuid:execution_id>/",
        documentation_views.runbook_execution_detail,
        name="runbook_execution_detail",
    ),
    # Admin notes
    path("notes/create/", documentation_views.admin_note_create, name="admin_note_create"),
    path(
        "notes/<uuid:note_id>/helpful/",
        documentation_views.admin_note_helpful,
        name="admin_note_helpful",
    ),
    # Search API
    path("api/search/", documentation_views.documentation_search_api, name="search_api"),
    # Documentation detail pages - must come last to avoid matching other patterns
    path("<slug:slug>/", documentation_views.documentation_detail, name="detail"),
    path("<slug:slug>/edit/", documentation_views.documentation_edit, name="edit"),
    path("<slug:slug>/publish/", documentation_views.documentation_publish, name="publish"),
    path("<slug:slug>/archive/", documentation_views.documentation_archive, name="archive"),
]
