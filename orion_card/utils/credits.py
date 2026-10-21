"""Prepaid SMS / WhatsApp message credits.

Balances live on one Message Credit Account per user and only ever change
through _apply(), which locks the account row (SELECT ... FOR UPDATE) and
writes a matching Credit Transaction, so the ledger always explains the
balance and parallel sends can't overspend.

Sending reserves credits first (consume) and gives them back if the gateway
call fails (refund) — see orion_card.api.messaging.send_message.
"""

import unicodedata

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

CHANNELS = ("SMS", "WhatsApp")
BALANCE_FIELDS = {
	"SMS": ("sms_balance", "sms_used"),
	"WhatsApp": ("whatsapp_balance", "whatsapp_used"),
}

# GSM 03.38 basic character set; anything outside it forces UCS-2 (70 chars/part).
GSM7_BASIC = set(
	"@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
	"¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
# Extension characters cost two septets each.
GSM7_EXTENDED = set("^{}\\[~]|€\f")
# Common characters outside GSM 03.38 and their plain stand-ins.
SMS_REPLACEMENTS = {
	"\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
	"\u2013": "-", "\u2014": "-", "\u2026": "...", "\u00a0": " ",
}


class InsufficientCreditsError(frappe.ValidationError):
	pass


def billing_enabled() -> bool:
	return bool(cint(frappe.db.get_single_value("OrionCard Settings", "enable_credit_billing")))


def purchase_enabled() -> bool:
	"""Customers may buy credits themselves at /credits. When off, they contact
	OrionCard and a System Manager adds credits on their Message Credit Account."""
	return bool(cint(frappe.db.get_single_value("OrionCard Settings", "allow_credit_purchase")))


def support_contact() -> dict:
	"""Who customers call when their credits or invitations run out."""
	phone, email = (
		frappe.db.get_single_value("OrionCard Settings", field) or ""
		for field in ("support_phone", "support_email")
	)
	return {"phone": phone.strip(), "email": email.strip()}


def contact_line() -> tuple:
	"""(Kiswahili, English) sentence telling the customer whom to contact."""
	contact = support_contact()
	how = contact["phone"] or contact["email"]
	if not how:
		return "Wasiliana na OrionCard.", "Contact OrionCard."
	return f"Wasiliana na OrionCard: {how}.", f"Contact OrionCard: {how}."


def out_of_credits_message(channel: str, needed: int, available: int) -> str:
	if purchase_enabled():
		sw, en = "Nunua credits zaidi kwenye ukurasa wa /credits.", "Buy more at /credits."
	else:
		sw, en = contact_line()
		sw, en = f"{sw} Utaongezewa credits.", f"{en} They will add credits for you."
	return _(
		"Credits zako za {0} zimeisha: zinahitajika {1}, zimebaki {2}. {3} / "
		"Your {0} credits have run out: {1} needed, {2} left. {4}"
	).format(channel, needed, available, sw, en)


def plain_sms_text(text: str) -> str:
	"""Swap characters outside the GSM alphabet (curly quotes, dashes, accents)
	for plain ones and drop the rest (emoji), so the SMS is billed at 160/153
	characters per part instead of 70/67."""
	out = []
	for ch in text or "":
		ch = SMS_REPLACEMENTS.get(ch, ch)
		if all(c in GSM7_BASIC or c in GSM7_EXTENDED for c in ch):
			out.append(ch)
		else:
			out.append(unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode())
	return "".join(out)


def sms_parts(text: str) -> int:
	"""Number of SMS segments the gateway will bill for this text."""
	text = text or ""
	if all(ch in GSM7_BASIC or ch in GSM7_EXTENDED for ch in text):
		length = sum(2 if ch in GSM7_EXTENDED else 1 for ch in text)
		single, multi = 160, 153
	else:
		length = len(text)
		single, multi = 70, 67
	if length <= single:
		return 1
	return -(-length // multi)


def credits_needed(channel: str, text: str) -> int:
	_validate_channel(channel)
	return sms_parts(text) if channel == "SMS" else 1


def get_account(user: str | None = None) -> str:
	"""Name of the user's Message Credit Account, creating it on first use."""
	user = user or frappe.session.user
	if not frappe.db.exists("Message Credit Account", user):
		frappe.get_doc({"doctype": "Message Credit Account", "user": user}).insert(ignore_permissions=True)
	return user


def get_balances(user: str | None = None) -> dict:
	name = get_account(user)
	row = frappe.db.get_value(
		"Message Credit Account",
		name,
		["sms_balance", "sms_used", "whatsapp_balance", "whatsapp_used"],
		as_dict=True,
	)
	return {k: cint(v) for k, v in row.items()}


def get_balance(user: str, channel: str) -> int:
	_validate_channel(channel)
	return get_balances(user)[BALANCE_FIELDS[channel][0]]


def ensure_balance(user: str, channel: str, needed: int):
	"""Throw a friendly error when the user can't afford `needed` credits."""
	if not billing_enabled():
		return
	available = get_balance(user, channel)
	if available < needed:
		frappe.throw(
			out_of_credits_message(channel, needed, available),
			exc=InsufficientCreditsError,
			title=_("Insufficient Credits"),
		)


def consume(user, channel, credits, occasion=None, reference_doctype=None, reference_name=None, remarks=None):
	"""Reserve credits for a send. Raises InsufficientCreditsError when short."""
	if not billing_enabled():
		return None
	return _apply(user, channel, -cint(credits), "Usage", occasion, reference_doctype, reference_name, remarks)


def refund(user, channel, credits, occasion=None, reference_doctype=None, reference_name=None, remarks=None):
	if not billing_enabled():
		return None
	return _apply(user, channel, cint(credits), "Refund", occasion, reference_doctype, reference_name, remarks)


def add(user, channel, credits, transaction_type="Admin Adjustment", reference_doctype=None,
		reference_name=None, remarks=None):
	return _apply(user, channel, cint(credits), transaction_type, None, reference_doctype, reference_name, remarks)


def _apply(user, channel, delta, transaction_type, occasion=None, reference_doctype=None,
		   reference_name=None, remarks=None):
	_validate_channel(channel)
	name = get_account(user)
	balance_field, used_field = BALANCE_FIELDS[channel]

	row = frappe.db.sql(
		f"select `{balance_field}`, `{used_field}` from `tabMessage Credit Account` where name=%s for update",
		name,
	)[0]
	balance, used = cint(row[0]), cint(row[1])

	new_balance = balance + delta
	if new_balance < 0:
		frappe.throw(
			out_of_credits_message(channel, -delta, balance),
			exc=InsufficientCreditsError,
			title=_("Insufficient Credits"),
		)

	if transaction_type == "Usage":
		used += -delta
	elif transaction_type == "Refund":
		used = max(used - delta, 0)

	frappe.db.set_value(
		"Message Credit Account", name, {balance_field: new_balance, used_field: used}, update_modified=True
	)
	frappe.get_doc({
		"doctype": "Credit Transaction",
		"user": name,
		"channel": channel,
		"transaction_type": transaction_type,
		"credits": delta,
		"balance_after": new_balance,
		"occasion": occasion,
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
		"remarks": remarks,
	}).insert(ignore_permissions=True)
	return new_balance


def credit_purchase(purchase_name: str) -> bool:
	"""Add a paid Credit Purchase's credits to its user — exactly once."""
	row = frappe.db.sql(
		"select user, channel, credits, credited from `tabCredit Purchase` where name=%s for update",
		purchase_name,
		as_dict=True,
	)
	if not row or cint(row[0].credited):
		return False
	row = row[0]
	add(
		row.user,
		row.channel,
		row.credits,
		transaction_type="Purchase",
		reference_doctype="Credit Purchase",
		reference_name=purchase_name,
	)
	frappe.db.set_value(
		"Credit Purchase",
		purchase_name,
		{"status": "Paid", "credited": 1, "paid_at": now_datetime()},
		update_modified=True,
	)
	from orion_card.receipts import queue_receipt

	queue_receipt("Credit Purchase", purchase_name)
	return True


@frappe.whitelist()
def admin_adjust(user: str, channel: str, credits: int, remarks: str | None = None):
	"""System Manager: add (or with a negative number, remove) credits by hand."""
	frappe.only_for("System Manager")
	credits = cint(credits)
	if not credits:
		frappe.throw(_("Enter a non-zero number of credits."))
	return add(user, channel, credits, transaction_type="Admin Adjustment", remarks=remarks)


def has_free_access(user: str | None) -> bool:
	"""A System Manager let this user use everything without a card subscription."""
	if not user:
		return False
	return bool(cint(frappe.db.get_value("Message Credit Account", user, "free_access")))


@frappe.whitelist()
def grant_free_access(user: str, sms_credits: int = 0, whatsapp_credits: int = 0, note: str | None = None):
	"""System Manager: give a user full access without a card subscription, plus
	free SMS / WhatsApp credits (logged as Complimentary). Not offered anywhere
	on the public site."""
	frappe.only_for("System Manager")
	if not frappe.db.exists("User", user):
		frappe.throw(_("User {0} does not exist.").format(user))
	sms_credits, whatsapp_credits = cint(sms_credits), cint(whatsapp_credits)
	if sms_credits < 0 or whatsapp_credits < 0:
		frappe.throw(_("Credits can't be negative. Use Admin Adjustment to take credits away."))

	name = get_account(user)
	values = {"free_access": 1}
	if note:
		values["free_access_note"] = note
	frappe.db.set_value("Message Credit Account", name, values)
	remarks = note or _("Free access")
	for channel, credits in (("SMS", sms_credits), ("WhatsApp", whatsapp_credits)):
		if credits:
			add(user, channel, credits, transaction_type="Complimentary", remarks=remarks)
	return get_balances(user)


def _validate_channel(channel):
	if channel not in CHANNELS:
		frappe.throw(_("Unknown message channel: {0}").format(channel))
