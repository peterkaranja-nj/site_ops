# Copyright (c) 2026, Peter Karanja and contributors
# For license information, please see license.txt

import frappe
from erpnext.stock.get_item_details import get_conversion_factor
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, fmt_money, getdate

from site_ops import utils


class PurchaseRequisition(Document):
	def validate(self):
		self.set_company()
		self.validate_dates()
		self.validate_allocation()
		self.validate_items()
		self.calculate_totals()
		self.set_approval_route()
		self.warn_if_over_budget()

	def on_submit(self):
		self.create_material_request()

	def on_cancel(self):
		self.ignore_linked_doctypes = ("Material Request",)
		self.cancel_material_request()

	def set_company(self):
		if not self.company:
			self.company = frappe.defaults.get_user_default("Company") or frappe.db.get_single_value(
				"Global Defaults", "default_company"
			)

	def validate_dates(self):
		if self.required_by and getdate(self.required_by) < getdate(self.transaction_date):
			frappe.throw(_("Required By date cannot be before the requisition date."))

	def validate_allocation(self):
		for fieldname, doctype in (("cost_center", "Cost Center"), ("warehouse", "Warehouse")):
			value = self.get(fieldname)
			if not value:
				continue
			company, is_group = frappe.db.get_value(doctype, value, ["company", "is_group"]) or (None, 0)
			if company and company != self.company:
				frappe.throw(
					_("{0} {1} belongs to company {2}, not {3}.").format(
						_(doctype), frappe.bold(value), frappe.bold(company), frappe.bold(self.company)
					)
				)
			if is_group:
				frappe.throw(
					_("{0} {1} is a group and cannot be used.").format(_(doctype), frappe.bold(value))
				)

		if self.project:
			project_company = frappe.db.get_value("Project", self.project, "company")
			if project_company and project_company != self.company:
				frappe.throw(
					_("Project {0} belongs to company {1}, not {2}.").format(
						frappe.bold(self.project), frappe.bold(project_company), frappe.bold(self.company)
					)
				)

	def validate_items(self):
		if not self.items:
			frappe.throw(_("At least one item is required."))

		item_codes = [row.item_code for row in self.items if row.item_code]
		master = {
			d.name: d
			for d in frappe.get_all(
				"Item",
				filters={"name": ["in", item_codes]},
				fields=["name", "disabled", "is_purchase_item"],
			)
		}

		seen = set()
		for row in self.items:
			if flt(row.qty) <= 0:
				frappe.throw(_("Row #{0}: Quantity must be greater than zero.").format(row.idx))
			if flt(row.rate) < 0:
				frappe.throw(_("Row #{0}: Estimated rate cannot be negative.").format(row.idx))

			item = master.get(row.item_code)
			if item and item.disabled:
				frappe.throw(_("Row #{0}: Item {1} is disabled.").format(row.idx, frappe.bold(row.item_code)))
			if item and not item.is_purchase_item:
				frappe.throw(
					_("Row #{0}: Item {1} is not marked as a purchase item.").format(
						row.idx, frappe.bold(row.item_code)
					)
				)

			key = (row.item_code, row.uom)
			if key in seen:
				frappe.throw(
					_("Row #{0}: Item {1} ({2}) is listed more than once.").format(
						row.idx, frappe.bold(row.item_code), row.uom
					)
				)
			seen.add(key)

	def calculate_totals(self):
		total = 0.0
		for row in self.items:
			row.amount = flt(flt(row.qty) * flt(row.rate), row.precision("amount"))
			total += row.amount
		self.total_estimated_amount = flt(total, self.precision("total_estimated_amount"))

	def set_approval_route(self):
		threshold = flt(utils.get_settings().director_approval_threshold)
		self.requires_director = int(threshold <= 0 or flt(self.total_estimated_amount) >= threshold)

	def warn_if_over_budget(self):
		if self.docstatus != 0 or not self.project:
			return

		position = utils.get_project_budget_position(self.project)
		if not position.budget or flt(self.total_estimated_amount) <= position.remaining:
			return

		currency = utils.company_currency(self.company)
		frappe.msgprint(
			_("Estimated total {0} exceeds the remaining budget of Project {1} ({2}).").format(
				fmt_money(self.total_estimated_amount, currency=currency),
				frappe.bold(self.project),
				fmt_money(position.remaining, currency=currency),
			),
			title=_("Budget Warning"),
			indicator="orange",
		)

	def create_material_request(self):
		mr = frappe.new_doc("Material Request")
		mr.update(
			{
				"material_request_type": "Purchase",
				"company": self.company,
				"transaction_date": self.transaction_date,
				"schedule_date": self.required_by,
				"set_warehouse": self.warehouse,
				"custom_purchase_requisition": self.name,
			}
		)

		for row in self.items:
			mr.append(
				"items",
				{
					"item_code": row.item_code,
					"item_name": row.item_name,
					"description": row.description or row.item_name,
					"qty": row.qty,
					"uom": row.uom,
					"conversion_factor": get_conversion_factor(row.item_code, row.uom).get(
						"conversion_factor"
					),
					"rate": row.rate,
					"warehouse": self.warehouse,
					"schedule_date": self.required_by,
					"cost_center": self.cost_center,
					"project": self.project,
				},
			)

		# The Director approving the requisition is not expected to hold Material Request permissions;
		# the document is derived from an already-approved requisition.
		mr.flags.ignore_permissions = True
		mr.insert()
		mr.submit()

		self.db_set("material_request", mr.name)

	def cancel_material_request(self):
		if not self.material_request:
			return

		mr = frappe.get_doc("Material Request", self.material_request)
		if mr.docstatus == 1:
			mr.flags.ignore_permissions = True
			mr.cancel()
