# Copyright (c) 2026, Peter Karanja and contributors
# For license information, please see license.txt

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from site_ops import constants as c
from site_ops.tests.utils import COMPANY, make_item, make_requisition

APPROVE_THROUGH_DIRECTOR = (c.ACTION_SUBMIT, c.ACTION_APPROVE, c.ACTION_APPROVE, c.ACTION_APPROVE)
APPROVE_WITHOUT_DIRECTOR = (c.ACTION_SUBMIT, c.ACTION_APPROVE, c.ACTION_APPROVE)


def run_workflow(doc, actions):
	for action in actions:
		doc = apply_workflow(doc, action)
	return doc


class TestPurchaseRequisition(FrappeTestCase):
	def test_row_amounts_and_total(self):
		doc = make_requisition()
		self.assertEqual([row.amount for row in doc.items], [8000, 10000])
		self.assertEqual(doc.total_estimated_amount, 18000)

	def test_duplicate_item_is_rejected(self):
		item = make_item("SO-TEST-CEMENT")
		with self.assertRaises(frappe.ValidationError):
			make_requisition(
				items=[
					{"item_code": item, "qty": 1, "rate": 10},
					{"item_code": item, "qty": 2, "rate": 10},
				]
			)

	def test_non_positive_quantity_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			make_requisition(items=[{"item_code": make_item("SO-TEST-CEMENT"), "qty": 0, "rate": 10}])

	def test_required_by_before_requisition_date_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			make_requisition(required_by=add_days(today(), -1))

	def test_cost_center_must_belong_to_company(self):
		foreign = frappe.db.get_value("Cost Center", {"company": ["!=", COMPANY], "is_group": 0})
		if not foreign:
			self.skipTest("No cost center from another company available")
		with self.assertRaises(frappe.ValidationError):
			make_requisition(cost_center=foreign)

	def test_director_required_by_default(self):
		self.assertEqual(make_requisition().requires_director, 1)

	def test_director_skipped_below_threshold(self):
		frappe.db.set_single_value("Site Ops Settings", "director_approval_threshold", 10**9)
		doc = make_requisition()
		self.assertEqual(doc.requires_director, 0)

		doc = run_workflow(doc, APPROVE_WITHOUT_DIRECTOR)
		self.assertEqual((doc.docstatus, doc.workflow_state), (1, c.STATE_APPROVED))

	def test_final_approval_raises_material_request(self):
		doc = run_workflow(make_requisition(), APPROVE_THROUGH_DIRECTOR)
		self.assertEqual((doc.docstatus, doc.workflow_state), (1, c.STATE_APPROVED))
		self.assertTrue(doc.material_request)

		mr = frappe.get_doc("Material Request", doc.material_request)
		self.assertEqual(mr.docstatus, 1)
		self.assertEqual(mr.material_request_type, "Purchase")
		self.assertEqual(mr.custom_purchase_requisition, doc.name)
		self.assertEqual(
			[(row.item_code, row.qty) for row in mr.items],
			[(row.item_code, row.qty) for row in doc.items],
		)

	def test_rejection_returns_to_requester(self):
		doc = run_workflow(make_requisition(), (c.ACTION_SUBMIT, c.ACTION_REJECT, c.ACTION_REOPEN))
		self.assertEqual((doc.docstatus, doc.workflow_state), (0, c.STATE_DRAFT))

	def test_cancelling_requisition_cancels_material_request(self):
		doc = run_workflow(make_requisition(), APPROVE_THROUGH_DIRECTOR)
		material_request = doc.material_request

		doc = apply_workflow(doc, c.ACTION_CANCEL)
		self.assertEqual(doc.docstatus, 2)
		self.assertEqual(frappe.db.get_value("Material Request", material_request, "docstatus"), 2)
