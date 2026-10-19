import frappe


def execute():
	"""Introduce "Occasion Manager" (self-registered customers) and move every
	existing "Occasion Client" user onto it; seed the new OrionCard Settings
	(credit prices, packages, Terms text)."""
	from orion_card.install import setup_roles, setup_settings_defaults

	setup_roles()

	legacy_users = frappe.get_all(
		"Has Role",
		filters={"role": "Occasion Client", "parenttype": "User"},
		pluck="parent",
		distinct=True,
	)
	for user_name in legacy_users:
		user = frappe.get_doc("User", user_name)
		roles = {r.role for r in user.roles}
		missing = [r for r in ("Occasion Manager", "Desk User") if r not in roles]
		if missing:
			user.append_roles(*missing)
			user.save(ignore_permissions=True)

	setup_settings_defaults()
	frappe.db.commit()
