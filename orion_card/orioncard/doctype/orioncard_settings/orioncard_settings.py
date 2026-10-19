import frappe
from frappe import _
from frappe.model.document import Document


class OrionCardSettings(Document):
	@property
	def webhook_url_preview(self):
		return frappe.utils.get_url("/api/method/orion_card.api.payments.payment_callback")

	def validate(self):
		self._validate_packages()
		self._validate_card_price_tiers()
		for field in ("sms_credit_price", "whatsapp_credit_price", "price_per_guest_card"):
			if (self.get(field) or 0) < 0:
				frappe.throw(_("{0} cannot be negative.").format(self.meta.get_label(field)))

	def on_update(self):
		frappe.clear_cache(doctype="OrionCard Settings")

	def _validate_card_price_tiers(self):
		from orion_card.utils.pricing import validate_tiers

		if not self.card_price_tiers:
			return
		for warning in validate_tiers(self.card_price_tiers, self.sms_credit_price, self.whatsapp_credit_price):
			frappe.msgprint(warning, title=_("Check card pricing"), indicator="orange")

	def _validate_packages(self):
		seen = set()
		for row in self.credit_packages:
			if row.credits <= 0:
				frappe.throw(_("Row {0}: package credits must be more than 0.").format(row.idx))
			key = (row.channel, row.label.strip().lower())
			if key in seen:
				frappe.throw(_("Row {0}: duplicate {1} package '{2}'.").format(row.idx, row.channel, row.label))
			seen.add(key)

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
