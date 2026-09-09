"""Tests for the Stage 17a migration patch.

Tests that existing Automation records are correctly migrated from old format
(workflow_json + flat trigger fields) to new graph-based model
(graph_definition + Automation Trigger child table).
"""

import json

import frappe
from frappe.tests import IntegrationTestCase

from automation_builder.migrate_17a import run as run_migration


class TestMigrationPatch(IntegrationTestCase):
    """Test the migration patch converts old format to new format correctly."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
        # Ensure clean state
        self._cleanup_test_automations()

    def tearDown(self):
        """Clean up test data."""
        super().tearDown()
        self._cleanup_test_automations()

    def _cleanup_test_automations(self):
        """Remove test automations created during tests."""
        frappe.db.sql(
            """DELETE FROM `tabAutomation Trigger` WHERE parent LIKE 'TEST-%'"""
        )
        frappe.db.sql(
            """DELETE FROM `tabAutomation` WHERE name LIKE 'TEST-%'"""
        )
        frappe.db.commit()

    def _create_legacy_automation(self, name, trigger_doctype="ToDo",
                                   trigger_event="On Update",
                                   condition_field="status",
                                   condition_operator="=",
                                   condition_value="Open",
                                   enabled=True,
                                   workflow_json=None):
        """Create an automation using the old format (flat fields + workflow_json)."""
        auto = frappe.new_doc("Automation")
        auto.name = name
        auto.automation_name = name
        auto.trigger_doctype = trigger_doctype
        auto.trigger_event = trigger_event
        auto.condition_field = condition_field
        auto.condition_operator = condition_operator
        auto.condition_value = condition_value
        auto.enabled = 1 if enabled else 0

        if workflow_json:
            auto.workflow_json = workflow_json
        else:
            # Create a simple workflow_json with trigger + condition + action
            auto.workflow_json = json.dumps({
                "nodes": [
                    {"id": "trigger", "type": "trigger", "position": {"x": 0, "y": 0}, "data": {}},
                    {"id": "condition", "type": "condition", "position": {"x": 0, "y": 150}, "data": {"condition_field": "status", "condition_operator": "=", "condition_value": "Open"}},
                    {"id": "action-1", "type": "action", "position": {"x": 0, "y": 300}, "data": {"action_type": "update_field", "target": "Same Document", "field_mapping": [{"target_field": "priority", "source_value": "High"}]}},
                ],
                "edges": [
                    {"id": "e-trigger-condition", "source": "trigger", "target": "condition"},
                    {"id": "e-condition-action", "source": "condition", "target": "action-1"},
                ],
            })

        auto.insert(ignore_permissions=True)
        frappe.db.commit()
        return auto.name

    def test_migration_sets_status_from_enabled(self):
        """Test that migration sets status based on enabled flag."""
        name = self._create_legacy_automation("TEST-MigrationStatus", enabled=True)
        run_migration()

        doc = frappe.get_doc("Automation", name)
        self.assertEqual(doc.status, "Published")

    def test_migration_sets_status_disabled(self):
        """Test that disabled automations get Draft status."""
        name = self._create_legacy_automation("TEST-MigrationDraft", enabled=False)
        run_migration()

        doc = frappe.get_doc("Automation", name)
        self.assertEqual(doc.status, "Draft")

    def test_migration_populates_triggers_table(self):
        """Test that migration populates triggers table from flat fields."""
        name = self._create_legacy_automation(
            "TEST-MigrationTriggers",
            trigger_doctype="ToDo",
            trigger_event="On Update",
            condition_field="status",
            condition_operator="=",
            condition_value="Open",
        )
        run_migration()

        doc = frappe.get_doc("Automation", name)
        self.assertEqual(len(doc.triggers), 1)
        trigger = doc.triggers[0]
        self.assertEqual(trigger.trigger_doctype, "ToDo")
        self.assertEqual(trigger.trigger_event, "On Update")
        self.assertEqual(trigger.condition_field, "status")
        self.assertEqual(trigger.condition_operator, "=")
        self.assertEqual(trigger.condition_value, "Open")

    def test_migration_preserves_workflow_json_as_graph(self):
        """Test that workflow_json is converted to graph_definition."""
        workflow = {
            "nodes": [
                {"id": "trigger", "type": "trigger", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "action-1", "type": "action", "position": {"x": 0, "y": 150}, "data": {"action_type": "telegram", "chat_id": "123456", "message": "Test"}},
            ],
            "edges": [
                {"id": "e-trigger-action", "source": "trigger", "target": "action-1"},
            ],
        }
        name = self._create_legacy_automation(
            "TEST-MigrationGraph",
            workflow_json=json.dumps(workflow),
        )
        run_migration()

        doc = frappe.get_doc("Automation", name)
        self.assertIsNotNone(doc.graph_definition)

        graph = json.loads(doc.graph_definition)
        self.assertEqual(len(graph["nodes"]), 2)
        self.assertEqual(len(graph["edges"]), 1)
        self.assertEqual(graph["nodes"][0]["id"], "trigger")
        self.assertEqual(graph["nodes"][1]["id"], "action-1")

    def test_migration_preserves_legacy_fields(self):
        """Test that legacy fields are preserved in hidden fields."""
        name = self._create_legacy_automation(
            "TEST-MigrationLegacy",
            trigger_doctype="ToDo",
            trigger_event="After Insert",
        )
        run_migration()

        doc = frappe.get_doc("Automation", name)
        self.assertEqual(doc.trigger_doctype, "ToDo")
        self.assertEqual(doc.trigger_event, "After Insert")
        self.assertIsNotNone(doc.workflow_json)

    def test_migration_idempotent(self):
        """Test that running migration twice doesn't duplicate data."""
        name = self._create_legacy_automation("TEST-MigrationIdempotent")
        run_migration()
        run_migration()

        doc = frappe.get_doc("Automation", name)
        self.assertEqual(len(doc.triggers), 1)

    def test_migration_empty_workflow(self):
        """Test migration handles empty/missing workflow_json."""
        auto = frappe.new_doc("Automation")
        auto.name = "TEST-MigrationEmpty"
        auto.automation_name = "TEST-MigrationEmpty"
        auto.trigger_doctype = "ToDo"
        auto.trigger_event = "On Update"
        auto.enabled = 1
        auto.insert(ignore_permissions=True)
        frappe.db.commit()

        run_migration()

        doc = frappe.get_doc("Automation", "TEST-MigrationEmpty")
        self.assertEqual(doc.status, "Published")
        self.assertEqual(len(doc.triggers), 1)
        # graph_definition may be empty or None
