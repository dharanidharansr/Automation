# Triggers, Multi-Trigger, and Cross-Doctype Model

Deep-dive on how automations start, how multiple triggers interact, and how the system
handles the ambiguity that arises when two different doctypes can fire the same automation.

---

## 1. What a Trigger Is

An **Automation** has a child table called `Automation Trigger` (one or more rows). Each row
specifies a **DocType** and a **Frappe hook event**. When a document of that doctype is saved
(submitted, cancelled, etc.), the hook fires and the dispatcher looks for automations whose
trigger rows match.

Multiple trigger rows use **OR semantics** — ANY matching row is sufficient to start a run.

### Real example

```
Automation: "New Lead Follow-up"
  Trigger row 1:  DocType = Lead,      Event = After Insert,  Conditions: lead_source = "Web"
  Trigger row 2:  DocType = ToDo,      Event = On Update,     Conditions: (none)
```

| What happens | Run starts? | Why |
|---|---|---|
| Lead inserted, `lead_source = "Web"` | Yes | Row 1 matches (doctype + event + condition) |
| Lead inserted, `lead_source = "Campaign"` | No | Row 1 matches doctype+event but condition fails; Row 2 doesn't match (wrong doctype) |
| ToDo updated (any) | Yes | Row 2 matches doctype+event, no conditions to block |
| Note inserted | No | No trigger row targets Note/After Insert |

**Important:** all trigger rows are evaluated against the **same document** (the one that
fired the hook). A Lead document is tested against both the Lead row and the ToDo row. The
ToDo row's conditions will typically fail because a Lead doesn't have ToDo fields — this is
expected and harmless.

### How dispatch works (the real path)

1. Frappe's hook system calls `on_doc_event(doc, method)` for every save/submit/cancel site-wide
   (`dispatcher.py:118`)
2. `on_doc_event` maps the method name to an event string via `EVENT_MAP` (`dispatcher.py:19-24`):
   - `after_insert` → `"After Insert"`
   - `on_update` → `"On Update"`
   - `on_submit` → `"On Submit"`
   - `on_cancel` → `"On Cancel"`
3. A SQL query joins `tabAutomation` with `tabAutomation Trigger` to find enabled+published
   automations matching the doctype+event (`dispatcher.py:136-145`)
4. For each match, `_evaluate_trigger_conditions` checks all trigger rows against the document
   (`dispatcher.py:164-202`)
5. If any row matches, `frappe.enqueue("automation_builder.dispatcher.execute_automation", ...)`
   is called (`dispatcher.py:153-159`)

---

## 2. Conditions Within a Trigger Row

Each trigger row can have multiple conditions stored in the **Automation Trigger Condition**
grandchild table. These are combined using the `condition_logic` field on the row:

| `condition_logic` value | Behaviour |
|---|---|
| `"All must match"` (default) | AND — every condition must be true |
| `"Any must match"` | OR — at least one condition must be true |

### Supported operators

Listed from `Automation Trigger Condition` doctype schema (`automation_trigger_condition.json`)
and the evaluation logic in `dispatcher.py:26-112`:

| Operator | Behaviour | Example |
|---|---|---|
| `=` | Exact equality | `status = "Open"` |
| `!=` | Not equal | `status != "Closed"` |
| `>` | Greater than (numeric coercion) | `amount > 100` |
| `<` | Less than (numeric coercion) | `amount < 50` |
| `>=` | Greater than or equal | `priority >= 3` |
| `<=` | Less than or equal | `score <= 10` |
| `like` | Case-insensitive substring match; supports `%` wildcard | `title like "%urgent%"` |
| `not like` | Inverse of like | `name not like "%test%"` |
| `in` | Value is one of comma-separated list | `status in "Open,Pending"` |
| `not in` | Value is NOT in comma-separated list | `priority not in "Low,Very Low"` |
| `is set` | Field is non-null and non-empty | `email_id is set` |
| `is not set` | Field is null or empty | `description is not set` |

When a trigger row has **no conditions** in the grandchild table, the row always matches
(any document of the right doctype+event fires it).

### Legacy path

Trigger rows also have hidden legacy fields (`condition_field`, `condition_operator`,
`condition_value`) for backward compatibility. If the grandchild table is empty, these flat
fields are evaluated instead (`dispatcher.py:197-200`). New automations should use the
grandchild table.

