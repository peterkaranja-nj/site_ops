// Copyright (c) 2026, Peter Karanja and contributors
// For license information, please see license.txt

frappe.ui.form.on("Material Request", {
	refresh(frm) {
		if (!frm.doc.custom_purchase_requisition) return;

		frm.add_custom_button(
			__("Purchase Requisition"),
			() => frappe.set_route("Form", "Purchase Requisition", frm.doc.custom_purchase_requisition),
			__("View")
		);
	},
});
