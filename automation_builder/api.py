"""Whitelisted API endpoints for the Automation Builder frontend."""

import frappe
from frappe import _


@frappe.whitelist()
def get_doctype_fields(doctype):
    """Return field list for a given DocType."""
    if not frappe.db.exists("DocType", doctype):
        frappe.throw(_("DocType {0} does not exist").format(doctype))

    meta = frappe.get_meta(doctype)
    fields = []
    for f in meta.fields:
        if f.fieldtype in ("Section Break", "Column Break", "Tab Break", "Button"):
            continue
        fields.append({
            "fieldname": f.fieldname,
            "label": f.label or f.fieldname,
            "fieldtype": f.fieldtype,
        })
    return fields


@frappe.whitelist()
def get_automation(name):
    """Return full Automation doc including workflow_json."""
    doc = frappe.get_doc("Automation", name)
    return {
        "name": doc.name,
        "automation_name": doc.automation_name,
        "trigger_doctype": doc.trigger_doctype,
        "trigger_event": doc.trigger_event,
        "condition_field": doc.condition_field,
        "condition_operator": doc.condition_operator,
        "condition_value": doc.condition_value,
        "enabled": doc.enabled,
        "workflow_json": doc.workflow_json,
        "description": doc.description,
    }


@frappe.whitelist()
def save_automation(
    name=None,
    workflow_json=None,
    automation_name=None,
    trigger_doctype=None,
    trigger_event=None,
    condition_field=None,
    condition_operator=None,
    condition_value=None,
    enabled=1,
):
    """Create or update an Automation record."""
    if not frappe.has_permission("Automation", "write"):
        frappe.throw(_("Insufficient permissions"))

    if name and frappe.db.exists("Automation", name):
        doc = frappe.get_doc("Automation", name)
        doc.automation_name = automation_name or doc.automation_name
        doc.trigger_doctype = trigger_doctype or doc.trigger_doctype
        doc.trigger_event = trigger_event or doc.trigger_event
        doc.condition_field = condition_field if condition_field is not None else doc.condition_field
        doc.condition_operator = condition_operator if condition_operator is not None else doc.condition_operator
        doc.condition_value = condition_value if condition_value is not None else doc.condition_value
        doc.enabled = int(enabled)
        if workflow_json is not None:
            doc.workflow_json = workflow_json
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.new_doc("Automation")
        doc.automation_name = automation_name
        doc.trigger_doctype = trigger_doctype
        doc.trigger_event = trigger_event
        doc.condition_field = condition_field
        doc.condition_operator = condition_operator
        doc.condition_value = condition_value
        doc.enabled = int(enabled)
        if workflow_json is not None:
            doc.workflow_json = workflow_json
        doc.insert(ignore_permissions=True)

    frappe.db.commit()
    return {"name": doc.name, "automation_name": doc.automation_name}


@frappe.whitelist()
def list_automations():
    """Return list of automations for the list view."""
    return frappe.get_all(
        "Automation",
        fields=[
            "name",
            "automation_name",
            "trigger_doctype",
            "trigger_event",
            "enabled",
            "modified",
        ],
        order_by="modified desc",
    )


@frappe.whitelist()
def list_runs(automation=None, limit_page_length=50):
    """Return Automation Run records, optionally filtered by automation."""
    filters = {}
    if automation:
        filters["automation"] = automation

    return frappe.get_all(
        "Automation Run",
        fields=[
            "name",
            "automation",
            "reference_doctype",
            "reference_name",
            "status",
            "started_at",
            "ended_at",
            "log",
            "error",
        ],
        filters=filters,
        order_by="started_at desc",
        limit_page_length=int(limit_page_length),
    )


@frappe.whitelist()
def get_doctype_list():
    """Return list of DocTypes for the trigger picker."""
    return frappe.get_all(
        "DocType",
        fields=["name"],
        filters={"istable": 0, "issingle": 0},
        order_by="name asc",
    )


@frappe.whitelist()
def get_action_types():
    """Return metadata for every registered action type.

    Returns label + config_schema for each type (not the execute functions).
    The frontend will use this to render config panels generically.
    """
    from automation_builder.action_types import get_all_action_types

    return get_all_action_types()


# ---------------------------------------------------------------------------
# Email Template endpoints
# ---------------------------------------------------------------------------


@frappe.whitelist()
def list_email_templates():
    """Return list of Automation Email Templates."""
    return frappe.get_all(
        "Automation Email Template",
        fields=["name", "template_name", "subject", "modified"],
        order_by="modified desc",
    )


@frappe.whitelist()
def get_email_template(name):
    """Return full Email Template doc."""
    doc = frappe.get_doc("Automation Email Template", name)
    return {
        "name": doc.name,
        "template_name": doc.template_name,
        "subject": doc.subject,
        "body": doc.body,
    }


@frappe.whitelist()
def save_email_template(name=None, template_name=None, subject=None, body=None):
    """Create or update an Automation Email Template."""
    if not frappe.has_permission("Automation Email Template", "write"):
        frappe.throw(_("Insufficient permissions"))

    if name and frappe.db.exists("Automation Email Template", name):
        doc = frappe.get_doc("Automation Email Template", name)
        doc.template_name = template_name or doc.template_name
        doc.subject = subject if subject is not None else doc.subject
        doc.body = body if body is not None else doc.body
        doc.save(ignore_permissions=True)
    else:
        doc = frappe.new_doc("Automation Email Template")
        doc.template_name = template_name
        doc.subject = subject
        doc.body = body
        doc.insert(ignore_permissions=True)

    frappe.db.commit()
    return {"name": doc.name, "template_name": doc.template_name}
