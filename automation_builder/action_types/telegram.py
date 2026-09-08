"""Telegram action type — sends a message via the Telegram Bot API.

When no bot token is configured in Automation Builder Settings, the action
runs in mock mode and logs what *would* have been sent — without making
any network call.
"""

import frappe
from frappe.utils import strip_html_tags

from automation_builder.action_types import register_action_type
from automation_builder.action_types._helpers import resolve_value
from automation_builder.action_types.http_request import make_http_request

CONFIG_SCHEMA = [
    {
        "name": "chat_id",
        "type": "data",
        "label": "Chat ID",
        "description": "Telegram chat ID. Supports {{trigger.fieldname}} tokens (e.g. {{trigger.telegram_chat_id}}).",
    },
    {
        "name": "message",
        "type": "textarea",
        "label": "Message",
        "description": "Message text to send. Supports {{trigger.fieldname}} tokens.",
    },
]


def _get_bot_token():
    """Retrieve the Telegram bot token from Automation Builder Settings."""
    try:
        token = frappe.get_single_value("Automation Builder Settings", "telegram_bot_token")
    except Exception:
        return None
    return token or None


def execute(context, config):
    """Send a Telegram message, or log a mock if no token is configured.

    config format::

        {
            "chat_id": "123456789",
            "message": "New lead: {{trigger.lead_name}}"
        }
    """
    chat_id = resolve_value(config.get("chat_id", ""), context)
    message_raw = config.get("message", "")
    message = strip_html_tags(resolve_value(message_raw, context))

    if not chat_id:
        raise ValueError("No chat_id specified in telegram action config")

    bot_token = _get_bot_token()

    if not bot_token:
        # Mock mode — no network call, clear log
        mock_line = (
            f"MOCK MODE (no Telegram bot token configured): "
            f"would have sent to chat_id={chat_id}: '{message}'"
        )
        return {
            "step_type": "telegram",
            "status": "Success",
            "output": mock_line,
        }

    # Real send — use the shared HTTP helper
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}

    result = make_http_request(
        method="POST",
        url=url,
        headers={"Content-Type": "application/json"},
        json_payload=payload,
        timeout=15,
    )

    if not result["ok"]:
        raise ValueError(
            f"Telegram sendMessage returned status {result['status_code']}: "
            f"{result['response_body']}"
        )

    return {
        "step_type": "telegram",
        "status": "Success",
        "output": (
            f"Telegram message sent to chat_id={chat_id}: "
            f"{result['response_body']}"
        ),
    }


register_action_type(
    key="telegram",
    label="Telegram",
    config_schema=CONFIG_SCHEMA,
    execute_fn=execute,
)
