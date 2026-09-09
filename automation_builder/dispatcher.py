"""Hook dispatcher — routes document events to matching automations.

Uses a wildcard ``*`` doc_events hook so a single handler fires for every
DocType.  The handler is intentionally cheap: it does an indexed query for
enabled automations matching the doctype+event, and returns immediately if
there are none.
"""

import json
import operator as op

import frappe

from automation_builder.action_types import get_action_type

# ---------------------------------------------------------------------------
# Event mapping: Frappe hook method names → automation trigger_event strings
# ---------------------------------------------------------------------------
EVENT_MAP = {
    "after_insert": "After Insert",
    "on_update": "On Update",
    "on_submit": "On Submit",
    "on_cancel": "On Cancel",
}

OPERATORS = {
    "=": op.eq,
    "!=": op.ne,
    ">": op.gt,
    "<": op.lt,
    ">=": op.ge,
    "<=": op.le,
}


# ---------------------------------------------------------------------------
# Hook entry point — called for every document save/submit/cancel site-wide
# ---------------------------------------------------------------------------
def on_doc_event(doc, method):
    """Fired on every document event. Finds matching automations and enqueues."""
    trigger_event = EVENT_MAP.get(method)
    if not trigger_event:
        return

    # Re-entry guard: skip if this doc is being saved by an automation action
    guard_key = f"_automation_running_{doc.doctype}_{doc.name}"
    if frappe.flags.get(guard_key):
        return

    try:
        automations = frappe.get_all(
            "Automation",
            filters={
                "enabled": 1,
                "trigger_doctype": doc.doctype,
                "trigger_event": trigger_event,
            },
            fields=["name", "condition_field", "condition_operator", "condition_value"],
        )

        if not automations:
            return

        for auto in automations:
            if _evaluate_condition(doc, auto):
                frappe.enqueue(
                    "automation_builder.dispatcher.execute_automation",
                    queue="short",
                    automation_name=auto.name,
                    ref_doctype=doc.doctype,
                    ref_name=doc.name,
                )
    except Exception:
        frappe.log_error(title="Automation Builder dispatch error")


# ---------------------------------------------------------------------------
# Background job — create Automation Run and execute actions via registry
# ---------------------------------------------------------------------------
def execute_automation(automation_name, ref_doctype, ref_name):
    """Background job: create Automation Run record and execute actions."""
    guard_key = f"_automation_running_{ref_doctype}_{ref_name}"
    frappe.flags[guard_key] = True
    try:
        automation = frappe.get_doc("Automation", automation_name)
        doc = frappe.get_doc(ref_doctype, ref_name)

        run = frappe.get_doc(
            {
                "doctype": "Automation Run",
                "automation": automation_name,
                "reference_doctype": ref_doctype,
                "reference_name": ref_name,
                "started_at": frappe.utils.now_datetime(),
            }
        )

        workflow_json = automation.workflow_json
        if not workflow_json:
            run.status = "Failed"
            run.error = "No workflow_json found on automation"
            run.ended_at = frappe.utils.now_datetime()
            run.insert(ignore_permissions=True)
            return

        try:
            workflow = json.loads(workflow_json)
        except (json.JSONDecodeError, TypeError):
            run.status = "Failed"
            run.error = "Invalid workflow_json"
            run.ended_at = frappe.utils.now_datetime()
            run.insert(ignore_permissions=True)
            return

        actions = workflow.get("actions", [])

        # Derive execution order from edges graph (single source of truth).
        # Walk from trigger → next source → next source ... following edges.
        edges = workflow.get("edges", [])
        nodes = workflow.get("nodes", [])
        if edges and nodes:
            graph = _build_edge_graph(edges)
            ordered_ids = _walk_graph(graph, "trigger")
            if ordered_ids:
                node_map = {n["id"]: n for n in nodes}
                edge_actions = []
                for nid in ordered_ids:
                    node = node_map.get(nid)
                    if node and node.get("type") == "action" and node.get("data", {}).get("action_type"):
                        edge_actions.append({
                            "type": node["data"]["action_type"],
                            "config": {k: v for k, v in node["data"].items() if k != "action_type"},
                        })
                if edge_actions:
                    actions = edge_actions

        any_failed = False
        step_results = []

        context = {"doc": doc, "ref_doctype": ref_doctype, "ref_name": ref_name}

        for action_cfg in actions:
            action_type = action_cfg.get("type")
            config = action_cfg.get("config", {})
            step_result = _execute_action(action_type, config, context)
            step_results.append(step_result)

            if step_result.get("status") != "Success":
                any_failed = True

        run.status = "Failed" if any_failed else "Success"
        run.log = json.dumps(step_results, indent=2)
        run.ended_at = frappe.utils.now_datetime()
        run.insert(ignore_permissions=True)

    except Exception as e:
        frappe.log_error(title="Automation Builder execution error")
        try:
            frappe.get_doc(
                {
                    "doctype": "Automation Run",
                    "automation": automation_name,
                    "reference_doctype": ref_doctype,
                    "reference_name": ref_name,
                    "status": "Failed",
                    "error": frappe.get_traceback(),
                    "started_at": frappe.utils.now_datetime(),
                    "ended_at": frappe.utils.now_datetime(),
                }
            ).insert(ignore_permissions=True)
        except Exception:
            frappe.log_error(title="Automation Builder: failed to create error Run record")
    finally:
        frappe.flags[guard_key] = False


def _execute_action(action_type, config, context):
    """Look up *action_type* in the registry and call its execute()."""
    handler = get_action_type(action_type)
    if handler is None:
        return {
            "step_type": action_type,
            "status": "Failed",
            "error": f"Unknown action type: {action_type}",
        }

    try:
        return handler["execute"](context, config)
    except Exception as e:
        return {
            "step_type": action_type,
            "status": "Failed",
            "error": str(e),
        }


def _evaluate_condition(doc, automation):
    """Evaluate the automation's condition against the document."""
    field = automation.condition_field
    operator = automation.condition_operator
    expected = automation.condition_value

    if not field or not operator:
        return True

    actual = doc.get(field)
    comparator = OPERATORS.get(operator)
    if comparator is None:
        return False

    if operator in (">", "<", ">=", "<="):
        try:
            actual = float(actual)
            expected = float(expected)
        except (TypeError, ValueError):
            pass

    return comparator(actual, expected)


# ---------------------------------------------------------------------------
# Edge-graph helpers — derive execution order from visual edges
# ---------------------------------------------------------------------------
def _build_edge_graph(edges):
    """Build adjacency list from edges array: {source_id: [target_id, ...]}."""
    graph = {}
    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        if src and tgt:
            graph.setdefault(src, []).append(tgt)
    return graph


def _walk_graph(graph, start_id):
    """Walk graph from start_id following ALL outgoing edges (BFS).

    Returns ordered list of node IDs in execution order (trigger first,
    then all nodes reachable from it). Handles branching (multiple
    outgoing edges from a single node).
    """
    from collections import deque

    visited = []
    seen = set()
    queue = deque([start_id])

    while queue:
        current = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        visited.append(current)
        targets = graph.get(current, [])
        for t in targets:
            if t not in seen:
                queue.append(t)

    return visited
