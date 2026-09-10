"""Switch Case logic type — evaluates a field against multiple cases.

Unlike action types (which have side effects and always continue to the next node),
logic types determine WHICH edge to follow next based on evaluating their config
against the run context.

Output handles are dynamic: one per configured case (case-0, case-1, ...) plus a
fixed 'default' handle for no match.
"""

from automation_builder.action_types import register_action_type
from automation_builder.action_types._helpers import resolve_value

CONFIG_SCHEMA = [
    {"name": "field_to_check", "type": "field_select", "label": "Field to Check"},
    {
        "name": "cases",
        "type": "case_list",
        "label": "Cases",
        "description": "Each case defines a value to match and a corresponding output branch.",
    },
]


def get_output_handles(config):
    """Return dynamic output handles based on configured cases."""
    cases = config.get("cases", [])
    handles = []
    for i, case in enumerate(cases):
        label = case.get("case_value", "") or f"Case {i + 1}"
        handles.append({"id": f"case-{i}", "label": label})
    handles.append({"id": "default", "label": "Default"})
    return handles


def evaluate_branch(config, context):
    """Evaluate Switch against cases and return (source_handle, log_message).

    config: dict with field_to_check, cases (list of {case_value})
    context: dict with 'doc' (the trigger document)
    """
    doc = context.get("doc")
    field = config.get("field_to_check", "")
    actual = doc.get(field) if doc else None
    field_value = str(actual) if actual is not None else ""

    cases = config.get("cases", [])
    for i, case in enumerate(cases):
        case_val = resolve_value(case.get("case_value", ""), context)
        if str(case_val) == field_value:
            return (
                f"case-{i}",
                f"SWITCH {field}='{field_value}' -> case-{i} ('{case_val}')",
            )

    return "default", f"SWITCH {field}='{field_value}' -> default (no match)"


register_action_type(
    key="switch_case",
    label="Switch",
    config_schema=CONFIG_SCHEMA,
    node_category="logic",
    output_handles="dynamic",
    evaluate_branch=evaluate_branch,
    get_output_handles=get_output_handles,
)
