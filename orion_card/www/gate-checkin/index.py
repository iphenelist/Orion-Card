import secrets

import frappe
from frappe.rate_limiter import rate_limit
from frappe.utils import cint

from orion_card.orioncard.doctype.occasion.occasion import card_admits


def get_context(context):
    context.page_title = "Occasion Gate Check-in"
    context.no_cache = 1
    code = frappe.form_dict.get("code")
    occasion = frappe.form_dict.get("occasion")
    context.auto_scan = bool(code)
    context.scan_code = code or ""
    context.scan_occasion = occasion or ""


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=20, seconds=60)
def validate_guest(guest_code: str, occasion_name: str | None = None, pin: str | None = None):
    """Validate a guest QR code at the gate.

    occasion_name is required: without it this would search guest codes
    sitewide, letting one occasion's gate page check in (and thereby
    invalidate) another occasion's guests.

    pin is the Occasion's gate PIN. Without it anyone holding a QR link (which
    names the occasion) could guess codes and burn real guests' cards before
    the event. Logged-in users who can open the Occasion don't need it.
    """
    if not guest_code or not occasion_name:
        return {"valid": False, "status": "Invalid", "message": "❌ Invalid QR Code", "color": "red"}

    gate_pin = frappe.db.get_value("Occasion", occasion_name, "gate_pin")
    if gate_pin is None:
        return {"valid": False, "status": "Invalid", "message": "❌ Invalid QR Code", "color": "red"}

    if not _can_skip_pin(occasion_name) and not (pin and secrets.compare_digest(str(pin), gate_pin)):
        return {
            "valid": False,
            "status": "PIN Required",
            "message": "🔒 Weka PIN sahihi ya geti. / Enter the correct gate PIN.",
            "color": "red",
        }

    filters = {"guest_code": guest_code, "parent": occasion_name, "parenttype": "Occasion"}

    results = frappe.db.get_all(
        "Occasion Contributor",
        filters=filters,
        fields=[
            "name", "contributor_name as guest_name", "card_type", "guest_code", "admits",
            "checked_in", "check_in_time", "rsvp_status", "parent"
        ],
        limit=1
    )

    if not results:
        return {
            "valid": False,
            "status": "Invalid",
            "message": "❌ Mgeni huyu hayupo kwenye orodha.",
            "color": "red"
        }

    guest = results[0]
    allow_reentry, table_size = frappe.db.get_value(
        "Occasion", guest["parent"], ["allow_reentry", "table_size"]
    )
    admits = card_admits(guest["card_type"], guest["admits"], table_size)
    # Lock the row: two gate phones scanning the same DOUBLE/TABLE card at once
    # must not both get the last place.
    entered = cint(frappe.db.get_value("Occasion Contributor", guest["name"], "entered_count", for_update=True))

    if entered >= admits and not allow_reentry:
        first_in = frappe.utils.format_datetime(guest["check_in_time"]) if guest["check_in_time"] else ""
        if admits > 1:
            message = f"⚠️ Kadi imeshatumika: watu {entered} kati ya {admits} wameingia (wa kwanza saa {first_in})"
        else:
            message = f"⚠️ Ameshaingia tayari saa {first_in}"
        return {
            "valid": False,
            "status": "Already Used",
            "message": message,
            "guest_name": guest["guest_name"],
            "card_type": guest["card_type"],
            "admits": admits,
            "entered": entered,
            "color": "orange"
        }

    # Count this person in. With re-entry on the card never runs out, so the
    # count stops at the card's size.
    entered = min(entered + 1, admits)
    values = {"checked_in": 1, "entered_count": entered, "check_in_status": "Valid"}
    if not guest["checked_in"] or not guest["check_in_time"]:
        values["check_in_time"] = frappe.utils.now()  # first arrival on this card
    frappe.db.set_value("Occasion Contributor", guest["name"], values)
    frappe.db.commit()

    occasion = frappe.db.get_value(
        "Occasion", guest["parent"],
        ["occasion_name", "couple_names"], as_dict=True
    )

    return {
        "valid": True,
        "status": "Valid",
        "message": f"✅ Karibu, {guest['guest_name']}!" + (f" ({entered}/{admits})" if admits > 1 else ""),
        "guest_name": guest["guest_name"],
        "card_type": guest["card_type"],
        "admits": admits,
        "entered": entered,
        "guest_code": guest["guest_code"],
        "occasion_name": occasion.occasion_name if occasion else "",
        "couple_names": occasion.couple_names if occasion else "",
        "color": "green"
    }


def _can_skip_pin(occasion_name: str) -> bool:
    if frappe.session.user == "Guest":
        return False
    return frappe.has_permission("Occasion", "read", doc=occasion_name)
