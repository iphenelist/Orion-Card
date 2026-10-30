import frappe
import requests

from orion_card.api.messaging import send_message, sender_line
from orion_card.utils.card_composer import issue_single_card
from orion_card.utils.credits import plain_sms_text
from orion_card.utils.invites import INVITATION, assert_within_limit

NOTIFY_AFRICA_URL = "https://api.notify.africa/api/v1/api/messages/send"
RODSMS_DEFAULT_BASE_URL = "https://rodsms.com/api/v1"

# RodSMS error codes (https://rodsms.com/docs) -> what the admin should do.
RODSMS_ERRORS = {
    "unauthorized": "RodSMS rejected the API key (missing, revoked or IP-restricted). Check OrionCard Settings.",
    "insufficient_credits": "The RodSMS account has run out of SMS credits. Top up on rodsms.com.",
    "sender_id_unusable": "The RodSMS Sender ID is not approved or not active. Check it in OrionCard Settings.",
    "insufficient_scope": "The RodSMS API key lacks the sms:send permission.",
    "rate_limited": "RodSMS rate limit reached. Try again in a moment.",
    "invalid_request": "RodSMS rejected the phone number or message.",
    "validation_error": "RodSMS rejected the request.",
}


def _settings():
    return frappe.get_single("OrionCard Settings")


def _provider(settings) -> str:
    return settings.sms_provider or "RodSMS"


def get_credentials():
    """(api_token, sender_id) for the selected SMS provider."""
    settings = _settings()
    if _provider(settings) == "Notify Africa":
        api_token = settings.get_password("notify_africa_api_token", raise_exception=False)
        sender_id = settings.notify_africa_sms_sender_id
        label = "Notify Africa"
    else:
        api_token = settings.get_password("rodsms_api_key", raise_exception=False)
        sender_id = settings.rodsms_sender_id
        label = "RodSMS"
    if not api_token:
        frappe.throw(f"{label} API key is not set in OrionCard Settings")
    if not sender_id:
        frappe.throw(f"{label} Sender ID is not set in OrionCard Settings")
    return api_token.strip(), sender_id.strip()


def normalize_phone(phone: str) -> str:
    return phone.replace("+", "").replace(" ", "").replace("-", "")


def send_sms(phone: str, message: str) -> dict:
    """Send a single SMS through the provider selected in OrionCard Settings."""
    settings = _settings()
    if _provider(settings) == "Notify Africa":
        return _send_notify_africa(phone, message)
    return _send_rodsms(settings, phone, message)


def _rodsms_base_url(settings) -> str:
    return (settings.rodsms_base_url or RODSMS_DEFAULT_BASE_URL).strip().rstrip("/")


def _rodsms_request(settings, method: str, path: str, payload: dict | None = None) -> dict:
    api_key = (settings.get_password("rodsms_api_key", raise_exception=False) or "").strip()
    if not api_key:
        frappe.throw("RodSMS API key is not set in OrionCard Settings")
    try:
        response = requests.request(
            method,
            f"{_rodsms_base_url(settings)}{path}",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": f"OrionCard/1.0 (+{frappe.utils.get_url()})",
                **({"Content-Type": "application/json"} if payload is not None else {}),
            },
            json=payload,
            timeout=30,
        )
    except requests.RequestException as e:
        # Outage, firewall or network problem: say so plainly instead of a traceback.
        frappe.log_error(title="RodSMS unreachable", message=frappe.get_traceback())
        frappe.throw(
            f"Could not reach RodSMS ({_rodsms_base_url(settings)}): the server closed the connection "
            f"or did not answer. This is a network/RodSMS problem, not your settings. "
            f"Try again later or contact RodSMS support. ({type(e).__name__})",
            title="RodSMS unreachable",
        )
    try:
        body = response.json() or {}
    except ValueError:
        body = {}
    if not response.ok or not body.get("success"):
        error = body.get("error") or {}
        code = error.get("code") or str(response.status_code)
        detail = error.get("message") or response.text[:300]
        hint = RODSMS_ERRORS.get(code, "RodSMS request failed.")
        frappe.throw(f"{hint} ({code}: {detail}; request {body.get('request_id', '-')})")
    return body


def _send_rodsms(settings, phone: str, message: str) -> dict:
    from orion_card.utils.phone import normalize_phone as to_international

    recipient = to_international(phone)
    if len(recipient) < 10:
        frappe.throw(f"Invalid phone number '{phone}' — cannot send SMS.")

    _api_key, sender_id = get_credentials()
    body = _rodsms_request(settings, "POST", "/messages", {
        "sender_id": sender_id,
        "recipient": recipient,
        "message": message,
    })
    return body.get("data") or {}


