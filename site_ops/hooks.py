app_name = "site_ops"
app_title = "Site Ops"
app_publisher = "Peter Karanja"
app_description = "Purchase requisition, approval and procurement control for ERPNext"
app_license = "MIT"

required_apps = ["erpnext"]

after_install = "site_ops.install.after_install"

doctype_js = {
	"Material Request": "public/js/material_request.js",
}

doc_events = {
	"Purchase Order": {
		"validate": "site_ops.events.purchase_order.validate_project_budget",
	},
}

scheduler_events = {
	"daily": [
		"site_ops.tasks.send_low_stock_alert",
	],
}

# Order matters: Custom Fields must exist before the Workflow is imported.
fixtures = [
	{"dt": "Custom Field", "filters": [["module", "=", "Site Ops"]]},
	{"dt": "Workflow", "filters": [["name", "=", "Purchase Requisition Approval"]]},
]
