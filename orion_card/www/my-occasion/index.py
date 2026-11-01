import frappe
from frappe import _
from frappe.utils import flt

no_cache = 1

BUDGET_CATEGORIES = ["Chakula", "Vinywaji", "Muziki/Burudani", "Usafiri", "Mavazi", "Mapambo", "Picha/Video", "Ukumbi", "Kadi/Mwaliko", "Mengineyo"]


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/dashboard"
		raise frappe.Redirect

	name = frappe.form_dict.get("name", "").strip()
	if not name:
		frappe.local.flags.redirect_location = "/dashboard"
		raise frappe.Redirect

	try:
		doc = frappe.get_doc("Occasion", name)
		doc.check_permission("read")
	except frappe.DoesNotExistError:
		frappe.local.flags.redirect_location = "/dashboard"
		raise frappe.Redirect
	except frappe.PermissionError:
		frappe.throw(_("Huna ruhusa ya kuona tukio hili."), frappe.PermissionError)

	# Statistics
	contribs = doc.contributors or []
	rsvp_accepted = sum(1 for c in contribs if c.rsvp_status == "Accepted")
	rsvp_declined = sum(1 for c in contribs if c.rsvp_status == "Declined")
	rsvp_pending  = sum(1 for c in contribs if c.rsvp_status not in ("Accepted", "Declined"))
	cards_generated = sum(1 for c in contribs if c.card_image)
	checked_in = sum(1 for c in contribs if c.checked_in)
	pay_full = sum(1 for c in contribs if c.payment_status == "Fully Paid")
	pay_part = sum(1 for c in contribs if c.payment_status == "Partially Paid")
	pay_none = sum(1 for c in contribs if c.payment_status in ("Not Paid", None, ""))

	# Credits
	credit_row = frappe.get_value(
		"Message Credit Account", {"user": frappe.session.user},
		["sms_balance", "whatsapp_balance"], as_dict=True,
	) or {}
	sms_balance = int(credit_row.get("sms_balance") or 0)
	wa_balance  = int(credit_row.get("whatsapp_balance") or 0)

	user_doc = frappe.get_cached_doc("User", frappe.session.user)
	context.title = f"{doc.couple_names or doc.name} — OrionCard"
	context.no_breadcrumbs = 1
	context.user_full_name = user_doc.full_name or user_doc.first_name or frappe.session.user
	context.user_email = frappe.session.user
	context.doc = doc
	context.can_edit = frappe.has_permission("Occasion", "write", doc=doc.name)
	context.csrf_token = frappe.sessions.get_csrf_token()
	context.budget_categories = BUDGET_CATEGORIES
	context.stats = {
		"total": len(contribs),
		"rsvp_accepted": rsvp_accepted,
		"rsvp_declined": rsvp_declined,
		"rsvp_pending": rsvp_pending,
		"cards_generated": cards_generated,
		"checked_in": checked_in,
		"pay_full": pay_full,
		"pay_part": pay_part,
		"pay_none": pay_none,
		"sms_balance": sms_balance,
		"wa_balance": wa_balance,
	}
