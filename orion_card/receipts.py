"""Payment receipts for card subscriptions and credit purchases.

When a payment is confirmed the customer gets a PDF receipt by WhatsApp (and
email when an outgoing account is set up). Receipts are system messages:
they never use the customer's credits.

WhatsApp can attach the PDF only when WaSenderAPI's servers can download it,
i.e. the site has a public address; on a local/dev site the message carries
the receipt link instead.
"""

import ipaddress
from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.utils import cint, flt, fmt_money, formatdate, get_url, now_datetime

from orion_card.permissions import is_staff

RECEIPT_DOCTYPES = ("Occasion Subscription", "Credit Purchase")


# ---------------------------------------------------------------- content


def receipt_context(doc) -> dict:
	settings = frappe.get_cached_doc("OrionCard Settings")
	currency = settings.currency or "TZS"
	user = frappe.db.get_value("User", doc.user, ["full_name", "email", "mobile_no"], as_dict=True) if doc.user else None

	ctx = {
		"receipt_no": f"RC-{doc.name}",
		"receipt_date": formatdate(doc.get("paid_at") or doc.modified, "dd-MM-yyyy"),
		"business_name": settings.business_legal_name or "OrionCard",
		"business_address": settings.business_address,
		"support_phone": settings.support_phone,
		"support_email": settings.support_email,
		"terms_url": get_url("/terms"),
		"money": lambda value: fmt_money(flt(value), precision=0, currency=currency),
		"occasion": None,
		"included": None,
		"payment_reference": None,
	}

	if doc.doctype == "Occasion Subscription":
		lines = frappe.parse_json(doc.price_lines or "[]") or []
		items = [
			{
				"description": _("Kadi za mwaliko / Invitation cards"),
				"detail": _("Kadi {0}–{1} / Cards {0}–{1}").format(line["from_card"], line["to_card"]),
				"qty": cint(line["cards"]),
				"rate": flt(line["price_per_card"]),
				"amount": cint(line["cards"]) * flt(line["price_per_card"]),
			}
			for line in lines
		] or [{
			"description": _("Kadi za mwaliko / Invitation cards"),
			"detail": None,
			"qty": cint(doc.number_of_guests),
			"rate": flt(doc.subscription_price) / max(cint(doc.number_of_guests), 1),
			"amount": flt(doc.subscription_price),
		}]
		ctx.update(
			customer_name=doc.applicant_name or (user and user.full_name),
			customer_email=doc.email or (user and user.email),
			customer_phone=doc.phone or (user and user.mobile_no),
			occasion=frappe.db.get_value("Occasion", doc.occasion, "occasion_name") if doc.occasion else None,
			items=items,
			total=flt(doc.subscription_price),
			payment_method=doc.get("payment_method") or _("Imethibitishwa na msimamizi / Confirmed by admin"),
			payment_reference=doc.get("payment_reference"),
			included=_("SMS {0} + WhatsApp {1} credits").format(
				cint(doc.sms_credits_included), cint(doc.whatsapp_credits_included)
			),
		)
	else:
		ctx.update(
			customer_name=(user and user.full_name) or doc.user,
			customer_email=user and user.email,
			customer_phone=doc.phone or (user and user.mobile_no),
			items=[{
				"description": _("{0} credits").format(doc.channel),
				"detail": doc.package if doc.package and doc.package != "Custom" else None,
				"qty": cint(doc.credits),
				"rate": flt(doc.unit_price),
				"amount": flt(doc.amount),
			}],
			total=flt(doc.amount),
			payment_method=_("Pesa ya simu (Abliner)") if doc.gateway == "Abliner" else _("Malipo yaliyothibitishwa / Confirmed payment"),
			payment_reference=doc.gateway_reference,
		)
	return ctx


def render_receipt_html(doc) -> str:
	return frappe.render_template("orion_card/templates/receipts/receipt.html", receipt_context(doc))


def make_receipt_pdf(doc) -> str:
	"""Create (or replace) the receipt PDF and return its file URL."""
	from frappe.utils.pdf import get_pdf

	pdf = get_pdf(render_receipt_html(doc), {"page-size": "A5", "margin-top": "0", "margin-bottom": "0",
											 "margin-left": "0", "margin-right": "0"})
	for old in frappe.get_all("File", filters={"attached_to_doctype": doc.doctype, "attached_to_name": doc.name,
												"file_name": ["like", "receipt-%"]}, pluck="name"):
		frappe.delete_doc("File", old, ignore_permissions=True, force=True)
	# Public so WhatsApp can fetch it; the random part keeps the link unguessable.
	file_doc = frappe.get_doc({
		"doctype": "File",
		"file_name": f"receipt-{doc.name}-{frappe.generate_hash(length=12)}.pdf",
		"content": pdf,
		"is_private": 0,
		"attached_to_doctype": doc.doctype,
		"attached_to_name": doc.name,
	}).insert(ignore_permissions=True)
	doc.db_set("receipt_url", file_doc.file_url, update_modified=False)
	return file_doc.file_url


# ---------------------------------------------------------------- delivery


def is_public_url(url: str) -> bool:
	host = (urlparse(url).hostname or "").lower()
	if not host or host == "localhost" or host.endswith(".local") or "." not in host:
		return False
	try:
		ip = ipaddress.ip_address(host)
		return not (ip.is_private or ip.is_loopback or ip.is_link_local)
	except ValueError:
		return True


