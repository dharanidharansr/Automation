"""Tests for Stage 17b-verify: Live governance + regression re-check."""

import frappe
from frappe.tests import IntegrationTestCase

from automation_builder.dispatcher import (
    _evaluate_trigger_conditions,
    _extract_actions_from_graph,
)


class TestLiveDraftPublishedExecution(IntegrationTestCase):
    """Test that Draft automations don't execute and Published ones do."""

    def setUp(self):
        """Clean up any leftover test automations."""
        for name in ["TEST-Draft-Verify", "TEST-Published-Verify", "TEST-Disabled-Published"]:
            if frappe.db.exists("Automation", name):
                frappe.delete_doc("Automation", name, force=True)
        frappe.db.commit()

    def tearDown(self):
        """Clean up test automations."""
        for name in ["TEST-Draft-Verify", "TEST-Published-Verify", "TEST-Disabled-Published"]:
            if frappe.db.exists("Automation", name):
                frappe.delete_doc("Automation", name, force=True)
        frappe.db.commit()

    def test_draft_automation_not_enqueued(self):
        """Draft automation should not be matched by on_doc_event."""
        # Create a Draft automation
        auto = frappe.get_doc({
            "doctype": "Automation",
            "automation_name": "TEST-Draft-Verify",
            "status": "Draft",
            "enabled": 1,
            "triggers": [{
                "trigger_doctype": "ToDo",
                "trigger_event": "On Update",
                "condition_field": "",
                "condition_operator": "=",
                "condition_value": "",
            }],
            "graph_definition": '{"nodes":[{"id":"trigger","type":"trigger","position":{"x":0,"y":0},"data":{"trigger_doctype":"ToDo","trigger_event":"On Update"}},{"id":"action-1","type":"action","position":{"x":0,"y":170},"data":{"action_type":"create_document","target_doctype":"ToDo"}}],"edges":[{"source":"trigger","target":"action-1","sourceHandle":"trigger-out","targetHandle":"action-1-in"}]}',
        })
        auto.insert(ignore_permissions=True)
        frappe.db.commit()

        # Query automations as on_doc_event would
        automations = frappe.get_all(
            "Automation",
            filters={
                "enabled": 1,
                "status": "Published",
                "trigger_doctype": "ToDo",
                "trigger_event": "On Update",
            },
            fields=["name"],
        )

        # Draft automation should NOT appear
        auto_names = [a.name for a in automations]
        self.assertNotIn(auto.name, auto_names,
                        "Draft automation should not be matched by dispatcher")

        # Cleanup
        frappe.delete_doc("Automation", auto.name, force=True)
        frappe.db.commit()

    def test_published_automation_is_enqueued(self):
        """Published automation should be matched by on_doc_event."""
        # Create a Published automation
        auto = frappe.get_doc({
            "doctype": "Automation",
            "automation_name": "TEST-Published-Verify",
            "status": "Published",
            "enabled": 1,
            "triggers": [{
                "trigger_doctype": "ToDo",
                "trigger_event": "On Update",
                "condition_field": "",
                "condition_operator": "=",
                "condition_value": "",
            }],
            "graph_definition": '{"nodes":[{"id":"trigger","type":"trigger","position":{"x":0,"y":0},"data":{"trigger_doctype":"ToDo","trigger_event":"On Update"}},{"id":"action-1","type":"action","position":{"x":0,"y":170},"data":{"action_type":"create_document","target_doctype":"ToDo"}}],"edges":[{"source":"trigger","target":"action-1","sourceHandle":"trigger-out","targetHandle":"action-1-in"}]}',
        })
        auto.insert(ignore_permissions=True)
        frappe.db.commit()

        # Verify the automation exists in the database
        self.assertTrue(frappe.db.exists("Automation", auto.name))

        # Verify the trigger exists
        triggers = frappe.get_all(
            "Automation Trigger",
            filters={"parent": auto.name},
            fields=["trigger_doctype", "trigger_event"],
        )
        self.assertEqual(len(triggers), 1)
        self.assertEqual(triggers[0].trigger_doctype, "ToDo")
        self.assertEqual(triggers[0].trigger_event, "On Update")

        # Query automations using the same SQL as the dispatcher
        automations = frappe.db.sql("""
            SELECT DISTINCT a.name
            FROM `tabAutomation` a
            INNER JOIN `tabAutomation Trigger` at
                ON at.parent = a.name
            WHERE a.enabled = 1
                AND a.status = 'Published'
                AND at.trigger_doctype = %s
                AND at.trigger_event = %s
        """, ("ToDo", "On Update"), as_dict=True)

        # Published automation SHOULD appear
        auto_names = [a.name for a in automations]
        self.assertIn(auto.name, auto_names,
                     "Published automation should be matched by dispatcher")

        # Cleanup
        frappe.delete_doc("Automation", auto.name, force=True)
        frappe.db.commit()

    def test_disabled_published_not_enqueued(self):
        """Published but disabled automation should not be matched."""
        auto = frappe.get_doc({
            "doctype": "Automation",
            "automation_name": "TEST-Disabled-Published",
            "status": "Published",
            "enabled": 0,
            "triggers": [{
                "trigger_doctype": "ToDo",
                "trigger_event": "On Update",
                "condition_field": "",
                "condition_operator": "=",
                "condition_value": "",
            }],
            "graph_definition": '{"nodes":[],"edges":[]}',
        })
        auto.insert(ignore_permissions=True)
        frappe.db.commit()

        automations = frappe.get_all(
            "Automation",
            filters={
                "enabled": 1,
                "status": "Published",
                "trigger_doctype": "ToDo",
                "trigger_event": "On Update",
            },
            fields=["name"],
        )

        auto_names = [a.name for a in automations]
        self.assertNotIn(auto.name, auto_names,
                        "Disabled automation should not be matched even if Published")

        frappe.delete_doc("Automation", auto.name, force=True)
        frappe.db.commit()