---

## 3. Cross-Doctype Triggers and the Field-Reference Problem

When an automation has triggers on two different doctypes (e.g., Lead + ToDo), a problem
arises in the action nodes downstream: **which doctype's fields should the field picker show?**

A Lead has `lead_name`, `company`, `email_id`. A ToDo has `description`, `assigned_to`. They
share almost no fields. If a single "Update Field" action node tries to reference
`{{trigger.lead_name}}` but the run was triggered by a ToDo, that token resolves to an empty
string — silently producing a broken update.

The system needs a way to either:
- **Scope** an action to a specific doctype (skip it when the wrong doctype fires), or
- **Share** an action across doctypes using only common fields (`name`, `owner`, `creation`)

This is what `trigger_doctype_select` solves.

---

## 4. `trigger_doctype_select` — The Three Modes

This config field appears on **Update Field** and **Create Document** action types only
(confirmed in `update_field.py:11-15`, `create_document.py:11-15`). It is **not** present on
Send Email, Telegram, HTTP Request, IF, Switch, or Condition nodes.

The dropdown is **only visible** when the automation has more than one trigger row
(`ActionConfigForm.vue:158-160`).

### Mode 1: Specific doctype (e.g., `"Lead"`)

The node **only executes** when that exact doctype fired this run. Any other firing doctype
causes the node to be **SKIPPED** (not failed).

The skip check happens in `_execute_action` (`dispatcher.py:389-400`) **before** the action's
`execute()` function is called — so no side effects occur.

**Log message format** (exact string from `dispatcher.py:396-399`):

```
Action scoped to {scoped_doctype}, this run was triggered by {run_doctype}
```

Example: `"Action scoped to Lead, this run was triggered by ToDo"`

A Skipped step does **not** mark the overall Automation Run as Failed. The run status logic
(`dispatcher.py:311,323`) only counts `"Failed"` — `"Skipped"` is treated as success for the
run's overall status.

### Mode 2: `"Any (whichever triggered)"`

The node always executes regardless of which configured trigger fired. The dropdown value is
the literal string `"any"` (`ActionConfigForm.vue:62`).

When `trigger_doctype_select == "any"`, the field picker in the UI falls back to showing the
**first** trigger doctype's fields as a best-effort guide (`ActionConfigForm.vue:224-225`).
At runtime, `{{trigger.fieldname}}` tokens resolve against whichever document actually
triggered this run.

**Critical behavior:** tokens referencing fields that don't exist on the actual triggering
doctype resolve to an **empty string**, not an error. The `try/except` in `resolve_value`
(`_helpers.py:38-42`) catches the `AttributeError`/`TypeError` and returns `""`.

The hint text shown in the UI (`ActionConfigForm.vue:65-68`):

> Resolves against whichever document triggered this run. Tokens for fields not on that
> doctype resolve to empty string. Use common fields only, or duplicate this node per branch
> when per-doctype logic differs.

### Mode 3: Unset / empty string (default)

When `trigger_doctype_select` is not set (empty string or absent from config), the node
**always executes** — it behaves the same as "Any" mode at runtime.

