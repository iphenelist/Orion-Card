"""One send path for every outgoing SMS / WhatsApp message.

send_message() reserves the credits, calls the gateway, logs the attempt to
Occasion Guest Invite Log, and refunds the credits when the gateway fails, so
invitations, contribution reminders and the hourly auto-sends all bill and
log the same way.
"""

import frappe
from frappe import _
from frappe.utils import cint

from orion_card.utils import credits


def payer_for(occasion_doc) -> str:
	"""Credits are paid by the Occasion's manager, falling back to whoever is sending."""
	return occasion_doc.assigned_user or frappe.session.user


def sender_line(occasion_doc) -> str:
	"""Makes clear the organiser — not the platform — is the sender."""
	return f"Kutoka: {occasion_doc.couple_names} (kupitia OrionCard)"


def channel_enabled(channel: str) -> bool:
	field = "sms_enabled" if channel == "SMS" else "whatsapp_enabled"
	value = frappe.db.get_single_value("OrionCard Settings", field)
	# Settings saved before these flags existed have NULL — treat as enabled.
	return value is None or bool(cint(value))


def send_message(
	occasion_doc,
	channel: str,
	phone: str,
	text: str,
	message_type: str = "Invitation",
	guest_code: str | None = None,
	contributor_id: str | None = None,
	recipient_name: str = "",
	image_url: str | None = None,
) -> dict:
	if not phone:
		frappe.throw(_("No phone number for {0}").format(recipient_name or _("this recipient")))
	if not channel_enabled(channel):
		frappe.throw(_("{0} sending is turned off in OrionCard Settings.").format(channel))

	needed = credits.credits_needed(channel, text)
	payer = payer_for(occasion_doc)
	remarks = f"{message_type}: {recipient_name} ({phone})"
	credits.consume(payer, channel, needed, occasion=occasion_doc.name, remarks=remarks)

	try:
		result = _gateway_send(channel, phone, text, image_url=image_url)
	except Exception as e:
		credits.refund(payer, channel, needed, occasion=occasion_doc.name, remarks=f"Failed — {remarks}")
		log_message(occasion_doc, channel, message_type, False, e, guest_code, contributor_id, 0)
		raise

	log_message(occasion_doc, channel, message_type, True, result, guest_code, contributor_id, needed)
	return result


def _gateway_send(channel, phone, text, image_url=None):
	if channel == "SMS":
		from orion_card.api.sms import send_sms

		return send_sms(phone, text)
	from orion_card.api.whatsapp import send_image, send_text

	if image_url:
		return send_image(phone, image_url, caption=text)
	return send_text(phone, text)


def log_message(occasion_doc, channel, message_type, success, response, guest_code=None,
				contributor_id=None, credits_used=0):
	frappe.get_doc({
		"doctype": "Occasion Guest Invite Log",
		"occasion": occasion_doc.name,
		"guest_code": guest_code,
		"contributor_id": contributor_id,
		"channel": channel,
		"message_type": message_type,
		"sent_at": frappe.utils.now(),
		"success": 1 if success else 0,
		"credits_used": credits_used,
		"response": str(response)[:140],
	}).insert(ignore_permissions=True)


@frappe.whitelist()
def estimate(occasion_name: str, channel: str, purpose: str = "Invitation", statuses: str | None = None) -> dict:
	"""Credits a bulk send would need vs. what the payer has — shown before sending."""
	occasion = frappe.get_doc("Occasion", occasion_name)
	occasion.check_permission("read")
	channel = channel or "SMS"
	channels = ["SMS", "WhatsApp"] if channel == "Both" else [channel]

	if purpose == "Invitation":
		from orion_card.api import sms, whatsapp

		builders = {"SMS": sms.build_invitation_message, "WhatsApp": whatsapp.build_invitation_message}
		pending = {ch: occasion.uninvited_guests(ch, statuses) for ch in channels}
		texts = {ch: [builders[ch](occasion, g) for g in pending[ch]] for ch in channels}
	else:
		from orion_card.api.reminders import build_reminder_message, select_contributors

		rows = select_contributors(occasion, frappe.parse_json(statuses) if statuses else None)
		texts = {ch: [build_reminder_message(occasion, c) for c in rows] for ch in channels}

	payer = payer_for(occasion)
	out = {"billing": credits.billing_enabled(), "channels": {}}
	for ch in channels:
		out["channels"][ch] = {
			"messages": len(texts[ch]),
			"needed": sum(credits.credits_needed(ch, t) for t in texts[ch]),
			"available": credits.get_balance(payer, ch),
		}
	return out
