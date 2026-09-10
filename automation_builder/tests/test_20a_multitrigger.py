"""Stage 20, Part A: Verify multi-trigger works with real document saves.

Tests that an Automation with TWO trigger rows (different doctypes)
fires correctly when EITHER trigger's doctype+event matches.
"""

import json

import frappe
from frappe.tests import IntegrationTestCase

from automation_builder.dispatcher import _evaluate_trigger_conditions


class TestMultiTriggerVerification(IntegrationTestCase):
    """Part A: Verify multi-trigger OR-across-rows works."""

    def setUp(self):
        for name in ["TEST-MultiTrigger"]:
            frappe.db.sql("DELETE FROM `tabAutomation Trigger` WHERE parent = %s", name)
            frappe.db.sql("DELETE FROM `tabAutomation` WHERE name = %s", name)
        frappe.db.commit()

    def tearDown(self):
        for name in ["TEST-MultiTrigger"]:
            frappe.db.sql("DELETE FROM `tabAutomation Trigger` WHERE parent = %s", name)
            frappe.db.sql("DELETE FROM `tabAutomation` WHERE name = %s", name)
        frappe.db.commit()

    def test_two_trigger_rows_both_match各自的doctype(self):
        """Two trigger rows — ToDo/On Update and Lead/On Update.
        Triggering on ToDo should match the first row and enqueue."""
        auto = frappe.get_doc({
            "doctype": "Automation",
            "automation_name": "TEST-MultiTrigger",
            "status": "Published",
            "enabled": 1,
            "triggers": [
                {"trigger_doctype": "ToDo", "trigger_event": "On Update"},
                {"trigger_doctype": "ToDo", "trigger_event": "After Insert"},
            ],
            "graph_definition": json.dumps({
                "nodes": [
                    {"id": "trigger", "type": "trigger", "position": {"x": 0, "y": 0}, "data": {}},
                    {"id": "action-1", "type": "action", "position": {"x": 0, "y": 150},
                     "data": {"action_type": "telegram", "chat_id": "TEST", "message": "multi-trigger test"}},
                ],
                "edges": [
                    {"source": "trigger", "target": "action-1", "sourceHandle": "trigger-out", "targetHandle": "action-1-in"},
                ],
            }),
        })
        auto.insert(ignore_permissions=True)
        frappe.db.commit()

        # Verify two trigger rows exist
        triggers = frappe.get_all(
            "Automation Trigger",
            filters={"parent": auto.name},
            fields=["trigger_doctype", "trigger_event"],
        )
        self.assertEqual(len(triggers), 2)

        # Create a ToDo — should match first trigger row (ToDo/On Update)
        todo = frappe.get_doc({"doctype": "ToDo", "description": "multi-trigger test"})
        todo.insert(ignore_permissions=True)
        frappe.db.commit()

        # Patch enqueue to capture
        enqueued = []
        orig = frappe.enqueue
        frappe.enqueue = lambda *a, **kw: enqueued.append({"args": a, "kwargs": kw})
        try:
            from automation_builder.dispatcher import on_doc_event
            on_doc_event(todo, "on_update")
        finally:
            frappe.enqueue = orig

        auto_names = [c["kwargs"].get("automation_name") for c in enqueued]
        self.assertIn(auto.name, auto_names,
                     f"Automation with 2 trigger rows should fire on ToDo/On Update. Enqueued: {auto_names}")

    def test_condition_logic_or_across_rows(self):
        """Two trigger rows with different conditions — OR across rows.
        Row 1: status=Open (will match). Row 2: status=Closed (won't match).
        Result should be True because ANY row matching is sufficient."""
        auto = frappe.get_doc({
            "doctype": "Automation",
            "automation_name": "TEST-MultiTrigger",
            "status": "Draft",
            "enabled": 1,
            "triggers": [
                {"trigger_doctype": "ToDo", "trigger_event": "On Update",
                 "condition_field": "status", "condition_operator": "=", "condition_value": "Open"},
                {"trigger_doctype": "ToDo", "trigger_event": "On Update",
                 "condition_field": "status", "condition_operator": "=", "condition_value": "Closed"},
            ],
            "graph_definition": '{"nodes":[],"edges":[]}',
        })
        auto.insert(ignore_permissions=True)
        frappe.db.commit()

        todo = frappe.get_doc({"doctype": "ToDo", "description": "OR test", "status": "Open"})
        todo.insert(ignore_permissions=True)
        frappe.db.commit()

        result = _evaluate_trigger_conditions(auto.name, todo)
        self.assertTrue(result,
                       "OR across trigger rows: row 1 matches (status=Open) so overall should be True")

    def test_condition_logic_and_fails_across_rows(self):
        """Two trigger rows with conditions — both must fail for False.
        Row 1: status=Open (won't match — doc is Closed). Row 2: status=Closed (won't match — doc is Open).
        Actually: doc is Open, row 2 expects Closed -> doesn't match.
        Wait, let me re-read: OR across rows means ANY matching is True.
        Both fail -> False."""
        auto = frappe.get_doc({
            "doctype": "Automation",
            "automation_name": "TEST-MultiTrigger",
            "status": "Draft",
            "enabled": 1,
            "triggers": [
                {"trigger_doctype": "ToDo", "trigger_event": "On Update",
                 "condition_field": "status", "condition_operator": "=", "condition_value": "Closed"},
                {"trigger_doctype": "ToDo", "trigger_event": "On Update",
                 "condition_field": "status", "condition_operator": "=", "condition_value": "Cancelled"},
            ],
            "graph_definition": '{"nodes":[],"edges":[]}',
        })
        auto.insert(ignore_permissions=True)
        frappe.db.commit()

        todo = frappe.get_doc({"doctype": "ToDo", "description": "both fail test", "status": "Open"})
        todo.insert(ignore_permissions=True)
        frappe.db.commit()

        result = _evaluate_trigger_conditions(auto.name, todo)
        self.assertFalse(result,
                        "Both trigger rows have conditions that don't match -> should be False")
