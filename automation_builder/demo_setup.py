"""Demo seed data script — idempotent, safe to re-run.

Usage:
    bench --site automate.localhost execute automation_builder.demo_setup.run
"""

import frappe


def run():
    """Set up clean demo state: sample Leads + Automation record."""
    _ensure_automation()
    leads = _create_leads()
    print(f"Demo ready: {len(leads)} leads, 1 automation")
    for lead in leads:
        print(f"  Lead {lead.name}: {lead.lead_name} ({lead.status})")


def _ensure_automation():
    """Create the demo Automation if it doesn't exist."""
    name = "Lead Qualified Demo"
    if frappe.db.exists("Automation", {"automation_name": name}):
        auto = frappe.get_doc("Automation", {"automation_name": name})
        if not auto.enabled:
            auto.enabled = 1
            auto.save()
            frappe.db.commit()
        return auto

    workflow_json = {
        "nodes": [
            {"id": "trigger", "type": "trigger", "position": {"x": 250, "y": 50},
             "data": {"trigger_doctype": "Lead", "trigger_event": "On Update"}},
            {"id": "condition", "type": "condition", "position": {"x": 250, "y": 220},
             "data": {"condition_field": "status", "condition_operator": "=", "condition_value": "Qualified"}},
            {"id": "action-1", "type": "action", "position": {"x": 250, "y": 390},
             "data": {"action_type": "create_document", "target_doctype": "Automation Task",
                      "field_mapping": [
                          {"target_field": "subject", "source_value": "Follow up: {{trigger.lead_name}}"},
                          {"target_field": "status", "source_value": "Open"},
                          {"target_field": "priority", "source_value": "Medium"},
                          {"target_field": "linked_doctype", "source_value": "Lead"},
                          {"target_field": "linked_document", "source_value": "{{trigger.name}}"},
                      ]}},
            {"id": "action-2", "type": "action", "position": {"x": 250, "y": 530},
             "data": {"action_type": "send_email", "recipient": "{{trigger.email}}",
                      "subject": "Lead {{trigger.lead_name}} is now Qualified",
                      "body": "Lead {{trigger.lead_name}} has been qualified and requires follow-up."}},
        ],
        "edges": [
            {"id": "e-t-c", "source": "trigger", "target": "condition", "type": "smoothstep"},
            {"id": "e-c-a1", "source": "condition", "target": "action-1", "type": "smoothstep"},
            {"id": "e-a1-a2", "source": "action-1", "target": "action-2", "type": "smoothstep"},
        ],
        "actions": [
            {
                "type": "create_document",
                "config": {
                    "target_doctype": "Automation Task",
                    "field_mapping": [
                        {"target_field": "subject", "source_value": "Follow up: {{trigger.lead_name}}"},
                        {"target_field": "status", "source_value": "Open"},
                        {"target_field": "priority", "source_value": "Medium"},
                        {"target_field": "linked_doctype", "source_value": "Lead"},
                        {"target_field": "linked_document", "source_value": "{{trigger.name}}"},
                    ],
                },
            },
            {
                "type": "send_email",
                "config": {
                    "recipient": "{{trigger.email}}",
                    "subject": "Lead {{trigger.lead_name}} is now Qualified",
                    "body": "Lead {{trigger.lead_name}} has been qualified and requires follow-up.",
                },
            },
        ],
    }

    import json
    auto = frappe.new_doc("Automation")
    auto.automation_name = name
    auto.trigger_doctype = "Lead"
    auto.trigger_event = "On Update"
    auto.condition_field = "status"
    auto.condition_operator = "="
    auto.condition_value = "Qualified"
    auto.enabled = 1
    auto.workflow_json = json.dumps(workflow_json)
    auto.description = "Demo: When a Lead becomes Qualified, create a follow-up Task and send an email."
    auto.insert(ignore_permissions=True)
    frappe.db.commit()
    return auto


def _create_leads():
    """Create 3 sample Leads with varied statuses."""
    leads = []

    # Lead 1: Already Qualified (shows the 'before' state)
    # Must create as Contacted first, then update to Qualified
    lead1 = _get_or_create_lead(
        name_hint="Demo Qualified Lead",
        defaults={
            "lead_name": "Demo Qualified Lead",
            "email": "qualified@example.com",
            "status": "Contacted",
            "organization": "Acme Corp",
            "assigned_to": "Administrator",
            "follow_up_date": "2026-09-15",
        },
    )
    if lead1.status != "Qualified":
        lead1.status = "Qualified"
        lead1.requirement = "Interested in enterprise plan"
        lead1.save(ignore_permissions=True)
        frappe.db.commit()
    leads.append(lead1)

    # Lead 2: Open/New (for live demo trigger)
    lead2 = _get_or_create_lead(
        name_hint="Demo Open Lead",
        defaults={
            "lead_name": "Demo Open Lead",
            "email": "open@example.com",
            "status": "New",
            "organization": "Startup Inc",
            "assigned_to": "Administrator",
            "follow_up_date": "2026-09-12",
        },
    )
    leads.append(lead2)

    # Lead 3: Contacted (can be moved to Qualified during demo)
    lead3 = _get_or_create_lead(
        name_hint="Demo Contacted Lead",
        defaults={
            "lead_name": "Demo Contacted Lead",
            "email": "contacted@example.com",
            "status": "Contacted",
            "organization": "Global Ltd",
            "assigned_to": "Administrator",
            "follow_up_date": "2026-09-14",
        },
    )
    leads.append(lead3)

    return leads


def _get_or_create_lead(name_hint, defaults):
    """Create a Lead if it doesn't already exist (by lead_name)."""
    existing = frappe.db.get_value("Lead", {"lead_name": defaults["lead_name"]}, "name")
    if existing:
        return frappe.get_doc("Lead", existing)

    lead = frappe.new_doc("Lead")
    for k, v in defaults.items():
        lead.set(k, v)
    lead.insert(ignore_permissions=True)
    frappe.db.commit()
    return lead
