import secrets
import string

import frappe


def execute():
	"""After the budget / contributions / credits upgrade:
	- mark existing Invite Log rows as invitations,
	- give every existing Occasion a gate PIN,
	- create a credit account for every Occasion Manager."""
	frappe.db.sql(
		"update `tabOccasion Guest Invite Log` set message_type='Invitation' "
		"where message_type is null or message_type=''"
	)

	for name in frappe.get_all("Occasion", filters={"gate_pin": ["in", ["", None]]}, pluck="name"):
		pin = "".join(secrets.choice(string.digits) for _ in range(6))
		frappe.db.set_value("Occasion", name, "gate_pin", pin, update_modified=False)

	from orion_card.utils.credits import get_account

	for user in frappe.get_all(
		"Has Role", filters={"role": "Occasion Manager", "parenttype": "User"}, pluck="parent", distinct=True
	):
		get_account(user)

	frappe.db.commit()
