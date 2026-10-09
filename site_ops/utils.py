import frappe
from frappe.query_builder.functions import IfNull, Sum
from frappe.utils import flt


def get_settings():
	return frappe.get_single("Site Ops Settings")


def company_currency(company):
	return frappe.get_cached_value("Company", company, "default_currency")


def get_project_budget_position(project, exclude_po=None):
	"""Budget, committed spend (submitted Purchase Orders) and remainder for a Project."""
	budget = flt(frappe.db.get_value("Project", project, "estimated_costing"))

	po = frappe.qb.DocType("Purchase Order")
	query = (
		frappe.qb.from_(po)
		.select(IfNull(Sum(po.base_grand_total), 0))
		.where(po.project == project)
		.where(po.docstatus == 1)
	)
	if exclude_po:
		query = query.where(po.name != exclude_po)
	spent = flt(query.run()[0][0])

	return frappe._dict(budget=budget, spent=spent, remaining=budget - spent)


def get_low_stock_items():
	"""Stock items whose on-hand quantity is at or below the reorder level set on the Item."""
	bin_ = frappe.qb.DocType("Bin")
	reorder = frappe.qb.DocType("Item Reorder")
	item = frappe.qb.DocType("Item")

	return (
		frappe.qb.from_(bin_)
		.inner_join(reorder)
		.on((reorder.parent == bin_.item_code) & (reorder.warehouse == bin_.warehouse))
		.inner_join(item)
		.on(item.name == bin_.item_code)
		.select(
			bin_.item_code,
			item.item_name,
			bin_.warehouse,
			bin_.actual_qty,
			reorder.warehouse_reorder_level,
			reorder.warehouse_reorder_qty,
		)
		.where(reorder.parenttype == "Item")
		.where(item.disabled == 0)
		.where(item.is_stock_item == 1)
		.where(reorder.warehouse_reorder_level > 0)
		.where(bin_.actual_qty <= reorder.warehouse_reorder_level)
		.orderby(bin_.warehouse)
		.orderby(bin_.item_code)
	).run(as_dict=True)
