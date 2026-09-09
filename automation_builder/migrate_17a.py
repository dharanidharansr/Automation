"""Standalone migration script for Stage 17a.

Run this script directly to migrate existing Automation records
from old format to new graph-based model.

Usage:
    bench --site automate.localhost execute automation_builder.migrate_17a.run
"""

import json

import frappe


def run():
    """Execute the migration."""
    print("Starting Stage 17a migration...")

    # First, ensure the new columns exist
    _ensure_columns()

    # Disable hooks during migration to prevent recursion
    frappe.flags.in_migrate = True

    try:
        # Then migrate the data
        automations = frappe.get_all("Automation", fields=["name"])
        print(f"Found {len(automations)} automations to migrate")

        for auto in automations:
            _migrate_automation(auto.name)

        print("Migration complete!")
    finally:
        frappe.flags.in_migrate = False


def _ensure_columns():
    """Add new columns to the Automation table if they don't exist."""
    columns_to_add = [
        ("status", "VARCHAR(20) DEFAULT 'Draft'"),
        ("graph_definition", "LONGTEXT"),
    ]

    for col_name, col_def in columns_to_add:
        try:
            frappe.db.sql(f"ALTER TABLE tabAutomation ADD COLUMN IF NOT EXISTS `{col_name}` {col_def}")
            print(f"  Added column: {col_name}")
        except Exception as e:
            print(f"  Column {col_name} may already exist: {e}")

    frappe.db.commit()


def _migrate_automation(name):
    """Migrate a single Automation record."""
    doc = frappe.get_doc("Automation", name)

    # Map legacy trigger_event values to valid options
    EVENT_MAP = {
        "Document Created": "After Insert",
        "Document Updated": "On Update",
        "Document Submitted": "On Submit",
        "Document Cancelled": "On Cancel",
    }
    OPERATOR_MAP = {
        "equals": "=",
        "not equals": "!=",
        "greater than": ">",
        "less than": "<",
        "greater than or equal": ">=",
        "less than or equal": "<=",
    }

    # Fix invalid values on the legacy fields themselves (they're Select fields)
    if doc.trigger_event in EVENT_MAP:
        frappe.db.set_value("Automation", name, "trigger_event", EVENT_MAP[doc.trigger_event])
    if doc.condition_operator in OPERATOR_MAP:
        frappe.db.set_value("Automation", name, "condition_operator", OPERATOR_MAP[doc.condition_operator])
    frappe.db.commit()

    # Re-read after fixing
    doc = frappe.get_doc("Automation", name)

    # 1. Set status based on enabled flag
    doc.status = "Published" if doc.enabled else "Draft"

    # 2. Migrate workflow_json to graph_definition
    if doc.workflow_json and not doc.graph_definition:
        graph = _convert_workflow_to_graph(doc.workflow_json)
        doc.graph_definition = json.dumps(graph, indent=2)

    # 3. Populate triggers table from flat fields
    if not doc.triggers and doc.trigger_doctype:
        trigger_event = doc.trigger_event
        condition_operator = doc.condition_operator

        doc.append("triggers", {
            "trigger_doctype": doc.trigger_doctype,
            "trigger_event": trigger_event,
            "condition_field": doc.condition_field,
            "condition_operator": condition_operator,
            "condition_value": doc.condition_value,
        })

    doc.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"  Migrated: {name}")


def _convert_workflow_to_graph(workflow_json):
    """Convert old workflow_json format to new graph_definition format."""
    try:
        workflow = json.loads(workflow_json)
    except (json.JSONDecodeError, TypeError):
        return {"nodes": [], "edges": []}

    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])

    return {
        "nodes": nodes,
        "edges": edges,
    }
