import frappe
from frappe.tests.utils import FrappeTestCase

from site_ops import api
from site_ops import constants as c
from site_ops.tests.utils import as_json, requisition_payload


class TestRequisitionApi(FrappeTestCase):
	def test_creates_draft_requisition(self):
		result = api.create_requisition(as_json(requisition_payload()))
		doc = frappe.get_doc("Purchase Requisition", result["name"])

		self.assertEqual(doc.docstatus, 0)
		self.assertEqual(doc.workflow_state, c.STATE_DRAFT)
		self.assertEqual(result["total_estimated_amount"], 18000)

	def test_can_route_for_approval_in_one_call(self):
		result = api.create_requisition(as_json(requisition_payload()), submit_for_approval=1)
		self.assertEqual(result["workflow_state"], c.STATE_PENDING_SITE_MANAGER)

	def test_privileged_fields_in_payload_are_ignored(self):
		payload = requisition_payload(
			workflow_state=c.STATE_APPROVED, docstatus=1, owner="someone@example.com"
		)
		result = api.create_requisition(as_json(payload))
		doc = frappe.get_doc("Purchase Requisition", result["name"])

		self.assertEqual(doc.docstatus, 0)
		self.assertEqual(doc.workflow_state, c.STATE_DRAFT)
		self.assertNotEqual(doc.owner, "someone@example.com")

	def test_rejects_payload_without_items(self):
		with self.assertRaises(frappe.ValidationError):
			api.create_requisition(as_json(requisition_payload(items=[])))

	def test_status_reports_pending_roles(self):
		result = api.create_requisition(as_json(requisition_payload()), submit_for_approval=1)
		status = api.get_requisition_status(result["name"])
		self.assertEqual(status["pending_with"], [c.ROLE_SITE_MANAGER])
