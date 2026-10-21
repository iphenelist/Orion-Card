import frappe


def execute():
	"""Every message is now sent by hand, and each guest gets at most 2
	invitations and 3 contribution reminders per channel (SMS and WhatsApp)."""
	from orion_card.install import set_message_limits
	from orion_card.utils.invites import LIMIT_FIELDS

	settings = frappe.get_single("OrionCard Settings")
	set_message_limits(settings)
	for field in LIMIT_FIELDS.values():
		frappe.db.set_single_value("OrionCard Settings", field, settings.get(field))
	frappe.db.commit()
