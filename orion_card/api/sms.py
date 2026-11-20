import frappe
import httpx

from orion_card.api.messaging import send_message, sender_line
from orion_card.utils.card_composer import issue_single_card
from orion_card.utils.credits import plain_sms_text
from orion_card.utils.invites import INVITATION, assert_within_limit

RODSMS_DEFAULT_BASE_URL = "https://rodsms.com/api/v1"

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


def _rodsms_base_url(settings) -> str:
	return (settings.rodsms_base_url or RODSMS_DEFAULT_BASE_URL).strip().rstrip("/")


def normalize_phone(phone: str) -> str:
	return phone.replace("+", "").replace(" ", "").replace("-", "")


def _rodsms_request(settings, method: str, path: str, payload: dict | None = None) -> dict:
	api_key = (settings.get_password("rodsms_api_key", raise_exception=False) or "").strip()
	if not api_key:
		frappe.throw("RodSMS API key is not set in OrionCard Settings")
	try:
		with httpx.Client(http2=True, timeout=30) as client:
			response = client.request(
				method,
				f"{_rodsms_base_url(settings)}{path}",
				headers={
					"Authorization": f"Bearer {api_key}",
					"Accept": "application/json",
					"User-Agent": f"OrionCard/1.0 (+{frappe.utils.get_url()})",
					**({"Content-Type": "application/json"} if payload is not None else {}),
				},
				json=payload,
			)
	except httpx.RequestError as e:
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
	if not response.is_success or not body.get("success"):
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

	api_key = (settings.get_password("rodsms_api_key", raise_exception=False) or "").strip()
	if not api_key:
		frappe.throw("RodSMS API key is not set in OrionCard Settings")
	sender_id = (settings.rodsms_sender_id or "").strip()
	if not sender_id:
		frappe.throw("RodSMS Sender ID is not set in OrionCard Settings")

	body = _rodsms_request(settings, "POST", "/messages", {
		"sender_id": sender_id,
		"recipient": recipient,
		"message": message,
		"sms_type": "transactional",
	})
	return body.get("data") or {}


def send_sms(phone: str, message: str) -> dict:
	"""Send a single SMS through RodSMS."""
	return _send_rodsms(_settings(), phone, message)


def rodsms_account_status() -> dict:
	"""RodSMS credit balance and approved Sender IDs (needs sms:read)."""
	settings = _settings()
	balance = _rodsms_request(settings, "GET", "/balance").get("data")
	sender_ids = _rodsms_request(settings, "GET", "/sender-ids").get("data")
	return {"balance": balance, "sender_ids": sender_ids}


SMS_MAX_CHARS = 1000
MIN_NAME_CHARS = 12


def build_invitation_message(occasion_doc, guest_row) -> str:
	"""The Swahili SMS invitation, kept within SMS_MAX_CHARS."""
	if occasion_doc.get("custom_sms_message"):
		return _custom_invitation_text(occasion_doc, guest_row)

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


def _custom_invitation_text(occasion_doc, guest_row) -> str:
	base = frappe.utils.get_url().rstrip("/")
	date_str = frappe.utils.formatdate(occasion_doc.occasion_date, "dd-MM-yyyy")
	link = f"{base}/k/{guest_row.guest_code}" if occasion_doc.card_design else ""
	text = (occasion_doc.custom_sms_message or "").format(
		guest=guest_row.contributor_name or "",
		occasion=occasion_doc.occasion_name or "",
		date=date_str,
		venue=occasion_doc.venue_name or "",
		address=occasion_doc.get("venue_address") or "",
		location=occasion_doc.get("venue_location") or "",
		card_type=guest_row.card_type or "",
		number=guest_row.guest_code or "",
		link=link,
		sender=sender_line(occasion_doc),
	)
	lines = [l for l in text.splitlines() if l.strip() and not l.strip().endswith(":")]
	return plain_sms_text("\n".join(lines))


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
