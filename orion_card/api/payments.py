"""Buying SMS / WhatsApp credits through the Abliner mobile-money gateway.

Same protocol as bandofy's hotspot payments (apps/bandofy/bandofy/api.py),
copied rather than imported so orion_card doesn't depend on bandofy:
  - POST {base_url}/deposits  -> STK push to the buyer's phone
  - webhook payment_callback  -> transaction.completed / transaction.failed
  - sync_pending_purchases    -> polls {base_url}/transactions when a webhook is missed
"""

import hashlib
import hmac
import json
import time

import frappe
import requests
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import add_to_date, cint, flt, get_url, now_datetime

from orion_card.utils import credits

DEFAULT_GATEWAY_BASE_URL = "https://abliner.net/api/v1"
WEBHOOK_MAX_AGE_SECONDS = 300  # Abliner: reject webhook timestamps older than 5 minutes
PAYMENT_POLL_GRACE_SECONDS = 90  # give the webhook this long to arrive before polling
PAYMENT_POLL_MAX_AGE_MINUTES = 60  # purchases still Pending after this are given up on


# ---------------------------------------------------------------- catalogue


def get_catalogue() -> dict:
	"""Prices and packages for the Buy Credits page."""
	settings = frappe.get_cached_doc("OrionCard Settings")
	prices = {"SMS": flt(settings.sms_credit_price), "WhatsApp": flt(settings.whatsapp_credit_price)}
	packages = {"SMS": [], "WhatsApp": []}
	for row in settings.credit_packages:
		if row.enabled and row.channel in packages:
			packages[row.channel].append({
				"label": row.label,
				"credits": cint(row.credits),
				"amount": cint(row.credits) * prices[row.channel],
			})
	for rows in packages.values():
		rows.sort(key=lambda r: r["credits"])
	return {
		"currency": settings.currency or "TZS",
		"prices": prices,
		"packages": packages,
		"min_custom": max(cint(settings.min_custom_credits) or 10, 1),
		"online_payment": bool(cint(settings.payment_enabled)) and bool(_api_key(settings)),
		"manual_instructions": settings.manual_payment_instructions or "",
	}


@frappe.whitelist()
def get_credit_page_data() -> dict:
	_require_login()
	data = get_catalogue()
	data["balances"] = credits.get_balances(frappe.session.user)
	data["phone"] = frappe.db.get_value("User", frappe.session.user, "mobile_no") or ""
	data["recent_purchases"] = frappe.get_all(
		"Credit Purchase",
		filters={"user": frappe.session.user},
		fields=["name", "channel", "credits", "amount", "status", "receipt_url"],
		order_by="creation desc",
		limit=5,
	)
	return data


