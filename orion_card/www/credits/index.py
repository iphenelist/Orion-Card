import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/credits"
		raise frappe.Redirect

	from orion_card.api.payments import get_credit_page_data

	context.title = "Credits — OrionCard"
	context.body_class = "ec-body"
	context.no_breadcrumbs = 1
	context.ec_business_name = frappe.db.get_single_value("OrionCard Settings", "business_legal_name")
	context.page_data = get_credit_page_data()
	context.user_phone = frappe.db.get_value("User", frappe.session.user, "mobile_no") or ""