class TestUIPermissionGating(IntegrationTestCase):
    """Test that can_publish API enforces System Manager role."""

    def test_can_publish_returns_boolean(self):
        """can_publish should return a boolean."""
        from automation_builder.api import can_publish
        result = can_publish()
        self.assertIsInstance(result, bool)

    def test_system_manager_can_publish(self):
        """System Manager should be able to publish."""
        from automation_builder.api import can_publish
        # Administrator has System Manager role
        frappe.set_user("Administrator")
        result = can_publish()
        self.assertTrue(result, "System Manager should be able to publish")

    def test_non_system_manager_cannot_publish(self):
        """Non-System Manager should not be able to publish."""
        from automation_builder.api import can_publish

        # Create a test user with only Automation User role
        test_user = "test_automation_user@example.com"
        if not frappe.db.exists("User", test_user):
            user = frappe.get_doc({
                "doctype": "User",
                "email": test_user,
                "first_name": "Test",
                "last_name": "Automation User",
                "new_password": "test123",
                "roles": [{"role": "Automation User"}],
            })
            user.insert(ignore_permissions=True)
            frappe.db.commit()

        frappe.set_user(test_user)
        result = can_publish()
        self.assertFalse(result, "Non-System Manager should not be able to publish")

        # Reset to Administrator
        frappe.set_user("Administrator")


