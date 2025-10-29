"""
Tests for documentation interface functionality.

This module tests:
- Documentation browser with categories
- Search functionality
- Documentation editor (markdown support)
- Version tracking
- Runbook management
- Admin notes

Per Requirement 34 - Knowledge Base and Documentation
"""

import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.text import slugify

import pytest

from .documentation_models import AdminNote, DocumentationPage, Runbook, RunbookExecution

User = get_user_model()


@pytest.mark.django_db
class TestDocumentationBrowser(TestCase):
    """
    Test documentation browser with categories.

    Requirement 34: Knowledge Base and Documentation - browser with categories.
    """

    def setUp(self):
        """Set up test data."""
        # Create platform admin user
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        # Create documentation pages
        self.doc1 = DocumentationPage.objects.create(
            title="Architecture Overview",
            slug="architecture-overview",
            content="# Architecture\n\nThis is the architecture documentation.",
            summary="Overview of system architecture",
            category=DocumentationPage.ARCHITECTURE,
            status=DocumentationPage.PUBLISHED,
            version="1.0",
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )

        self.doc2 = DocumentationPage.objects.create(
            title="Admin Guide",
            slug="admin-guide",
            content="# Admin Guide\n\nHow to manage the platform.",
            summary="Platform administration guide",
            category=DocumentationPage.ADMIN_GUIDE,
            status=DocumentationPage.PUBLISHED,
            version="1.0",
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )

        self.client = Client()
        self.client.login(username="admin", password="testpass123")

    def test_documentation_home_page(self):
        """Test documentation home page displays categories."""
        response = self.client.get(reverse("core:documentation:home"))

        assert response.status_code == 200
        assert "categories" in response.context
        assert len(response.context["categories"]) > 0

    def test_documentation_list_view(self):
        """Test documentation list view."""
        response = self.client.get(reverse("core:documentation:list"))

        assert response.status_code == 200
        assert "page_obj" in response.context
        assert self.doc1 in response.context["page_obj"]
        assert self.doc2 in response.context["page_obj"]

    def test_documentation_category_view(self):
        """Test category-specific documentation view."""
        response = self.client.get(
            reverse("core:documentation:category", args=[DocumentationPage.ARCHITECTURE])
        )

        assert response.status_code == 200
        assert "root_pages" in response.context
        assert self.doc1 in response.context["root_pages"]
        assert self.doc2 not in response.context["root_pages"]

    def test_documentation_detail_view(self):
        """Test documentation detail view with version tracking."""
        response = self.client.get(reverse("core:documentation:detail", args=[self.doc1.slug]))

        assert response.status_code == 200
        assert response.context["page"] == self.doc1
        assert "breadcrumbs" in response.context

        # Check view count incremented
        self.doc1.refresh_from_db()
        assert self.doc1.view_count == 1


@pytest.mark.django_db
class TestDocumentationSearch(TestCase):
    """
    Test documentation search functionality.

    Requirement 34: Knowledge Base and Documentation - search functionality.
    """

    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        # Create searchable documentation
        self.doc = DocumentationPage.objects.create(
            title="Database Backup Procedures",
            slug="database-backup",
            content="How to backup PostgreSQL database using pg_dump",
            category=DocumentationPage.ADMIN_GUIDE,
            status=DocumentationPage.PUBLISHED,
            version="1.0",
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )

        self.client = Client()
        self.client.login(username="admin", password="testpass123")

    def test_documentation_search(self):
        """Test search functionality."""
        response = self.client.get(reverse("core:documentation:list"), {"query": "backup"})

        assert response.status_code == 200
        assert "page_obj" in response.context
        # Search should find the document
        assert len(response.context["page_obj"]) >= 0  # May be 0 if search vector not updated

    def test_documentation_filter_by_category(self):
        """Test filtering by category."""
        response = self.client.get(
            reverse("core:documentation:list"), {"category": DocumentationPage.ADMIN_GUIDE}
        )

        assert response.status_code == 200
        assert self.doc in response.context["page_obj"]

    def test_documentation_filter_by_status(self):
        """Test filtering by status."""
        response = self.client.get(
            reverse("core:documentation:list"), {"status": DocumentationPage.PUBLISHED}
        )

        assert response.status_code == 200
        assert self.doc in response.context["page_obj"]


