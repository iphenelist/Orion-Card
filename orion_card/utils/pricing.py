"""Card subscription pricing: graduated per-card tiers from OrionCard Settings.

Each tier covers a range of card numbers (1-100, 101+ …) and says what one
card in that range costs, how much of that is the owner's profit (internal),
and how many SMS / WhatsApp credits the customer receives with it.

A first subscription is priced card by card through the tiers ("only cards
101+ cost more"). Top-ups may keep the rate the customer subscribed at (the
tier of the last card of their first booking), but only for a limited number
of cards: at most
`top_up_locked_percent` (default 20%) of the cards already paid, counted over
all top-ups together. Only cards that would otherwise cost more use up that
allowance; the rest are priced by the tiers as usual.

E.g. 100 cards paid at 900: +20 = 20 x 900; +30 = 20 x 900 + 10 x 1,200.
"""

import frappe
from frappe import _
from frappe.utils import cint, flt


def get_tiers() -> list:
	settings = frappe.get_cached_doc("OrionCard Settings")
	tiers = sorted(settings.card_price_tiers, key=lambda t: cint(t.from_card))
	if not tiers:
		frappe.throw(_("Card prices are not set up yet. Add Card Price Tiers in OrionCard Settings."))
	return tiers


def _tier_for(card_number: int, tiers):
	for tier in tiers:
		upper = cint(tier.to_card)
		if cint(tier.from_card) <= card_number and (not upper or card_number <= upper):
			return tier
	frappe.throw(_("No card price tier covers card number {0}. Check OrionCard Settings.").format(card_number))


def quote(number_of_guests: int, already_paid: int = 0, locked_allowance: int = 0,
		  first_booking: int | None = None) -> dict:
	"""Price, internal profit and included credits for `number_of_guests` more
	cards on an Occasion that already has `already_paid` cards. Up to
	`locked_allowance` of them may keep the rate of card `first_booking` (the
	last card of the customer's first booking; defaults to `already_paid`)."""
	number_of_guests = cint(number_of_guests)
	already_paid = max(cint(already_paid), 0)
	allowance = max(cint(locked_allowance), 0)
	tiers = get_tiers()
	rate_card = cint(first_booking) or already_paid
	locked_tier = _tier_for(rate_card, tiers) if rate_card else None

	lines = {}
	locked_cards = 0
	for card_number in range(already_paid + 1, already_paid + number_of_guests + 1):
		tier = _tier_for(card_number, tiers)
		if (
			locked_tier
			and locked_cards < allowance
			and flt(locked_tier.price_per_card) < flt(tier.price_per_card)
		):
			tier = locked_tier
			locked_cards += 1
		line = lines.setdefault(tier.name, {
			"from_card": card_number,
			"to_card": card_number,
			"cards": 0,
			"price_per_card": flt(tier.price_per_card),
			"profit_per_card": flt(tier.profit_per_card),
			"sms_credits_per_card": cint(tier.sms_credits_per_card),
			"whatsapp_credits_per_card": cint(tier.whatsapp_credits_per_card),
		})
		line["cards"] += 1
		line["to_card"] = card_number

	lines = sorted(lines.values(), key=lambda line: line["from_card"])
	return {
		"number_of_guests": number_of_guests,
		"already_paid": already_paid,
		"locked_cards": locked_cards,
		"lines": lines,
		"price": sum(line["cards"] * line["price_per_card"] for line in lines),
		"profit": sum(line["cards"] * line["profit_per_card"] for line in lines),
		"sms_credits": sum(line["cards"] * line["sms_credits_per_card"] for line in lines),
		"whatsapp_credits": sum(line["cards"] * line["whatsapp_credits_per_card"] for line in lines),
	}


def public_quote(q: dict) -> dict:
	"""The customer-facing part of a quote: no profit figures."""
	return {
		"number_of_guests": q["number_of_guests"],
		"locked_cards": q["locked_cards"],
		"price": q["price"],
		"sms_credits": q["sms_credits"],
		"whatsapp_credits": q["whatsapp_credits"],
		"lines": [
			{k: line[k] for k in ("from_card", "to_card", "cards", "price_per_card",
								  "sms_credits_per_card", "whatsapp_credits_per_card")}
			for line in q["lines"]
		],
	}


