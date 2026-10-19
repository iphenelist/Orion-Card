import frappe


def execute():
	"""Graduated card pricing replaces the flat price per guest card:
	cards 1-100 at 900 (400 profit, 10 SMS + 3 WhatsApp credits),
	cards 101+ at 1,200 (400 profit, 14 SMS + 6 WhatsApp credits)."""
	from orion_card.install import seed_card_price_tiers

	settings = frappe.get_single("OrionCard Settings")
	if settings.card_price_tiers:
		return
	seed_card_price_tiers(settings)
	settings.flags.ignore_permissions = True
	settings.save()
	frappe.db.commit()
