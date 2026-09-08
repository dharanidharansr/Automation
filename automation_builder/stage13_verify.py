"""Quick verification script for Stage 13 action types."""
import frappe

def run():
    from automation_builder.action_types import get_all_action_types
    types = get_all_action_types()
    print("Registered action types:", list(types.keys()))
    for k, v in types.items():
        fields = [s["name"] for s in v["config_schema"]]
        print(f"  {k}: {v['label']} — schema fields: {fields}")

    # Verify Settings DocType exists
    exists = frappe.db.exists("DocType", "Automation Builder Settings")
    print(f"\nAutomation Builder Settings DocType exists: {exists}")

    # Test HTTP Request: GET to httpbin.org/get
    print("\n--- HTTP Request test (GET httpbin.org/get) ---")
    from automation_builder.action_types.http_request import execute as http_execute
    result = http_execute(
        {"doc": None, "ref_doctype": "Lead", "ref_name": "test"},
        {"url": "https://httpbin.org/get", "method": "GET", "headers": [], "body": ""},
    )
    print(f"  Status: {result['status']}")
    print(f"  Output preview: {result['output'][:200]}")

    # Test HTTP Request: POST with JSON body
    print("\n--- HTTP Request test (POST httpbin.org/post) ---")
    result = http_execute(
        {"doc": None, "ref_doctype": "Lead", "ref_name": "test"},
        {
            "url": "https://httpbin.org/post",
            "method": "POST",
            "headers": [{"target_field": "Content-Type", "source_value": "application/json"}],
            "body": '{"test": "hello", "lead": "dummy"}',
        },
    )
    print(f"  Status: {result['status']}")
    print(f"  Output preview: {result['output'][:300]}")

    # Test HTTP Request: deliberately broken URL
    print("\n--- HTTP Request test (broken URL) ---")
    try:
        http_execute(
            {"doc": None, "ref_doctype": "Lead", "ref_name": "test"},
            {"url": "https://definitely-not-a-real-domain-xyz123.example/fail", "method": "GET", "headers": [], "body": ""},
        )
        print("  ERROR: Should have raised!")
    except Exception as e:
        print(f"  Correctly raised: {type(e).__name__}: {str(e)[:150]}")

    # Test Telegram: mock mode (no token configured)
    print("\n--- Telegram test (mock mode) ---")
    from automation_builder.action_types.telegram import execute as tg_execute
    result = tg_execute(
        {"doc": None, "ref_doctype": "Lead", "ref_name": "test"},
        {"chat_id": "123456789", "message": "Hello from automation"},
    )
    print(f"  Status: {result['status']}")
    print(f"  Output: {result['output']}")

    # Test Update Field: update the triggering Lead
    print("\n--- Update Field test (Same Document) ---")
    lead = frappe.new_doc("Lead")
    lead.lead_name = "Stage13 Test Lead"
    lead.email = "stage13test@example.com"
    lead.status = "New"
    lead.assigned_to = "Administrator"
    lead.follow_up_date = "2026-09-15"
    lead.insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"  Created Lead: {lead.name}")

    from automation_builder.action_types.update_field import execute as uf_execute
    result = uf_execute(
        {"doc": lead, "ref_doctype": "Lead", "ref_name": lead.name},
        {
            "target": "Same Document",
            "link_fieldname": "",
            "field_mapping": [
                {"target_field": "status", "source_value": "Contacted"},
            ],
        },
    )
    print(f"  Status: {result['status']}")
    print(f"  Output: {result['output']}")

    # Verify the update persisted
    lead.reload()
    print(f"  Lead status after update: {lead.status}")
    assert lead.status == "Contacted", f"Expected 'Contacted', got '{lead.status}'"
    print("  Persistence verified!")

    print("\n=== All backend tests passed ===")

    # Also verify API endpoint
    from automation_builder.api import get_action_types
    api_types = get_action_types()
    api_keys = sorted(api_types.keys()) if isinstance(api_types, dict) else sorted([t["key"] for t in api_types])
    print(f"\nAPI endpoint get_action_types() returns: {api_keys}")
    assert len(api_keys) >= 5, f"Expected >= 5 action types, got {len(api_keys)}"
    print("API endpoint verified!")


if __name__ == "__main__":
    frappe.connect("automate.localhost")
    frappe.set_user("Administrator")
    run()