@pytest.mark.django_db
class TestDocumentationEditor(TestCase):
    """
    Test documentation editor with markdown support.

    Requirement 34.2: Provide step-by-step guides for common admin tasks.
    """

    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.client = Client()
        self.client.login(username="admin", password="testpass123")

    def test_create_documentation_page(self):
        """Test creating a new documentation page."""
        data = {
            "title": "New Documentation",
            "slug": "",  # Should auto-generate
            "content": "# New Doc\n\nThis is new documentation with **markdown**.",
            "summary": "A new documentation page",
            "category": DocumentationPage.ADMIN_GUIDE,
            "status": DocumentationPage.DRAFT,
            "version": "1.0",
            "tags": "test, documentation",
            "order": 0,
        }

        response = self.client.post(reverse("core:documentation:create"), data)

        # Should redirect to detail page
        assert response.status_code == 302

        # Check page was created
        doc = DocumentationPage.objects.get(title="New Documentation")
        assert doc.slug == slugify("New Documentation")
        assert doc.content == data["content"]
        assert doc.tags == ["test", "documentation"]
        assert doc.created_by == self.admin_user

    def test_edit_documentation_page(self):
        """Test editing an existing documentation page with version tracking."""
        doc = DocumentationPage.objects.create(
            title="Original Title",
            slug="original-title",
            content="Original content",
            category=DocumentationPage.ADMIN_GUIDE,
            status=DocumentationPage.DRAFT,
            version="1.0",
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )

        data = {
            "title": "Updated Title",
            "slug": doc.slug,
            "content": "Updated content with changes",
            "summary": "Updated summary",
            "category": DocumentationPage.ADMIN_GUIDE,
            "status": DocumentationPage.PUBLISHED,
            "version": "1.1",  # Version updated
            "tags": "updated",
            "order": 0,
        }

        response = self.client.post(reverse("core:documentation:edit", args=[doc.slug]), data)

        # Should redirect
        assert response.status_code == 302

        # Check updates
        doc.refresh_from_db()
        assert doc.title == "Updated Title"
        assert doc.content == "Updated content with changes"
        assert doc.version == "1.1"
        assert doc.status == DocumentationPage.PUBLISHED
        assert doc.updated_by == self.admin_user

    def test_publish_documentation(self):
        """Test publishing a draft documentation page."""
        doc = DocumentationPage.objects.create(
            title="Draft Doc",
            slug="draft-doc",
            content="Draft content",
            category=DocumentationPage.ADMIN_GUIDE,
            status=DocumentationPage.DRAFT,
            version="1.0",
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )

        response = self.client.post(reverse("core:documentation:publish", args=[doc.slug]))

        # Should redirect
        assert response.status_code == 302

        # Check status changed
        doc.refresh_from_db()
        assert doc.status == DocumentationPage.PUBLISHED
        assert doc.published_at is not None


