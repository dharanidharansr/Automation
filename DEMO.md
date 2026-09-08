
# Automation Builder — Demo Walkthrough

## One-sentence pitch

> The Automation Builder lets non-technical users visually create "when X happens, do Y" workflows for Frappe — no developer needed for simple automations like lead follow-ups.

---

## Before you start

Run the demo seed script to set up clean sample data:

```bash
bench --site automate.localhost execute automation_builder.demo_setup.run
```

Start the bench:

```bash
bench start
```

---

## Step-by-step walkthrough

### 1. Open the Automation Builder

- Navigate to `http://localhost:8000/app/spa-builder`
- You'll see the **Automation List** showing the pre-configured automation: "Lead Qualified Demo"

**What to say:** *"This is the automation dashboard. Each card represents a workflow that runs automatically when certain conditions are met."*

### 2. Open the Lead → Qualified automation

- Click on "Lead Qualified Demo" to open the builder canvas
- Walk through each node:

  - **Trigger node (blue):** "This automation fires on Lead → On Update"
  - **Condition node (amber):** "It checks if the Lead's status equals Qualified"
  - **Action 1 (green):** "If matched, it creates a follow-up Task linked to the Lead"
  - **Action 2 (green):** "Then it sends an email notification to the Lead's email address"

**What to say:** *"Each node is configurable — you can click any node to change its settings in the side panel. The visual flow shows exactly what happens and in what order."*

### 3. Trigger the automation

- Open a test Lead record: navigate to the CRM Lead list and find "Demo Open Lead" (status: New)
- Change its status to **Qualified**
- Click Save

**What to say:** *"Watch what happens when I qualify this lead..."*

### 4. Check the Run History

- Go back to the Automation Builder (`/app/spa-builder`)
- Click "Runs" on the Lead Qualified Demo card
- You should see a **Success** run with a log showing:
  - `Condition matched: status = Qualified`
  - `Created Task TASK-XXXXX`
  - `Sent email to open@example.com`

**What to say:** *"The automation ran successfully. Here's the full audit trail — you can see exactly what happened and when."*

### 5. Verify the results

- **Task created:** Navigate to Automation Task list → find "Follow up: Demo Open Lead"
  - It's linked to the Lead, status is Open
- **Email sent:** If your bench has email configured, the Lead's email received a notification. If not, the log will show "send failed" gracefully — the automation still succeeded.

---

## What's scoped for v0 vs. the full product

| Feature | v0 (this demo) | Full product |
|---------|----------------|--------------|
| Trigger doctypes | Lead only | Any DocType |
| Condition types | Single field/operator/value | Multiple conditions with AND/OR logic |
| Action types | Create Task, Send Email | Update fields, webhooks, custom scripts |
| Branching | Linear chain only | If/else branches, parallel paths |
| UI | Vue canvas with 3 node types | Full drag-and-drop with custom node library |
| Execution | Background job via `frappe.enqueue` | Reliable queue with retry, rate limiting |
| Run history | Basic log per run | Step-by-step timing, per-action status |
| Error handling | Graceful email failure | Alerting, rollback, dead letter queue |

---

## Architecture (for the curious)

```
Frontend (Vue 3 + Vue Flow)
  ↓ save_automation()
  ↓ workflow_json stored in Automation DocType
  ↓
Backend (hooks.py → dispatcher.py → executor.py)
  ↓ on Lead on_update
  ↓ evaluate condition
  ↓ frappe.enqueue → execute_automation
  ↓ create Task + send email
  ↓ log results to Automation Run
```

- The frontend is a standard Vite-built Vue SPA served via a Frappe Page
- The backend uses Frappe's `doc_events` hook system and background job queue
- All state is persisted in Frappe DocTypes (Automation, Automation Run, Automation Task)
