import frappe
from frappe import _
from frappe.utils import flt, fmt_money

from site_ops import utils


def validate_project_budget(doc, method=None):
	"""Block a Purchase Order that would take its Project past the Estimated Cost."""
	if not doc.get("project") or doc.docstatus == 2:
		return
	if not utils.get_settings().enforce_project_budget:
		return

	position = utils.get_project_budget_position(doc.project, exclude_po=doc.name)
	if not position.budget:
		return

	projected = position.spent + flt(doc.base_grand_total)
	if projected <= position.budget:
		return

	currency = utils.company_currency(doc.company)
	frappe.throw(
		_(
			"Purchase Order total {0} exceeds the remaining budget of Project {1} ({2} of {3} already committed)."
		).format(
			fmt_money(flt(doc.base_grand_total), currency=currency),
			frappe.bold(doc.project),
			fmt_money(position.spent, currency=currency),
			fmt_money(position.budget, currency=currency),
		),
		title=_("Project Budget Exceeded"),
	)
