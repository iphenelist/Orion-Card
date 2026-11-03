"""Card subscription pricing: flat price per card from OrionCard Settings."""

import frappe
from frappe import _
from frappe.utils import cint, flt


def get_price_per_card() -> float:
    """Return the flat price per guest card from OrionCard Settings."""
    settings = frappe.get_cached_doc("OrionCard Settings")
    price = flt(settings.price_per_card)
    if not price:
        frappe.throw(_("Card price is not set. Set Price per Card in OrionCard Settings."))
    return price


def quote(number_of_guests: int, already_paid: int = 0, **_kwargs) -> dict:
    """Price for `number_of_guests` cards at the flat rate."""
    number_of_guests = cint(number_of_guests)
    already_paid = max(cint(already_paid), 0)
    price_per_card = get_price_per_card()
    lines = [{
        "from_card": already_paid + 1,
        "to_card": already_paid + number_of_guests,
        "cards": number_of_guests,
        "price_per_card": price_per_card,
        "profit_per_card": 0.0,
        "sms_credits_per_card": 0,
        "whatsapp_credits_per_card": 0,
    }] if number_of_guests else []
    return {
        "number_of_guests": number_of_guests,
        "already_paid": already_paid,
        "locked_cards": 0,
        "lines": lines,
        "price": number_of_guests * price_per_card,
        "profit": 0.0,
        "sms_credits": 0,
        "whatsapp_credits": 0,
    }


def public_quote(q: dict) -> dict:
    """The customer-facing part of a quote (no profit figures)."""
    return {
        "number_of_guests": q["number_of_guests"],
        "locked_cards": 0,
        "price": q["price"],
        "sms_credits": 0,
        "whatsapp_credits": 0,
        "lines": [
            {k: line[k] for k in ("from_card", "to_card", "cards", "price_per_card",
                                   "sms_credits_per_card", "whatsapp_credits_per_card")}
            for line in q["lines"]
        ],
    }


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


def quote_for_occasion(number_of_guests: int, occasion: str | None, exclude: str | None = None) -> dict:
    return quote(number_of_guests, paid_cards(occasion, exclude))


@frappe.whitelist(allow_guest=True)
def get_quote(number_of_guests: int, occasion: str | None = None) -> dict:
    """Live price for the application form. Public — no internal profit."""
    number_of_guests = cint(number_of_guests)
    if number_of_guests < 0 or number_of_guests > 100_000:
        frappe.throw(_("Enter a number of guests between 1 and 100,000."))
    if occasion and frappe.session.user != "Guest" and frappe.has_permission("Occasion", "read", doc=occasion):
        return public_quote(quote_for_occasion(number_of_guests, occasion))
    return public_quote(quote(number_of_guests))
