"""HTTP Request action type — makes an HTTP call to any URL.

This module also exposes ``make_http_request()`` as a reusable helper so that
other action types (e.g. Telegram) can issue HTTP calls without duplicating
the request-building, error-handling, and logging logic.
"""

import json
from urllib.parse import urlencode

import frappe
import requests as _requests

from automation_builder.action_types import register_action_type
from automation_builder.action_types._helpers import resolve_value

CONFIG_SCHEMA = [
    {
        "name": "url",
        "type": "data",
        "label": "URL",
        "description": "Full URL. Supports {{trigger.fieldname}} tokens.",
    },
    {
        "name": "method",
        "type": "select",
        "label": "Method",
        "options": ["GET", "POST", "PUT", "PATCH", "DELETE"],
    },
    {
        "name": "headers",
        "type": "field_mapping_table",
        "label": "Headers",
        "description": "Optional HTTP headers (key/value). Supports {{trigger.fieldname}} in values.",
    },
    {
        "name": "body",
        "type": "textarea",
        "label": "Body",
        "description": "Request body (sent as JSON for POST/PUT/PATCH). Supports {{trigger.fieldname}} tokens.",
    },
]


# ---------------------------------------------------------------------------
# Shared helper — used by http_request.execute() and telegram.py
# ---------------------------------------------------------------------------
def make_http_request(method, url, headers=None, body=None, json_payload=None, timeout=30):
    """Issue an HTTP request and return a result dict.

    Args:
        method: HTTP method string (GET, POST, ...).
        url: Full URL.
        headers: Optional dict of request headers.
        body: Optional string body.  Parsed as JSON when possible.
        json_payload: Optional dict to send as JSON body (takes precedence
            over *body* for POST/PUT/PATCH).
        timeout: Request timeout in seconds.

    Returns:
        dict with keys: status_code, response_body (truncated), ok (bool).

    Raises:
        requests.exceptions.RequestException on connection errors.
    """
    headers = headers or {}
    method = (method or "GET").upper()

    kwargs = {"headers": headers, "timeout": timeout}

    if method in ("POST", "PUT", "PATCH"):
        if json_payload is not None:
            kwargs["json"] = json_payload
        elif body is not None:
            # Attempt to parse as JSON; fall back to raw text
            try:
                kwargs["json"] = json.loads(body)
            except (json.JSONDecodeError, TypeError):
                kwargs["data"] = body

    resp = _requests.request(method, url, **kwargs)

    # Truncate response body for logging (keep first 2000 chars)
    resp_text = resp.text[:2000] if resp.text else ""

    return {
        "status_code": resp.status_code,
        "response_body": resp_text,
        "ok": resp.ok,
    }


# ---------------------------------------------------------------------------
# Action type execute
# ---------------------------------------------------------------------------
def execute(context, config):
    """Make an HTTP request to the configured URL.

    config format::

        {
            "url": "https://example.com/api",
            "method": "POST",
            "headers": [{"target_field": "Content-Type", "source_value": "application/json"}],
            "body": '{"key": "{{trigger.lead_name}}"}'
        }

    Raises on failure — the exception propagates to the dispatcher which
    marks the Automation Run as Failed with the real traceback.
    """
    url = resolve_value(config.get("url", ""), context)
    method = config.get("method", "GET")
    body_raw = config.get("body", "")

    if not url:
        raise ValueError("No URL specified in http_request action config")

    # Resolve token placeholders in body
    body = resolve_value(body_raw, context) if body_raw else None

    # Build headers dict from field_mapping_table rows
    raw_headers = config.get("headers", [])
    headers = {}
    for row in raw_headers:
        key = resolve_value(row.get("target_field", ""), context)
        val = resolve_value(row.get("source_value", ""), context)
        if key:
            headers[key] = val

    result = make_http_request(method, url, headers=headers, body=body)

    status_code = result["status_code"]
    resp_preview = result["response_body"]

    if not result["ok"]:
        raise ValueError(
            f"HTTP {method} {url} returned status {status_code}: {resp_preview}"
        )

    return {
        "step_type": "http_request",
        "status": "Success",
        "output": f"HTTP {method} {url} → {status_code}\n{resp_preview}",
    }


register_action_type(
    key="http_request",
    label="HTTP Request",
    config_schema=CONFIG_SCHEMA,
    execute_fn=execute,
)