def _send_notify_africa(phone: str, message: str) -> dict:
    api_token, sender_id = get_credentials()

    response = requests.post(
        NOTIFY_AFRICA_URL,
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        json={
            "phone_number": normalize_phone(phone),
            "message": message,
            "sender_id": sender_id,
        },
        timeout=30,
    )
    if not response.ok:
        frappe.throw(f"Notify Africa SMS API error ({response.status_code}): {response.text}")
    return response.json()


def rodsms_account_status() -> dict:
    """RodSMS credit balance and approved Sender IDs (needs sms:read)."""
    settings = _settings()
    balance = _rodsms_request(settings, "GET", "/balance").get("data")
    sender_ids = _rodsms_request(settings, "GET", "/sender-ids").get("data")
    return {"balance": balance, "sender_ids": sender_ids}


SMS_MAX_PARTS = 2
SMS_MAX_CHARS = SMS_MAX_PARTS * 153
MIN_NAME_CHARS = 12


def build_invitation_message(occasion_doc, guest_row) -> str:
    """The Swahili SMS invitation, kept to SMS_MAX_PARTS billed parts: plain
    GSM characters only, and a long event name, venue or guest name is cut
    short rather than paying for a third part."""
    names = {
        "guest": guest_row.contributor_name or "",
        "occasion": occasion_doc.occasion_name or "",
        "venue": occasion_doc.venue_name or "",
    }
    text = _invitation_text(occasion_doc, guest_row, names)
    for key in ("occasion", "venue", "guest"):
        overflow = len(text) - SMS_MAX_CHARS
        if overflow <= 0:
            break
        keep = max(len(names[key]) - overflow - 2, MIN_NAME_CHARS)
        if keep < len(names[key]):
            names[key] = names[key][:keep].rstrip() + ".."
            text = _invitation_text(occasion_doc, guest_row, names)
    return text


def _invitation_text(occasion_doc, guest_row, names) -> str:
    date_str = frappe.utils.formatdate(occasion_doc.occasion_date, "dd-MM-yyyy")
    when = ", ".join(part for part in (date_str, occasion_doc.occasion_time) if part)
    base = frappe.utils.get_url().rstrip("/")
    lines = [
        f"Habari {names['guest']},",
        f"Umealikwa kwenye {names['occasion']}.",
        f"Tarehe: {when}",
        f"Ukumbi: {names['venue']}",
    ]
    if occasion_doc.get("venue_address"):
        lines.append(f"Anwani: {occasion_doc.venue_address}")
    if occasion_doc.get("venue_location"):
        lines.append(f"Mahali: {occasion_doc.venue_location}")
    lines.append(f"Kadi: {guest_row.card_type}, Namba: {guest_row.guest_code}")
    if occasion_doc.card_design:
        lines.append(f"Pakua kadi yako: {base}/k/{guest_row.guest_code}")
    lines.append(sender_line(occasion_doc))
    return plain_sms_text("\n".join(lines))


def send_invitation(occasion_doc, guest_row) -> dict:
    """Send the invitation text to a guest via SMS"""
    if not guest_row.phone:
        frappe.throw(f"No phone number for {guest_row.contributor_name}")
    assert_within_limit(occasion_doc, guest_row, "SMS", INVITATION)

    message = build_invitation_message(occasion_doc, guest_row)
    result = send_message(
        occasion_doc,
        "SMS",
        guest_row.phone,
        message,
        message_type="Invitation",
        guest_code=guest_row.guest_code,
        recipient_name=guest_row.contributor_name,
    )

    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Occasion",
        "reference_name": occasion_doc.name,
        "content": f"SMS sent to {guest_row.contributor_name} ({guest_row.phone}). Response: {result}"
    }).insert(ignore_permissions=True)

    return result


@frappe.whitelist()
def send_single(occasion_name: str, guest_code: str):
    """Whitelisted: send SMS invitation to one guest by guest_code"""
    occasion = frappe.get_doc("Occasion", occasion_name)
    occasion.check_permission("write")
    occasion.assert_can_send()
    for contributor in occasion.contributors:
        if contributor.guest_code == guest_code:
            if not contributor.card_image:
                issue_single_card(occasion, contributor)
            result = send_invitation(occasion, contributor)
            return {"success": True, "result": result}
    frappe.throw(f"Contributor with card code '{guest_code}' not found in occasion '{occasion_name}'")
