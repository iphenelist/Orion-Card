"""Row-level permission helpers shared by orion_card doctypes.

Only Administrator and System Manager see everything. Everyone else — in
practice the self-registered Occasion Manager — only sees their own rows.
"""

import frappe

STAFF_ROLES = {"System Manager"}


def is_staff(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return user == "Administrator" or bool(STAFF_ROLES.intersection(frappe.get_roles(user)))


def user_field_condition(doctype: str, field: str, user: str | None = None) -> str:
	user = user or frappe.session.user
	if is_staff(user):
		return ""
	return f"`tab{doctype}`.`{field}` = {frappe.db.escape(user)}"


# --- doctypes owned directly through a `user` field --------------------------


def credit_account_query(user=None):
	return user_field_condition("Message Credit Account", "user", user)


def credit_account_has_permission(doc, ptype="read", user=None):
	return is_staff(user) or doc.user == (user or frappe.session.user)


def credit_transaction_query(user=None):
	return user_field_condition("Credit Transaction", "user", user)


def credit_transaction_has_permission(doc, ptype="read", user=None):
	return is_staff(user) or doc.user == (user or frappe.session.user)


def credit_purchase_query(user=None):
	return user_field_condition("Credit Purchase", "user", user)


def credit_purchase_has_permission(doc, ptype="read", user=None):
	return is_staff(user) or doc.user == (user or frappe.session.user)
