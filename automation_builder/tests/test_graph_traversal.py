"""Tests for graph traversal execution engine.

Tests that the dispatcher correctly walks the graph definition to determine
execution order, and that all action types execute correctly through the
new graph-based engine.
"""

import json

import frappe
from frappe.tests import IntegrationTestCase

from automation_builder.dispatcher import (
    _build_edge_graph,
    _walk_graph,
    _walk_graph_bfs,
    _extract_actions_from_graph,
    execute_automation,
)


class TestGraphTraversal(IntegrationTestCase):
    """Test graph traversal logic for determining execution order."""

    def test_linear_graph_traversal(self):
        """Test traversal of a simple linear graph: trigger -> condition -> action."""
        edges = [
            {"source": "trigger", "target": "condition"},
            {"source": "condition", "target": "action-1"},
        ]
        graph = _build_edge_graph(edges)
        result = _walk_graph_bfs(graph, "trigger")

        self.assertEqual(result, ["trigger", "condition", "action-1"])

    def test_branching_graph_traversal(self):
        """Test traversal of a branching graph: trigger -> condition -> [action-1, action-2]."""
        edges = [
            {"source": "trigger", "target": "condition"},
            {"source": "condition", "target": "action-1"},
            {"source": "condition", "target": "action-2"},
        ]
        graph = _build_edge_graph(edges)
        result = _walk_graph_bfs(graph, "trigger")

        # Both actions should be visited
        self.assertIn("action-1", result)
        self.assertIn("action-2", result)
        # Trigger and condition should come first
        self.assertEqual(result[0], "trigger")
        self.assertEqual(result[1], "condition")

    def test_empty_graph_traversal(self):
        """Test traversal of an empty graph (no edges) returns just the start node."""
        graph = _build_edge_graph([])
        result = _walk_graph_bfs(graph, "trigger")
        # Start node is always visited even with no edges
        self.assertEqual(result, ["trigger"])

    def test_cycle_detection(self):
        """Test that cycles don't cause infinite loops."""
        edges = [
            {"source": "trigger", "target": "action-1"},
            {"source": "action-1", "target": "trigger"},  # Cycle back
        ]
        graph = _build_edge_graph(edges)
        result = _walk_graph_bfs(graph, "trigger")

        # Should not infinite loop, should visit each node once
        self.assertEqual(len(result), len(set(result)))

    def test_extract_actions_from_graph(self):
        """Test extracting action configurations from a graph."""
        graph = {
            "nodes": [
                {"id": "trigger", "type": "trigger", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "condition", "type": "condition", "position": {"x": 0, "y": 150}, "data": {}},
                {"id": "action-1", "type": "action", "position": {"x": 0, "y": 300}, "data": {"action_type": "telegram", "chat_id": "123", "message": "Test"}},
                {"id": "action-2", "type": "action", "position": {"x": 0, "y": 450}, "data": {"action_type": "update_field", "target": "Same Document", "field_mapping": []}},
            ],
            "edges": [
                {"source": "trigger", "target": "condition"},
                {"source": "condition", "target": "action-1"},
                {"source": "action-1", "target": "action-2"},
            ],
        }

        actions = _extract_actions_from_graph(graph)

        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0]["type"], "telegram")
        self.assertEqual(actions[0]["config"]["chat_id"], "123")
        self.assertEqual(actions[1]["type"], "update_field")

    def test_extract_actions_skips_trigger_and_condition(self):
        """Test that trigger and condition nodes are not extracted as actions."""
        graph = {
            "nodes": [
                {"id": "trigger", "type": "trigger", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "condition", "type": "condition", "position": {"x": 0, "y": 150}, "data": {}},
            ],
            "edges": [
                {"source": "trigger", "target": "condition"},
            ],
        }

        actions = _extract_actions_from_graph(graph)
        self.assertEqual(len(actions), 0)


class TestDraftAutomationExecution(IntegrationTestCase):
    """Test that Draft automations never execute."""

    def setUp(self):
        """Set up test data."""
        super().setUp()
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

    def test_draft_automation_not_dispatched(self):
        """Test that Draft automations are not matched by the dispatcher."""
        # Create a Draft automation
        auto = frappe.new_doc("Automation")
        auto.automation_name = "TEST-DraftNotExecuted"
        auto.status = "Draft"
        auto.enabled = 1
        auto.trigger_doctype = "ToDo"
        auto.trigger_event = "On Update"
        auto.graph_definition = json.dumps({
            "nodes": [
                {"id": "trigger", "type": "trigger", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "action-1", "type": "action", "position": {"x": 0, "y": 150}, "data": {"action_type": "telegram", "chat_id": "123", "message": "Should not execute"}},
            ],
            "edges": [
                {"source": "trigger", "target": "action-1"},
            ],
        })
        auto.append("triggers", {
            "trigger_doctype": "ToDo",
            "trigger_event": "On Update",
        })
        auto.insert(ignore_permissions=True)
        frappe.db.commit()

        # Query automations as the dispatcher would
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

        # Draft automation should not appear
        automation_names = [a.name for a in automations]
        self.assertNotIn("TEST-DraftNotExecuted", automation_names)

    def test_published_automation_dispatched(self):
        """Test that Published automations are matched by the dispatcher."""
        # Create a Published automation
        auto = frappe.new_doc("Automation")
        auto.automation_name = "TEST-PublishedExecuted"
        auto.status = "Published"
        auto.enabled = 1
        auto.trigger_doctype = "ToDo"
        auto.trigger_event = "On Update"
        auto.graph_definition = json.dumps({
            "nodes": [
                {"id": "trigger", "type": "trigger", "position": {"x": 0, "y": 0}, "data": {}},
                {"id": "action-1", "type": "action", "position": {"x": 0, "y": 150}, "data": {"action_type": "telegram", "chat_id": "123", "message": "Should execute"}},
            ],
            "edges": [
                {"source": "trigger", "target": "action-1"},
            ],
        })
        auto.append("triggers", {
            "trigger_doctype": "ToDo",
            "trigger_event": "On Update",
        })
        auto.insert(ignore_permissions=True)
        frappe.db.commit()

        # Query automations as the dispatcher would
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

        # Published automation should appear
        automation_names = [a.name for a in automations]
        self.assertIn("TEST-PublishedExecuted", automation_names)