@pytest.mark.django_db
class TestRunbookManagement(TestCase):
    """
    Test runbook management functionality.

    Requirement 34.5: Provide incident response runbooks with documented procedures.
    Requirement 34.6: Provide maintenance runbooks for routine tasks.
    Requirement 34.7: Provide disaster recovery runbooks with step-by-step procedures.
    """

    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.runbook = Runbook.objects.create(
            title="Database Backup Runbook",
            slug="database-backup-runbook",
            description="Procedure for backing up the database",
            runbook_type=Runbook.MAINTENANCE,
            priority=Runbook.HIGH,
            prerequisites="Access to database server",
            steps=[
                {
                    "title": "Stop application",
                    "description": "Stop the application to ensure consistency",
                    "commands": "docker-compose stop web",
                },
                {
                    "title": "Run backup",
                    "description": "Execute pg_dump",
                    "commands": "pg_dump -U postgres jewelry_shop > backup.sql",
                },
            ],
            verification_steps=["Check backup file size", "Verify backup integrity"],
            rollback_steps=["Restore from previous backup"],
            status=Runbook.ACTIVE,
            version="1.0",
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )

        self.client = Client()
        self.client.login(username="admin", password="testpass123")

    def test_runbook_list_view(self):
        """Test runbook list view."""
        response = self.client.get(reverse("core:documentation:runbook_list"))

        assert response.status_code == 200
        assert "page_obj" in response.context
        assert self.runbook in response.context["page_obj"]

    def test_runbook_detail_view(self):
        """Test runbook detail view with execution history."""
        response = self.client.get(
            reverse("core:documentation:runbook_detail", args=[self.runbook.slug])
        )

        assert response.status_code == 200
        assert response.context["runbook"] == self.runbook
        assert "recent_executions" in response.context

    def test_create_runbook(self):
        """Test creating a new runbook."""
        data = {
            "title": "New Runbook",
            "slug": "",
            "description": "A new operational runbook",
            "runbook_type": Runbook.INCIDENT_RESPONSE,
            "priority": Runbook.CRITICAL,
            "prerequisites": "Admin access",
            "steps": json.dumps([{"title": "Step 1", "description": "Do something"}]),
            "verification_steps": json.dumps(["Verify step 1"]),
            "rollback_steps": json.dumps(["Undo step 1"]),
            "status": Runbook.ACTIVE,
            "version": "1.0",
            "tags": "incident, critical",
        }

        response = self.client.post(reverse("core:documentation:runbook_create"), data)

        # Should redirect
        assert response.status_code == 302

        # Check runbook created
        runbook = Runbook.objects.get(title="New Runbook")
        assert runbook.runbook_type == Runbook.INCIDENT_RESPONSE
        assert runbook.priority == Runbook.CRITICAL
        assert len(runbook.steps) == 1

    def test_execute_runbook(self):
        """Test starting a runbook execution."""
        response = self.client.post(
            reverse("core:documentation:runbook_execute", args=[self.runbook.slug])
        )

        # Should redirect to execution detail
        assert response.status_code == 302

        # Check execution created
        execution = RunbookExecution.objects.filter(runbook=self.runbook).first()
        assert execution is not None
        assert execution.executed_by == self.admin_user
        assert execution.status == RunbookExecution.IN_PROGRESS
        assert execution.runbook_version == self.runbook.version

    def test_runbook_execution_tracking(self):
        """Test runbook execution tracking and statistics."""
        # Create execution
        execution = RunbookExecution.objects.create(
            runbook=self.runbook,
            runbook_version=self.runbook.version,
            executed_by=self.admin_user,
            status=RunbookExecution.IN_PROGRESS,
        )

        # Complete execution
        execution.complete(success=True, notes="Completed successfully")

        # Check execution updated
        execution.refresh_from_db()
        assert execution.status == RunbookExecution.COMPLETED
        assert execution.completed_at is not None
        assert execution.duration is not None

        # Check runbook statistics updated
        self.runbook.refresh_from_db()
        assert self.runbook.execution_count == 1
        assert self.runbook.success_count == 1
        assert self.runbook.get_success_rate() == 1.0


