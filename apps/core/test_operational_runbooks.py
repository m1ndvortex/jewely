"""
Integration tests for operational runbooks.

Tests Task 25.3: Create operational runbooks
Tests Requirement 34: Knowledge Base and Documentation

These tests verify that operational runbooks are created correctly
and satisfy all requirements without using mocks.
"""

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

import pytest

from apps.core.documentation_models import AdminNote, Runbook, RunbookExecution

User = get_user_model()


@pytest.mark.django_db
class OperationalRunbooksTestCase(TestCase):
    """
    Test operational runbooks creation and functionality.

    Tests Requirements:
    - 34.5: Incident response runbooks with documented procedures
    - 34.6: Maintenance runbooks for routine tasks
    - 34.7: Disaster recovery runbooks with step-by-step procedures
    - 34.8: Track runbook versions and updates
    - 34.9: Allow admins to add notes and tips
    """

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username="admin_user",
            email="admin@test.com",
            password="testpass123",
            role=User.PLATFORM_ADMIN,
        )

    def test_management_command_creates_runbooks(self):
        """
        Test that management command creates all operational runbooks.
        """
        # Run the management command
        out = StringIO()
        call_command("create_operational_runbooks", stdout=out)

        # Verify output
        output = out.getvalue()
        self.assertIn("Successfully created operational runbooks", output)

        # Verify runbooks were created
        self.assertGreater(Runbook.objects.count(), 0)
        self.assertGreater(AdminNote.objects.count(), 0)

    def test_incident_response_runbooks_created(self):
        """
        Test Requirement 34.5: Incident response runbooks with documented procedures.
        """
        # Run the management command
        call_command("create_operational_runbooks", verbosity=0)

        # Verify incident response runbooks exist
        incident_runbooks = Runbook.objects.filter(runbook_type=Runbook.INCIDENT_RESPONSE)
        self.assertGreaterEqual(incident_runbooks.count(), 3)

        # Check specific runbooks
        db_outage = Runbook.objects.filter(slug="incident-database-outage").first()
        self.assertIsNotNone(db_outage)
        self.assertEqual(db_outage.priority, Runbook.CRITICAL)
        self.assertEqual(db_outage.status, Runbook.ACTIVE)
        self.assertIsNotNone(db_outage.rto)
        self.assertGreater(len(db_outage.steps), 0)
        self.assertGreater(len(db_outage.verification_steps), 0)

        app_crash = Runbook.objects.filter(slug="incident-application-crash").first()
        self.assertIsNotNone(app_crash)
        self.assertEqual(app_crash.priority, Runbook.CRITICAL)

        security_breach = Runbook.objects.filter(slug="incident-security-breach").first()
        self.assertIsNotNone(security_breach)
        self.assertEqual(security_breach.priority, Runbook.CRITICAL)

    def test_maintenance_runbooks_created(self):
        """
        Test Requirement 34.6: Maintenance runbooks for routine tasks.
        """
        # Run the management command
        call_command("create_operational_runbooks", verbosity=0)

        # Verify maintenance runbooks exist
        maintenance_runbooks = Runbook.objects.filter(runbook_type=Runbook.MAINTENANCE)
        self.assertGreaterEqual(maintenance_runbooks.count(), 3)

        # Check specific runbooks
        db_maintenance = Runbook.objects.filter(slug="maintenance-database-routine").first()
        self.assertIsNotNone(db_maintenance)
        self.assertEqual(db_maintenance.runbook_type, Runbook.MAINTENANCE)
        self.assertGreater(len(db_maintenance.steps), 0)
        self.assertIsNotNone(db_maintenance.expected_duration)

        ssl_renewal = Runbook.objects.filter(slug="maintenance-ssl-certificate-renewal").first()
        self.assertIsNotNone(ssl_renewal)
        self.assertEqual(ssl_renewal.priority, Runbook.HIGH)

        dependency_updates = Runbook.objects.filter(slug="maintenance-dependency-updates").first()
        self.assertIsNotNone(dependency_updates)

    def test_disaster_recovery_runbooks_created(self):
        """
        Test Requirement 34.7: Disaster recovery runbooks with step-by-step procedures.
        """
        # Run the management command
        call_command("create_operational_runbooks", verbosity=0)

        # Verify disaster recovery runbooks exist
        dr_runbooks = Runbook.objects.filter(runbook_type=Runbook.DISASTER_RECOVERY)
        self.assertGreaterEqual(dr_runbooks.count(), 2)

        # Check database disaster recovery
        db_recovery = Runbook.objects.filter(slug="disaster-recovery-database-restore").first()
        self.assertIsNotNone(db_recovery)
        self.assertEqual(db_recovery.priority, Runbook.CRITICAL)
        self.assertIsNotNone(db_recovery.rto)
        self.assertIsNotNone(db_recovery.rpo)
        self.assertGreater(len(db_recovery.steps), 0)
        self.assertGreater(len(db_recovery.verification_steps), 0)

        # Verify step-by-step procedures exist
        self.assertIn("title", db_recovery.steps[0])
        self.assertIn("description", db_recovery.steps[0])
        self.assertIn("commands", db_recovery.steps[0])

        # Check complete system recovery
        system_recovery = Runbook.objects.filter(slug="disaster-recovery-complete-system").first()
        self.assertIsNotNone(system_recovery)
        self.assertEqual(system_recovery.priority, Runbook.CRITICAL)
        self.assertIsNotNone(system_recovery.rto)
        self.assertIsNotNone(system_recovery.rpo)

    def test_runbook_version_tracking(self):
        """
        Test Requirement 34.8: Track runbook versions and updates.
        """
        # Run the management command
        call_command("create_operational_runbooks", verbosity=0)

        # Get a runbook
        runbook = Runbook.objects.filter(slug="incident-database-outage").first()
        self.assertIsNotNone(runbook)

        # Verify version field exists and has value
        self.assertIsNotNone(runbook.version)
        self.assertEqual(runbook.version, "1.0")

        # Verify changelog field exists
        self.assertIsNotNone(runbook.changelog)

        # Test version update
        runbook.version = "1.1"
        runbook.changelog = "Updated step 3 with new command"
        runbook.save()

        # Verify update
        updated_runbook = Runbook.objects.get(id=runbook.id)
        self.assertEqual(updated_runbook.version, "1.1")
        self.assertIn("Updated step 3", updated_runbook.changelog)

    def test_runbook_execution_tracking(self):
        """
        Test Requirement 34.8: Track runbook versions and updates (execution tracking).
        """
        # Run the management command
        call_command("create_operational_runbooks", verbosity=0)

        # Get a runbook
        runbook = Runbook.objects.filter(slug="incident-database-outage").first()
        self.assertIsNotNone(runbook)

        # Create an execution
        execution = RunbookExecution.objects.create(
            runbook=runbook,
            runbook_version=runbook.version,
            executed_by=self.user,
            status=RunbookExecution.IN_PROGRESS,
        )

        # Verify execution created
        self.assertEqual(execution.runbook, runbook)
        self.assertEqual(execution.runbook_version, "1.0")
        self.assertEqual(execution.status, RunbookExecution.IN_PROGRESS)

        # Complete execution
        execution.complete(success=True, notes="All steps completed successfully")

        # Verify completion
        self.assertEqual(execution.status, RunbookExecution.COMPLETED)
        self.assertIsNotNone(execution.completed_at)
        self.assertIsNotNone(execution.duration)

        # Verify runbook statistics updated
        runbook.refresh_from_db()
        self.assertEqual(runbook.execution_count, 1)
        self.assertEqual(runbook.success_count, 1)
        self.assertIsNotNone(runbook.last_executed_at)

    def test_admin_notes_created(self):
        """
        Test Requirement 34.9: Allow admins to add notes and tips for other admins.
        """
        # Run the management command
        call_command("create_operational_runbooks", verbosity=0)

        # Verify admin notes exist
        notes = AdminNote.objects.all()
        self.assertGreaterEqual(notes.count(), 8)

        # Check different note types exist
        tips = AdminNote.objects.filter(note_type=AdminNote.TIP)
        self.assertGreater(tips.count(), 0)

        warnings = AdminNote.objects.filter(note_type=AdminNote.WARNING)
        self.assertGreater(warnings.count(), 0)

        best_practices = AdminNote.objects.filter(note_type=AdminNote.BEST_PRACTICE)
        self.assertGreater(best_practices.count(), 0)

        lessons_learned = AdminNote.objects.filter(note_type=AdminNote.LESSON_LEARNED)
        self.assertGreater(lessons_learned.count(), 0)

    def test_admin_notes_pinning(self):
        """
        Test Requirement 34.9: Admin notes can be pinned for visibility.
        """
        # Run the management command
        call_command("create_operational_runbooks", verbosity=0)

        # Verify pinned notes exist
        pinned_notes = AdminNote.objects.filter(is_pinned=True)
        self.assertGreater(pinned_notes.count(), 0)

        # Test pinning functionality
        note = AdminNote.objects.filter(is_pinned=False).first()
        if note:
            note.pin()
            note.refresh_from_db()
            self.assertTrue(note.is_pinned)

            note.unpin()
            note.refresh_from_db()
            self.assertFalse(note.is_pinned)

    def test_admin_notes_helpful_tracking(self):
        """
        Test Requirement 34.9: Track helpful count for admin notes.
        """
        # Run the management command
        call_command("create_operational_runbooks", verbosity=0)

        # Get a note
        note = AdminNote.objects.first()
        self.assertIsNotNone(note)

        # Initial helpful count should be 0
        self.assertEqual(note.helpful_count, 0)

        # Mark as helpful
        note.mark_helpful()
        note.refresh_from_db()
        self.assertEqual(note.helpful_count, 1)

        # Mark as helpful again
        note.mark_helpful()
        note.refresh_from_db()
        self.assertEqual(note.helpful_count, 2)


