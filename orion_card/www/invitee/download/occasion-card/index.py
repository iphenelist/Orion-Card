import frappe
from frappe.rate_limiter import rate_limit


def get_context(context):
    # Support both URL param and path segment
    guest_code = (
        frappe.form_dict.get("guest_code")
        or frappe.form_dict.get("code")
        or frappe.local.path_info.split("/")[-1]
    )

    if not guest_code:
        frappe.throw("Invalid link.", frappe.DoesNotExistError)

    results = frappe.db.get_all(
        "Occasion Contributor",
        filters={"guest_code": guest_code, "parenttype": "Occasion"},
        fields=[
            "name", "contributor_name as guest_name", "phone", "card_type",
            "guest_code", "card_image", "rsvp_status", "parent"
        ],
        limit=1
    )

    if not results:
        frappe.throw("This invitation link is invalid or has expired.", frappe.DoesNotExistError)

    guest = results[0]
    occasion = frappe.get_doc("Occasion", guest["parent"])

    context.guest = guest
    context.occasion = occasion
    context.page_title = f"Invitation – {guest['guest_name']}"
    context.no_cache = 1

    if guest.get("card_image"):
        base = frappe.utils.get_url().rstrip("/")
        url = guest["card_image"]
        context.card_download_url = url if url.startswith("http") else f"{base}{url}"
    else:
        context.card_download_url = None


@frappe.whitelist(allow_guest=True)
@rate_limit(limit=20, seconds=60)
def confirm_rsvp(guest_code: str, status: str):
    """Guest RSVP confirmation from the invitation page."""
    if status not in ("Confirmed", "Declined"):
        frappe.throw("Invalid RSVP status")

    results = frappe.db.get_all(
        "Occasion Contributor",
        filters={"guest_code": guest_code, "parenttype": "Occasion"},
        fields=["name"],
        limit=1
    )
    if not results:
        frappe.throw("This invitation link is invalid or has expired.", frappe.DoesNotExistError)

    frappe.db.set_value("Occasion Contributor", results[0]["name"], "rsvp_status", status)
    frappe.db.commit()

    return {"success": True, "rsvp_status": status}
