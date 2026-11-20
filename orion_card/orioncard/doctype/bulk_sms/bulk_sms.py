import time

import frappe
import httpx
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password

from orion_card.api.sms import RODSMS_DEFAULT_BASE_URL, RODSMS_ERRORS
from orion_card.utils.phone import normalize_phone

SEND_DELAY = 0.5  # seconds between sends to avoid rate-limiting
MAX_RETRIES = 2


class BulkSMS(Document):
	def send_sms(self, phone, message):
		api_key = (get_decrypted_password("Bulk SMS", self.name, "sms_api_key") or "").strip()
		sender_id = (self.sms_sender_id or "").strip()

		if not api_key:
			frappe.throw("API Key is not set in the SMS Settings tab.")
		if not sender_id:
			frappe.throw("Sender ID is not set in the SMS Settings tab.")

		recipient = normalize_phone(phone)
		if len(recipient) < 10:
			frappe.throw(f"Invalid phone number '{phone}'.")

		base_url = (self.sms_base_url or RODSMS_DEFAULT_BASE_URL).rstrip("/")

		try:
			with httpx.Client(http2=True, timeout=30) as client:
				resp = client.post(
					f"{base_url}/messages",
					headers={
						"Authorization": f"Bearer {api_key}",
						"Accept": "application/json",
					},
					json={"recipient": recipient, "sender_id": sender_id, "message": message},
				)
		except httpx.RequestError as e:
			frappe.log_error(title="Bulk SMS - RodSMS unreachable", message=frappe.get_traceback())
			frappe.throw(
				f"Could not reach RodSMS: server closed the connection or did not respond. "
				f"Check your internet connection or try again later. ({type(e).__name__})",
				title="RodSMS unreachable",
			)

		try:
			result = resp.json() or {}
		except ValueError:
			result = {}

		if not resp.is_success or not result.get("success"):
			error = result.get("error") or {}
			code = error.get("code") or str(resp.status_code)
			detail = error.get("message") or resp.text[:300]
			hint = RODSMS_ERRORS.get(code, "RodSMS request failed.")
			frappe.throw(f"{hint} ({code}: {detail})")

		return result.get("data") or {}


@frappe.whitelist()
def send_to_recipient(docname, row_name):
	"""Send SMS to a single recipient row."""
	doc = frappe.get_doc("Bulk SMS", docname)
	if not doc.message:
		frappe.throw("Please write a message before sending.")

	for row in doc.recipients:
		if row.name == row_name:
			try:
				doc.send_sms(row.phone_no, doc.message)
				frappe.db.set_value("Bulk SMS Recipient", row_name, "sent", 1)
				frappe.db.commit()
				return {"status": "success", "phone": row.phone_no}
			except Exception as e:
				frappe.log_error(frappe.get_traceback(), "Bulk SMS - Send to Recipient")
				frappe.throw(str(e))

	frappe.throw(f"Recipient {row_name} not found in this document.")


@frappe.whitelist()
def send_bulk(docname):
	"""Send SMS to all unsent recipients."""
	doc = frappe.get_doc("Bulk SMS", docname)
	if not doc.message:
		frappe.throw("Please write a message before sending.")

	sent_count = 0
	errors = []
	for row in doc.recipients:
		if row.sent:
			continue
		last_exc = None
		for attempt in range(1, MAX_RETRIES + 2):
			try:
				doc.send_sms(row.phone_no, doc.message)
				frappe.db.set_value("Bulk SMS Recipient", row.name, "sent", 1)
				frappe.db.commit()
				sent_count += 1
				last_exc = None
				break
			except (httpx.RequestError) as e:
				last_exc = e
				if attempt <= MAX_RETRIES:
					time.sleep(attempt * SEND_DELAY)
			except Exception as e:
				last_exc = e
				break
		if last_exc:
			errors.append(f"{row.recipient_name} ({row.phone_no}): {last_exc}")
		time.sleep(SEND_DELAY)

	if errors:
		return {"status": "partial", "sent": sent_count, "errors": errors}
	return {"status": "success", "sent": sent_count}


@frappe.whitelist()
def send_test(docname):
	"""Send a test SMS to the test phone number."""
	doc = frappe.get_doc("Bulk SMS", docname)
	if not doc.test_phone:
		frappe.throw("Please enter a test phone number in the SMS Settings tab.")
	if not doc.message:
		frappe.throw("Please write a message before sending.")
	try:
		doc.send_sms(doc.test_phone, doc.message)
		return {"status": "success", "phone": doc.test_phone}
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), "Bulk SMS - Test Send")
		frappe.throw(str(e))
