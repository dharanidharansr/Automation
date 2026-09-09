"""
Stage 17a migration: Convert existing Automation records from old format
(workflow_json + flat trigger fields) to new graph-based model
(graph_definition + Automation Trigger child table).

This migration:
1. Converts workflow_json (linear array) to graph_definition (nodes/edges)
2. Populates Automation Trigger child table from old flat trigger fields
3. Sets status to "Published" for enabled automations, "Draft" for disabled
4. Preserves all existing demo data
"""

import json

import frappe


def execute():
    """Migrate existing Automation records to new graph model."""
    automations = frappe.get_all("Automation", fields=["name", "workflow_json", "enabled",
                                                         "trigger_doctype", "trigger_event",
                                                         "condition_field", "condition_operator",
                                                         "condition_value"])

    for auto in automations:
        _migrate_automation(auto)


def _migrate_automation(auto):
    """Migrate a single Automation record."""
    doc = frappe.get_doc("Automation", auto.name)

    # 1. Set status based on enabled flag
    doc.status = "Published" if doc.enabled else "Draft"

    # 2. Migrate workflow_json to graph_definition
    if doc.workflow_json and not doc.graph_definition:
        graph = _convert_workflow_to_graph(doc.workflow_json)
        doc.graph_definition = json.dumps(graph, indent=2)

    # 3. Populate triggers table from flat fields
    if not doc.triggers and doc.trigger_doctype:
        doc.append("triggers", {
            "trigger_doctype": doc.trigger_doctype,
            "trigger_event": doc.trigger_event,
            "condition_field": doc.condition_field,
            "condition_operator": doc.condition_operator,
            "condition_value": doc.condition_value,
        })

    # 4. Preserve old fields as legacy (hidden but accessible)
    doc.legacy_trigger_doctype = doc.trigger_doctype
    doc.legacy_trigger_event = doc.trigger_event
    doc.legacy_condition_field = doc.condition_field
    doc.legacy_condition_operator = doc.condition_operator
    doc.legacy_condition_value = doc.condition_value
    doc.legacy_workflow_json = doc.workflow_json

    doc.save(ignore_permissions=True)
    frappe.db.commit()


def _convert_workflow_to_graph(workflow_json):
    """Convert old workflow_json format to new graph_definition format.

    Old format: {"nodes": [...], "edges": [...], "actions": [...]}
    New format: {"nodes": [...], "edges": [...]} (actions embedded in nodes)
    """
    try:
        workflow = json.loads(workflow_json)
    except (json.JSONDecodeError, TypeError):
        return {"nodes": [], "edges": []}

    nodes = workflow.get("nodes", [])
    edges = workflow.get("edges", [])

    # The old format already has nodes/edges, just return them
    # Actions are already embedded in action nodes' data
    return {
        "nodes": nodes,
        "edges": edges,
    }