class TestGraphSchemaInteraction(IntegrationTestCase):
    """Test graph interactions that were previously fragile."""

    def test_drag_to_add_node_from_handle(self):
        """Test that adding a node from a handle creates proper edges."""
        graph = {
            "nodes": [
                {"id": "trigger", "type": "trigger", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "condition", "type": "condition", "position": {"x": 0, "y": 170}, "data": {}},
            ],
            "edges": [
                {"source": "trigger", "target": "condition", "sourceHandle": "trigger-out", "targetHandle": "condition-in"},
            ],
        }

        # Simulate adding an action from condition's handle
        new_node = {"id": "action-1", "type": "action", "position": {"x": 0, "y": 340}, "data": {"action_type": "send_email"}}
        new_edge = {"source": "condition", "target": "action-1", "sourceHandle": "condition-out", "targetHandle": "action-1-in"}

        graph["nodes"].append(new_node)
        graph["edges"].append(new_edge)

        # Verify graph traversal works with new node
        actions = _extract_actions_from_graph(graph)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["type"], "send_email")

    def test_sidebar_drag_and_drop(self):
        """Test that sidebar DnD creates a free-floating node."""
        graph = {
            "nodes": [
                {"id": "trigger", "type": "trigger", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "condition", "type": "condition", "position": {"x": 0, "y": 170}, "data": {}},
                {"id": "action-1", "type": "action", "position": {"x": 0, "y": 340}, "data": {"action_type": "create_document"}},
            ],
            "edges": [
                {"source": "trigger", "target": "condition", "sourceHandle": "trigger-out", "targetHandle": "condition-in"},
                {"source": "condition", "target": "action-1", "sourceHandle": "condition-out", "targetHandle": "action-1-in"},
            ],
        }

        # Simulate sidebar drop creating a free-floating node (no source connection)
        free_node = {"id": "action-2", "type": "action", "position": {"x": 400, "y": 200}, "data": {"action_type": "telegram"}}
        graph["nodes"].append(free_node)

        # Free-floating node should not affect traversal of connected graph
        actions = _extract_actions_from_graph(graph)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["type"], "create_document")

    def test_mid_chain_node_removal(self):
        """Test removing a middle node from a 3+ node chain reconnects properly."""
        graph = {
            "nodes": [
                {"id": "trigger", "type": "trigger", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "condition", "type": "condition", "position": {"x": 0, "y": 170}, "data": {}},
                {"id": "action-1", "type": "action", "position": {"x": 0, "y": 340}, "data": {"action_type": "create_document"}},
                {"id": "action-2", "type": "action", "position": {"x": 0, "y": 510}, "data": {"action_type": "send_email"}},
            ],
            "edges": [
                {"source": "trigger", "target": "condition", "sourceHandle": "trigger-out", "targetHandle": "condition-in"},
                {"source": "condition", "target": "action-1", "sourceHandle": "condition-out", "targetHandle": "action-1-in"},
                {"source": "action-1", "target": "action-2", "sourceHandle": "action-1-out", "targetHandle": "action-2-in"},
            ],
        }

        # Simulate removing action-1 (middle node)
        # In the UI, removeActionNode reconnects prev->next
        removed_id = "action-1"

        # Find prev and next edges
        prev_edge = next((e for e in graph["edges"] if e["target"] == removed_id), None)
        next_edge = next((e for e in graph["edges"] if e["source"] == removed_id), None)

        # Remove node and its edges
        graph["nodes"] = [n for n in graph["nodes"] if n["id"] != removed_id]
        graph["edges"] = [e for e in graph["edges"] if e["source"] != removed_id and e["target"] != removed_id]

        # Reconnect if both prev and next exist
        if prev_edge and next_edge:
            graph["edges"].append({
                "source": prev_edge["source"],
                "target": next_edge["target"],
                "sourceHandle": prev_edge["sourceHandle"],
                "targetHandle": next_edge["targetHandle"],
            })

        # Verify graph still traverses correctly
        actions = _extract_actions_from_graph(graph)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["type"], "send_email")

    def test_graph_save_load_roundtrip(self):
        """Test that graph_definition survives save/load cycle."""
        original_graph = {
            "nodes": [
                {"id": "trigger", "type": "trigger", "position": {"x": 0, "y": 0}, "data": {"trigger_doctype": "ToDo", "trigger_event": "On Update"}},
                {"id": "condition", "type": "condition", "position": {"x": 0, "y": 170}, "data": {"condition_field": "status", "condition_operator": "=", "condition_value": "Open"}},
                {"id": "action-1", "type": "action", "position": {"x": 0, "y": 340}, "data": {"action_type": "send_email", "recipient": "test@example.com"}},
            ],
            "edges": [
                {"source": "trigger", "target": "condition", "sourceHandle": "trigger-out", "targetHandle": "condition-in"},
                {"source": "condition", "target": "action-1", "sourceHandle": "condition-out", "targetHandle": "action-1-in"},
            ],
        }

        # Simulate save (JSON stringify)
        saved_json = frappe.as_json(original_graph)

        # Simulate load (JSON parse)
        loaded_graph = frappe.parse_json(saved_json)

        # Verify structure preserved
        self.assertEqual(len(loaded_graph["nodes"]), 3)
        self.assertEqual(len(loaded_graph["edges"]), 2)
        self.assertEqual(loaded_graph["nodes"][0]["id"], "trigger")
        self.assertEqual(loaded_graph["nodes"][2]["data"]["action_type"], "send_email")

        # Verify traversal works on loaded graph
        actions = _extract_actions_from_graph(loaded_graph)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["type"], "send_email")