def receipt_message(ctx: dict, link: str) -> str:
	lines = [
		f"Habari {ctx['customer_name']},",
		"Asante! Malipo yako yamepokelewa. / Thank you, your payment was received.",
		"",
		f"Risiti: {ctx['receipt_no']}",
		f"Tarehe: {ctx['receipt_date']}",
	]
	if ctx.get("occasion"):
		lines.append(f"Tukio: {ctx['occasion']}")
	for item in ctx["items"]:
		lines.append(f"{item['description']}: {item['qty']:,} x {ctx['money'](item['rate'])}")
	lines.append(f"Jumla: {ctx['money'](ctx['total'])}")
	if ctx.get("included"):
		lines.append(f"Imejumuisha: {ctx['included']}")
	lines += ["", f"Pakua risiti (PDF): {link}", "", f"— {ctx['business_name']}"]
	return "\n".join(lines)


def send_receipt(doctype: str, name: str) -> dict:
	"""Generate the receipt and send it by WhatsApp and email. Never raises:
	a delivery problem must not undo the payment it confirms."""
	result = {"whatsapp": False, "email": False, "url": None}
	try:
		doc = frappe.get_doc(doctype, name)
		file_url = make_receipt_pdf(doc)
		link = get_url(file_url)
		result["url"] = link
		ctx = receipt_context(doc)
		message = receipt_message(ctx, link)

		if ctx.get("customer_phone"):
			result["whatsapp"] = _send_whatsapp(ctx["customer_phone"], message, link, file_url)
		if ctx.get("customer_email"):
			result["email"] = _send_email(doc, ctx, message, file_url)

		doc.db_set("receipt_sent_at", now_datetime(), update_modified=False)
		doc.add_comment("Info", _("Receipt sent — WhatsApp: {0}, email: {1}. {2}").format(
			_("yes") if result["whatsapp"] else _("no"), _("yes") if result["email"] else _("no"), link))
	except Exception:
		frappe.log_error(title=f"OrionCard receipt failed: {doctype} {name}", message=frappe.get_traceback())
	return result


def _send_whatsapp(phone, message, link, file_url) -> bool:
	from orion_card.api.messaging import channel_enabled
	from orion_card.api.whatsapp import send_document, send_text

	if not channel_enabled("WhatsApp"):
		return False
	try:
		if is_public_url(link):
			send_document(phone, link, file_url.rsplit("/", 1)[-1], caption=message)
		else:
			send_text(phone, message)
		return True
	except Exception:
		frappe.log_error(title="OrionCard receipt WhatsApp failed", message=frappe.get_traceback())
		return False


def _send_email(doc, ctx, message, file_url) -> bool:
	try:
		file_doc = frappe.get_doc("File", {"file_url": file_url})
		frappe.sendmail(
			recipients=[ctx["customer_email"]],
			subject=_("Risiti {0} — OrionCard").format(ctx["receipt_no"]),
			message=message.replace("\n", "<br>"),
			attachments=[{"fname": file_doc.file_name, "fcontent": file_doc.get_content()}],
			reference_doctype=doc.doctype,
			reference_name=doc.name,
		)
		return True
	except Exception:
		frappe.log_error(title="OrionCard receipt email failed", message=frappe.get_traceback())
		return False


def queue_receipt(doctype: str, name: str):
	"""Send after the payment is committed, in the background."""
	if frappe.flags.in_test or frappe.flags.in_migrate or frappe.flags.in_patch:
		return
	frappe.enqueue(
		"orion_card.receipts.send_receipt",
		queue="short",
		enqueue_after_commit=True,
		doctype=doctype,
		name=name,
	)


# ---------------------------------------------------------------- desk / portal actions


@frappe.whitelist()
def resend_receipt(doctype: str, name: str) -> dict:
	if doctype not in RECEIPT_DOCTYPES:
		frappe.throw(_("Receipts are only available for card subscriptions and credit purchases."))
	frappe.only_for("System Manager")
	_assert_paid(frappe.get_doc(doctype, name))
	return send_receipt(doctype, name)


@frappe.whitelist()
def download_receipt(doctype: str, name: str):
	"""Stream the receipt PDF to its owner (or staff)."""
	from frappe.utils.pdf import get_pdf

	if doctype not in RECEIPT_DOCTYPES:
		frappe.throw(_("Receipts are only available for card subscriptions and credit purchases."))
	doc = frappe.get_doc(doctype, name)
	# Occasion Managers have no Desk access to these doctypes, so check
	# ownership directly instead of doc.check_permission().
	if doc.user != frappe.session.user and not is_staff():
		raise frappe.PermissionError
	_assert_paid(doc)
	frappe.local.response.filename = f"receipt-{doc.name}.pdf"
	frappe.local.response.filecontent = get_pdf(render_receipt_html(doc), {"page-size": "A5"})
	frappe.local.response.type = "pdf"


def _assert_paid(doc):
	paid = doc.docstatus == 1 if doc.doctype == "Occasion Subscription" else doc.status == "Paid"
	if not paid:
		frappe.throw(_("A receipt is only available once the payment is confirmed."))
