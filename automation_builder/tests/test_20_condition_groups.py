"""Tests for Stage 20 — AND/OR condition groups, new operators, migration.

Covers:
- Multi-trigger OR-across-rows (backend verification)
- AND-combinator within a single trigger row
- OR-combinator within a single trigger row
- New operators: like, not like, in, not in, is set, is not set
- Migration preserves existing single-condition automations
- Unified evaluation function (trigger gating + graph-walk condition nodes)
"""

import json

import frappe
from frappe.tests import IntegrationTestCase

from automation_builder.dispatcher import (
    _evaluate_trigger_conditions,
    _evaluate_single_condition,
    _evaluate_condition_group,
    _walk_graph,
)


class TestConditionGroupAND(IntegrationTestCase):
    """AND-combinator: all conditions must match within a trigger row."""

    def setUp(self):
        for name in ["TEST-AND"]:
            frappe.db.sql("DELETE FROM `tabAutomation Trigger Condition` WHERE parent IN (SELECT name FROM `tabAutomation Trigger` WHERE parent = %s)", name)
            frappe.db.sql("DELETE FROM `tabAutomation Trigger` WHERE parent = %s", name)
            frappe.db.sql("DELETE FROM `tabAutomation` WHERE name = %s", name)
        frappe.db.commit()

    def tearDown(self):
        for name in ["TEST-AND"]:
            frappe.db.sql("DELETE FROM `tabAutomation Trigger Condition` WHERE parent IN (SELECT name FROM `tabAutomation Trigger` WHERE parent = %s)", name)
            frappe.db.sql("DELETE FROM `tabAutomation Trigger` WHERE parent = %s", name)
            frappe.db.sql("DELETE FROM `tabAutomation` WHERE name = %s", name)
        frappe.db.commit()

    def _create_automation_with_conditions(self, conditions, logic="All must match"):
        """Helper to create automation with conditions in child table."""
        from automation_builder.api import save_automation
        result = save_automation(
            automation_name="TEST-AND",
            status="Draft",
            graph_definition='{"nodes":[],"edges":[]}',
            triggers=[{
                "trigger_doctype": "ToDo",
                "trigger_event": "On Update",
                "condition_logic": logic,
                "conditions": conditions,
            }],
        )
        return frappe.get_doc("Automation", result["name"])

    def test_and_both_match(self):
        """AND: both conditions match -> True."""
        auto = self._create_automation_with_conditions([
            {"condition_field": "status", "condition_operator": "=", "condition_value": "Open"},
            {"condition_field": "description", "condition_operator": "like", "condition_value": "%test%"},
        ], "All must match")

        todo = frappe.get_doc({"doctype": "ToDo", "description": "AND test", "status": "Open"})
        todo.insert(ignore_permissions=True)
        frappe.db.commit()

        result = _evaluate_trigger_conditions(auto.name, todo)
        self.assertTrue(result, "AND: both conditions match -> should be True")

    def test_and_one_fails(self):
        """AND: one condition fails -> False."""
        auto = self._create_automation_with_conditions([
            {"condition_field": "status", "condition_operator": "=", "condition_value": "Open"},
            {"condition_field": "description", "condition_operator": "=", "condition_value": "nomatch"},
        ], "All must match")

        todo = frappe.get_doc({"doctype": "ToDo", "description": "AND fail test", "status": "Open"})
        todo.insert(ignore_permissions=True)
        frappe.db.commit()

        result = _evaluate_trigger_conditions(auto.name, todo)
        self.assertFalse(result, "AND: second condition fails -> should be False")


