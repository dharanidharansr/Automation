"""Whitelisted API endpoints for the Automation Builder frontend."""

import frappe
from frappe import _


def _enforce_publish_permission(status):
    """Enforce that only System Manager can set status to Published.

    Called from BOTH create and update paths of save_automation to ensure
    no code path can set status="Published" without this check.
    """
    if status == "Published" and "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Manager can publish automations"))


def _validate_triggers_for_publish(triggers):
    """Require at least one valid trigger row when publishing.

    Called when status is being set to Published. An automation with no
    trigger data would be a silent no-op — Published but never fires.
    """
    if not triggers:
        frappe.throw(
            _("Cannot publish: at least one trigger with trigger_doctype and "
              "trigger_event is required.")
        )
    for i, trigger in enumerate(triggers):
        doctype = trigger.get("trigger_doctype") if isinstance(trigger, dict) else getattr(trigger, "trigger_doctype", None)
        event = trigger.get("trigger_event") if isinstance(trigger, dict) else getattr(trigger, "trigger_event", None)
        if not doctype or not event:
            frappe.throw(
                _("Cannot publish: trigger row {0} is missing trigger_doctype "
                  "or trigger_event.").format(i + 1)
            )


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
        field_data = {
            "fieldname": f.fieldname,
            "label": f.label or f.fieldname,
            "fieldtype": f.fieldtype,
        }
        if f.fieldtype == "Link" and f.options:
            field_data["options"] = f.options
        fields.append(field_data)
    return fields


@frappe.whitelist()
def get_automation(name):
    """Return full Automation doc including graph_definition and triggers."""
    doc = frappe.get_doc("Automation", name)

    # Get triggers from child table
    triggers = []
    for trigger in doc.triggers:
        triggers.append({
            "trigger_doctype": trigger.trigger_doctype,
            "trigger_event": trigger.trigger_event,
            "condition_field": trigger.condition_field,
            "condition_operator": trigger.condition_operator,
            "condition_value": trigger.condition_value,
        })

    return {
        "name": doc.name,
        "automation_name": doc.automation_name,
        "status": doc.status,
        "enabled": doc.enabled,
        "graph_definition": doc.graph_definition,
        "triggers": triggers,
        "description": doc.description,
        # Legacy fields for backward compatibility
        "trigger_doctype": doc.trigger_doctype or (triggers[0]["trigger_doctype"] if triggers else None),
        "trigger_event": doc.trigger_event or (triggers[0]["trigger_event"] if triggers else None),
        "condition_field": doc.condition_field or (triggers[0]["condition_field"] if triggers else None),
        "condition_operator": doc.condition_operator or (triggers[0]["condition_operator"] if triggers else None),
        "condition_value": doc.condition_value or (triggers[0]["condition_value"] if triggers else None),
        "workflow_json": doc.workflow_json or doc.graph_definition,
    }


@frappe.whitelist()
def save_automation(
    name=None,
    graph_definition=None,
    automation_name=None,
    status=None,
    enabled=1,
    triggers=None,
    description=None,
    # Legacy fields for backward compatibility
    workflow_json=None,
    trigger_doctype=None,
    trigger_event=None,
    condition_field=None,
    condition_operator=None,
    condition_value=None,
):
    """Create or update an Automation record."""
    if not frappe.has_permission("Automation", "write"):
        frappe.throw(_("Insufficient permissions"))

    if name and frappe.db.exists("Automation", name):
        doc = frappe.get_doc("Automation", name)
        doc.automation_name = automation_name or doc.automation_name

        # Handle status with permission check
        if status is not None:
            _enforce_publish_permission(status)
            if status == "Published":
                # Validate triggers exist before publishing
                effective_triggers = triggers if triggers is not None else [
                    {"trigger_doctype": t.trigger_doctype, "trigger_event": t.trigger_event,
                     "condition_field": t.condition_field, "condition_operator": t.condition_operator,
                     "condition_value": t.condition_value}
                    for t in doc.triggers
                ]
                _validate_triggers_for_publish(effective_triggers)
            doc.status = status

        doc.enabled = int(enabled)
        doc.description = description if description is not None else doc.description

        # Handle graph_definition (new format)
        if graph_definition is not None:
            doc.graph_definition = graph_definition

        # Handle triggers table (new format)
        if triggers is not None:
            doc.triggers = []
            for trigger_data in triggers:
                doc.append("triggers", trigger_data)

        # Handle legacy fields for backward compatibility
        if workflow_json is not None:
            doc.workflow_json = workflow_json
        if trigger_doctype is not None:
            doc.trigger_doctype = trigger_doctype
        if trigger_event is not None:
            doc.trigger_event = trigger_event
        if condition_field is not None:
            doc.condition_field = condition_field
        if condition_operator is not None:
            doc.condition_operator = condition_operator
        if condition_value is not None:
            doc.condition_value = condition_value

        doc.save(ignore_permissions=True)
    else:
        doc = frappe.new_doc("Automation")
        doc.automation_name = automation_name
        # Enforce publish permission BEFORE setting status (create path)
        effective_status = status or "Draft"
        _enforce_publish_permission(effective_status)
        if effective_status == "Published":
            _validate_triggers_for_publish(triggers or [])
        doc.status = effective_status
        doc.enabled = int(enabled)
        doc.description = description

        # Handle graph_definition (new format)
        if graph_definition is not None:
            doc.graph_definition = graph_definition

        # Handle triggers table (new format)
        if triggers is not None:
            for trigger_data in triggers:
                doc.append("triggers", trigger_data)

        # Handle legacy fields for backward compatibility
        if workflow_json is not None:
            doc.workflow_json = workflow_json
        if trigger_doctype is not None:
            doc.trigger_doctype = trigger_doctype
        if trigger_event is not None:
            doc.trigger_event = trigger_event
        if condition_field is not None:
            doc.condition_field = condition_field
        if condition_operator is not None:
            doc.condition_operator = condition_operator
        if condition_value is not None:
            doc.condition_value = condition_value

        doc.insert(ignore_permissions=True)

    return {"name": doc.name, "automation_name": doc.automation_name}


@frappe.whitelist()
def list_automations():
    """Return list of automations for the list view."""
    return frappe.get_all(
        "Automation",
        fields=[
            "name",
            "automation_name",
            "status",
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


@frappe.whitelist()
def can_publish():
    """Check if current user can publish automations (System Manager only)."""
    return "System Manager" in frappe.get_roles()


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

    return {"name": doc.name, "template_name": doc.template_name}