# ---------------------------------------------------------------- purchase


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=60 * 10)
def create_purchase(channel: str, credit_count: int, phone: str | None = None, accept_terms=None,
					package: str | None = None) -> dict:
	"""Create a Pending Credit Purchase and, when online payment is on, push the STK prompt."""
	from orion_card.legal import assert_terms_accepted, record_acceptance

	_require_login()
	if not cint(accept_terms):
		frappe.throw(_("Tafadhali kubali masharti ya ununuzi wa credits. / Please accept the credit purchase terms."))
	assert_terms_accepted()

	if channel not in credits.CHANNELS:
		frappe.throw(_("Choose SMS or WhatsApp credits."))
	catalogue = get_catalogue()
	credit_count = cint(credit_count)
	package_labels = {p["label"]: p["credits"] for p in catalogue["packages"][channel]}
	if package and package_labels.get(package) != credit_count:
		package = None  # quantity was edited after picking a package: treat as custom
	if credit_count < catalogue["min_custom"] and not package:
		frappe.throw(_("The minimum is {0} credits.").format(catalogue["min_custom"]))
	if credit_count > 1_000_000:
		frappe.throw(_("That quantity is too large. Contact support for bulk credits."))

	unit_price = catalogue["prices"][channel]
	amount = credit_count * unit_price
	if amount <= 0:
		frappe.throw(_("Credit prices are not set yet. Contact the administrator."))

	online = catalogue["online_payment"]
	if online and not phone:
		frappe.throw(_("Enter the mobile money number to pay with."))

	purchase = frappe.get_doc({
		"doctype": "Credit Purchase",
		"user": frappe.session.user,
		"channel": channel,
		"package": package or _("Custom"),
		"credits": credit_count,
		"unit_price": unit_price,
		"amount": amount,
		"phone": phone,
		"status": "Pending",
		"gateway": "Abliner" if online else "Manual",
	})
	purchase.insert(ignore_permissions=True)
	record_acceptance(frappe.session.user, "Credit Purchase")
	frappe.db.commit()  # nosemgrep — the purchase must exist before the gateway calls back

	if not online:
		return {
			"purchase": purchase.name,
			"status": "Pending",
			"manual": True,
			"message": catalogue["manual_instructions"]
			or _("Payment instructions will be shared by the administrator."),
		}

	try:
		reference = trigger_stk_push(phone, amount, purchase.name)
	except Exception as e:
		frappe.log_error(title=f"OrionCard credit STK push failed: {purchase.name}", message=frappe.get_traceback())
		purchase.db_set({"status": "Failed", "gateway_message": str(e)[:500]}, commit=True)
		frappe.throw(_("Could not reach the payment gateway. Please try again in a moment."))

	if reference:
		purchase.db_set("gateway_reference", reference, commit=True)
	return {
		"purchase": purchase.name,
		"status": "Pending",
		"manual": False,
		"message": _("Angalia simu yako uweke PIN kukamilisha malipo. / Check your phone and enter your PIN to pay."),
	}


@frappe.whitelist()
def get_purchase_status(purchase: str) -> dict:
	_require_login()
	row = frappe.db.get_value(
		"Credit Purchase", purchase, ["user", "status", "channel", "credits"], as_dict=True
	)
	if not row or (row.user != frappe.session.user and "System Manager" not in frappe.get_roles()):
		frappe.throw(_("Purchase not found."), frappe.DoesNotExistError)
	return {"status": row.status, "channel": row.channel, "credits": row.credits,
			"balances": credits.get_balances(row.user)}


# ---------------------------------------------------------------- Abliner


def trigger_stk_push(phone, amount, purchase_name) -> str | None:
	settings = frappe.get_single("OrionCard Settings")
	api_key = _api_key(settings)
	base_url = _gateway_base_url(settings)
	timeout = max(5, min(cint(settings.request_timeout or 30), 120))
	currency = (settings.currency or "TZS").strip().upper()

	# Abliner echoes `reference` back as `customer_reference` on the deposit,
	# the webhook and the transactions lookup — that's how we find the purchase.
	body = json.dumps(
		{
			"amount": round(flt(amount)),
			"method": "mobile",
			"currency": currency,
			"phone": phone,
			"reference": purchase_name,
			"callback_url": get_url("/api/method/orion_card.api.payments.payment_callback"),
		},
		separators=(",", ":"),
	)
	headers = {
		"Authorization": f"Bearer {api_key}",
		"Content-Type": "application/json",
		"Idempotency-Key": purchase_name,
	}
	signing_secret = _webhook_secret(settings)
	if signing_secret:
		timestamp = str(int(time.time()))
		headers["x-abliner-timestamp"] = timestamp
		headers["x-abliner-signature"] = hmac.new(
			signing_secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256
		).hexdigest()

	response = requests.post(f"{base_url}/deposits", headers=headers, data=body, timeout=timeout)
	try:
		result = response.json() or {}
	except ValueError:
		result = {}
	if not response.ok or result.get("status") == "error":
		raise Exception(
			f"Abliner deposit failed (HTTP {response.status_code}): "
			f"{result.get('code') or ''} {result.get('message') or response.text[:500]}"
		)
	return (result.get("data") or {}).get("id")


