import frappe
import requests

from orion_card.api.messaging import send_message, sender_line
from orion_card.utils.invites import INVITATION, assert_within_limit
from orion_card.utils.card_composer import issue_single_card

WASENDER_BASE_URL = "https://www.wasenderapi.com/api"


def get_credentials():
    settings = frappe.get_single("OrionCard Settings")
    api_token = settings.get_password("wasender_api_token", raise_exception=False)
    if not api_token:
        frappe.throw("WaSender API Token is not set in OrionCard Settings")
    return api_token


def normalize_phone(phone: str) -> str:
    """Return the phone number as digits with country code (e.g. 255712345678), no '+', as required by WaSenderAPI"""
    return "".join(ch for ch in phone if ch.isdigit())


def send_text(phone: str, text: str) -> dict:
    """Send a plain WhatsApp text message via the WaSenderAPI"""
    api_token = get_credentials()

    response = requests.post(
        f"{WASENDER_BASE_URL}/send-message",
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        json={"to": normalize_phone(phone), "text": text},
        timeout=30,
    )
    if not response.ok:
        frappe.throw(f"WaSenderAPI error ({response.status_code}): {response.text}")
    return response.json()


def send_image(phone: str, image_url: str, caption: str = "") -> dict:
    """Send a WhatsApp image message (with optional caption) via the WaSenderAPI"""
    api_token = get_credentials()

    payload = {"to": normalize_phone(phone), "imageUrl": image_url}
    if caption:
        payload["text"] = caption

    response = requests.post(
        f"{WASENDER_BASE_URL}/send-message",
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    if not response.ok:
        frappe.throw(f"WaSenderAPI error ({response.status_code}): {response.text}")
    return response.json()


def send_document(phone: str, document_url: str, file_name: str, caption: str = "") -> dict:
    """Send a WhatsApp document (e.g. a PDF receipt) via the WaSenderAPI.
    The URL must be publicly reachable by WaSenderAPI's servers."""
    api_token = get_credentials()

    payload = {"to": normalize_phone(phone), "documentUrl": document_url, "fileName": file_name}
    if caption:
        payload["text"] = caption

    response = requests.post(
        f"{WASENDER_BASE_URL}/send-message",
        headers={
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    if not response.ok:
        frappe.throw(f"WaSenderAPI error ({response.status_code}): {response.text}")
    return response.json()


def build_invitation_message(occasion_doc, guest_row) -> str:
    """Build the warm Swahili WhatsApp invitation (WhatsApp shows *bold* and
    _italics_; one message costs one credit whatever its length)."""
    date_str = frappe.utils.formatdate(occasion_doc.occasion_date, "dd-MM-yyyy")
    base = frappe.utils.get_url().rstrip("/")
    download_url = f"{base}/invitee/download/occasion-card/{guest_row.guest_code}"
    contacts = " / ".join(c for c in (occasion_doc.contact_1, occasion_doc.contact_2) if c)

    lines = [
        f"🎉 *Karibu sana, {guest_row.contributor_name}!*",
        "",
        f"Kwa furaha kubwa, *{occasion_doc.couple_names}* wanakualika kwa heshima kwenye",
        f"✨ *{occasion_doc.occasion_name}* ✨",
        "",
        "Uwepo wako utaifanya siku hii kuwa ya kipekee zaidi. Tunatarajia sana kukuona! 💐",
        "",
        f"📅 *Tarehe:* {date_str}",
    ]
    if occasion_doc.occasion_time:
        lines.append(f"⏰ *Muda:* {occasion_doc.occasion_time}")
    lines.append(f"📍 *Ukumbi:* {occasion_doc.venue_name}")
    if occasion_doc.get("venue_location"):
        lines.append(f"🗺️ *Ramani:* {occasion_doc.venue_location}")
    if occasion_doc.dress_code:
        lines.append(f"👗 *Mavazi:* {occasion_doc.dress_code}")
    lines += [
        "",
        f"🎟️ *Kadi yako:* {guest_row.card_type}",
        f"🔢 *Namba ya kadi:* {guest_row.guest_code}",
        "",
        "📲 Pakua kadi yako hapa:",
        download_url,
        "Tafadhali fika na kadi hii (au ujumbe huu) mlangoni.",
    ]
    if contacts:
        lines += ["", f"📞 Kwa maswali: {contacts}"]
    lines += [
        "",
        "Karibu sana, tunakusubiri kwa hamu! 🙏",
        f"_{sender_line(occasion_doc)}_",
    ]
    return "\n".join(lines)


def get_card_image_url(guest_row) -> str:
    """Build an absolute, publicly reachable URL for the guest's card image"""
    base = frappe.utils.get_url().rstrip("/")
    url = guest_row.card_image
    return url if url.startswith("http") else f"{base}{url}"


def send_card_image_enabled() -> bool:
    return bool(frappe.db.get_single_value("OrionCard Settings", "whatsapp_send_card_image"))


def send_invitation(occasion_doc, guest_row) -> dict:
    """Send the invitation (with card download link) to a guest via WhatsApp.

    With "Send the card image on WhatsApp" ticked in OrionCard Settings the card
    picture goes out with the text as its caption. WaSenderAPI fetches the
    image itself, so that only works once the site is on a public domain.
    """
    if not guest_row.phone:
        frappe.throw(f"No phone number for {guest_row.contributor_name}")
    if not guest_row.card_image:
        frappe.throw(f"Card not generated for {guest_row.contributor_name}. Run Generate Cards first.")
    assert_within_limit(occasion_doc, guest_row, "WhatsApp", INVITATION)

    message = build_invitation_message(occasion_doc, guest_row)
    result = send_message(
        occasion_doc,
        "WhatsApp",
        guest_row.phone,
        message,
        message_type="Invitation",
        guest_code=guest_row.guest_code,
        recipient_name=guest_row.contributor_name,
        image_url=get_card_image_url(guest_row) if send_card_image_enabled() else None,
    )

    frappe.get_doc({
        "doctype": "Comment",
        "comment_type": "Info",
        "reference_doctype": "Occasion",
        "reference_name": occasion_doc.name,
        "content": f"WhatsApp sent to {guest_row.contributor_name} ({guest_row.phone}). Response: {result}"
    }).insert(ignore_permissions=True)

    return result


@frappe.whitelist()
def send_single(occasion_name: str, guest_code: str):
    """Whitelisted: send WhatsApp invitation to one guest by guest_code"""
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