@pytest.mark.django_db
class RunbookContentValidationTestCase(TestCase):
    """
    Test that runbooks have all required content and structure.
    """

    def setUp(self):
        """Set up test data."""
        call_command("create_operational_runbooks", verbosity=0)

    def test_all_runbooks_have_required_fields(self):
        """
        Verify all runbooks have required fields populated.
        """
        runbooks = Runbook.objects.all()
        self.assertGreater(runbooks.count(), 0)

        for runbook in runbooks:
            # Required fields
            self.assertIsNotNone(runbook.title)
            self.assertIsNotNone(runbook.slug)
            self.assertIsNotNone(runbook.description)
            self.assertIsNotNone(runbook.runbook_type)
            self.assertIsNotNone(runbook.priority)
            self.assertIsNotNone(runbook.status)
            self.assertIsNotNone(runbook.version)

            # Steps should be a list with at least one step
            self.assertIsInstance(runbook.steps, list)
            self.assertGreater(len(runbook.steps), 0)

            # Each step should have required fields
            for step in runbook.steps:
                self.assertIn("title", step)
                self.assertIn("description", step)
                self.assertIn("commands", step)

            # Verification steps should exist
            self.assertIsInstance(runbook.verification_steps, list)
            self.assertGreater(len(runbook.verification_steps), 0)

            # Tags should be a list
            self.assertIsInstance(runbook.tags, list)
            self.assertGreater(len(runbook.tags), 0)

    def test_critical_runbooks_have_rto(self):
        """
        Verify critical runbooks have RTO defined.
        """
        critical_runbooks = Runbook.objects.filter(priority=Runbook.CRITICAL)
        self.assertGreater(critical_runbooks.count(), 0)

        for runbook in critical_runbooks:
            if runbook.runbook_type in [Runbook.INCIDENT_RESPONSE, Runbook.DISASTER_RECOVERY]:
                self.assertIsNotNone(
                    runbook.rto, f"Runbook {runbook.title} should have RTO defined"
                )

    def test_disaster_recovery_runbooks_have_rpo(self):
        """
        Verify disaster recovery runbooks have RPO defined.
        """
        dr_runbooks = Runbook.objects.filter(runbook_type=Runbook.DISASTER_RECOVERY)
        self.assertGreater(dr_runbooks.count(), 0)

        for runbook in dr_runbooks:
            self.assertIsNotNone(runbook.rpo, f"DR runbook {runbook.title} should have RPO")

    def test_runbooks_have_expected_duration(self):
        """
        Verify runbooks have expected duration defined.
        """
        runbooks = Runbook.objects.exclude(runbook_type=Runbook.INCIDENT_RESPONSE)

        for runbook in runbooks:
            if runbook.runbook_type in [Runbook.MAINTENANCE, Runbook.DEPLOYMENT]:
                self.assertIsNotNone(
                    runbook.expected_duration,
                    f"Runbook {runbook.title} should have expected duration",
                )


