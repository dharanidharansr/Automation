"""Update Field action type — updates fields on the triggering or a linked document."""

import frappe

from automation_builder.action_types import register_action_type
from automation_builder.action_types._helpers import resolve_value

CONFIG_SCHEMA = [
    {
        "name": "target",
        "type": "select",
        "label": "Target",
        "options": ["Same Document", "Linked Document"],
        "description": "Which document to update.",
        "default": "Same Document",
    },
    {
        "name": "link_fieldname",
        "type": "data",
        "label": "Link Field",
        "description": "Field on the trigger doc that links to the document to update. Only used when Target = Linked Document. Supports {{trigger.fieldname}} tokens.",
        "depends_on": "target",
        "depends_on_value": "Linked Document",
    },
    {
        "name": "field_mapping",
        "type": "field_mapping_table",
        "label": "Field Mapping",
        "description": "Map source values/tokens to fields on the target document.",
    },
]


def execute(context, config):
    """Update fields on the target document.

    config format::

        {
            "target": "Same Document",
            "link_fieldname": "",
            "field_mapping": [
                {"target_field": "status", "source_value": "Contacted"},
                {"target_field": "notes", "source_value": "Updated by {{trigger.lead_name}}"},
            ]
        }

    Raises on failure — the exception propagates to the dispatcher which
    marks the Automation Run as Failed with the real traceback.
    """
    target_mode = config.get("target", "Same Document")
    field_mapping = config.get("field_mapping", [])

    if not field_mapping:
        raise ValueError("No field_mapping specified in update_field action config")

    doc = context.get("doc")
    if doc is None:
        raise ValueError("No trigger document available in context")

    if target_mode == "Linked Document":
        link_fieldname = resolve_value(config.get("link_fieldname", ""), context)
        if not link_fieldname:
            raise ValueError(
                "No link_fieldname specified for Linked Document target"
            )
        linked_name = doc.get(link_fieldname)
        if not linked_name:
            raise ValueError(
                f"Link field '{link_fieldname}' is empty on the trigger document"
            )
        target_doc = frappe.get_doc(doc.doctype, linked_name)
    else:
        target_doc = doc

    updated_fields = []
    for mapping in field_mapping:
        target_field = mapping.get("target_field")
        source_value = mapping.get("source_value", "")
        if not target_field:
            continue
        resolved = resolve_value(source_value, context)
        target_doc.set(target_field, resolved)
        updated_fields.append(target_field)

    target_doc.save(ignore_permissions=True)

    return {
        "step_type": "update_field",
        "status": "Success",
        "output": (
            f"Updated {target_doc.doctype} {target_doc.name}: "
            f"{', '.join(updated_fields)}"
        ),
    }


register_action_type(
    key="update_field",
    label="Update Field",
    config_schema=CONFIG_SCHEMA,
    execute_fn=execute,
)
