"""Delivery receipt (DLR) webhook for RodSMS.

Register in the RodSMS dashboard:
  https://<site>/api/method/orion_card.api.delivery_webhook.rodsms_dlr
"""

import frappe


def _normalize_status(raw: str) -> str:
	"""Map provider-specific status strings to our three canonical values."""
	raw = (raw or "").lower().strip()
	if raw in ("delivered", "success", "acceptd"):
		return "Delivered"
	if raw in ("failed", "undeliverable", "rejected", "expired", "unknown"):
		return "Failed"
	return "Unknown"


@frappe.whitelist(allow_guest=True)
def rodsms_dlr():
	"""Handle RodSMS delivery receipt callback.

	RodSMS sends a POST with JSON body:
	  {"message_id": "...", "status": "delivered|failed|...", ...}
	or as form fields. Both formats are handled.
	"""
	data = frappe.local.form_dict
	message_id = data.get("message_id") or data.get("messageId") or ""
	raw_status = data.get("status") or data.get("dlr_status") or ""

	if not message_id:
		frappe.response["http_status_code"] = 400
		return {"error": "missing message_id"}

	status = _normalize_status(raw_status)
	from orion_card.api.messaging import update_delivery_status
	update_delivery_status(str(message_id), status)
	return {"ok": True}


