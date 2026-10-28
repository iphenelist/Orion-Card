import frappe


def landing_page_at_root():
	"""before_request hook: "/" always shows the OrionCard landing page.

	Logged-in users otherwise get their Role's home page at "/" (Occasion
	Managers: /app/occasion). The flag only applies to this request, so the
	redirect after login still uses the Role's home page.
	"""
	request = getattr(frappe.local, "request", None)
	if request and request.path in ("/", "/index"):
		frappe.local.flags.home_page = "orioncard"