def locked_allowance(occasion: str | None, exclude: str | None = None) -> int:
	"""How many more cards of this Occasion may still keep the old rate."""
	if not occasion:
		return 0
	percent = cint(frappe.db.get_single_value("OrionCard Settings", "top_up_locked_percent"))
	conditions = "occasion=%(occasion)s and docstatus=1"
	if exclude:
		conditions += " and name!=%(exclude)s"
	used = cint(frappe.db.sql(
		f"select coalesce(sum(locked_rate_cards), 0) from `tabOccasion Subscription` where {conditions}",
		{"occasion": occasion, "exclude": exclude},
	)[0][0])
	return max(paid_cards(occasion, exclude) * percent // 100 - used, 0)


def first_booking(occasion: str | None, exclude: str | None = None) -> int:
	"""Card count of the Occasion's first approved subscription."""
	if not occasion:
		return 0
	filters = {"occasion": occasion, "docstatus": 1}
	if exclude:
		filters["name"] = ["!=", exclude]
	rows = frappe.get_all("Occasion Subscription", filters=filters, fields=["number_of_guests"],
						  order_by="creation asc", limit=1)
	return cint(rows[0].number_of_guests) if rows else 0


def quote_for_occasion(number_of_guests: int, occasion: str | None, exclude: str | None = None) -> dict:
	return quote(
		number_of_guests,
		paid_cards(occasion, exclude),
		locked_allowance(occasion, exclude),
		first_booking(occasion, exclude),
	)


def paid_cards(occasion: str | None, exclude: str | None = None) -> int:
	"""Cards already covered by approved subscriptions of this Occasion."""
	if not occasion:
		return 0
	conditions = "occasion=%(occasion)s and docstatus=1"
	if exclude:
		conditions += " and name!=%(exclude)s"
	return cint(frappe.db.sql(
		f"select coalesce(sum(number_of_guests), 0) from `tabOccasion Subscription` where {conditions}",
		{"occasion": occasion, "exclude": exclude},
	)[0][0])


@frappe.whitelist(allow_guest=True)
def get_quote(number_of_guests: int, occasion: str | None = None) -> dict:
	"""Live price for the application form and the 'Request Card Subscription'
	dialog. Public, so it never includes the internal profit."""
	number_of_guests = cint(number_of_guests)
	if number_of_guests < 0 or number_of_guests > 100_000:
		frappe.throw(_("Enter a number of guests between 1 and 100,000."))
	if occasion and frappe.session.user != "Guest" and frappe.has_permission("Occasion", "read", doc=occasion):
		return public_quote(quote_for_occasion(number_of_guests, occasion))
	return public_quote(quote(number_of_guests))


def validate_tiers(tiers, sms_price: float, whatsapp_price: float) -> list:
	"""Throw on gaps/overlaps; return warnings when a tier gives away more than it earns."""
	tiers = sorted(tiers, key=lambda t: cint(t.from_card))
	warnings = []
	expected_from = 1
	for i, tier in enumerate(tiers):
		start, end = cint(tier.from_card), cint(tier.to_card)
		if start != expected_from:
			frappe.throw(_("Card Price Tiers must start at card 1 and follow on without gaps: row {0} starts at {1}, expected {2}.")
						 .format(tier.idx, start, expected_from))
		if end and end < start:
			frappe.throw(_("Card Price Tiers row {0}: 'To Card' is before 'From Card'.").format(tier.idx))
		if not end and i != len(tiers) - 1:
			frappe.throw(_("Card Price Tiers row {0}: only the last tier can be open-ended (To Card = 0).").format(tier.idx))
		expected_from = end + 1 if end else None

		credit_value = cint(tier.sms_credits_per_card) * flt(sms_price) + cint(tier.whatsapp_credits_per_card) * flt(whatsapp_price)
		if flt(tier.profit_per_card) + credit_value > flt(tier.price_per_card):
			warnings.append(_(
				"Tier {0}: profit {1} + included credits worth {2} is more than the card price {3}."
			).format(tier.idx, flt(tier.profit_per_card), credit_value, flt(tier.price_per_card)))
	if tiers and cint(tiers[-1].to_card):
		frappe.throw(_("The last Card Price Tier must be open-ended (To Card = 0) so every guest count has a price."))
	return warnings
