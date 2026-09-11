"""Create Document action type — creates a new Frappe document."""

import frappe

from automation_builder.action_types import register_action_type
from automation_builder.action_types._denylist import check_denylist
from automation_builder.action_types._helpers import resolve_value

CONFIG_SCHEMA = [
    {
        "name": "trigger_doctype_select",
        "type": "trigger_doctype_select",
        "label": "Trigger DocType",
        "description": "Which trigger's document to use for field tokens. Only shown when automation has multiple triggers.",
    },
    {
        "name": "target_doctype",
        "type": "doctype_link",
        "label": "Target DocType",
    },
    {
        "name": "field_mapping",
        "type": "field_mapping_table",
        "label": "Field Mapping",
        "description": "Map trigger document fields to the new document's fields.",
    },
]


def execute(context, config):
    """Create a new document of *target_doctype* using *field_mapping*.

    config format:
        {
            "target_doctype": "Automation Task",
            "field_mapping": [
                {"target_field": "subject", "source_value": "Follow up: {{trigger.lead_name}}"},
                {"target_field": "priority", "source_value": "Medium"},
            ]
        }

    Raises on failure — the exception propagates to the dispatcher which
    marks the Automation Run as Failed with the real traceback.
    """
    target_doctype = config.get("target_doctype")
    if not target_doctype:
        raise ValueError("No target_doctype specified in create_document action config")

    if not frappe.db.exists("DocType", target_doctype):
        raise ValueError(f"DocType '{target_doctype}' does not exist")

    # Security: refuse to target sensitive core/governance doctypes
    check_denylist(target_doctype)

    doc = frappe.new_doc(target_doctype)
    field_mapping = config.get("field_mapping", [])

    for mapping in field_mapping:
        target_field = mapping.get("target_field")
        source_value = mapping.get("source_value", "")
        if not target_field:
            continue
        resolved = resolve_value(source_value, context)
        doc.set(target_field, resolved)

    doc.insert(ignore_permissions=True)

    return {
        "step_type": "create_document",
        "status": "Success",
        "output": f"Created {target_doctype} {doc.name}",
    }


register_action_type(
    key="create_document",
    label="Create Document",
    config_schema=CONFIG_SCHEMA,
    execute_fn=execute,
)
