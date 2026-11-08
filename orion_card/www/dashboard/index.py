import frappe

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/dashboard"
		raise frappe.Redirect

	user = frappe.session.user
	user_doc = frappe.get_cached_doc("User", user)

	occasions = frappe.get_list(
		"Occasion",
		fields=["name", "couple_names", "occasion_date", "occasion_time", "venue_name", "status", "card_design"],
		order_by="occasion_date desc",
		ignore_permissions=False,
	)

	active_count = sum(1 for o in occasions if o.status == "Active")

	total_guests = frappe.db.sql(
		"""
		SELECT COUNT(*)
		FROM `tabOccasion Contributor` oc
		JOIN `tabOccasion` o ON oc.parent = o.name
		WHERE o.assigned_user = %s
		""",
		user,
	)[0][0] or 0

	cards_sent = frappe.db.sql(
		"""
		SELECT COUNT(*)
		FROM `tabOccasion Contributor` oc
		JOIN `tabOccasion` o ON oc.parent = o.name
		WHERE o.assigned_user = %s AND (oc.card_image IS NOT NULL AND oc.card_image != '')
		""",
		user,
	)[0][0] or 0

	credit_row = frappe.get_value(
		"Message Credit Account",
		{"user": user},
		["sms_balance", "whatsapp_balance"],
		as_dict=True,
	) or {}
	credits_balance = int((credit_row.get("sms_balance") or 0) + (credit_row.get("whatsapp_balance") or 0))

	context.csrf_token = frappe.sessions.get_csrf_token()
	context.title = "Matukio Yangu — OrionCard"
	context.no_breadcrumbs = 1
	context.user_full_name = user_doc.full_name or user_doc.first_name or user
	context.user_email = user
	context.occasions = occasions
	context.stats = {
		"active_occasions": active_count,
		"total_occasions": len(occasions),
		"total_guests": total_guests,
		"cards_sent": cards_sent,
		"credits_balance": credits_balance,
	}
