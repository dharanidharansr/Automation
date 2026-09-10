"""Hook dispatcher — routes document events to matching automations.

Uses a wildcard ``*`` doc_events hook so a single handler fires for every
DocType.  The handler is intentionally cheap: it does an indexed query for
enabled + published automations matching the doctype+event, and returns
immediately if there are none.
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

    # Skip during migration to prevent recursion
    if frappe.flags.get("in_migrate"):
        return

    # Re-entry guard: skip if this doc is being saved by an automation action
    guard_key = f"_automation_running_{doc.doctype}_{doc.name}"
    if frappe.flags.get(guard_key):
        return

    try:
        # Query automations: must be enabled AND published
        # Join with Automation Trigger child table to match trigger_doctype and trigger_event
        automations = frappe.db.sql("""
            SELECT DISTINCT a.name
            FROM `tabAutomation` a
            INNER JOIN `tabAutomation Trigger` at
                ON at.parent = a.name
            WHERE a.enabled = 1
                AND a.status = 'Published'
                AND at.trigger_doctype = %s
                AND at.trigger_event = %s
        """, (doc.doctype, trigger_event), as_dict=True)

        if not automations:
            return

        # For each matching automation, check conditions from triggers table
        for auto in automations:
            if _evaluate_trigger_conditions(auto.name, doc):
                frappe.enqueue(
                    "automation_builder.dispatcher.execute_automation",
                    queue="short",
                    automation_name=auto.name,
                    ref_doctype=doc.doctype,
                    ref_name=doc.name,
                )
    except Exception:
        frappe.log_error(title="Automation Builder dispatch error")


def _evaluate_trigger_conditions(automation_name, doc):
    """Evaluate all trigger conditions for an automation against the document.

    An automation can have multiple triggers (Phase 2 prep). For now, typically
    only one trigger row exists. Returns True if ANY trigger's conditions match.
    """
    triggers = frappe.get_all(
        "Automation Trigger",
        filters={"parent": automation_name},
        fields=["condition_field", "condition_operator", "condition_value"],
    )

    if not triggers:
        return True

    for trigger in triggers:
        if _evaluate_condition(doc, trigger):
            return True

    return False


def _evaluate_condition(doc, trigger_row):
    """Evaluate a single condition against the document."""
    field = trigger_row.condition_field
    operator = trigger_row.condition_operator
    expected = trigger_row.condition_value

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

        # Use graph_definition (new format), fall back to workflow_json (legacy)
        graph_json = automation.graph_definition or automation.legacy_workflow_json
        if not graph_json:
            run.status = "Failed"
            run.error = "No graph_definition found on automation"
            run.ended_at = frappe.utils.now_datetime()
            run.insert(ignore_permissions=True)
            return

        try:
            graph = json.loads(graph_json)
        except (json.JSONDecodeError, TypeError):
            run.status = "Failed"
            run.error = "Invalid graph_definition JSON"
            run.ended_at = frappe.utils.now_datetime()
            run.insert(ignore_permissions=True)
            return

        # Build node map for lookup during execution
        node_map = {n["id"]: n for n in graph.get("nodes", [])}

        context = {"doc": doc, "ref_doctype": ref_doctype, "ref_name": ref_name}

        # Walk graph with branching evaluation
        step_trace = _walk_graph(graph, "trigger", context)

        any_failed = False
        step_results = []

        for entry in step_trace:
            entry_type = entry.get("type")
            entry_node_id = entry.get("node_id")

            if entry_type == "branch":
                # Branching decision — log which branch was taken
                step_result = {
                    "step_type": entry.get("node_type", "unknown"),
                    "status": "Success",
                    "branch_taken": entry.get("branch_taken", ""),
                    "output": entry.get("output", ""),
                }
                step_results.append(step_result)

                # Also create Automation Run Step record
                _create_run_step(run, entry, node_map)

            elif entry_type == "action":
                node = node_map.get(entry_node_id, {})
                data = node.get("data", {})
                action_type = data.get("action_type")
                if not action_type:
                    continue
                config = {k: v for k, v in data.items() if k != "action_type"}
                step_result = _execute_action(action_type, config, context)
                step_results.append(step_result)

                if step_result.get("status") != "Success":
                    any_failed = True

                # Create Automation Run Step record
                _create_run_step(run, {
                    "type": "action",
                    "node_id": entry_node_id,
                    "step_type": action_type,
                    "status": step_result.get("status", "Failed"),
                    "output": step_result.get("output", step_result.get("error", "")),
                }, node_map)

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


def _create_run_step(run, entry, node_map):
    """Create an Automation Run Step child record for a trace entry."""
    node_id = entry.get("node_id", "")
    node = node_map.get(node_id, {})
    node_type = node.get("type", entry.get("type", ""))

    step_type = entry.get("step_type", "")
    if not step_type and node_type == "action":
        step_type = node.get("data", {}).get("action_type", "action")

    step = frappe.get_doc({
        "doctype": "Automation Run Step",
        "node_id": node_id,
        "node_type": node_type,
        "step_type": step_type or node_type,
        "status": entry.get("status", "Success"),
        "branch_taken": entry.get("branch_taken", ""),
        "output": entry.get("output", ""),
        "error": entry.get("error", ""),
    })
    run.append("steps", step)


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


# ---------------------------------------------------------------------------
# Branching-aware graph walker
# ---------------------------------------------------------------------------
def _evaluate_branching_node(node, context):
    """Evaluate a branching node (IF/Switch) and determine which handle to follow.

    Returns (source_handle, log_message) tuple.
    """
    node_type = node.get("type")
    node_data = node.get("data", {})
    handler = get_action_type(
        "if_condition" if node_type == "if" else "switch_case"
    )
    if handler and "evaluate_branch" in handler:
        return handler["evaluate_branch"](node_data, context)
    return None, f"Unknown branching type: {node_type}"


def _walk_graph(graph, start_id, context=None):
    """Walk graph from start_id, evaluating branching nodes if context is provided.

    Returns a list of trace entries: [{"type": "branch"|"action"|"node", ...}]
    preserving execution order.

    When context is None (structural walk), follows the first outgoing edge of
    every node — used for UI layout or when branching evaluation is not needed.
    When context is provided (execution walk), branching nodes are evaluated and
    only the matching branch is followed.
    """
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    nodes_map = {n["id"]: n for n in nodes}

    # Build edge map: source_id -> [(sourceHandle, target_id), ...]
    edge_map = {}
    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        sh = e.get("sourceHandle", "")
        if src and tgt:
            edge_map.setdefault(src, []).append((sh, tgt))

    trace = []
    seen = set()
    current_id = start_id

    while current_id and current_id not in seen:
        seen.add(current_id)
        node = nodes_map.get(current_id, {})
        node_type = node.get("type")
        outgoing = edge_map.get(current_id, [])

        if not outgoing:
            # Leaf node — end of this branch
            if node_type == "action" and node.get("data", {}).get("action_type"):
                trace.append({"type": "action", "node_id": current_id})
            break

        if context and node_type in ("if", "switch"):
            # Evaluate branching node
            source_handle, log_msg = _evaluate_branching_node(node, context)
            trace.append({
                "type": "branch",
                "node_id": current_id,
                "node_type": node_type,
                "branch_taken": source_handle,
                "output": log_msg,
            })
            # Follow only the matching edge
            next_id = None
            for sh, tgt in outgoing:
                if sh == source_handle:
                    next_id = tgt
                    break
            if next_id is None and outgoing:
                # Fallback: follow first edge
                next_id = outgoing[0][1]
            current_id = next_id
        else:
            # Non-branching node: action, trigger, condition
            if node_type == "action" and node.get("data", {}).get("action_type"):
                trace.append({"type": "action", "node_id": current_id})
            # Follow the single outgoing edge
            current_id = outgoing[0][1] if len(outgoing) == 1 else (outgoing[0][1] if outgoing else None)

    return trace


# ---------------------------------------------------------------------------
# Legacy helpers — kept for backward compatibility / structural graph walks
# ---------------------------------------------------------------------------
def _extract_actions_from_graph(graph):
    """Extract action configurations from graph, in structural traversal order.

    Follows the first outgoing edge at each node (no branching evaluation).
    Used for graph save/load validation, not execution.
    """
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])

    if not nodes:
        return []

    node_map = {n["id"]: n for n in nodes}
    graph_adj = _build_edge_graph(edges)
    ordered_ids = _walk_graph_bfs(graph_adj, "trigger")

    actions = []
    for nid in ordered_ids:
        node = node_map.get(nid)
        if node and node.get("type") == "action" and node.get("data", {}).get("action_type"):
            actions.append({
                "type": node["data"]["action_type"],
                "config": {k: v for k, v in node["data"].items() if k != "action_type"},
            })

    return actions


def _build_edge_graph(edges):
    """Build adjacency list from edges array: {source_id: [target_id, ...]}."""
    graph = {}
    for e in edges:
        src = e.get("source")
        tgt = e.get("target")
        if src and tgt:
            graph.setdefault(src, []).append(tgt)
    return graph


def _walk_graph_bfs(graph, start_id):
    """BFS walk from start_id following ALL outgoing edges.

    Returns ordered list of node IDs in execution order. Handles branching
    (multiple outgoing edges from a single node) by visiting all targets.
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
