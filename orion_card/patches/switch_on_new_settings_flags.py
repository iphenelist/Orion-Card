import frappe


def execute():
	"""create_occasion_manager_role saved the new on-by-default Check fields
	(SMS/WhatsApp sending, credit billing, payment polling, re-acceptance) as 0,
	which would have switched off all sending. Turn them on once."""
	from orion_card.install import ON_BY_DEFAULT

	for field in ON_BY_DEFAULT:
		frappe.db.set_single_value("OrionCard Settings", field, 1)
	frappe.db.commit()
