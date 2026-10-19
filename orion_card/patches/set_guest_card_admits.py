import frappe

from orion_card.orioncard.doctype.occasion.occasion import card_admits


def execute():
	"""DOUBLE and TABLE cards now let in more than one person at the gate:
	fill in how many people each existing card admits, and count guests who
	already checked in as one person entered."""
	if not frappe.db.table_exists("Occasion Guest"):
		return
	frappe.db.sql("update `tabOccasion` set table_size = 10 where ifnull(table_size, 0) = 0")
	table_sizes = dict(frappe.get_all("Occasion", fields=["name", "table_size"], as_list=True))
	for guest in frappe.get_all("Occasion Guest", fields=["name", "parent", "card_type", "admits", "checked_in"]):
		frappe.db.set_value("Occasion Guest", guest.name, {
			"admits": card_admits(guest.card_type, guest.admits, table_sizes.get(guest.parent)),
			"entered_count": 1 if guest.checked_in else 0,
		}, update_modified=False)