@pytest.mark.django_db
class RunbookCoverageTestCase(TestCase):
    """
    Test that all required runbook types are created.
    """

    def setUp(self):
        """Set up test data."""
        call_command("create_operational_runbooks", verbosity=0)

    def test_incident_response_coverage(self):
        """
        Test that key incident response scenarios are covered.
        """
        required_incidents = [
            "incident-database-outage",
            "incident-application-crash",
            "incident-security-breach",
        ]

        for slug in required_incidents:
            runbook = Runbook.objects.filter(slug=slug).first()
            self.assertIsNotNone(runbook, f"Missing incident runbook: {slug}")
            self.assertEqual(runbook.runbook_type, Runbook.INCIDENT_RESPONSE)
            self.assertEqual(runbook.priority, Runbook.CRITICAL)

    def test_maintenance_coverage(self):
        """
        Test that key maintenance tasks are covered.
        """
        required_maintenance = [
            "maintenance-database-routine",
            "maintenance-ssl-certificate-renewal",
            "maintenance-dependency-updates",
        ]

        for slug in required_maintenance:
            runbook = Runbook.objects.filter(slug=slug).first()
            self.assertIsNotNone(runbook, f"Missing maintenance runbook: {slug}")
            self.assertEqual(runbook.runbook_type, Runbook.MAINTENANCE)

    def test_disaster_recovery_coverage(self):
        """
        Test that disaster recovery scenarios are covered.
        """
        required_dr = [
            "disaster-recovery-database-restore",
            "disaster-recovery-complete-system",
        ]

        for slug in required_dr:
            runbook = Runbook.objects.filter(slug=slug).first()
            self.assertIsNotNone(runbook, f"Missing DR runbook: {slug}")
            self.assertEqual(runbook.runbook_type, Runbook.DISASTER_RECOVERY)
            self.assertEqual(runbook.priority, Runbook.CRITICAL)

    def test_deployment_coverage(self):
        """
        Test that deployment runbooks exist.
        """
        deployment_runbooks = Runbook.objects.filter(runbook_type=Runbook.DEPLOYMENT)
        self.assertGreater(deployment_runbooks.count(), 0)

    def test_troubleshooting_coverage(self):
        """
        Test that troubleshooting runbooks exist.
        """
        troubleshooting_runbooks = Runbook.objects.filter(runbook_type=Runbook.TROUBLESHOOTING)
        self.assertGreater(troubleshooting_runbooks.count(), 0)

    def test_backup_restore_coverage(self):
        """
        Test that backup and restore runbooks exist.
        """
        backup_runbooks = Runbook.objects.filter(runbook_type=Runbook.BACKUP_RESTORE)
        self.assertGreater(backup_runbooks.count(), 0)