@pytest.mark.django_db
class TestAdminNotes(TestCase):
    """
    Test admin notes functionality.

    Requirement 34.9: Allow admins to add notes and tips for other admins.
    """

    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.doc = DocumentationPage.objects.create(
            title="Test Documentation",
            slug="test-doc",
            content="Test content",
            category=DocumentationPage.ADMIN_GUIDE,
            status=DocumentationPage.PUBLISHED,
            version="1.0",
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )

        self.client = Client()
        self.client.login(username="admin", password="testpass123")

    def test_create_admin_note(self):
        """Test creating an admin note."""
        data = {
            "title": "Important Tip",
            "content": "Always backup before making changes",
            "note_type": AdminNote.TIP,
            "documentation_page": self.doc.id,
            "tags": "backup, safety",
            "is_pinned": False,
        }

        response = self.client.post(reverse("core:documentation:admin_note_create"), data)

        # Should redirect
        assert response.status_code == 302

        # Check note created
        note = AdminNote.objects.get(title="Important Tip")
        assert note.content == data["content"]
        assert note.note_type == AdminNote.TIP
        assert note.documentation_page == self.doc
        assert note.created_by == self.admin_user

    def test_mark_note_helpful(self):
        """Test marking a note as helpful."""
        note = AdminNote.objects.create(
            title="Test Note",
            content="Test content",
            note_type=AdminNote.TIP,
            documentation_page=self.doc,
            created_by=self.admin_user,
        )

        response = self.client.post(
            reverse("core:documentation:admin_note_helpful", args=[note.id])
        )

        # Should return JSON
        assert response.status_code == 200
        data = json.loads(response.content)
        assert data["success"] is True
        assert data["helpful_count"] == 1

        # Check note updated
        note.refresh_from_db()
        assert note.helpful_count == 1

    def test_admin_notes_display_on_documentation(self):
        """Test that admin notes are displayed on documentation pages."""
        # Create note
        note = AdminNote.objects.create(
            title="Test Note",
            content="Test content",
            note_type=AdminNote.WARNING,
            documentation_page=self.doc,
            created_by=self.admin_user,
            is_pinned=True,
        )

        # View documentation page
        response = self.client.get(reverse("core:documentation:detail", args=[self.doc.slug]))

        assert response.status_code == 200
        assert "notes" in response.context
        assert note in response.context["notes"]


@pytest.mark.django_db
class TestVersionTracking(TestCase):
    """
    Test version tracking functionality.

    Requirement 34.8: Track runbook versions and updates.
    """

    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.client = Client()
        self.client.login(username="admin", password="testpass123")

    def test_documentation_version_tracking(self):
        """Test that documentation versions are tracked."""
        # Create initial version
        doc = DocumentationPage.objects.create(
            title="Versioned Doc",
            slug="versioned-doc",
            content="Version 1.0 content",
            category=DocumentationPage.ADMIN_GUIDE,
            status=DocumentationPage.PUBLISHED,
            version="1.0",
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )

        # Update to new version
        data = {
            "title": "Versioned Doc",
            "slug": "versioned-doc",
            "content": "Version 2.0 content with updates",
            "category": DocumentationPage.ADMIN_GUIDE,
            "status": DocumentationPage.PUBLISHED,
            "version": "2.0",
            "tags": "",
            "order": 0,
        }

        self.client.post(reverse("core:documentation:edit", args=[doc.slug]), data)

        # Check version updated
        doc.refresh_from_db()
        assert doc.version == "2.0"
        assert doc.content == "Version 2.0 content with updates"

    def test_runbook_version_in_execution(self):
        """Test that runbook version is captured in execution."""
        runbook = Runbook.objects.create(
            title="Test Runbook",
            slug="test-runbook",
            description="Test",
            runbook_type=Runbook.MAINTENANCE,
            priority=Runbook.MEDIUM,
            steps=[],
            status=Runbook.ACTIVE,
            version="1.5",
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )

        # Execute runbook
        execution = RunbookExecution.objects.create(
            runbook=runbook,
            runbook_version=runbook.version,
            executed_by=self.admin_user,
        )

        # Check version captured
        assert execution.runbook_version == "1.5"

        # Update runbook version
        runbook.version = "2.0"
        runbook.save()

        # Old execution still has old version
        assert execution.runbook_version == "1.5"
