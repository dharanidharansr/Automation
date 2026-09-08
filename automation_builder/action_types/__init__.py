"""Action type registry — the plug-and-play system for automation actions.

Each action type is a small, isolated module registered into a central dict.
Dispatcher/executor only needs to look up the registry and call execute().

To add a new action type:
    1. Create automation_builder/action_types/my_action.py
    2. Import and register it here, or use register_action_type() directly.
"""

ACTION_TYPES = {}


def register_action_type(key, label, config_schema, execute_fn):
    """Register an action type into the global registry.

    Args:
        key: Unique string identifier (e.g. "create_document").
        label: Human-readable label (e.g. "Create Document").
        config_schema: List of field definition dicts describing the config UI.
            Each dict has: name, type, label, optional (default), options.
        execute_fn: Callable(context, config) -> dict with at least "status".
            Must raise on failure (don't swallow exceptions).
    """
    ACTION_TYPES[key] = {
        "key": key,
        "label": label,
        "config_schema": config_schema,
        "execute": execute_fn,
    }


def get_action_type(key):
    """Return the action type dict for *key*, or None."""
    return ACTION_TYPES.get(key)


def get_all_action_types():
    """Return metadata for every registered type (no execute functions)."""
    return {
        k: {"key": v["key"], "label": v["label"], "config_schema": v["config_schema"]}
        for k, v in ACTION_TYPES.items()
    }


# ---------------------------------------------------------------------------
# Import built-in action types so they register on first import of this package.
# ---------------------------------------------------------------------------
from automation_builder.action_types import create_document  # noqa: E402, F401
from automation_builder.action_types import send_email  # noqa: E402, F401
from automation_builder.action_types import http_request  # noqa: E402, F401
from automation_builder.action_types import telegram  # noqa: E402, F401
from automation_builder.action_types import update_field  # noqa: E402, F401