@pytest.mark.django_db
class AdminNotesCoverageTestCase(TestCase):
    """
    Test that admin notes cover important topics.
    """

    def setUp(self):
        """Set up test data."""
        call_command("create_operational_runbooks", verbosity=0)

    def test_security_warnings_exist(self):
        """
        Test that security warnings are created.
        """
        warnings = AdminNote.objects.filter(note_type=AdminNote.WARNING)
        self.assertGreater(warnings.count(), 0)

        # Check for critical security warning
        security_warning = AdminNote.objects.filter(
            note_type=AdminNote.WARNING, tags__contains=["security"]
        ).first()
        self.assertIsNotNone(security_warning)
        self.assertTrue(security_warning.is_pinned)

    def test_best_practices_exist(self):
        """
        Test that best practices are documented.
        """
        best_practices = AdminNote.objects.filter(note_type=AdminNote.BEST_PRACTICE)
        self.assertGreater(best_practices.count(), 0)

    def test_operational_tips_exist(self):
        """
        Test that operational tips are provided.
        """
        tips = AdminNote.objects.filter(note_type=AdminNote.TIP)
        self.assertGreater(tips.count(), 0)

    def test_lessons_learned_exist(self):
        """
        Test that lessons learned are documented.
        """
        lessons = AdminNote.objects.filter(note_type=AdminNote.LESSON_LEARNED)
        self.assertGreater(lessons.count(), 0)


@pytest.mark.django_db
class RunbookIdempotencyTestCase(TestCase):
    """
    Test that management command is idempotent.
    """

    def test_command_can_run_multiple_times(self):
        """
        Test that running the command multiple times doesn't create duplicates.
        """
        # Run command first time
        call_command("create_operational_runbooks", verbosity=0)
        first_count = Runbook.objects.count()
        first_notes_count = AdminNote.objects.count()

        # Run command second time
        call_command("create_operational_runbooks", verbosity=0)
        second_count = Runbook.objects.count()
        second_notes_count = AdminNote.objects.count()

        # Counts should be the same (update_or_create prevents duplicates)
        self.assertEqual(first_count, second_count)
        self.assertEqual(first_notes_count, second_notes_count)

    def test_command_updates_existing_runbooks(self):
        """
        Test that running command again updates existing runbooks.
        """
        # Run command first time
        call_command("create_operational_runbooks", verbosity=0)

        # Get a runbook and modify it
        runbook = Runbook.objects.filter(slug="incident-database-outage").first()
        original_title = runbook.title
        runbook.title = "Modified Title"
        runbook.save()

        # Run command again
        call_command("create_operational_runbooks", verbosity=0)

        # Verify title was restored to original
        runbook.refresh_from_db()
        self.assertEqual(runbook.title, original_title)
