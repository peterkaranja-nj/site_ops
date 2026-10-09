// Copyright (c) 2026, Peter Karanja and contributors
// For license information, please see license.txt

frappe.ui.form.on("Purchase Requisition", {
	setup(frm) {
		const company_filter = () => ({ filters: { company: frm.doc.company, is_group: 0 } });

		frm.set_query("cost_center", company_filter);
		frm.set_query("warehouse", company_filter);
		frm.set_query("project", () => ({
			filters: {
				company: frm.doc.company,
				status: ["not in", ["Completed", "Cancelled"]],
			},
		}));
		frm.set_query("item_code", "items", () => ({
			filters: { disabled: 0, is_purchase_item: 1 },
		}));
	},

	onload(frm) {
		if (frm.is_new() && !frm.doc.company) {
			frm.set_value("company", frappe.defaults.get_user_default("Company"));
		}
	},

	refresh(frm) {
		if (frm.doc.material_request) {
			frm.add_custom_button(
				__("Material Request"),
				() => frappe.set_route("Form", "Material Request", frm.doc.material_request),
				__("View")
			);
		}

		if (frm.doc.project && frm.doc.docstatus < 2) {
			frm.add_custom_button(__("Project Budget"), () => frm.trigger("show_budget"), __("View"));
		}

		if (!frm.is_new() && frm.doc.docstatus === 0) {
			frm.set_intro(
				frm.doc.requires_director
					? __("This requisition requires Director approval.")
					: __("Director approval is not required for this amount."),
				"blue"
			);
		}
	},

	company(frm) {
		["cost_center", "warehouse", "project"].forEach((field) => frm.set_value(field, null));
	},

	show_budget(frm) {
		frappe.call({
			method: "site_ops.api.get_project_budget",
			args: { project: frm.doc.project },
			callback: ({ message: budget }) => {
				if (!budget) return;

				const currency = frappe.defaults.get_default("currency");
				const row = (label, value) =>
					`<tr><td>${label}</td><td class="text-right">${format_currency(value, currency)}</td></tr>`;

				frappe.msgprint({
					title: __("Project Budget"),
					indicator: budget.remaining < 0 ? "red" : "green",
					message: `<table class="table table-bordered"><tbody>
						${row(__("Estimated Cost"), budget.budget)}
						${row(__("Committed (Purchase Orders)"), budget.spent)}
						${row(__("Remaining"), budget.remaining)}
					</tbody></table>`,
				});
			},
		});
	},
});

frappe.ui.form.on("Requisition Item", {
	qty: set_row_amount,
	rate: set_row_amount,
	items_remove(frm) {
		set_total(frm);
	},
});

function set_row_amount(frm, cdt, cdn) {
	const row = locals[cdt][cdn];
	frappe.model.set_value(cdt, cdn, "amount", flt(row.qty) * flt(row.rate));
	set_total(frm);
}

function set_total(frm) {
	const total = (frm.doc.items || []).reduce((sum, row) => sum + flt(row.qty) * flt(row.rate), 0);
	frm.set_value("total_estimated_amount", total);
}
