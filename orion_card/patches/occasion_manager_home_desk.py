import frappe


def execute():
	"""Occasion Managers manage their Occasions in the Desk again (/app/occasion)."""
	if frappe.db.exists("Role", "Occasion Manager"):
		frappe.db.set_value("Role", "Occasion Manager", "home_page", "/app/occasion")
		frappe.cache.delete_value("home_page")