@frappe.whitelist(allow_guest=True, methods=["POST"])
def payment_callback():
	"""Abliner webhook. Verifies the signature, then marks the purchase Paid
	(adding credits once) or Failed. Duplicate deliveries are no-ops."""
	settings = frappe.get_single("OrionCard Settings")
	raw_body = frappe.request.get_data(as_text=True) or ""
	webhook_secret = _webhook_secret(settings)
	if not webhook_secret:
		# Without a secret anyone could forge "completed" events — refuse.
		frappe.local.response["http_status_code"] = 503
		return {"status": "error", "message": "Webhook secret not configured"}
	if not _verify_webhook_signature(webhook_secret, raw_body):
		frappe.local.response["http_status_code"] = 401
		return {"status": "error", "message": "Invalid webhook signature"}

	try:
		payload = json.loads(raw_body) if raw_body else {}
	except json.JSONDecodeError:
		frappe.local.response["http_status_code"] = 400
		return {"status": "error", "message": "Invalid JSON payload"}

	event_type = str(payload.get("event") or "").strip().lower()
	data = payload.get("data") or {}
	reference = str(data.get("customer_reference") or "").strip()
	reference_id = str(data.get("id") or "").strip()
	gateway_status = str(data.get("status") or "").strip().lower()

	doctype, name = _find_payment_target(reference, reference_id)
	if not name:
		frappe.log_error(title="OrionCard payment callback: payment not found", message=frappe.as_json(payload))
		frappe.local.response["http_status_code"] = 404
		return {"status": "error", "message": "Purchase not found"}

	paid_amount = data.get("amount")
	if doctype == "Occasion Subscription":
		return _resolve_subscription(name, event_type, gateway_status, reference_id)
	return _resolve(name, event_type, gateway_status, reference_id, paid_amount)


# Things a customer can pay for through Abliner: the push's `reference` is the
# document name, which the webhook echoes back as `customer_reference`.
PAYABLE_DOCTYPES = ("Credit Purchase", "Occasion Subscription")


def _find_payment_target(reference: str, gateway_id: str) -> tuple:
	for doctype in PAYABLE_DOCTYPES:
		if reference and frappe.db.exists(doctype, reference):
			return doctype, reference
	if gateway_id:
		for doctype in PAYABLE_DOCTYPES:
			name = frappe.db.get_value(doctype, {"gateway_reference": gateway_id})
			if name:
				return doctype, name
	return None, None


def _resolve(name, event_type, gateway_status, reference_id, paid_amount=None) -> dict:
	status = frappe.db.get_value("Credit Purchase", name, "status")
	if status != "Pending":
		return {"status": "ok", "message": "Already processed"}

	if event_type == "transaction.completed" or gateway_status == "completed":
		# The STK push amount is set server-side, so the buyer can't change it;
		# a different reported amount (e.g. net of fees) is only flagged.
		expected = flt(frappe.db.get_value("Credit Purchase", name, "amount"))
		if paid_amount is not None and abs(flt(paid_amount) - expected) >= 1:
			frappe.db.set_value(
				"Credit Purchase", name, "gateway_message", f"Gateway reported {paid_amount}, expected {expected}"
			)
		if reference_id:
			frappe.db.set_value("Credit Purchase", name, "gateway_reference", reference_id)
		credits.credit_purchase(name)
		frappe.db.commit()  # nosemgrep
		return {"status": "success"}

	if event_type == "transaction.failed" or gateway_status == "failed":
		frappe.db.set_value("Credit Purchase", name, "status", "Failed")
		frappe.db.commit()  # nosemgrep
		return {"status": "failed"}

	return {"status": "pending"}


