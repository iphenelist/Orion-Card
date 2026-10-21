import frappe
from frappe.utils import cint, flt, fmt_money

no_cache = 1


def get_context(context):
	from orion_card.api.payments import get_catalogue

	settings = frappe.get_cached_doc("OrionCard Settings")
	catalogue = get_catalogue()
	currency = catalogue["currency"]

	context.title = "OrionCard — Kadi za mwaliko, michango na wageni"
	context.body_class = "ec-body"
	context.no_breadcrumbs = 1
	context.ec_business_name = settings.business_legal_name
	context.money = lambda v: fmt_money(flt(v), precision=0, currency=currency)
	# Public prices only: profit and the credits included per card are not shown.
	context.card_tiers = [
		{
			"from_card": cint(t.from_card),
			"to_card": cint(t.to_card),
			"price": flt(t.price_per_card),
		}
		for t in sorted(settings.card_price_tiers, key=lambda t: cint(t.from_card))
	]
	context.top_up_percent = cint(settings.top_up_locked_percent)
	context.sms_price = catalogue["prices"]["SMS"]
	context.whatsapp_price = catalogue["prices"]["WhatsApp"]
	context.credit_expiry_months = cint(settings.credit_expiry_months)
	context.allow_credit_purchase = cint(settings.allow_credit_purchase)

	# One row per package size, SMS and WhatsApp side by side.
	by_label = {}
	for channel in ("SMS", "WhatsApp"):
		for p in catalogue["packages"][channel]:
			row = by_label.setdefault(p["label"], {"label": p["label"], "credits": p["credits"]})
			row[channel] = p["amount"]
	context.package_rows = sorted(by_label.values(), key=lambda r: r["credits"])

