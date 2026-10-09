// Copyright (c) 2026, Peter Karanja and contributors
// For license information, please see license.txt

frappe.provide("site_ops");

frappe.pages["procurement-dashboard"].on_page_load = function (wrapper) {
	wrapper.dashboard = new site_ops.ProcurementDashboard(wrapper);
};

frappe.pages["procurement-dashboard"].on_page_show = function (wrapper) {
	if (wrapper.dashboard) wrapper.dashboard.load();
};

site_ops.ProcurementDashboard = class ProcurementDashboard {
	constructor(wrapper) {
		this.load = frappe.utils.debounce(() => this.fetch(), 250);
		this.currency = frappe.defaults.get_default("currency");

		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Procurement Dashboard"),
			single_column: true,
		});

		this.make_filters();
		this.make_layout();

		if (frappe.model.can_create("Purchase Requisition")) {
			this.page.set_primary_action(
				__("New Requisition"),
				() => frappe.new_doc("Purchase Requisition"),
				"add"
			);
		}
	}

	make_filters() {
		const field = (df) => this.page.add_field({ ...df, change: () => this.load() });

		this.filters = {
			company: field({
				fieldname: "company",
				label: __("Company"),
				fieldtype: "Link",
				options: "Company",
				default: frappe.defaults.get_user_default("Company"),
			}),
			from_date: field({
				fieldname: "from_date",
				label: __("From"),
				fieldtype: "Date",
				default: frappe.datetime.add_months(frappe.datetime.get_today(), -3),
			}),
			to_date: field({
				fieldname: "to_date",
				label: __("To"),
				fieldtype: "Date",
				default: frappe.datetime.get_today(),
			}),
		};
	}

	make_layout() {
		frappe.dom.set_style(this.get_style(), "site-ops-dashboard");

		this.$body = $(`
			<div class="so-dashboard">
				<div class="so-cards"></div>
				<div class="so-grid">
					<div class="so-panel">
						<div class="so-panel-title">${__("Spend by Supplier")}</div>
						<div class="so-chart"></div>
					</div>
					<div class="so-panel">
						<div class="so-panel-title">${__("Awaiting My Action")}</div>
						<div class="so-queue"></div>
					</div>
				</div>
			</div>
		`).appendTo(this.page.main);
	}

	fetch() {
		frappe.call({
			method: "site_ops.api.get_dashboard_data",
			args: {
				company: this.filters.company.get_value(),
				from_date: this.filters.from_date.get_value(),
				to_date: this.filters.to_date.get_value(),
			},
			callback: ({ message }) => message && this.render(message),
		});
	}

	render(data) {
		this.currency = data.currency || this.currency;
		this.render_cards(data.cards);
		this.render_chart(data.suppliers);
		this.render_queue(data.queue);
	}

	render_cards(cards) {
		const money = (value) => format_currency(value, this.currency);
		const defs = [
			{ label: __("Awaiting My Action"), value: cards.awaiting_my_action, tone: cards.awaiting_my_action ? "orange" : "" },
			{ label: __("Open Requisitions"), value: cards.open_requisitions },
			{ label: __("Approved in Period"), value: cards.approved_in_period },
			{ label: __("PO Spend in Period"), value: cards.po_spend, format: money },
			{ label: __("Items at Reorder Level"), value: cards.low_stock_items, tone: cards.low_stock_items ? "red" : "" },
		];

		const html = defs
			.map(({ label, value, tone, format }) => {
				const shown = value === null || value === undefined ? "&ndash;" : format ? format(value) : value;
				return `
					<div class="so-card ${tone || ""}">
						<div class="so-card-label">${label}</div>
						<div class="so-card-value">${shown}</div>
					</div>`;
			})
			.join("");

		this.$body.find(".so-cards").html(html);
	}

	render_chart(suppliers) {
		const $chart = this.$body.find(".so-chart").empty();

		if (!suppliers.labels.length) {
			$chart.html(`<div class="so-empty">${__("No submitted Purchase Orders in this period.")}</div>`);
			return;
		}

		new frappe.Chart($chart[0], {
			type: "bar",
			height: 280,
			colors: ["#4f7cff"],
			data: { labels: suppliers.labels, datasets: [{ name: __("Spend"), values: suppliers.values }] },
			axisOptions: { xIsSeries: 1 },
			barOptions: { spaceRatio: 0.4 },
			tooltipOptions: { formatTooltipY: (value) => format_currency(value, this.currency) },
		});
	}

	render_queue(queue) {
		const $queue = this.$body.find(".so-queue").empty();

		if (!queue.length) {
			$queue.html(`<div class="so-empty">${__("Nothing is waiting for you.")}</div>`);
			return;
		}

		const esc = frappe.utils.escape_html;
		const rows = queue
			.map(
				(d) => `
				<tr>
					<td><a href="/app/purchase-requisition/${encodeURIComponent(d.name)}">${esc(d.name)}</a>
						<div class="text-muted small">${esc(d.requested_by || "")}${d.project ? " &middot; " + esc(d.project) : ""}</div></td>
					<td class="text-right">${format_currency(d.total_estimated_amount, this.currency)}</td>
					<td><span class="indicator-pill orange">${esc(__(d.workflow_state))}</span></td>
					<td>${frappe.datetime.str_to_user(d.required_by)}</td>
				</tr>`
			)
			.join("");

		$queue.html(`
			<table class="table table-sm so-table">
				<thead><tr>
					<th>${__("Requisition")}</th>
					<th class="text-right">${__("Amount")}</th>
					<th>${__("Stage")}</th>
					<th>${__("Required By")}</th>
				</tr></thead>
				<tbody>${rows}</tbody>
			</table>`);
	}

	get_style() {
		return `
			.so-dashboard { padding: var(--padding-md, 12px) 0; }
			.so-cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 12px; margin-bottom: 16px; }
			.so-card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: var(--border-radius-md); padding: 14px 16px; }
			.so-card-label { color: var(--text-muted); font-size: var(--text-sm); }
			.so-card-value { color: var(--heading-color); font-size: 24px; font-weight: 600; margin-top: 4px; }
			.so-card.orange .so-card-value { color: var(--orange-600, #c2410c); }
			.so-card.red .so-card-value { color: var(--red-600, #b91c1c); }
			.so-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 12px; }
			.so-panel { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: var(--border-radius-md); padding: 14px 16px; min-height: 320px; }
			.so-panel-title { color: var(--heading-color); font-weight: 600; margin-bottom: 10px; }
			.so-empty { color: var(--text-muted); padding: 40px 0; text-align: center; }
			.so-table td, .so-table th { vertical-align: middle; }
			@media (max-width: 991px) { .so-grid { grid-template-columns: minmax(0, 1fr); } }
		`;
	}
};