def _resolve_subscription(name, event_type, gateway_status, reference_id) -> dict:
	"""A paid card subscription approves itself: submitting it adds the
	included credits, unlocks card sending and sends the receipt."""
	sub = frappe.get_doc("Occasion Subscription", name)
	if sub.payment_status != "Pending" or sub.docstatus != 0:
		return {"status": "ok", "message": "Already processed"}

	if event_type == "transaction.completed" or gateway_status == "completed":
		sub.payment_status = "Paid"
		sub.payment_method = "Mobile Money (Abliner)"
		sub.payment_reference = reference_id or sub.gateway_reference
		if reference_id:
			sub.gateway_reference = reference_id
		sub.flags.ignore_permissions = True
		sub.submit()
		frappe.db.commit()  # nosemgrep
		return {"status": "success"}

	if event_type == "transaction.failed" or gateway_status == "failed":
		sub.db_set("payment_status", "Failed")
		frappe.db.commit()  # nosemgrep
		return {"status": "failed"}

	return {"status": "pending"}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=10, seconds=60 * 10)
def pay_subscription(subscription: str, phone: str | None = None, accept_terms=None) -> dict:
	"""Pay a card subscription request: push the mobile-money PIN prompt
	(or return the manual instructions when online payment is off)."""
	from orion_card.legal import assert_terms_accepted, record_acceptance

	_require_login()
	sub = frappe.get_doc("Occasion Subscription", subscription)
	if sub.user != frappe.session.user and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Subscription not found."), frappe.DoesNotExistError)
	if sub.docstatus != 0:
		frappe.throw(_("This subscription is already paid."))
	if not cint(accept_terms):
		frappe.throw(_("Tafadhali kubali Vigezo na Masharti. / Please accept the Terms & Conditions."))
	assert_terms_accepted()
	record_acceptance(frappe.session.user, "Card Payment")

	catalogue = get_catalogue()
	if not catalogue["online_payment"]:
		frappe.db.commit()  # nosemgrep
		return {
			"status": "Pending",
			"manual": True,
			"message": catalogue["manual_instructions"]
			or _("Payment instructions will be shared by the administrator."),
		}
	if not phone:
		frappe.throw(_("Enter the mobile money number to pay with."))

	sub.db_set({"payment_status": "Pending", "paying_phone": phone})
	frappe.db.commit()  # nosemgrep — must exist before the gateway calls back
	try:
		reference = trigger_stk_push(phone, sub.subscription_price, sub.name)
	except Exception:
		frappe.log_error(title=f"OrionCard card payment STK push failed: {sub.name}", message=frappe.get_traceback())
		sub.db_set("payment_status", "Failed", commit=True)
		frappe.throw(_("Could not reach the payment gateway. Please try again in a moment."))
	if reference:
		sub.db_set("gateway_reference", reference, commit=True)
	return {
		"status": "Pending",
		"manual": False,
		"message": _("Angalia simu yako uweke PIN kukamilisha malipo. / Check your phone and enter your PIN to pay."),
	}


@frappe.whitelist()
def get_subscription_payment_status(subscription: str) -> dict:
	_require_login()
	row = frappe.db.get_value(
		"Occasion Subscription", subscription, ["user", "docstatus", "payment_status", "receipt_url"], as_dict=True
	)
	if not row or (row.user != frappe.session.user and "System Manager" not in frappe.get_roles()):
		frappe.throw(_("Subscription not found."), frappe.DoesNotExistError)
	return {"paid": row.docstatus == 1, "payment_status": row.payment_status, "receipt_url": row.receipt_url}


