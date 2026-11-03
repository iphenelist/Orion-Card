import frappe
from frappe.utils import cint, flt, fmt_money

no_cache = 1


def get_context(context):
	settings = frappe.get_cached_doc("OrionCard Settings")
	currency = settings.currency or "TZS"
	price_per_card = flt(settings.price_per_card)

	context.title = "OrionCard — Kadi za mwaliko, michango na wageni"
	context.body_class = "ec-body ec-body--dark"
	context.no_breadcrumbs = 1
	context.ec_business_name = settings.business_legal_name
	context.money = lambda v: fmt_money(flt(v), precision=0, currency=currency)
	context.card_tiers = [{"from_card": 1, "to_card": 0, "price": price_per_card}]
	context.top_up_percent = 0
	context.sms_price = 0
	context.whatsapp_price = 0
	context.credit_expiry_months = 0
	context.allow_credit_purchase = 0
	context.package_rows = []

