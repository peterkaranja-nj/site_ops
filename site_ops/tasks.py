import frappe
from frappe import _
from frappe.utils import get_url, getdate, today
from frappe.utils.user import get_users_with_role

from site_ops import utils


def send_low_stock_alert():
	"""Daily digest of stock items at or below reorder level. Sends at most once per calendar day."""
	settings = utils.get_settings()
	if not settings.stock_alert_enabled or not settings.stock_alert_role:
		return
	if settings.last_stock_alert_on and getdate(settings.last_stock_alert_on) == getdate(today()):
		return

	try:
		items = utils.get_low_stock_items()
		if not items:
			return

		recipients = [u for u in get_users_with_role(settings.stock_alert_role) if u != "Administrator"]
		if not recipients:
			return

		frappe.sendmail(
			recipients=recipients,
			subject=_("Low stock: {0} item(s) at or below reorder level").format(len(items)),
			message=frappe.render_template(
				"site_ops/templates/emails/low_stock.html",
				{"items": items, "dashboard_url": get_url("/app/procurement-dashboard")},
			),
		)
		frappe.db.set_single_value("Site Ops Settings", "last_stock_alert_on", today())
	except Exception:
		frappe.log_error(title="Site Ops: low stock alert failed")
