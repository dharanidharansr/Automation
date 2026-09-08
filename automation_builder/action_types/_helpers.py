"""Shared helpers used by all action types."""

import re

_TRIGGER_TOKEN_RE = re.compile(r"\{\{trigger\.(\w+)\}\}")


def resolve_value(raw_value, context):
    """Resolve token placeholders in *raw_value* against the trigger context.

    Supported tokens:
        {{trigger.fieldname}}  ->  doc.get("fieldname") on the triggering document

    Static strings (no tokens) pass through unchanged.
    Non-string values are returned as-is.
    """
    if not isinstance(raw_value, str) or "{{" not in raw_value:
        return raw_value

    doc = context.get("doc")

    def _replace(match):
        field = match.group(1)
        if doc is None:
            return ""
        val = doc.get(field)
        return str(val) if val is not None else ""

    return _TRIGGER_TOKEN_RE.sub(_replace, raw_value)
