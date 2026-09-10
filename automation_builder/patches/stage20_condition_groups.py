"""Patch: Stage 20 — Migrate flat trigger conditions to condition group child table.

Migrates existing single condition_field/operator/value on Automation Trigger
rows into the new Automation Trigger Condition grandchild table. Sets
condition_logic to "All must match" (equivalent to old single-condition behavior).
"""

import frappe


def execute():
    """Run the Stage 20 migration patch."""
    frappe.reload_doc("automation_builder", "doctype", "automation_trigger_condition")
    frappe.reload_doc("automation_builder", "doctype", "automation_trigger")

    # Migrate flat condition fields into the new conditions child table
    _migrate_flat_conditions_to_group()


def _migrate_flat_conditions_to_group():
    """Move flat condition_field/operator/value into conditions child table."""
    triggers = frappe.get_all(
        "Automation Trigger",
        fields=["name", "condition_field", "condition_operator", "condition_value",
                "condition_logic", "parent"],
    )

    for trigger in triggers:
        # Skip if already migrated (has conditions child rows)
        existing = frappe.get_all(
            "Automation Trigger Condition",
            filters={"parent": trigger.name},
        )
        if existing:
            continue

        # Skip if no flat condition to migrate
        if not trigger.condition_field or not trigger.condition_operator:
            # Set default condition_logic if not set
            if not trigger.condition_logic:
                frappe.db.set_value("Automation Trigger", trigger.name,
                                   "condition_logic", "All must match")
            continue

        # Create the condition row in the grandchild table
        doc = frappe.get_doc("Automation Trigger", trigger.name)
        doc.append("conditions", {
            "condition_field": trigger.condition_field,
            "condition_operator": trigger.condition_operator,
            "condition_value": trigger.condition_value or "",
        })
        doc.condition_logic = "All must match"
        doc.save(ignore_permissions=True)

    frappe.db.commit()
