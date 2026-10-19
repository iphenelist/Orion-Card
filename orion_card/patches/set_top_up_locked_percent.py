import frappe


def execute():
	"""Extra guests added later keep the customer's earlier card rate for at
	most 20% of the cards already paid (see orion_card.utils.pricing)."""
	from orion_card.install import _saved_before

	if not _saved_before("top_up_locked_percent"):
		frappe.db.set_single_value("OrionCard Settings", "top_up_locked_percent", 20)
		frappe.db.commit()
