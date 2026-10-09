import json

import frappe
from frappe.utils import add_days, today

COMPANY = "_Test Company"
COST_CENTER = "_Test Cost Center - _TC"
WAREHOUSE = "_Test Warehouse - _TC"


def make_item(item_code):
	from erpnext.stock.doctype.item.test_item import make_item as _make_item

	return _make_item(item_code, {"is_stock_item": 1, "is_purchase_item": 1}).name


def requisition_payload(**overrides):
	items = overrides.pop(
		"items",
		[
			{"item_code": make_item("SO-TEST-CEMENT"), "qty": 10, "rate": 800},
			{"item_code": make_item("SO-TEST-STEEL"), "qty": 4, "rate": 2500},
		],
	)
	payload = {
		"company": COMPANY,
		"required_by": add_days(today(), 7),
		"cost_center": COST_CENTER,
		"warehouse": WAREHOUSE,
		"purpose": "Slab pour, block B",
		"items": items,
	}
	payload.update(overrides)
	return payload


def make_requisition(**overrides):
	payload = requisition_payload(**overrides)
	doc = frappe.new_doc("Purchase Requisition")
	doc.update({k: v for k, v in payload.items() if k != "items"})
	for row in payload["items"]:
		doc.append("items", row)
	return doc.insert()


def make_project(estimated_costing, name="SO Test Project"):
	return frappe.get_doc(
		{
			"doctype": "Project",
			"project_name": name,
			"company": COMPANY,
			"estimated_costing": estimated_costing,
		}
	).insert()


def as_json(payload):
	return json.dumps(payload, default=str)
