import frappe


def execute():
	"""SMS now goes through RodSMS (rodsms.com) by default. Notify Africa stays
	available as a provider choice; the Terms text names the new provider."""
	settings = frappe.get_single("OrionCard Settings")
	if settings.sms_provider != "RodSMS":
		frappe.db.set_single_value("OrionCard Settings", "sms_provider", "RodSMS")
	if not settings.rodsms_base_url:
		frappe.db.set_single_value("OrionCard Settings", "rodsms_base_url", "https://rodsms.com/api/v1")
	for field in ("terms_content_sw", "terms_content_en"):
		text = settings.get(field) or ""
		if "(Notify Africa, WaSenderAPI)" in text:
			frappe.db.set_single_value(
				"OrionCard Settings", field, text.replace("(Notify Africa, WaSenderAPI)", "(RodSMS, WaSenderAPI)")
			)
	frappe.db.commit()
