"""Shared helpers used by all action types."""

import re

import frappe
from frappe.utils import sanitize_html

_TRIGGER_TOKEN_RE = re.compile(r"\{\{trigger\.(\w+)\}\}")


def resolve_value(raw_value, context):
    """Resolve token placeholders in *raw_value* against the trigger context.

    Supported tokens:
        {{trigger.fieldname}}  ->  doc.get("fieldname") on the triggering document

    Static strings (no tokens) pass through unchanged.
    Non-string values are returned as-is.

    Token values are sanitized via frappe.utils.sanitize_html() to prevent
    XSS injection when substituted into HTML email bodies or message fields.
    """
    if not isinstance(raw_value, str) or "{{" not in raw_value:
        return raw_value

    doc = context.get("doc")

    def _replace(match):
        field = match.group(1)
        if doc is None:
            return ""
        val = doc.get(field)
        if val is None:
            return ""
        val_str = str(val)
        # Sanitize to prevent XSS when token values are rendered as HTML
        return sanitize_html(val_str)

    return _TRIGGER_TOKEN_RE.sub(_replace, raw_value)
