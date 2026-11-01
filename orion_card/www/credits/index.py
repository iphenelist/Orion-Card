import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/credits"
		raise frappe.Redirect

	from orion_card.api.payments import get_credit_page_data

	user_doc = frappe.get_cached_doc("User", frappe.session.user)
	context.title = "Credits — OrionCard"
	context.no_breadcrumbs = 1
	context.user_full_name = user_doc.full_name or user_doc.first_name or frappe.session.user
	context.user_email = frappe.session.user
	context.page_data = get_credit_page_data()
	context.user_phone = user_doc.mobile_no or ""
