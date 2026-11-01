import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/new-occasion"
		raise frappe.Redirect

	user_doc = frappe.get_cached_doc("User", frappe.session.user)
	context.title = "Tukio Jipya — OrionCard"
	context.no_breadcrumbs = 1
	context.user_full_name = user_doc.full_name or user_doc.first_name or frappe.session.user
	context.user_email = frappe.session.user
	context.csrf_token = frappe.sessions.get_csrf_token()
