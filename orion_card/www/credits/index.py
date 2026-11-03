import frappe

no_cache = 1


def get_context(context):
	frappe.local.flags.redirect_location = "/dashboard"
	raise frappe.Redirect
