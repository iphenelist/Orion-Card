"""Contribution (michango) reminders by SMS / WhatsApp, sent by hand. Each
contributor gets at most 3 per channel (see orion_card.utils.invites)."""

import frappe
from frappe import _
from frappe.utils import cint, flt, fmt_money, formatdate, now_datetime

from orion_card.api.messaging import send_message, sender_line
from orion_card.utils.credits import plain_sms_text
from orion_card.utils.invites import REMINDER, MessageLimitError, assert_within_limit, message_limit, sent_counts

DEFAULT_TEMPLATE = (
	"Habari {name}, tunakukumbusha mchango wako kwa {occasion} ({date}). "
	"Ahadi: {pledged}, Umelipa: {paid}, Salio: {balance}. "
	"Tafadhali kamilisha kabla ya {deadline}. {payment_info} Asante. {sender}"
)
REMINDABLE_STATUSES = ("Not Paid", "Partially Paid")


class _SafeDict(dict):
	def __missing__(self, key):
		return "{" + key + "}"


def _money(value) -> str:
	return fmt_money(flt(value), precision=0, currency="TZS")


def build_reminder_message(occasion_doc, contributor, channel: str = "SMS") -> str:
	template = (occasion_doc.reminder_template or "").strip() or DEFAULT_TEMPLATE
	deadline = occasion_doc.contribution_deadline or occasion_doc.occasion_date
	values = _SafeDict(
		name=contributor.contributor_name,
		pledged=_money(contributor.pledged_amount),
		paid=_money(contributor.paid_amount),
		balance=_money(contributor.balance),
		occasion=occasion_doc.occasion_name,
		date=formatdate(occasion_doc.occasion_date, "dd-MM-yyyy"),
		deadline=formatdate(deadline, "dd-MM-yyyy") if deadline else "",
		payment_info=(occasion_doc.payment_instructions or "").strip(),
		sender=sender_line(occasion_doc),
	)
	text = " ".join(template.format_map(values).split())
	return plain_sms_text(text) if channel == "SMS" else text


def select_contributors(occasion_doc, statuses=None, contributor_ids=None, channel=None) -> list:
	"""Contributors with a balance and a phone; with `channel`, only those
	still under the reminder limit on it."""
	statuses = [s for s in (statuses or REMINDABLE_STATUSES) if s in REMINDABLE_STATUSES]
	rows = [
		c for c in occasion_doc.contributors
		if c.payment_status in statuses and flt(c.balance) > 0 and c.phone
	]
	if contributor_ids:
		wanted = set(contributor_ids)
		rows = [c for c in rows if c.contributor_id in wanted]
	if channel:
		counts, limit = sent_counts(occasion_doc.name, channel, REMINDER), message_limit(REMINDER)
		rows = [c for c in rows if counts.get(c.contributor_id, 0) < limit]
	return rows


def send_reminder(occasion_doc, contributor, channel: str) -> dict:
	assert_within_limit(occasion_doc, contributor, channel, REMINDER)
	message = build_reminder_message(occasion_doc, contributor, channel)
	result = send_message(
		occasion_doc,
		channel,
		contributor.phone,
		message,
		message_type="Contribution Reminder",
		contributor_id=contributor.contributor_id,
		recipient_name=contributor.contributor_name,
	)
	frappe.db.set_value(
		"Occasion Contributor",
		contributor.name,
		{"last_reminder_at": now_datetime(), "reminder_count": cint(contributor.reminder_count) + 1},
		update_modified=False,
	)
	return result


@frappe.whitelist()
def preview(occasion: str, contributor_id: str | None = None) -> str:
	doc = frappe.get_doc("Occasion", occasion)
	doc.check_permission("read")
	contributor = next((c for c in doc.contributors if c.contributor_id == contributor_id), None)
	if not contributor:
		# Preview with the first contributor who would actually be reminded.
		contributor = next(iter(select_contributors(doc)), None)
	if not contributor:
		contributor = frappe._dict(
			contributor_name="Juma Ali", pledged_amount=100000, paid_amount=40000, balance=60000
		)
	return build_reminder_message(doc, contributor)


@frappe.whitelist()
def send_reminders(occasion: str, channel: str = "SMS", statuses=None, contributor_ids=None) -> dict:
	from orion_card.utils.credits import InsufficientCreditsError, support_contact

	doc = frappe.get_doc("Occasion", occasion)
	doc.check_permission("write")
	doc.assert_can_send()
	statuses = frappe.parse_json(statuses) if isinstance(statuses, str) else statuses
	contributor_ids = frappe.parse_json(contributor_ids) if isinstance(contributor_ids, str) else contributor_ids
	channels = ["SMS", "WhatsApp"] if channel == "Both" else [channel]
	if any(ch not in ("SMS", "WhatsApp") for ch in channels):
		frappe.throw(_("Unknown channel {0}").format(channel))

	results = {"success": 0, "failed": 0, "errors": [], "credits_out": False}
	for ch in channels:
		for contributor in select_contributors(doc, statuses, contributor_ids):
			try:
				send_reminder(doc, contributor, ch)
				results["success"] += 1
			except MessageLimitError as e:
				# Bulk sends just skip whoever had all their reminders; a chosen contributor is told why.
				if contributor_ids:
					results["failed"] += 1
					results["errors"].append(str(e))
			except InsufficientCreditsError as e:
				results["failed"] += 1
				results["errors"].append(str(e))
				results["credits_out"] = True
				break
			except Exception as e:
				results["failed"] += 1
				results["errors"].append(f"{contributor.contributor_name} ({ch}): {e}")
	if results["credits_out"]:
		results["contact"] = support_contact()
	return results
