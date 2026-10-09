import frappe
from frappe import _
from frappe.model.workflow import apply_workflow
from frappe.utils import add_months, cint, getdate, today

from site_ops import constants as c
from site_ops import utils

# Only these keys are read from client payloads; everything else (docstatus,
# workflow_state, owner, ...) is ignored so it cannot be set from outside.
HEADER_FIELDS = ("company", "required_by", "project", "cost_center", "warehouse", "priority", "purpose")
ITEM_FIELDS = ("item_code", "qty", "uom", "rate", "remarks")


@frappe.whitelist(methods=["POST"])
def create_requisition(requisition, submit_for_approval=0):
	"""Create a Purchase Requisition from a JSON payload, optionally routing it for approval."""
	data = frappe.parse_json(requisition)
	if not isinstance(data, dict):
		frappe.throw(_("Requisition must be a JSON object."))

	rows = data.get("items")
	if not isinstance(rows, list) or not rows:
		frappe.throw(_("At least one item is required."))

	doc = frappe.new_doc("Purchase Requisition")
	for field in HEADER_FIELDS:
		if data.get(field) not in (None, ""):
			doc.set(field, data[field])

	for row in rows:
		if not isinstance(row, dict):
			frappe.throw(_("Each item must be a JSON object."))
		doc.append("items", {f: row[f] for f in ITEM_FIELDS if row.get(f) not in (None, "")})

	doc.insert()
	if cint(submit_for_approval):
		doc = apply_workflow(doc, c.ACTION_SUBMIT)

	return {
		"name": doc.name,
		"workflow_state": doc.workflow_state,
		"total_estimated_amount": doc.total_estimated_amount,
	}


@frappe.whitelist()
def get_requisition_status(name):
	doc = frappe.get_doc("Purchase Requisition", name)
	doc.check_permission("read")

	pending_with = []
	if doc.docstatus == 0:
		pending_with = frappe.get_all(
			"Workflow Transition",
			filters={"parent": c.WORKFLOW_NAME, "state": doc.workflow_state},
			pluck="allowed",
			distinct=True,
		)

	return {
		"name": doc.name,
		"docstatus": doc.docstatus,
		"workflow_state": doc.workflow_state,
		"requires_director": doc.requires_director,
		"total_estimated_amount": doc.total_estimated_amount,
		"material_request": doc.material_request,
		"pending_with": pending_with,
	}


@frappe.whitelist()
def get_project_budget(project):
	frappe.has_permission("Project", "read", project, throw=True)
	return utils.get_project_budget_position(project)


@frappe.whitelist()
def get_dashboard_data(company=None, from_date=None, to_date=None):
	frappe.has_permission("Purchase Requisition", "read", throw=True)

	from_date = getdate(from_date) if from_date else getdate(add_months(today(), -3))
	to_date = getdate(to_date) if to_date else getdate(today())
	period = ["between", [from_date, to_date]]

	base = {"company": company} if company else {}
	acting_states = _get_actionable_states()

	cards = {
		"awaiting_my_action": _count(
			"Purchase Requisition", {**base, "workflow_state": ["in", acting_states]}
		)
		if acting_states
		else 0,
		"open_requisitions": _count(
			"Purchase Requisition", {**base, "docstatus": 0, "workflow_state": ["in", c.PENDING_STATES]}
		),
		"approved_in_period": _count(
			"Purchase Requisition", {**base, "docstatus": 1, "transaction_date": period}
		),
		"po_spend": None,
		"low_stock_items": None,
	}

	suppliers = {"labels": [], "values": []}
	if frappe.has_permission("Purchase Order", "read"):
		po_filters = {**base, "docstatus": 1, "transaction_date": period}
		cards["po_spend"] = (
			frappe.get_list(
				"Purchase Order",
				filters=po_filters,
				fields=["sum(base_grand_total) as total"],
				limit_page_length=0,
			)[0].total
			or 0
		)
		by_supplier = frappe.get_list(
			"Purchase Order",
			filters=po_filters,
			fields=["supplier", "sum(base_grand_total) as total"],
			group_by="supplier",
			limit_page_length=0,
		)
		top = sorted(by_supplier, key=lambda d: d.total or 0, reverse=True)[:8]
		suppliers = {"labels": [d.supplier for d in top], "values": [d.total or 0 for d in top]}

	if frappe.has_permission("Bin", "read"):
		cards["low_stock_items"] = len(utils.get_low_stock_items())

	queue = []
	if acting_states:
		queue = frappe.get_list(
			"Purchase Requisition",
			filters={**base, "workflow_state": ["in", acting_states]},
			fields=[
				"name",
				"requested_by",
				"project",
				"total_estimated_amount",
				"workflow_state",
				"required_by",
			],
			order_by="required_by asc",
			limit_page_length=15,
		)

	currency = utils.company_currency(company) if company else frappe.db.get_default("currency")
	return {"cards": cards, "suppliers": suppliers, "queue": queue, "currency": currency}


def _count(doctype, filters):
	return frappe.get_list(doctype, filters=filters, fields=["count(name) as count"], limit_page_length=0)[
		0
	].count


def _get_actionable_states():
	"""Pending stages the current user holds a role for in the approval workflow."""
	states = frappe.get_all(
		"Workflow Transition",
		filters={"parent": c.WORKFLOW_NAME, "allowed": ["in", frappe.get_roles()]},
		pluck="state",
	)
	return sorted({state for state in states if state in c.PENDING_STATES})
