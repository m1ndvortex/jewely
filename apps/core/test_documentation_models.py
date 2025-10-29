"""
Integration tests for documentation models.

Tests Requirement 34: Knowledge Base and Documentation

These tests verify the actual functionality of documentation models
without using mocks, ensuring real database operations work correctly.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

import pytest

from apps.core.documentation_models import AdminNote, DocumentationPage, Runbook, RunbookExecution

User = get_user_model()


@pytest.mark.django_db
class DocumentationPageTestCase(TestCase):
    """
    Test DocumentationPage model.

    Tests Requirements:
    - 34.1: Platform architecture and components documentation
    - 34.2: Step-by-step guides for common admin tasks
    - 34.3: Troubleshooting guides
    - 34.4: Internal API documentation
    - 34.10: FAQ for common tenant questions
    """

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="admin_user",
            email="admin@test.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

    def test_create_architecture_documentation(self):
        """
        Test Requirement 34.1: Provide documentation of platform architecture.
        """
        doc = DocumentationPage.objects.create(
            title="System Architecture Overview",
            slug="system-architecture-overview",
            content="# Architecture\n\nMulti-tenant SaaS platform...",
            summary="Overview of system architecture",
            category=DocumentationPage.ARCHITECTURE,
            status=DocumentationPage.DRAFT,
            version="1.0",
            created_by=self.user,
        )

        self.assertEqual(doc.category, DocumentationPage.ARCHITECTURE)
        self.assertEqual(doc.status, DocumentationPage.DRAFT)
        self.assertIsNotNone(doc.id)
        self.assertEqual(doc.view_count, 0)

    def test_create_admin_guide(self):
        """
        Test Requirement 34.2: Provide step-by-step guides for admin tasks.
        """
        doc = DocumentationPage.objects.create(
            title="How to Manage Tenants",
            slug="how-to-manage-tenants",
            content="## Step 1\nNavigate to admin panel...",
            summary="Guide for tenant management",
            category=DocumentationPage.ADMIN_GUIDE,
            status=DocumentationPage.PUBLISHED,
            version="1.0",
            created_by=self.user,
        )

        self.assertEqual(doc.category, DocumentationPage.ADMIN_GUIDE)
        self.assertTrue(doc.content.startswith("## Step 1"))

    def test_create_troubleshooting_guide(self):
        """
        Test Requirement 34.3: Provide troubleshooting guides.
        """
        doc = DocumentationPage.objects.create(
            title="Database Connection Issues",
            slug="database-connection-issues",
            content="### Problem\nCannot connect to database...",
            summary="Troubleshooting database issues",
            category=DocumentationPage.TROUBLESHOOTING,
            status=DocumentationPage.PUBLISHED,
            version="1.0",
            created_by=self.user,
        )

        self.assertEqual(doc.category, DocumentationPage.TROUBLESHOOTING)

    def test_create_api_documentation(self):
        """
        Test Requirement 34.4: Provide internal API documentation.
        """
        doc = DocumentationPage.objects.create(
            title="Admin API Endpoints",
            slug="admin-api-endpoints",
            content="## Tenant Management API\n\nGET /api/admin/tenants/",
            summary="Internal API documentation",
            category=DocumentationPage.API_DOCUMENTATION,
            status=DocumentationPage.PUBLISHED,
            version="1.0",
            created_by=self.user,
        )

        self.assertEqual(doc.category, DocumentationPage.API_DOCUMENTATION)

    def test_create_faq(self):
        """
        Test Requirement 34.10: Maintain FAQ for common tenant questions.
        """
        doc = DocumentationPage.objects.create(
            title="Frequently Asked Questions",
            slug="faq",
            content="## Q: How do I reset my password?\nA: Click forgot password...",
            summary="Common questions and answers",
            category=DocumentationPage.FAQ,
            status=DocumentationPage.PUBLISHED,
            version="1.0",
            created_by=self.user,
        )

        self.assertEqual(doc.category, DocumentationPage.FAQ)

    def test_publish_documentation(self):
        """Test publishing documentation page."""
        doc = DocumentationPage.objects.create(
            title="Test Doc",
            slug="test-doc",
            content="Content",
            category=DocumentationPage.ARCHITECTURE,
            status=DocumentationPage.DRAFT,
            created_by=self.user,
        )

        self.assertEqual(doc.status, DocumentationPage.DRAFT)
        self.assertIsNone(doc.published_at)

        doc.publish()

        self.assertEqual(doc.status, DocumentationPage.PUBLISHED)
        self.assertIsNotNone(doc.published_at)

    def test_archive_documentation(self):
        """Test archiving documentation page."""
        doc = DocumentationPage.objects.create(
            title="Old Doc",
            slug="old-doc",
            content="Outdated content",
            category=DocumentationPage.ARCHITECTURE,
            status=DocumentationPage.PUBLISHED,
            created_by=self.user,
        )

        doc.archive()

        self.assertEqual(doc.status, DocumentationPage.ARCHIVED)

    def test_view_count_tracking(self):
        """Test view count tracking."""
        doc = DocumentationPage.objects.create(
            title="Popular Doc",
            slug="popular-doc",
            content="Content",
            category=DocumentationPage.ARCHITECTURE,
            created_by=self.user,
        )

        self.assertEqual(doc.view_count, 0)
        self.assertIsNone(doc.last_viewed_at)

        doc.increment_view_count()
        self.assertEqual(doc.view_count, 1)
        self.assertIsNotNone(doc.last_viewed_at)

        doc.increment_view_count()
        self.assertEqual(doc.view_count, 2)

    def test_hierarchical_organization(self):
        """Test parent-child relationships."""
        parent = DocumentationPage.objects.create(
            title="Parent Doc",
            slug="parent-doc",
            content="Parent content",
            category=DocumentationPage.ARCHITECTURE,
            created_by=self.user,
        )

        child = DocumentationPage.objects.create(
            title="Child Doc",
            slug="child-doc",
            content="Child content",
            category=DocumentationPage.ARCHITECTURE,
            parent=parent,
            created_by=self.user,
        )

        self.assertEqual(child.parent, parent)
        self.assertIn(child, parent.children.all())

    def test_breadcrumbs(self):
        """Test breadcrumb generation."""
        root = DocumentationPage.objects.create(
            title="Root",
            slug="root",
            content="Root",
            category=DocumentationPage.ARCHITECTURE,
            created_by=self.user,
        )

        level1 = DocumentationPage.objects.create(
            title="Level 1",
            slug="level-1",
            content="Level 1",
            category=DocumentationPage.ARCHITECTURE,
            parent=root,
            created_by=self.user,
        )

        level2 = DocumentationPage.objects.create(
            title="Level 2",
            slug="level-2",
            content="Level 2",
            category=DocumentationPage.ARCHITECTURE,
            parent=level1,
            created_by=self.user,
        )

        breadcrumbs = level2.get_breadcrumbs()
        self.assertEqual(len(breadcrumbs), 3)
        self.assertEqual(breadcrumbs[0], ("Root", "root"))
        self.assertEqual(breadcrumbs[1], ("Level 1", "level-1"))
        self.assertEqual(breadcrumbs[2], ("Level 2", "level-2"))

    def test_unique_slug_constraint(self):
        """Test that slugs must be unique."""
        DocumentationPage.objects.create(
            title="Doc 1",
            slug="same-slug",
            content="Content 1",
            category=DocumentationPage.ARCHITECTURE,
            created_by=self.user,
        )

        with self.assertRaises(IntegrityError):
            DocumentationPage.objects.create(
                title="Doc 2",
                slug="same-slug",
                content="Content 2",
                category=DocumentationPage.ARCHITECTURE,
                created_by=self.user,
            )


@pytest.mark.django_db
class RunbookTestCase(TestCase):
    """
    Test Runbook model.

    Tests Requirements:
    - 34.5: Incident response runbooks
    - 34.6: Maintenance runbooks
    - 34.7: Disaster recovery runbooks
    - 34.8: Track runbook versions and updates
    """

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="admin_user",
            email="admin@test.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

    def test_create_incident_response_runbook(self):
        """
        Test Requirement 34.5: Incident response runbooks.
        """
        runbook = Runbook.objects.create(
            title="Database Outage Response",
            slug="database-outage-response",
            description="Steps to respond to database outage",
            runbook_type=Runbook.INCIDENT_RESPONSE,
            priority=Runbook.CRITICAL,
            status=Runbook.ACTIVE,
            steps=[
                {
                    "title": "Assess Impact",
                    "description": "Check affected services",
                    "commands": ["kubectl get pods", "docker ps"],
                },
                {
                    "title": "Notify Team",
                    "description": "Alert on-call engineer",
                    "commands": ["send_alert.sh"],
                },
            ],
            expected_duration=timedelta(minutes=30),
            created_by=self.user,
        )

        self.assertEqual(runbook.runbook_type, Runbook.INCIDENT_RESPONSE)
        self.assertEqual(runbook.priority, Runbook.CRITICAL)
        self.assertEqual(len(runbook.steps), 2)
        self.assertEqual(runbook.steps[0]["title"], "Assess Impact")

    def test_create_maintenance_runbook(self):
        """
        Test Requirement 34.6: Maintenance runbooks.
        """
        runbook = Runbook.objects.create(
            title="Weekly Database Maintenance",
            slug="weekly-db-maintenance",
            description="Routine database maintenance tasks",
            runbook_type=Runbook.MAINTENANCE,
            priority=Runbook.MEDIUM,
            status=Runbook.ACTIVE,
            steps=[
                {
                    "title": "Vacuum Database",
                    "description": "Run VACUUM ANALYZE",
                    "commands": ["psql -c 'VACUUM ANALYZE;'"],
                },
            ],
            expected_duration=timedelta(hours=1),
            created_by=self.user,
        )

        self.assertEqual(runbook.runbook_type, Runbook.MAINTENANCE)

    def test_create_disaster_recovery_runbook(self):
        """
        Test Requirement 34.7: Disaster recovery runbooks with RTO/RPO.
        """
        runbook = Runbook.objects.create(
            title="Complete System Recovery",
            slug="complete-system-recovery",
            description="Full disaster recovery procedure",
            runbook_type=Runbook.DISASTER_RECOVERY,
            priority=Runbook.CRITICAL,
            status=Runbook.ACTIVE,
            steps=[
                {
                    "title": "Download Latest Backup",
                    "description": "Retrieve from R2 storage",
                    "commands": ["aws s3 cp s3://backups/latest.dump ."],
                },
                {
                    "title": "Restore Database",
                    "description": "Restore from backup",
                    "commands": ["pg_restore -d jewelry_shop latest.dump"],
                },
            ],
            rto=timedelta(hours=1),
            rpo=timedelta(minutes=15),
            expected_duration=timedelta(hours=1),
            verification_steps=[
                {
                    "title": "Verify Database",
                    "description": "Check row counts",
                    "commands": ["psql -c 'SELECT COUNT(*) FROM tenants;'"],
                }
            ],
            rollback_steps=[
                {
                    "title": "Restore Previous Version",
                    "description": "Rollback to previous backup",
                    "commands": ["pg_restore -d jewelry_shop previous.dump"],
                }
            ],
            created_by=self.user,
        )

        self.assertEqual(runbook.runbook_type, Runbook.DISASTER_RECOVERY)
        self.assertEqual(runbook.rto, timedelta(hours=1))
        self.assertEqual(runbook.rpo, timedelta(minutes=15))
        self.assertEqual(len(runbook.verification_steps), 1)
        self.assertEqual(len(runbook.rollback_steps), 1)

    def test_version_tracking(self):
        """
        Test Requirement 34.8: Track runbook versions and updates.
        """
        runbook = Runbook.objects.create(
            title="Test Runbook",
            slug="test-runbook",
            description="Test",
            runbook_type=Runbook.MAINTENANCE,
            version="1.0",
            changelog="Initial version",
            created_by=self.user,
        )

        self.assertEqual(runbook.version, "1.0")
        self.assertEqual(runbook.changelog, "Initial version")

        # Update version
        runbook.version = "1.1"
        runbook.changelog = "1.1: Added new step\n1.0: Initial version"
        runbook.save()

        self.assertEqual(runbook.version, "1.1")

    def test_activate_runbook(self):
        """Test activating a runbook."""
        runbook = Runbook.objects.create(
            title="Test",
            slug="test",
            description="Test",
            runbook_type=Runbook.MAINTENANCE,
            status=Runbook.DRAFT,
            created_by=self.user,
        )

        self.assertEqual(runbook.status, Runbook.DRAFT)

        runbook.activate()

        self.assertEqual(runbook.status, Runbook.ACTIVE)

    def test_deprecate_runbook(self):
        """Test deprecating a runbook."""
        runbook = Runbook.objects.create(
            title="Old Runbook",
            slug="old-runbook",
            description="Outdated procedure",
            runbook_type=Runbook.MAINTENANCE,
            status=Runbook.ACTIVE,
            created_by=self.user,
        )

        runbook.deprecate()

        self.assertEqual(runbook.status, Runbook.DEPRECATED)

    def test_execution_tracking(self):
        """Test execution count and success rate tracking."""
        runbook = Runbook.objects.create(
            title="Test Runbook",
            slug="test-exec",
            description="Test",
            runbook_type=Runbook.MAINTENANCE,
            created_by=self.user,
        )

        self.assertEqual(runbook.execution_count, 0)
        self.assertEqual(runbook.success_count, 0)
        self.assertEqual(runbook.failure_count, 0)
        self.assertIsNone(runbook.get_success_rate())

        # Record successful execution
        runbook.record_execution(success=True)
        self.assertEqual(runbook.execution_count, 1)
        self.assertEqual(runbook.success_count, 1)
        self.assertEqual(runbook.failure_count, 0)
        self.assertEqual(runbook.get_success_rate(), 1.0)

        # Record failed execution
        runbook.record_execution(success=False)
        self.assertEqual(runbook.execution_count, 2)
        self.assertEqual(runbook.success_count, 1)
        self.assertEqual(runbook.failure_count, 1)
        self.assertEqual(runbook.get_success_rate(), 0.5)

        # Record more successful executions
        runbook.record_execution(success=True)
        runbook.record_execution(success=True)
        self.assertEqual(runbook.execution_count, 4)
        self.assertEqual(runbook.success_count, 3)
        self.assertEqual(runbook.get_success_rate(), 0.75)


@pytest.mark.django_db
class RunbookExecutionTestCase(TestCase):
    """
    Test RunbookExecution model.

    Tests Requirement 34.8: Track runbook versions and updates.
    """

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="admin_user",
            email="admin@test.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

        self.runbook = Runbook.objects.create(
            title="Test Runbook",
            slug="test-runbook",
            description="Test runbook",
            runbook_type=Runbook.MAINTENANCE,
            version="1.0",
            steps=[
                {"title": "Step 1", "description": "First step"},
                {"title": "Step 2", "description": "Second step"},
            ],
            created_by=self.user,
        )

    def test_create_execution(self):
        """Test creating a runbook execution."""
        execution = RunbookExecution.objects.create(
            runbook=self.runbook,
            runbook_version=self.runbook.version,
            executed_by=self.user,
            status=RunbookExecution.IN_PROGRESS,
        )

        self.assertEqual(execution.runbook, self.runbook)
        self.assertEqual(execution.runbook_version, "1.0")
        self.assertEqual(execution.status, RunbookExecution.IN_PROGRESS)
        self.assertIsNotNone(execution.started_at)
        self.assertIsNone(execution.completed_at)

    def test_complete_execution_success(self):
        """Test completing a successful execution."""
        execution = RunbookExecution.objects.create(
            runbook=self.runbook,
            runbook_version=self.runbook.version,
            executed_by=self.user,
        )

        initial_success_count = self.runbook.success_count

        execution.complete(success=True, notes="All steps completed successfully")

        self.assertEqual(execution.status, RunbookExecution.COMPLETED)
        self.assertIsNotNone(execution.completed_at)
        self.assertIsNotNone(execution.duration)
        self.assertEqual(execution.notes, "All steps completed successfully")

        # Verify runbook statistics updated
        self.runbook.refresh_from_db()
        self.assertEqual(self.runbook.success_count, initial_success_count + 1)

    def test_complete_execution_failure(self):
        """Test completing a failed execution."""
        execution = RunbookExecution.objects.create(
            runbook=self.runbook,
            runbook_version=self.runbook.version,
            executed_by=self.user,
        )

        initial_failure_count = self.runbook.failure_count

        execution.complete(success=False, notes="Step 2 failed")

        self.assertEqual(execution.status, RunbookExecution.FAILED)
        self.assertIsNotNone(execution.completed_at)

        # Verify runbook statistics updated
        self.runbook.refresh_from_db()
        self.assertEqual(self.runbook.failure_count, initial_failure_count + 1)

    def test_cancel_execution(self):
        """Test cancelling an execution."""
        execution = RunbookExecution.objects.create(
            runbook=self.runbook,
            runbook_version=self.runbook.version,
            executed_by=self.user,
        )

        execution.cancel(reason="Emergency maintenance required")

        self.assertEqual(execution.status, RunbookExecution.CANCELLED)
        self.assertIsNotNone(execution.completed_at)
        self.assertIn("Cancelled", execution.notes)

    def test_track_version_at_execution(self):
        """Test that execution tracks runbook version."""
        # Create execution with version 1.0
        execution1 = RunbookExecution.objects.create(
            runbook=self.runbook,
            runbook_version=self.runbook.version,
            executed_by=self.user,
        )

        self.assertEqual(execution1.runbook_version, "1.0")

        # Update runbook version
        self.runbook.version = "2.0"
        self.runbook.save()

        # Create new execution with version 2.0
        execution2 = RunbookExecution.objects.create(
            runbook=self.runbook,
            runbook_version=self.runbook.version,
            executed_by=self.user,
        )

        self.assertEqual(execution2.runbook_version, "2.0")

        # Verify both executions exist with different versions
        self.assertEqual(execution1.runbook_version, "1.0")
        self.assertEqual(execution2.runbook_version, "2.0")


@pytest.mark.django_db
class AdminNoteTestCase(TestCase):
    """
    Test AdminNote model.

    Tests Requirement 34.9: Allow admins to add notes and tips.
    """

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="admin_user",
            email="admin@test.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

        self.doc = DocumentationPage.objects.create(
            title="Test Doc",
            slug="test-doc",
            content="Content",
            category=DocumentationPage.ARCHITECTURE,
            created_by=self.user,
        )

        self.runbook = Runbook.objects.create(
            title="Test Runbook",
            slug="test-runbook",
            description="Test",
            runbook_type=Runbook.MAINTENANCE,
            created_by=self.user,
        )

    def test_create_tip_note(self):
        """
        Test Requirement 34.9: Create admin tip.
        """
        note = AdminNote.objects.create(
            title="Helpful Tip",
            content="Always check logs before restarting services",
            note_type=AdminNote.TIP,
            documentation_page=self.doc,
            created_by=self.user,
        )

        self.assertEqual(note.note_type, AdminNote.TIP)
        self.assertEqual(note.documentation_page, self.doc)
        self.assertEqual(note.helpful_count, 0)
        self.assertFalse(note.is_pinned)

    def test_create_warning_note(self):
        """Test creating a warning note."""
        note = AdminNote.objects.create(
            title="Important Warning",
            content="Never run this command in production without backup",
            note_type=AdminNote.WARNING,
            runbook=self.runbook,
            created_by=self.user,
        )

        self.assertEqual(note.note_type, AdminNote.WARNING)
        self.assertEqual(note.runbook, self.runbook)

    def test_create_best_practice_note(self):
        """Test creating a best practice note."""
        note = AdminNote.objects.create(
            title="Best Practice",
            content="Always test in staging first",
            note_type=AdminNote.BEST_PRACTICE,
            created_by=self.user,
        )

        self.assertEqual(note.note_type, AdminNote.BEST_PRACTICE)

    def test_create_lesson_learned_note(self):
        """Test creating a lesson learned note."""
        note = AdminNote.objects.create(
            title="Lesson Learned",
            content="Database timeout was caused by missing index",
            note_type=AdminNote.LESSON_LEARNED,
            created_by=self.user,
        )

        self.assertEqual(note.note_type, AdminNote.LESSON_LEARNED)

    def test_mark_helpful(self):
        """Test marking note as helpful."""
        note = AdminNote.objects.create(
            title="Tip",
            content="Useful tip",
            note_type=AdminNote.TIP,
            created_by=self.user,
        )

        self.assertEqual(note.helpful_count, 0)

        note.mark_helpful()
        self.assertEqual(note.helpful_count, 1)

        note.mark_helpful()
        self.assertEqual(note.helpful_count, 2)

    def test_pin_note(self):
        """Test pinning a note."""
        note = AdminNote.objects.create(
            title="Important Note",
            content="Critical information",
            note_type=AdminNote.WARNING,
            created_by=self.user,
        )

        self.assertFalse(note.is_pinned)

        note.pin()
        self.assertTrue(note.is_pinned)

    def test_unpin_note(self):
        """Test unpinning a note."""
        note = AdminNote.objects.create(
            title="Note",
            content="Content",
            note_type=AdminNote.TIP,
            is_pinned=True,
            created_by=self.user,
        )

        self.assertTrue(note.is_pinned)

        note.unpin()
        self.assertFalse(note.is_pinned)

    def test_note_linked_to_documentation(self):
        """Test note linked to documentation page."""
        note = AdminNote.objects.create(
            title="Doc Note",
            content="Note about this documentation",
            note_type=AdminNote.TIP,
            documentation_page=self.doc,
            created_by=self.user,
        )

        self.assertEqual(note.documentation_page, self.doc)
        self.assertIn(note, self.doc.admin_notes.all())

    def test_note_linked_to_runbook(self):
        """Test note linked to runbook."""
        note = AdminNote.objects.create(
            title="Runbook Note",
            content="Important note about this runbook",
            note_type=AdminNote.WARNING,
            runbook=self.runbook,
            created_by=self.user,
        )

        self.assertEqual(note.runbook, self.runbook)
        self.assertIn(note, self.runbook.admin_notes.all())


@pytest.mark.django_db
class DocumentationIntegrationTestCase(TestCase):
    """
    Integration tests for complete documentation workflows.

    Tests all requirements together in realistic scenarios.
    """

    def setUp(self):
        """Set up test data."""
        self.admin = User.objects.create_user(
            username="admin",
            email="admin@test.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

    def test_complete_documentation_workflow(self):
        """Test complete documentation creation and usage workflow."""
        # Create architecture documentation
        arch_doc = DocumentationPage.objects.create(
            title="System Architecture",
            slug="system-architecture",
            content="# Architecture\n\nMulti-tenant platform...",
            summary="System architecture overview",
            category=DocumentationPage.ARCHITECTURE,
            status=DocumentationPage.DRAFT,
            version="1.0",
            created_by=self.admin,
        )

        # Publish it
        arch_doc.publish()
        self.assertEqual(arch_doc.status, DocumentationPage.PUBLISHED)

        # Add admin note
        note = AdminNote.objects.create(
            title="Architecture Tip",
            content="Remember to update this when adding new services",
            note_type=AdminNote.TIP,
            documentation_page=arch_doc,
            created_by=self.admin,
        )

        # Simulate views
        arch_doc.increment_view_count()
        arch_doc.increment_view_count()
        self.assertEqual(arch_doc.view_count, 2)

        # Mark note as helpful
        note.mark_helpful()
        self.assertEqual(note.helpful_count, 1)

    def test_complete_runbook_workflow(self):
        """Test complete runbook creation and execution workflow."""
        # Create disaster recovery runbook
        dr_runbook = Runbook.objects.create(
            title="Database Disaster Recovery",
            slug="db-disaster-recovery",
            description="Complete database recovery procedure",
            runbook_type=Runbook.DISASTER_RECOVERY,
            priority=Runbook.CRITICAL,
            status=Runbook.DRAFT,
            version="1.0",
            steps=[
                {
                    "title": "Download Backup",
                    "description": "Get latest backup from R2",
                    "commands": ["aws s3 cp s3://backups/latest.dump ."],
                },
                {
                    "title": "Restore Database",
                    "description": "Restore from backup file",
                    "commands": ["pg_restore -d jewelry_shop latest.dump"],
                },
            ],
            rto=timedelta(hours=1),
            rpo=timedelta(minutes=15),
            expected_duration=timedelta(minutes=45),
            verification_steps=[
                {
                    "title": "Check Data",
                    "description": "Verify data integrity",
                    "commands": ["psql -c 'SELECT COUNT(*) FROM tenants;'"],
                }
            ],
            created_by=self.admin,
        )

        # Activate runbook
        dr_runbook.activate()
        self.assertEqual(dr_runbook.status, Runbook.ACTIVE)

        # Execute runbook (successful)
        execution1 = RunbookExecution.objects.create(
            runbook=dr_runbook,
            runbook_version=dr_runbook.version,
            executed_by=self.admin,
        )
        execution1.complete(success=True, notes="Recovery completed successfully")

        # Execute again (failed)
        execution2 = RunbookExecution.objects.create(
            runbook=dr_runbook,
            runbook_version=dr_runbook.version,
            executed_by=self.admin,
        )
        execution2.complete(success=False, notes="Backup file corrupted")

        # Check statistics
        dr_runbook.refresh_from_db()
        self.assertEqual(dr_runbook.execution_count, 2)
        self.assertEqual(dr_runbook.success_count, 1)
        self.assertEqual(dr_runbook.failure_count, 1)
        self.assertEqual(dr_runbook.get_success_rate(), 0.5)

        # Add warning note
        warning = AdminNote.objects.create(
            title="Critical Warning",
            content="Always verify backup integrity before restoring",
            note_type=AdminNote.WARNING,
            runbook=dr_runbook,
            created_by=self.admin,
        )
        warning.pin()

        self.assertTrue(warning.is_pinned)

    def test_hierarchical_documentation_structure(self):
        """Test creating hierarchical documentation structure."""
        # Create root documentation
        root = DocumentationPage.objects.create(
            title="Platform Documentation",
            slug="platform-docs",
            content="Root documentation",
            category=DocumentationPage.ARCHITECTURE,
            created_by=self.admin,
        )

        # Create child pages
        child1 = DocumentationPage.objects.create(
            title="Database Architecture",
            slug="database-architecture",
            content="Database details",
            category=DocumentationPage.ARCHITECTURE,
            parent=root,
            order=1,
            created_by=self.admin,
        )

        child2 = DocumentationPage.objects.create(
            title="API Architecture",
            slug="api-architecture",
            content="API details",
            category=DocumentationPage.ARCHITECTURE,
            parent=root,
            order=2,
            created_by=self.admin,
        )

        # Create grandchild
        grandchild = DocumentationPage.objects.create(
            title="PostgreSQL Configuration",
            slug="postgresql-config",
            content="PostgreSQL setup",
            category=DocumentationPage.ARCHITECTURE,
            parent=child1,
            order=1,
            created_by=self.admin,
        )

        # Verify hierarchy
        self.assertEqual(root.children.count(), 2)
        self.assertIn(child1, root.children.all())
        self.assertIn(child2, root.children.all())
        self.assertEqual(grandchild.parent, child1)

        # Test breadcrumbs
        breadcrumbs = grandchild.get_breadcrumbs()
        self.assertEqual(len(breadcrumbs), 3)
        self.assertEqual(breadcrumbs[0][0], "Platform Documentation")
        self.assertEqual(breadcrumbs[1][0], "Database Architecture")
        self.assertEqual(breadcrumbs[2][0], "PostgreSQL Configuration")

    def test_multiple_runbook_types(self):
        """Test creating different types of runbooks."""
        # Incident response
        Runbook.objects.create(
            title="Security Incident Response",
            slug="security-incident",
            description="Handle security incidents",
            runbook_type=Runbook.INCIDENT_RESPONSE,
            priority=Runbook.CRITICAL,
            created_by=self.admin,
        )

        # Maintenance
        Runbook.objects.create(
            title="Monthly Maintenance",
            slug="monthly-maintenance",
            description="Routine monthly tasks",
            runbook_type=Runbook.MAINTENANCE,
            priority=Runbook.MEDIUM,
            created_by=self.admin,
        )

        # Deployment
        Runbook.objects.create(
            title="Production Deployment",
            slug="prod-deployment",
            description="Deploy to production",
            runbook_type=Runbook.DEPLOYMENT,
            priority=Runbook.HIGH,
            created_by=self.admin,
        )

        # Verify all created
        self.assertEqual(Runbook.objects.count(), 3)
        self.assertEqual(Runbook.objects.filter(runbook_type=Runbook.INCIDENT_RESPONSE).count(), 1)
        self.assertEqual(Runbook.objects.filter(runbook_type=Runbook.MAINTENANCE).count(), 1)
        self.assertEqual(Runbook.objects.filter(runbook_type=Runbook.DEPLOYMENT).count(), 1)

    def test_all_documentation_categories(self):
        """Test creating documentation in all categories."""
        categories = [
            (DocumentationPage.ARCHITECTURE, "Architecture Doc"),
            (DocumentationPage.ADMIN_GUIDE, "Admin Guide"),
            (DocumentationPage.TROUBLESHOOTING, "Troubleshooting Guide"),
            (DocumentationPage.API_DOCUMENTATION, "API Docs"),
            (DocumentationPage.FAQ, "FAQ"),
            (DocumentationPage.DEVELOPER_GUIDE, "Developer Guide"),
            (DocumentationPage.USER_GUIDE, "User Guide"),
        ]

        for category, title in categories:
            DocumentationPage.objects.create(
                title=title,
                slug=title.lower().replace(" ", "-"),
                content=f"Content for {title}",
                category=category,
                created_by=self.admin,
            )

        # Verify all categories have documentation
        self.assertEqual(DocumentationPage.objects.count(), 7)
        for category, _ in categories:
            self.assertTrue(DocumentationPage.objects.filter(category=category).exists())
