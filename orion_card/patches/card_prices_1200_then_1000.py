import frappe

from orion_card.patches.seed_card_price_tiers import execute as seed_if_empty

OLD_DEFAULT_TIERS = (
	[(1, 100, 900, 400, 10, 3), (101, 0, 1200, 400, 14, 6)],
	[(1, 100, 1200, 600, 10, 3), (101, 0, 1000, 400, 10, 3)],
	[(1, 100, 1200, 600, 10, 1), (101, 0, 1000, 400, 10, 1)],
)
OLD_WHATSAPP_CREDIT_PRICE = 75
WHATSAPP_CREDIT_PRICE = 25
TIER_FIELDS = ("from_card", "to_card", "price_per_card", "profit_per_card",
			   "sms_credits_per_card", "whatsapp_credits_per_card")


def execute():
	"""New card prices: cards 1-100 at 1,200 (600 profit), cards 101+ at 1,000
	(400 profit), each card with 10 SMS + 5 WhatsApp credits: per channel 2
	invitations + 3 reminders per guest, an SMS being 2 parts. A WhatsApp credit is valued at 25
	like an SMS (WaSenderAPI is a flat monthly fee). Only replaces values
	still on an old default, never prices set by hand."""
	from orion_card.install import DEFAULT_CARD_TIERS

	if frappe.utils.flt(frappe.db.get_single_value("OrionCard Settings", "whatsapp_credit_price")) == OLD_WHATSAPP_CREDIT_PRICE:
		frappe.db.set_single_value("OrionCard Settings", "whatsapp_credit_price", WHATSAPP_CREDIT_PRICE)
	settings = frappe.get_single("OrionCard Settings")
	if not settings.card_price_tiers:
		seed_if_empty()
		return
	current = [
		tuple(int(row.get(f) or 0) for f in TIER_FIELDS)
		for row in sorted(settings.card_price_tiers, key=lambda r: int(r.from_card or 0))
	]
	if current not in OLD_DEFAULT_TIERS:
		return
	settings.set("card_price_tiers", [dict(zip(TIER_FIELDS, tier)) for tier in DEFAULT_CARD_TIERS])
	settings.flags.ignore_permissions = True
	settings.save()
	frappe.db.commit()
