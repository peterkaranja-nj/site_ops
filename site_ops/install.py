import frappe

from site_ops import constants as c

WORKFLOW_STATE_STYLES = {
	c.STATE_DRAFT: "Inverse",
	c.STATE_PENDING_SITE_MANAGER: "Warning",
	c.STATE_PENDING_PROCUREMENT: "Warning",
	c.STATE_PENDING_DIRECTOR: "Warning",
	c.STATE_APPROVED: "Success",
	c.STATE_REJECTED: "Danger",
	c.STATE_CANCELLED: "Danger",
}

WORKFLOW_ACTIONS = (
	c.ACTION_SUBMIT,
	c.ACTION_APPROVE,
	c.ACTION_REJECT,
	c.ACTION_REOPEN,
	c.ACTION_CANCEL,
)


def after_install():
	create_roles()
	create_workflow_masters()
	initialise_settings()


def create_roles():
	for role in c.ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)


def create_workflow_masters():
	for state, style in WORKFLOW_STATE_STYLES.items():
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc(
				{"doctype": "Workflow State", "workflow_state_name": state, "style": style}
			).insert(ignore_permissions=True)

	for action in WORKFLOW_ACTIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)


def initialise_settings():
	# Persist field defaults so the Single reads back identically everywhere.
	frappe.get_single("Site Ops Settings").save(ignore_permissions=True)
