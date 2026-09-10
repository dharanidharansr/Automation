"""Patch: Stage 19 security hardening — encrypt telegram_bot_token + add index.

1. Migrates any existing plaintext telegram_bot_token to the Password
   encrypted store.
2. Adds composite index on (trigger_doctype, trigger_event) for the
   dispatcher's query performance.
"""

import frappe


def execute():
    """Run the Stage 19 migration patch."""
    frappe.reload_doc("automation_builder", "doctype", "automation_builder_settings")
    frappe.reload_doc("automation_builder", "doctype", "automation_trigger")

    # 1. Migrate plaintext telegram_bot_token to encrypted store
    _migrate_bot_token_to_password()

    # 2. Add composite index on Automation Trigger
    _add_trigger_composite_index()


def _migrate_bot_token_to_password():
    """Move any existing plaintext bot token into the Password encrypted store."""
    try:
        settings = frappe.get_single_doc("Automation Builder Settings")
    except Exception:
        return

    # Check if there's a plaintext value in the old Data field
    # After fieldtype change to Password, get_password() will return the
    # encrypted value. But if there was a plaintext value before the change,
    # we need to ensure it's properly stored.
    # The Password fieldtype in Frappe handles this automatically on save,
    # so we just need to save the doc to trigger re-encryption.
    try:
        token = settings.get_password("telegram_bot_token")
        if token:
            # Re-save to ensure encryption
            settings.save(ignore_permissions=True)
            frappe.db.commit()
    except Exception:
        pass


def _add_trigger_composite_index():
    """Add composite index on (trigger_doctype, trigger_event) for query performance."""
    index_name = "idx_trigger_doctype_event"
    table_name = "tabAutomation Trigger"

    # Check if index already exists
    existing = frappe.db.sql(
        "SHOW INDEX FROM `{table}` WHERE Key_name = %s".format(table=table_name),
        index_name,
    )

    if not existing:
        frappe.db.sql(
            "CREATE INDEX `{idx}` ON `{table}` (`trigger_doctype`, `trigger_event`)".format(
                idx=index_name, table=table_name
            )
        )
        frappe.db.commit()
