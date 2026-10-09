import frappe
from frappe.tests.utils import FrappeTestCase

from site_ops.events.purchase_order import validate_project_budget
from site_ops.tests.utils import COMPANY, make_project
from site_ops.utils import get_project_budget_position


def purchase_order_stub(project, total):
	return frappe._dict(name="PO-STUB", project=project, docstatus=0, company=COMPANY, base_grand_total=total)


class TestProjectBudget(FrappeTestCase):
	def test_position_with_no_committed_spend(self):
		project = make_project(1000)
		position = get_project_budget_position(project.name)
		self.assertEqual((position.budget, position.spent, position.remaining), (1000, 0, 1000))

	def test_order_within_budget_passes(self):
		project = make_project(1000)
		validate_project_budget(purchase_order_stub(project.name, 1000))

	def test_order_over_budget_is_blocked(self):
		project = make_project(1000)
		with self.assertRaises(frappe.ValidationError):
			validate_project_budget(purchase_order_stub(project.name, 1000.01))

	def test_project_without_budget_is_not_checked(self):
		project = make_project(0)
		validate_project_budget(purchase_order_stub(project.name, 5_000_000))

	def test_enforcement_can_be_disabled(self):
		project = make_project(1000)
		frappe.db.set_single_value("Site Ops Settings", "enforce_project_budget", 0)
		validate_project_budget(purchase_order_stub(project.name, 5000))
