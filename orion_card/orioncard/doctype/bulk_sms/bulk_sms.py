import frappe
import requests
from frappe.model.document import Document
from frappe.utils.password import get_decrypted_password


class BulkSms(Document):
	def send_sms(self, phone, message):
		provider = self.sms_provider
		if not provider:
			frappe.throw("Please configure an SMS provider in the SMS Settings tab.")

		api_key = get_decrypted_password("Bulk SMS", self.name, "sms_api_key") or ""
		sender_id = self.sms_sender_id or ""

		if provider == "RodSMS":
			return self._send_via_rodsms(phone, message, api_key, sender_id)
		elif provider == "Notify Africa":
			return self._send_via_notify_africa(phone, message, api_key, sender_id)
		elif provider == "Custom":
			return self._send_via_custom(phone, message, api_key, sender_id)
		else:
			frappe.throw(f"Unknown SMS provider: {provider}")

	def _send_via_rodsms(self, phone, message, api_key, sender_id):
		base_url = self.sms_base_url or "https://api.rodsms.com/sms/v1"
		resp = requests.post(
			f"{base_url}/send",
			json={"api_key": api_key, "sender_id": sender_id, "phone": phone, "message": message},
			timeout=30,
		)
		resp.raise_for_status()
		return resp.json()

	def _send_via_notify_africa(self, phone, message, api_key, sender_id):
		resp = requests.post(
			"https://app.notify.africa/api/send/message/token",
			json={
				"to": phone,
				"message": message,
				"sender_id": sender_id,
				"token": api_key,
			},
			timeout=30,
		)
		resp.raise_for_status()
		return resp.json()

	def _send_via_custom(self, phone, message, api_key, sender_id):
		if not self.sms_base_url:
			frappe.throw("API Base URL is required for Custom provider.")
		resp = requests.post(
			self.sms_base_url,
			json={"api_key": api_key, "sender_id": sender_id, "phone": phone, "message": message},
			timeout=30,
		)
		resp.raise_for_status()
		return resp.json()


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
		try:
			doc.send_sms(row.phone_no, doc.message)
			frappe.db.set_value("Bulk SMS Recipient", row.name, "sent", 1)
			sent_count += 1
		except Exception as e:
			errors.append(f"{row.recipient_name} ({row.phone_no}): {e}")

	frappe.db.commit()

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
