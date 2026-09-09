"""Setup module for Automation Builder app."""

import frappe


def create_automation_roles():
    """Create custom roles for Automation Builder."""
    roles = [
        {
            "role_name": "Automation User",
            "desk_access": 1,
            "is_custom": 0,
        },
    ]
    
    for role_data in roles:
        if not frappe.db.exists("Role", role_data["role_name"]):
            frappe.get_doc({
                "doctype": "Role",
                "role_name": role_data["role_name"],
                "desk_access": role_data.get("desk_access", 1),
                "is_custom": role_data.get("is_custom", 0),
            }).insert(ignore_permissions=True)
            frappe.db.commit()
