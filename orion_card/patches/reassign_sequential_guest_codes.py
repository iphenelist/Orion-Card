import frappe


def execute():
	"""Reassign all guest codes from random 6-digit strings to sequential integers
	(1, 2, 3 …), ordered by occasion then row position within each occasion.
	Also updates download_url and the matching rows in the invite log."""
	base = frappe.utils.get_url().rstrip("/")

	rows = frappe.db.sql(
		"""
		SELECT name, guest_code
		FROM `tabOccasion Contributor`
		ORDER BY parent, idx
		""",
		as_dict=True,
	)

	if not rows:
		return

	# Build old→new mapping and write in one loop
	old_to_new = {}
	for seq, row in enumerate(rows, start=1):
		new_code = str(seq)
		old_to_new[row.guest_code] = new_code
		new_url = f"{base}/invitee/download/occasion-card/{new_code}"
		frappe.db.set_value(
			"Occasion Contributor",
			row.name,
			{"guest_code": new_code, "download_url": new_url},
			update_modified=False,
		)

	# Update invite log so history stays linked to the right guest
	for old_code, new_code in old_to_new.items():
		if old_code:
			frappe.db.sql(
				"UPDATE `tabOccasion Guest Invite Log` SET guest_code=%s WHERE guest_code=%s",
				(new_code, old_code),
			)

	frappe.db.commit()