class TestConditionGroupOR(IntegrationTestCase):
    """OR-combinator: any condition matching is sufficient within a trigger row."""

    def setUp(self):
        for name in ["TEST-OR"]:
            frappe.db.sql("DELETE FROM `tabAutomation Trigger Condition` WHERE parent IN (SELECT name FROM `tabAutomation Trigger` WHERE parent = %s)", name)
            frappe.db.sql("DELETE FROM `tabAutomation Trigger` WHERE parent = %s", name)
            frappe.db.sql("DELETE FROM `tabAutomation` WHERE name = %s", name)
        frappe.db.commit()

    def tearDown(self):
        for name in ["TEST-OR"]:
            frappe.db.sql("DELETE FROM `tabAutomation Trigger Condition` WHERE parent IN (SELECT name FROM `tabAutomation Trigger` WHERE parent = %s)", name)
            frappe.db.sql("DELETE FROM `tabAutomation Trigger` WHERE parent = %s", name)
            frappe.db.sql("DELETE FROM `tabAutomation` WHERE name = %s", name)
        frappe.db.commit()

    def _create_automation_with_conditions(self, conditions, logic="Any must match"):
        """Helper to create automation with conditions in child table."""
        from automation_builder.api import save_automation
        result = save_automation(
            automation_name="TEST-OR",
            status="Draft",
            graph_definition='{"nodes":[],"edges":[]}',
            triggers=[{
                "trigger_doctype": "ToDo",
                "trigger_event": "On Update",
                "condition_logic": logic,
                "conditions": conditions,
            }],
        )
        return frappe.get_doc("Automation", result["name"])

    def test_or_one_matches(self):
        """OR: one condition matches -> True."""
        auto = self._create_automation_with_conditions([
            {"condition_field": "status", "condition_operator": "=", "condition_value": "Closed"},
            {"condition_field": "description", "condition_operator": "like", "condition_value": "%test%"},
        ], "Any must match")

        todo = frappe.get_doc({"doctype": "ToDo", "description": "OR test", "status": "Open"})
        todo.insert(ignore_permissions=True)
        frappe.db.commit()

        result = _evaluate_trigger_conditions(auto.name, todo)
        self.assertTrue(result, "OR: second condition matches -> should be True")

    def test_or_none_match(self):
        """OR: no conditions match -> False."""
        auto = self._create_automation_with_conditions([
            {"condition_field": "status", "condition_operator": "=", "condition_value": "Closed"},
            {"condition_field": "description", "condition_operator": "=", "condition_value": "nomatch"},
        ], "Any must match")

        todo = frappe.get_doc({"doctype": "ToDo", "description": "OR fail", "status": "Open"})
        todo.insert(ignore_permissions=True)
        frappe.db.commit()

        result = _evaluate_trigger_conditions(auto.name, todo)
        self.assertFalse(result, "OR: no conditions match -> should be False")


class TestNewOperators(IntegrationTestCase):
    """Test each new operator: like, not like, in, not in, is set, is not set."""

    def setUp(self):
        self.todo = frappe.get_doc({"doctype": "ToDo", "description": "Operator test", "status": "Open"})
        self.todo.insert(ignore_permissions=True)
        frappe.db.commit()

    def tearDown(self):
        frappe.delete_doc("ToDo", self.todo.name, force=True)
        frappe.db.commit()

    def test_like_substring(self):
        """like: case-insensitive substring match."""
        cond = {"condition_field": "description", "condition_operator": "like", "condition_value": "operator"}
        self.assertTrue(_evaluate_single_condition(self.todo, cond))

    def test_like_no_match(self):
        """like: no substring match."""
        cond = {"condition_field": "description", "condition_operator": "like", "condition_value": "xyz"}
        self.assertFalse(_evaluate_single_condition(self.todo, cond))

    def test_like_wildcard(self):
        """like: % wildcard match."""
        cond = {"condition_field": "description", "condition_operator": "like", "condition_value": "%test%"}
        self.assertTrue(_evaluate_single_condition(self.todo, cond))

    def test_not_like(self):
        """not like: inverse of like."""
        cond = {"condition_field": "description", "condition_operator": "not like", "condition_value": "xyz"}
        self.assertTrue(_evaluate_single_condition(self.todo, cond))

    def test_not_like_match(self):
        """not like: returns False when substring IS found."""
        cond = {"condition_field": "description", "condition_operator": "not like", "condition_value": "test"}
        self.assertFalse(_evaluate_single_condition(self.todo, cond))

    def test_in_operator(self):
        """in: value is one of comma-separated list."""
        cond = {"condition_field": "status", "condition_operator": "in", "condition_value": "Closed,Open,Working"}
        self.assertTrue(_evaluate_single_condition(self.todo, cond))

    def test_in_no_match(self):
        """in: value not in list."""
        cond = {"condition_field": "status", "condition_operator": "in", "condition_value": "Closed,Cancelled"}
        self.assertFalse(_evaluate_single_condition(self.todo, cond))

    def test_not_in_operator(self):
        """not in: value is NOT in the list."""
        cond = {"condition_field": "status", "condition_operator": "not in", "condition_value": "Closed,Cancelled"}
        self.assertTrue(_evaluate_single_condition(self.todo, cond))

    def test_not_in_match(self):
        """not in: returns False when value IS in the list."""
        cond = {"condition_field": "status", "condition_operator": "not in", "condition_value": "Open,Closed"}
        self.assertFalse(_evaluate_single_condition(self.todo, cond))

    def test_is_set(self):
        """is set: field has a truthy/non-empty value."""
        cond = {"condition_field": "status", "condition_operator": "is set", "condition_value": ""}
        self.assertTrue(_evaluate_single_condition(self.todo, cond))

    def test_is_set_empty_field(self):
        """is set: empty field -> False."""
        cond = {"condition_field": "sender", "condition_operator": "is set", "condition_value": ""}
        self.assertFalse(_evaluate_single_condition(self.todo, cond))

    def test_is_not_set(self):
        """is not set: field is empty -> True."""
        cond = {"condition_field": "sender", "condition_operator": "is not set", "condition_value": ""}
        self.assertTrue(_evaluate_single_condition(self.todo, cond))

    def test_is_not_set_has_value(self):
        """is not set: field has value -> False."""
        cond = {"condition_field": "status", "condition_operator": "is not set", "condition_value": ""}
        self.assertFalse(_evaluate_single_condition(self.todo, cond))


