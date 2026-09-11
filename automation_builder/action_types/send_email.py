"""Send Email action type — sends an email via Frappe's sendmail."""

import frappe

from automation_builder.action_types import register_action_type
from automation_builder.action_types._helpers import resolve_value

CONFIG_SCHEMA = [
    {
        "name": "trigger_doctype_select",
        "type": "trigger_doctype_select",
        "label": "Trigger DocType",
        "description": "Which trigger's document to use for field tokens. Only shown when automation has multiple triggers.",
    },
    {
        "name": "recipient",
        "type": "data",
        "label": "Recipient",
        "description": "Email address. Supports {{trigger.fieldname}} tokens.",
    },
    {
        "name": "template",
        "type": "template_picker",
        "label": "Email Template",
        "description": "Optional. If selected, template subject/body are used as defaults.",
    },
    {
        "name": "subject",
        "type": "data",
        "label": "Subject",
        "description": "Email subject. Supports {{trigger.fieldname}} tokens.",
    },
    {
        "name": "body",
        "type": "textarea",
        "label": "Body",
        "description": "Email body. Supports {{trigger.fieldname}} tokens.",
    },
]


def execute(context, config):
    """Send an email using *recipient*, *subject*, and *body* from config.

    If a template is selected, its subject/body are used as the base values.
    Manual subject/body fields override the template values when provided.

    All fields support {{trigger.fieldname}} token resolution.

    Raises on failure — the exception propagates to the dispatcher which
    marks the Automation Run as Failed with the real traceback.
    """
    recipient = resolve_value(config.get("recipient", ""), context)

    # Resolve template defaults if a template is selected
    template_name = config.get("template")
    template_subject = ""
    template_body = ""
    if template_name:
        try:
            tpl = frappe.get_doc("Automation Email Template", template_name)
            template_subject = tpl.subject or ""
            template_body = tpl.body or ""
        except frappe.DoesNotExistError:
            pass  # template was deleted; fall through to manual fields

    # Manual fields override template; fall back to template if manual is empty
    subject_raw = config.get("subject") or template_subject
    body_raw = config.get("body") or template_body

    subject = resolve_value(subject_raw, context)
    body = resolve_value(body_raw, context)

    if not recipient:
        raise ValueError("No recipient specified in send_email action config")

    frappe.sendmail(recipients=[recipient], subject=subject, message=body)

    return {
        "step_type": "send_email",
        "status": "Success",
        "output": f"Email sent to {recipient}: {subject}",
    }


register_action_type(
    key="send_email",
    label="Send Email",
    config_schema=CONFIG_SCHEMA,
    execute_fn=execute,
)
