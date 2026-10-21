import frappe


def execute():
	"""Orion Digital Tz as the business name (website copyright, Terms,
	receipts) and its WhatsApp, Instagram and TikTok in the website footer,
	only where nothing is set yet."""
	from orion_card.install import WEBSITE_CONTACT

	for field, value in WEBSITE_CONTACT.items():
		if not frappe.db.get_single_value("OrionCard Settings", field):
			frappe.db.set_single_value("OrionCard Settings", field, value)
	frappe.db.commit()