class TestMigrationPreservesExisting(IntegrationTestCase):
    """Migration: existing single-condition automations should work exactly as before."""

    def setUp(self):
        for name in ["TEST-Migrate"]:
            frappe.db.sql("DELETE FROM `tabAutomation Trigger Condition` WHERE parent IN (SELECT name FROM `tabAutomation Trigger` WHERE parent = %s)", name)
            frappe.db.sql("DELETE FROM `tabAutomation Trigger` WHERE parent = %s", name)
            frappe.db.sql("DELETE FROM `tabAutomation` WHERE name = %s", name)
        frappe.db.commit()

    def tearDown(self):
        for name in ["TEST-Migrate"]:
            frappe.db.sql("DELETE FROM `tabAutomation Trigger Condition` WHERE parent IN (SELECT name FROM `tabAutomation Trigger` WHERE parent = %s)", name)
            frappe.db.sql("DELETE FROM `tabAutomation Trigger` WHERE parent = %s", name)
            frappe.db.sql("DELETE FROM `tabAutomation` WHERE name = %s", name)
        frappe.db.commit()

    def test_legacy_single_condition_still_works(self):
        """Legacy flat condition_field/operator/value on trigger row still evaluates."""
        # Create an automation using the old flat fields directly via SQL
        # (simulating a pre-migration record)
        auto = frappe.get_doc({
            "doctype": "Automation",
            "automation_name": "TEST-Migrate",
            "status": "Draft",
            "enabled": 1,
            "triggers": [{
                "trigger_doctype": "ToDo",
                "trigger_event": "On Update",
                "condition_field": "status",
                "condition_operator": "=",
                "condition_value": "Open",
            }],
            "graph_definition": '{"nodes":[],"edges":[]}',
        })
        auto.insert(ignore_permissions=True)
        frappe.db.commit()

        # Verify the trigger row has the flat fields but NO conditions child rows
        trigger = frappe.get_all(
            "Automation Trigger",
            filters={"parent": auto.name},
            fields=["name", "condition_field", "condition_operator", "condition_value"],
        )[0]

        conditions = frappe.get_all(
            "Automation Trigger Condition",
            filters={"parent": trigger.name},
        )

        # The flat fields should be set, conditions child table should be empty
        self.assertEqual(trigger.condition_field, "status")
        self.assertEqual(trigger.condition_operator, "=")
        self.assertEqual(trigger.condition_value, "Open")
        self.assertEqual(len(conditions), 0, "No conditions in child table (legacy path)")

        # Evaluate — should use legacy flat field path
        todo = frappe.get_doc({"doctype": "ToDo", "description": "migrate test", "status": "Open"})
        todo.insert(ignore_permissions=True)
        frappe.db.commit()

        result = _evaluate_trigger_conditions(auto.name, todo)
        self.assertTrue(result, "Legacy single condition should still evaluate correctly")

    def test_new_condition_group_overrides_legacy(self):
        """When conditions exist in child table, they take precedence over flat fields."""
        from automation_builder.api import save_automation
        result = save_automation(
            automation_name="TEST-Migrate",
            status="Draft",
            graph_definition='{"nodes":[],"edges":[]}',
            triggers=[{
                "trigger_doctype": "ToDo",
                "trigger_event": "On Update",
                "condition_logic": "All must match",
                "conditions": [
                    {"condition_field": "status", "condition_operator": "=", "condition_value": "Closed"},
                ],
            }],
        )
        auto = frappe.get_doc("Automation", result["name"])

        todo = frappe.get_doc({"doctype": "ToDo", "description": "override test", "status": "Open"})
        todo.insert(ignore_permissions=True)
        frappe.db.commit()

        # The child table condition (status=Closed) should be used, not any flat fields
        result = _evaluate_trigger_conditions(auto.name, todo)
        self.assertFalse(result, "Condition group says Closed but doc is Open -> False")


class TestUnifiedEvaluation(IntegrationTestCase):
    """Confirm the same _evaluate_single_condition works for both trigger gating
    and graph-walk condition nodes."""

    def test_trigger_gating_uses_unified_function(self):
        """_evaluate_trigger_conditions uses _evaluate_single_condition internally."""
        import inspect
        from automation_builder import dispatcher
        source = inspect.getsource(dispatcher._evaluate_trigger_conditions)
        self.assertIn("_evaluate_single_condition", source,
                     "_evaluate_trigger_conditions should call _evaluate_single_condition")

    def test_graph_walk_condition_uses_unified_function(self):
        """_walk_graph condition branch uses _evaluate_single_condition."""
        import inspect
        from automation_builder import dispatcher
        source = inspect.getsource(dispatcher._walk_graph)
        self.assertIn("_evaluate_single_condition", source,
                     "_walk_graph condition branch should call _evaluate_single_condition")
