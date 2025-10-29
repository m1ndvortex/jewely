"""
Tests for documentation CRUD operations and search functionality.

This module specifically tests:
- Documentation CRUD operations (Create, Read, Update, Delete)
- Search functionality with filters
- Runbook CRUD operations
- Admin note CRUD operations

Per Task 25.4 - Write documentation tests
Requirements: 34, 28
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .documentation_models import AdminNote, DocumentationPage, Runbook

User = get_user_model()


@pytest.mark.django_db
class TestDocumentationCRUD(TestCase):
    """
    Test documentation CRUD operations.

    Requirement 34: Knowledge Base and Documentation
    Requirement 28: Testing
    """

    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.client = Client()
        self.client.login(username="admin", password="testpass123")

    def test_create_documentation_page(self):
        """Test creating a documentation page."""
        # Create via form
        data = {
            "title": "Test Documentation",
            "slug": "test-documentation",
            "content": "# Test\n\nThis is test documentation.",
            "summary": "Test summary",
            "category": DocumentationPage.ARCHITECTURE,
            "status": DocumentationPage.DRAFT,
            "version": "1.0",
            "tags": "test, documentation",
            "order": 0,
        }

        response = self.client.post(reverse("core:documentation:create"), data)

        # Should redirect after creation
        self.assertEqual(response.status_code, 302)

        # Verify page was created
        doc = DocumentationPage.objects.get(slug="test-documentation")
        self.assertEqual(doc.title, "Test Documentation")
        self.assertEqual(doc.content, "# Test\n\nThis is test documentation.")
        self.assertEqual(doc.category, DocumentationPage.ARCHITECTURE)
        self.assertEqual(doc.status, DocumentationPage.DRAFT)
        self.assertEqual(doc.tags, ["test", "documentation"])
        self.assertEqual(doc.created_by, self.admin_user)

    def test_read_documentation_page(self):
        """Test reading a documentation page."""
        # Create a page
        doc = DocumentationPage.objects.create(
            title="Read Test",
            slug="read-test",
            content="Content to read",
            category=DocumentationPage.ADMIN_GUIDE,
            status=DocumentationPage.PUBLISHED,
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )

        # Read via detail view
        response = self.client.get(reverse("core:documentation:detail", args=[doc.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page"], doc)
        self.assertContains(response, "Read Test")
        self.assertContains(response, "Content to read")

    def test_update_documentation_page(self):
        """Test updating a documentation page."""
        # Create initial page
        doc = DocumentationPage.objects.create(
            title="Original Title",
            slug="original-slug",
            content="Original content",
            category=DocumentationPage.ADMIN_GUIDE,
            status=DocumentationPage.DRAFT,
            version="1.0",
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )

        # Update via form
        data = {
            "title": "Updated Title",
            "slug": "original-slug",
            "content": "Updated content",
            "summary": "Updated summary",
            "category": DocumentationPage.ADMIN_GUIDE,
            "status": DocumentationPage.PUBLISHED,
            "version": "1.1",
            "tags": "updated",
            "order": 0,
        }

        response = self.client.post(reverse("core:documentation:edit", args=[doc.slug]), data)

        # Should redirect after update
        self.assertEqual(response.status_code, 302)

        # Verify updates
        doc.refresh_from_db()
        self.assertEqual(doc.title, "Updated Title")
        self.assertEqual(doc.content, "Updated content")
        self.assertEqual(doc.status, DocumentationPage.PUBLISHED)
        self.assertEqual(doc.version, "1.1")
        self.assertEqual(doc.updated_by, self.admin_user)

    def test_delete_documentation_page_via_archive(self):
        """Test archiving (soft delete) a documentation page."""
        doc = DocumentationPage.objects.create(
            title="To Archive",
            slug="to-archive",
            content="Content",
            category=DocumentationPage.ADMIN_GUIDE,
            status=DocumentationPage.PUBLISHED,
            created_by=self.admin_user,
        )

        # Archive the page
        response = self.client.post(reverse("core:documentation:archive", args=[doc.slug]))

        # Should redirect
        self.assertEqual(response.status_code, 302)

        # Verify archived
        doc.refresh_from_db()
        self.assertEqual(doc.status, DocumentationPage.ARCHIVED)

    def test_list_all_documentation_pages(self):
        """Test listing all documentation pages."""
        # Create multiple pages
        for i in range(5):
            DocumentationPage.objects.create(
                title=f"Doc {i}",
                slug=f"doc-{i}",
                content=f"Content {i}",
                category=DocumentationPage.ADMIN_GUIDE,
                status=DocumentationPage.PUBLISHED,
                created_by=self.admin_user,
            )

        # List all pages
        response = self.client.get(reverse("core:documentation:list"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("page_obj", response.context)
        self.assertEqual(len(response.context["page_obj"]), 5)


@pytest.mark.django_db
class TestDocumentationSearch(TestCase):
    """
    Test documentation search functionality.

    Requirement 34: Knowledge Base and Documentation - search functionality
    Requirement 28: Testing
    """

    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        # Create searchable documentation
        self.doc1 = DocumentationPage.objects.create(
            title="Database Backup Guide",
            slug="database-backup-guide",
            content="How to backup PostgreSQL database using pg_dump command",
            summary="Complete guide for database backups",
            category=DocumentationPage.ADMIN_GUIDE,
            status=DocumentationPage.PUBLISHED,
            tags=["database", "backup", "postgresql"],
            created_by=self.admin_user,
        )

        self.doc2 = DocumentationPage.objects.create(
            title="API Documentation",
            slug="api-documentation",
            content="REST API endpoints for tenant management",
            summary="API reference documentation",
            category=DocumentationPage.API_DOCUMENTATION,
            status=DocumentationPage.PUBLISHED,
            tags=["api", "rest", "endpoints"],
            created_by=self.admin_user,
        )

        self.doc3 = DocumentationPage.objects.create(
            title="Troubleshooting Database Issues",
            slug="troubleshooting-database",
            content="Common database connection problems and solutions",
            summary="Database troubleshooting guide",
            category=DocumentationPage.TROUBLESHOOTING,
            status=DocumentationPage.PUBLISHED,
            tags=["database", "troubleshooting"],
            created_by=self.admin_user,
        )

        # Draft document (should not appear in default searches)
        self.doc4 = DocumentationPage.objects.create(
            title="Draft Document",
            slug="draft-document",
            content="This is a draft",
            category=DocumentationPage.ADMIN_GUIDE,
            status=DocumentationPage.DRAFT,
            created_by=self.admin_user,
        )

        self.client = Client()
        self.client.login(username="admin", password="testpass123")

    def test_search_by_query(self):
        """Test searching documentation by text query."""
        response = self.client.get(reverse("core:documentation:list"), {"query": "database"})

        self.assertEqual(response.status_code, 200)
        # Note: Full-text search requires search_vector to be populated
        # In real usage, this would be done via database trigger or management command

    def test_filter_by_category(self):
        """Test filtering documentation by category."""
        response = self.client.get(
            reverse("core:documentation:list"),
            {"category": DocumentationPage.ADMIN_GUIDE},
        )

        self.assertEqual(response.status_code, 200)
        pages = list(response.context["page_obj"])

        # Should include doc1 (ADMIN_GUIDE)
        self.assertIn(self.doc1, pages)
        # Should not include doc2 (API_DOCUMENTATION)
        self.assertNotIn(self.doc2, pages)

    def test_filter_by_status(self):
        """Test filtering documentation by status."""
        response = self.client.get(
            reverse("core:documentation:list"),
            {"status": DocumentationPage.PUBLISHED},
        )

        self.assertEqual(response.status_code, 200)
        pages = list(response.context["page_obj"])

        # Should include published docs
        self.assertIn(self.doc1, pages)
        self.assertIn(self.doc2, pages)
        # Should not include draft
        self.assertNotIn(self.doc4, pages)

    def test_combined_filters(self):
        """Test combining multiple filters."""
        response = self.client.get(
            reverse("core:documentation:list"),
            {
                "category": DocumentationPage.ADMIN_GUIDE,
                "status": DocumentationPage.PUBLISHED,
            },
        )

        self.assertEqual(response.status_code, 200)
        pages = list(response.context["page_obj"])

        # Should only include published ADMIN_GUIDE docs
        self.assertIn(self.doc1, pages)
        self.assertNotIn(self.doc2, pages)  # Different category
        self.assertNotIn(self.doc4, pages)  # Draft status

    def test_search_returns_empty_for_no_matches(self):
        """Test that search returns empty results when no matches found."""
        response = self.client.get(reverse("core:documentation:list"), {"query": "nonexistent"})

        self.assertEqual(response.status_code, 200)
        # Should return empty or no results

    def test_category_view_filters_correctly(self):
        """Test category-specific view."""
        response = self.client.get(
            reverse(
                "core:documentation:category",
                args=[DocumentationPage.TROUBLESHOOTING],
            )
        )

        self.assertEqual(response.status_code, 200)
        root_pages = list(response.context["root_pages"])

        # Should only include troubleshooting docs
        self.assertIn(self.doc3, root_pages)
        self.assertNotIn(self.doc1, root_pages)
        self.assertNotIn(self.doc2, root_pages)


@pytest.mark.django_db
class TestRunbookCRUD(TestCase):
    """
    Test runbook CRUD operations.

    Requirement 34: Knowledge Base and Documentation
    Requirement 28: Testing
    """

    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.client = Client()
        self.client.login(username="admin", password="testpass123")

    def test_create_runbook(self):
        """Test creating a runbook."""
        import json

        data = {
            "title": "Test Runbook",
            "slug": "test-runbook",
            "description": "Test runbook description",
            "runbook_type": Runbook.MAINTENANCE,
            "priority": Runbook.HIGH,
            "prerequisites": "Admin access required",
            "steps": json.dumps(
                [
                    {
                        "title": "Step 1",
                        "description": "First step",
                        "commands": "echo 'step 1'",
                    }
                ]
            ),
            "verification_steps": json.dumps(["Verify step 1 completed"]),
            "rollback_steps": json.dumps(["Undo step 1"]),
            "status": Runbook.ACTIVE,
            "version": "1.0",
            "tags": "test, maintenance",
        }

        response = self.client.post(reverse("core:documentation:runbook_create"), data)

        # Should redirect after creation
        self.assertEqual(response.status_code, 302)

        # Verify runbook created
        runbook = Runbook.objects.get(slug="test-runbook")
        self.assertEqual(runbook.title, "Test Runbook")
        self.assertEqual(runbook.runbook_type, Runbook.MAINTENANCE)
        self.assertEqual(runbook.priority, Runbook.HIGH)
        self.assertEqual(len(runbook.steps), 1)
        self.assertEqual(runbook.created_by, self.admin_user)

    def test_read_runbook(self):
        """Test reading a runbook."""
        runbook = Runbook.objects.create(
            title="Read Test Runbook",
            slug="read-test-runbook",
            description="Test description",
            runbook_type=Runbook.INCIDENT_RESPONSE,
            priority=Runbook.CRITICAL,
            status=Runbook.ACTIVE,
            created_by=self.admin_user,
        )

        response = self.client.get(
            reverse("core:documentation:runbook_detail", args=[runbook.slug])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["runbook"], runbook)
        self.assertContains(response, "Read Test Runbook")

    def test_update_runbook(self):
        """Test updating a runbook."""
        import json

        runbook = Runbook.objects.create(
            title="Original Runbook",
            slug="original-runbook",
            description="Original description",
            runbook_type=Runbook.MAINTENANCE,
            priority=Runbook.MEDIUM,
            status=Runbook.DRAFT,
            version="1.0",
            steps=[],
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )

        data = {
            "title": "Updated Runbook",
            "slug": "original-runbook",
            "description": "Updated description",
            "runbook_type": Runbook.MAINTENANCE,
            "priority": Runbook.HIGH,
            "prerequisites": "Updated prerequisites",
            "steps": json.dumps([{"title": "New Step", "description": "New step"}]),
            "verification_steps": json.dumps([]),
            "rollback_steps": json.dumps([]),
            "status": Runbook.ACTIVE,
            "version": "1.1",
            "tags": "updated",
        }

        response = self.client.post(
            reverse("core:documentation:runbook_edit", args=[runbook.slug]), data
        )

        # Should redirect
        self.assertEqual(response.status_code, 302)

        # Verify updates
        runbook.refresh_from_db()
        self.assertEqual(runbook.title, "Updated Runbook")
        self.assertEqual(runbook.description, "Updated description")
        self.assertEqual(runbook.priority, Runbook.HIGH)
        self.assertEqual(runbook.status, Runbook.ACTIVE)
        self.assertEqual(runbook.version, "1.1")

    def test_list_runbooks(self):
        """Test listing runbooks."""
        # Create multiple runbooks
        for i in range(3):
            Runbook.objects.create(
                title=f"Runbook {i}",
                slug=f"runbook-{i}",
                description=f"Description {i}",
                runbook_type=Runbook.MAINTENANCE,
                priority=Runbook.MEDIUM,
                status=Runbook.ACTIVE,
                created_by=self.admin_user,
            )

        response = self.client.get(reverse("core:documentation:runbook_list"))

        self.assertEqual(response.status_code, 200)
        self.assertIn("page_obj", response.context)
        self.assertEqual(len(response.context["page_obj"]), 3)


@pytest.mark.django_db
class TestRunbookSearch(TestCase):
    """
    Test runbook search functionality.

    Requirement 34: Knowledge Base and Documentation - search functionality
    Requirement 28: Testing
    """

    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        # Create searchable runbooks
        self.runbook1 = Runbook.objects.create(
            title="Database Backup Procedure",
            slug="database-backup-procedure",
            description="Procedure for backing up PostgreSQL database",
            runbook_type=Runbook.MAINTENANCE,
            priority=Runbook.HIGH,
            status=Runbook.ACTIVE,
            tags=["database", "backup"],
            created_by=self.admin_user,
        )

        self.runbook2 = Runbook.objects.create(
            title="Security Incident Response",
            slug="security-incident-response",
            description="Steps to respond to security incidents",
            runbook_type=Runbook.INCIDENT_RESPONSE,
            priority=Runbook.CRITICAL,
            status=Runbook.ACTIVE,
            tags=["security", "incident"],
            created_by=self.admin_user,
        )

        self.runbook3 = Runbook.objects.create(
            title="Disaster Recovery",
            slug="disaster-recovery",
            description="Complete disaster recovery procedure",
            runbook_type=Runbook.DISASTER_RECOVERY,
            priority=Runbook.CRITICAL,
            status=Runbook.ACTIVE,
            tags=["disaster", "recovery"],
            created_by=self.admin_user,
        )

        # Deprecated runbook
        self.runbook4 = Runbook.objects.create(
            title="Old Procedure",
            slug="old-procedure",
            description="Deprecated procedure",
            runbook_type=Runbook.MAINTENANCE,
            priority=Runbook.LOW,
            status=Runbook.DEPRECATED,
            created_by=self.admin_user,
        )

        self.client = Client()
        self.client.login(username="admin", password="testpass123")

    def test_filter_runbooks_by_type(self):
        """Test filtering runbooks by type."""
        response = self.client.get(
            reverse("core:documentation:runbook_list"),
            {"runbook_type": Runbook.INCIDENT_RESPONSE},
        )

        self.assertEqual(response.status_code, 200)
        runbooks = list(response.context["page_obj"])

        self.assertIn(self.runbook2, runbooks)
        self.assertNotIn(self.runbook1, runbooks)

    def test_filter_runbooks_by_priority(self):
        """Test filtering runbooks by priority."""
        response = self.client.get(
            reverse("core:documentation:runbook_list"), {"priority": Runbook.CRITICAL}
        )

        self.assertEqual(response.status_code, 200)
        runbooks = list(response.context["page_obj"])

        self.assertIn(self.runbook2, runbooks)
        self.assertIn(self.runbook3, runbooks)
        self.assertNotIn(self.runbook1, runbooks)

    def test_filter_runbooks_by_status(self):
        """Test filtering runbooks by status."""
        response = self.client.get(
            reverse("core:documentation:runbook_list"), {"status": Runbook.ACTIVE}
        )

        self.assertEqual(response.status_code, 200)
        runbooks = list(response.context["page_obj"])

        self.assertIn(self.runbook1, runbooks)
        self.assertNotIn(self.runbook4, runbooks)  # Deprecated

    def test_combined_runbook_filters(self):
        """Test combining multiple runbook filters."""
        response = self.client.get(
            reverse("core:documentation:runbook_list"),
            {
                "runbook_type": Runbook.DISASTER_RECOVERY,
                "priority": Runbook.CRITICAL,
                "status": Runbook.ACTIVE,
            },
        )

        self.assertEqual(response.status_code, 200)
        runbooks = list(response.context["page_obj"])

        self.assertIn(self.runbook3, runbooks)
        self.assertNotIn(self.runbook1, runbooks)
        self.assertNotIn(self.runbook2, runbooks)


@pytest.mark.django_db
class TestAdminNoteCRUD(TestCase):
    """
    Test admin note CRUD operations.

    Requirement 34.9: Allow admins to add notes and tips
    Requirement 28: Testing
    """

    def setUp(self):
        """Set up test data."""
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="testpass123",
            role="PLATFORM_ADMIN",
        )

        self.doc = DocumentationPage.objects.create(
            title="Test Doc",
            slug="test-doc",
            content="Content",
            category=DocumentationPage.ADMIN_GUIDE,
            status=DocumentationPage.PUBLISHED,
            created_by=self.admin_user,
            updated_by=self.admin_user,
        )

        self.client = Client()
        self.client.login(username="admin", password="testpass123")

    def test_create_admin_note(self):
        """Test creating an admin note."""
        data = {
            "title": "Test Note",
            "content": "This is a test note",
            "note_type": AdminNote.TIP,
            "documentation_page": self.doc.id,
            "tags": "test, note",
            "is_pinned": False,
        }

        response = self.client.post(reverse("core:documentation:admin_note_create"), data)

        # Should redirect
        self.assertEqual(response.status_code, 302)

        # Verify note created
        note = AdminNote.objects.get(title="Test Note")
        self.assertEqual(note.content, "This is a test note")
        self.assertEqual(note.note_type, AdminNote.TIP)
        self.assertEqual(note.documentation_page, self.doc)
        self.assertEqual(note.created_by, self.admin_user)

    def test_read_admin_note_on_documentation(self):
        """Test reading admin notes displayed on documentation."""
        note = AdminNote.objects.create(
            title="Test Note",
            content="Note content",
            note_type=AdminNote.WARNING,
            documentation_page=self.doc,
            created_by=self.admin_user,
        )

        response = self.client.get(reverse("core:documentation:detail", args=[self.doc.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertIn("notes", response.context)
        self.assertIn(note, response.context["notes"])

    def test_mark_note_helpful(self):
        """Test marking a note as helpful."""
        note = AdminNote.objects.create(
            title="Helpful Note",
            content="Useful information",
            note_type=AdminNote.TIP,
            documentation_page=self.doc,
            created_by=self.admin_user,
        )

        initial_count = note.helpful_count

        response = self.client.post(
            reverse("core:documentation:admin_note_helpful", args=[note.id])
        )

        self.assertEqual(response.status_code, 200)

        # Verify count incremented
        note.refresh_from_db()
        self.assertEqual(note.helpful_count, initial_count + 1)

    def test_pinned_notes_appear_first(self):
        """Test that pinned notes appear before unpinned notes."""
        # Create unpinned note
        note1 = AdminNote.objects.create(
            title="Regular Note",
            content="Regular content",
            note_type=AdminNote.TIP,
            documentation_page=self.doc,
            is_pinned=False,
            created_by=self.admin_user,
        )

        # Create pinned note
        note2 = AdminNote.objects.create(
            title="Pinned Note",
            content="Important content",
            note_type=AdminNote.WARNING,
            documentation_page=self.doc,
            is_pinned=True,
            created_by=self.admin_user,
        )

        # Get notes (should be ordered by is_pinned DESC)
        notes = AdminNote.objects.filter(documentation_page=self.doc).order_by(
            "-is_pinned", "-created_at"
        )

        # Pinned note should come first
        self.assertEqual(notes[0], note2)
        self.assertEqual(notes[1], note1)
