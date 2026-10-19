import frappe


def execute():
	"""Ensure the "Occasion Client" role exists on sites that installed
	orion_card before this role was introduced (after_install only runs on a
	fresh install), and move any applicant Users already created by
	Occasion Subscription off the old "Event Manager" role onto it — those
	accounts should only ever see the Occasion doctype, never the
	Subscription, Invite Log, or reports that Event Manager grants access to.
	"""
	if not frappe.db.exists("Role", "Occasion Client"):
		role = frappe.new_doc("Role")
		role.role_name = "Occasion Client"
		role.desk_access = 1
		role.insert(ignore_permissions=True)
	else:
		# Defensive: make sure it's actually usable for desk login even if the
		# record already existed with desk_access unset for any reason.
		frappe.db.set_value("Role", "Occasion Client", "desk_access", 1)

	if not frappe.db.table_exists("Occasion Subscription"):
		frappe.db.commit()
		return

	linked_users = set(frappe.get_all(
		"Occasion Subscription",
		filters={"user": ["is", "set"]},
		pluck="user",
	))

	for user_name in linked_users:
		if not frappe.db.exists("User", user_name):
			continue
		user = frappe.get_doc("User", user_name)
		roles = {r.role for r in user.roles}
		if "Event Manager" in roles:
			user.remove_roles("Event Manager")
		missing_roles = [r for r in ("Occasion Client", "Desk User") if r not in roles]
		if missing_roles:
			user.append_roles(*missing_roles)
		user.user_type = "System User"
		user.save(ignore_permissions=True)

	frappe.db.commit()