The difference is in the field picker: with no selection, `loadFields()` uses
`props.triggerDoctype` (the first trigger's doctype) as the field reference
(`ActionConfigForm.vue:226`). With `"any"` explicitly selected, it uses
`props.triggerDoctypes[0]` — functionally the same value but semantically explicit.

**There is no skip behavior when unset.** The skip check in `_execute_action`
(`dispatcher.py:392`) requires `scoped_doctype` to be truthy **and** not `"any"` **and**
not equal to `run_doctype`. An empty string is falsy, so the check short-circuits and the
node executes.

---

## 5. Two Patterns for Shared vs Per-Doctype Logic

### Pattern A — Shared step, common fields only

Use **"Any" mode** and only reference fields you know exist on every configured trigger
doctype. The `name` field exists on every Frappe document, so `{{trigger.name}}` is always
safe.

```
Lead Trigger ──┐
               ├──> Shared Action (Any mode) ──> Send common notification
ToDo Trigger ──┘
```

### Pattern B — Genuinely different logic per doctype

Duplicate the node once per branch instead of trying to share one. Each copy gets its own
`trigger_doctype_select` set to a specific doctype, with doctype-specific field references.

```
Lead Trigger ──> Lead Action (scoped to Lead, references lead_name)
ToDo Trigger ──> ToDo Action (scoped to ToDo, references description)
```

**When to use which:** if the shared node uses only common fields (`name`, `owner`,
`creation`), Pattern A is cleaner. If each doctype needs different field names or different
actions entirely, Pattern B avoids empty-token confusion.

```mermaid
flowchart TD
    T1[Lead Trigger] --> Shared1{{"Shared node<br/>(Any mode)"}}
    T2[ToDo Trigger] --> Shared1
    Shared1 --> Action1[Send common notification]

    T3[Lead Trigger] --> LeadAction["Lead-specific action<br/>(references lead_name)"]
    T4[ToDo Trigger] --> ToDoAction["ToDo-specific action<br/>(references description)"]
```

---

## 6. Doctype Branching via IF + "Triggering Doctype"

### Current state: no built-in pseudo-field

**There is currently no "Triggering Doctype" pseudo-field in the IF node config UI.**
The IF node's field picker (`ConfigPanel.vue:64-67`) loads real fields from the trigger
doctype via `getDoctypeFields()`. There is no synthetic option for `trigger_doctype` or
`ref_doctype`.

The `trigger_doctype` value **is** available in the execution context
(`dispatcher.py:274`: `context["trigger_doctype"] = ref_doctype`), but the IF node's
`evaluate_branch` function (`if_condition.py:46-77`) evaluates `doc.get(field)` — it reads
fields from the document, not from the context dict. So there is no way to branch on the
triggering doctype using the current IF node.

### Workaround: doctype-specific field check

Since different doctypes have different fields, you can branch indirectly by checking for a
field that exists on one doctype but not the other:

```
IF: lead_name is set  →  True branch: Lead-specific actions
                       →  False branch: ToDo-specific actions (or fallthrough)
```

A Lead document has `lead_name`, so the condition evaluates to TRUE. A ToDo document does not
have `lead_name`, so `doc.get("lead_name")` returns `None` and the condition evaluates to
FALSE.

This is not clean, and a proper "Triggering Doctype" pseudo-field would be better. If this
feature is added later, it would likely be a synthetic field in the IF node's field picker
that resolves to `context["trigger_doctype"]` instead of `doc.get(field)`.

---

## 7. Full Worked Example, End to End

### Setup

```
Automation: "Lead + ToDo Follow-up"
  Status: Published
  Triggers:
    Row 1: Lead / After Insert / Conditions: lead_source = "Web"
    Row 2: ToDo / After Insert / Conditions: (none)

  Graph:
    trigger ──> IF (lead_name is set)
                   ├─ True ──> Update Field (scoped to Lead)
                   │             target: Same Document
                   │             field: status = "Contacted"
                   └─ False ──> Update Field (scoped to ToDo)
                                  target: Same Document
                                  field: description = "Auto follow-up"
```

### Case 1: Lead inserted with `lead_source = "Web"`

1. Frappe calls `on_doc_event(lead, "after_insert")`
2. Dispatcher query finds the automation (Lead/After Insert matches)
3. `_evaluate_trigger_conditions`: Row 1 conditions (`lead_source = "Web"`) → **TRUE**. Row 2
   evaluated against the Lead (ToDo fields don't exist) → **FALSE**. Overall: **TRUE**.
4. `frappe.enqueue(execute_automation, ...)`
5. Graph walk starts at trigger node
6. IF node: `lead_name` → `"Test Lead"` (not null) → **TRUE** → follows `if-true` edge
7. Update Field action: `trigger_doctype_select = "Lead"`, `ref_doctype = "Lead"` → match,
   executes. Sets `status = "Contacted"` on the Lead.
8. Run status: **Success**. Log: `[{"step_type": "if_condition", "status": "Success", ...}, {"step_type": "update_field", "status": "Success", ...}]`

### Case 2: ToDo inserted (any description)

1. Frappe calls `on_doc_event(todo, "after_insert")`
2. Dispatcher query finds the automation (ToDo/After Insert matches)
3. `_evaluate_trigger_conditions`: Row 1 (Lead/After Insert) — the query matches on
   doctype+event, but the Lead conditions are evaluated against the ToDo → **FALSE**. Row 2
   (ToDo/After Insert, no conditions) → **TRUE**. Overall: **TRUE**.
4. `frappe.enqueue(execute_automation, ...)`
5. Graph walk starts at trigger node
6. IF node: `lead_name` → `None` (ToDo has no such field) → **FALSE** → follows `if-false` edge
7. Update Field action: `trigger_doctype_select = "ToDo"`, `ref_doctype = "ToDo"` → match,
   executes. Sets `description = "Auto follow-up"` on the ToDo.
8. Run status: **Success**. Log: `[{"step_type": "if_condition", "status": "Success", ...}, {"step_type": "update_field", "status": "Success", ...}]`

### Case 3: Lead inserted with `lead_source = "Campaign"`

1. Dispatcher finds the automation (Lead/After Insert matches)
2. `_evaluate_trigger_conditions`: Row 1 conditions (`lead_source = "Web"`) → **FALSE**
   (actual is "Campaign"). Row 2 evaluated against Lead → **FALSE**. Overall: **FALSE**.
3. Automation is NOT enqueued. No run is created.

### Run History would show

For Case 1:
| Step | Type | Status | Output |
|---|---|---|---|
| 1 | if_condition | Success | `IF lead_name = 'Test Lead' -> TRUE (actual: 'Test Lead')` |
| 2 | update_field | Success | `Updated Lead L-00001: status` |

For Case 2:
| Step | Type | Status | Output |
|---|---|---|---|
| 1 | if_condition | Success | `IF lead_name = '' -> FALSE (actual: None)` |
| 2 | update_field | Success | `Updated ToDo TD-00001: description` |

---

## 8. Testing Notes & Honest Gaps

### Why full-path tests matter

The Stage 22 follow-up discovered that skip-detection logic for `trigger_doctype_select`
was reported as "built and tested" but actually did not exist — the tests were calling
`execute_automation()` directly, bypassing `on_doc_event()` and the SQL dispatch query. A
regression in the dispatch path would have gone undetected.

### What IS covered by a full-path test

| Test name | What it exercises |
|---|---|
| `test_full_path_skip_via_on_doc_event` | `doc.insert()` → `on_doc_event()` → SQL dispatch query → `frappe.enqueue` (patched sync) → `execute_automation()` → graph walk → `_execute_action` skip check. Tests both the ToDo (skips) and Lead (executes) branches. |

This is the **only** test that exercises the complete chain from document event to action
execution for the skip-detection feature.

### What is covered by narrower/unit-level tests

| Test name | Level | What it covers |
|---|---|---|
| `test_specific_doctype_skips_on_wrong_trigger` | Direct call to `execute_automation()` | Skip logic inside `_execute_action` — confirms Skipped status and message format. Does NOT test dispatch path. |
| `test_any_mode_resolves_common_field_and_empty_for_missing` | Direct call + `resolve_value()` | Token resolution with "any" mode — confirms common fields resolve and missing fields resolve to empty string. |
| `test_any_mode_node_executes_not_skips` | Direct call to `execute_automation()` | "Any" mode never skips — confirms node executes for both Lead and Note triggers. |
| `test_trigger_token_resolves_against_triggering_doc` | Unit test of `resolve_value()` | `{{trigger.fieldname}}` token substitution. |
| `test_trigger_doctype_hint_in_context` | Direct call to `execute_automation()` | Context includes `trigger_doctype` key. |

### What is NOT covered

- **Dispatch path for "Any" mode**: no full-path test inserts a document and verifies the
  "Any"-mode action executes via `on_doc_event()`.
- **Condition evaluation in cross-doctype triggers**: `test_dispatch_lead_insert_matches_lead_trigger`
  tests `_evaluate_trigger_conditions` directly but does not exercise the full path.
- **Multiple trigger rows with conditions**: no test creates an automation with two trigger
  rows (different doctypes, each with conditions) and fires both paths end-to-end.
- **Frontend rendering**: no automated test verifies the `trigger_doctype_select` dropdown
  renders, the "Any" hint text appears, or the field picker updates when the selection
  changes. (No display server available for browser testing.)

### Where to be skeptical

Any claim about the cross-doctype model that was verified **only** via direct calls to
`execute_automation()` or `resolve_value()` should be treated as partially verified — the
dispatch path (the SQL query in `on_doc_event`, the `frappe.enqueue` handoff) is a separate
code path that could regress independently.
