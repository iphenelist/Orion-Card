import frappe
from frappe import _
from frappe.model.document import Document


class OrionCardSettings(Document):
	@property
	def webhook_url_preview(self):
		return frappe.utils.get_url("/api/method/orion_card.api.payments.payment_callback")

	def validate(self):
		if (self.price_per_card or 0) < 0:
			frappe.throw(_("Price per Card cannot be negative."))

	def on_update(self):
		frappe.clear_cache(doctype="OrionCard Settings")

	@frappe.whitelist()
	def send_test_sms(self):
		frappe.only_for("System Manager")
		from orion_card.api.sms import send_sms

		if not self.test_sms_phone:
			frappe.throw(_("Enter a test phone number first."))
		return send_sms(self.test_sms_phone, "OrionCard: test SMS / Ujumbe wa majaribio.")

	@frappe.whitelist()
	def check_sms_balance(self):
		frappe.only_for("System Manager")
		from orion_card.api.sms import rodsms_account_status

		return rodsms_account_status()

	@frappe.whitelist()
	def send_test_whatsapp(self):
		frappe.only_for("System Manager")
		from orion_card.api.whatsapp import send_text

		if not self.test_whatsapp_phone:
			frappe.throw(_("Enter a test phone number first."))
		return send_text(self.test_whatsapp_phone, "OrionCard: test WhatsApp / Ujumbe wa majaribio.")

	@frappe.whitelist()
	def reset_legal_text(self):
		frappe.only_for("System Manager")
		from orion_card.legal import set_default_legal_text

		set_default_legal_text(self)
		self.save()
		return True
