import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user != "Guest":
		frappe.local.flags.redirect_location = "/app/occasion"
		raise frappe.Redirect

	settings = frappe.get_cached_doc("OrionCard Settings")
	context.title = "Jisajili — OrionCard"
	context.body_class = "ec-body"
	context.no_breadcrumbs = 1
	context.ec_business_name = settings.business_legal_name
	context.terms_version = settings.terms_version or "1.0"