def sync_pending_purchases():
	"""Every 5 minutes: ask Abliner about purchases the webhook didn't resolve."""
	settings = frappe.get_single("OrionCard Settings")
	api_key = _api_key(settings)
	if not cint(settings.payment_enabled) or not cint(settings.poll_pending_payments) or not api_key:
		return

	cutoff_recent = add_to_date(now_datetime(), seconds=-PAYMENT_POLL_GRACE_SECONDS)
	cutoff_old = add_to_date(now_datetime(), minutes=-PAYMENT_POLL_MAX_AGE_MINUTES)
	pending = frappe.get_all(
		"Credit Purchase",
		filters={"status": "Pending", "gateway": "Abliner", "creation": ["<=", cutoff_recent]},
		fields=["name", "gateway_reference", "creation"],
		limit_page_length=200,
	)
	base_url = _gateway_base_url(settings)
	timeout = max(5, min(cint(settings.request_timeout or 30), 120))

	for row in pending:
		params = {"id": row.gateway_reference} if row.gateway_reference else {"customer_reference": row.name}
		try:
			response = requests.get(
				f"{base_url}/transactions",
				headers={"Authorization": f"Bearer {api_key}"},
				params=params,
				timeout=timeout,
			)
			response.raise_for_status()
			matches = (response.json() or {}).get("data") or []
			match = matches[0] if matches else {}
			gateway_status = str(match.get("status") or "").strip().lower()
			reference_id = row.gateway_reference or str(match.get("id") or "")
		except Exception:
			frappe.log_error(title=f"OrionCard payment poll failed: {row.name}", message=frappe.get_traceback())
			continue

		if gateway_status in ("completed", "failed"):
			_resolve(row.name, "", gateway_status, reference_id, match.get("amount"))
		elif row.creation <= cutoff_old:
			frappe.db.set_value("Credit Purchase", row.name, {
				"status": "Failed", "gateway_message": "No confirmation from the gateway within 60 minutes",
			})

	# Card subscriptions waiting for their mobile-money payment.
	for row in frappe.get_all(
		"Occasion Subscription",
		filters={"payment_status": "Pending", "docstatus": 0, "modified": ["<=", cutoff_recent]},
		fields=["name", "gateway_reference", "modified"],
		limit_page_length=200,
	):
		params = {"id": row.gateway_reference} if row.gateway_reference else {"customer_reference": row.name}
		try:
			response = requests.get(
				f"{base_url}/transactions",
				headers={"Authorization": f"Bearer {api_key}"},
				params=params,
				timeout=timeout,
			)
			response.raise_for_status()
			matches = (response.json() or {}).get("data") or []
			match = matches[0] if matches else {}
			gateway_status = str(match.get("status") or "").strip().lower()
		except Exception:
			frappe.log_error(title=f"OrionCard card payment poll failed: {row.name}", message=frappe.get_traceback())
			continue
		if gateway_status in ("completed", "failed"):
			_resolve_subscription(row.name, "", gateway_status, row.gateway_reference or str(match.get("id") or ""))
		elif row.modified <= cutoff_old:
			frappe.db.set_value("Occasion Subscription", row.name, "payment_status", "Failed")
	frappe.db.commit()  # nosemgrep


# ---------------------------------------------------------------- helpers


def _require_login():
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in first."), frappe.PermissionError)


def _api_key(settings) -> str:
	return (settings.get_password("abliner_api_key", raise_exception=False) or "").strip()


def _webhook_secret(settings) -> str:
	return (settings.get_password("abliner_webhook_secret", raise_exception=False) or "").strip()


def _gateway_base_url(settings) -> str:
	return (settings.base_url or DEFAULT_GATEWAY_BASE_URL).strip().rstrip("/")


def _verify_webhook_signature(webhook_secret, raw_body) -> bool:
	"""Abliner signs webhooks as hex HMAC-SHA256 of "<timestamp>.<raw body>"."""
	signature = (frappe.get_request_header("X-Webhook-Signature") or "").strip()
	timestamp = (frappe.get_request_header("X-Webhook-Timestamp") or "").strip()
	if not (signature and timestamp.isdigit()):
		return False
	if abs(time.time() - int(timestamp)) > WEBHOOK_MAX_AGE_SECONDS:
		return False
	expected = hmac.new(webhook_secret.encode(), f"{timestamp}.{raw_body}".encode(), hashlib.sha256).hexdigest()
	return hmac.compare_digest(expected, signature)
