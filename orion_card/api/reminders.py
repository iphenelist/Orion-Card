"""Contribution (michango) reminders by SMS / WhatsApp."""

import frappe
from frappe import _
from frappe.utils import (
	add_days,
	cint,
	flt,
	fmt_money,
	formatdate,
	get_datetime,
	getdate,
	now_datetime,
	today,
)

from orion_card.api.messaging import send_message, sender_line

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


def build_reminder_message(occasion_doc, contributor) -> str:
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
	return " ".join(template.format_map(values).split())


def select_contributors(occasion_doc, statuses=None, contributor_ids=None) -> list:
	statuses = [s for s in (statuses or REMINDABLE_STATUSES) if s in REMINDABLE_STATUSES]
	rows = [
		c for c in occasion_doc.contributors
		if c.payment_status in statuses and flt(c.balance) > 0 and c.phone
	]
	if contributor_ids:
		wanted = set(contributor_ids)
		rows = [c for c in rows if c.contributor_id in wanted]
	return rows


def send_reminder(occasion_doc, contributor, channel: str) -> dict:
	message = build_reminder_message(occasion_doc, contributor)
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
	from orion_card.utils.credits import InsufficientCreditsError

	doc = frappe.get_doc("Occasion", occasion)
	doc.check_permission("write")
	doc.assert_can_send()
	statuses = frappe.parse_json(statuses) if isinstance(statuses, str) else statuses
	contributor_ids = frappe.parse_json(contributor_ids) if isinstance(contributor_ids, str) else contributor_ids
	channels = ["SMS", "WhatsApp"] if channel == "Both" else [channel]
	if any(ch not in ("SMS", "WhatsApp") for ch in channels):
		frappe.throw(_("Unknown channel {0}").format(channel))

	results = {"success": 0, "failed": 0, "errors": []}
	for ch in channels:
		for contributor in select_contributors(doc, statuses, contributor_ids):
			try:
				send_reminder(doc, contributor, ch)
				results["success"] += 1
			except InsufficientCreditsError as e:
				results["failed"] += 1
				results["errors"].append(str(e))
				break
			except Exception as e:
				results["failed"] += 1
				results["errors"].append(f"{contributor.contributor_name} ({ch}): {e}")
	return results


def process_auto_reminders():
	"""Hourly: remind contributors with a balance, every N days, until the deadline."""
	occasions = frappe.get_all(
		"Occasion",
		filters={"auto_reminders": 1},
		fields=["name", "contribution_deadline", "occasion_date", "reminder_interval_days"],
	)
	for row in occasions:
		last_day = getdate(row.contribution_deadline or row.occasion_date)
		if not last_day or getdate(today()) > last_day:
			continue
		try:
			_process_occasion(row)
		except Exception:
			frappe.log_error(title=f"Auto reminders failed for {row.name}", message=frappe.get_traceback())


def _process_occasion(row):
	from orion_card.legal import terms_pending
	from orion_card.utils.credits import InsufficientCreditsError

	doc = frappe.get_doc("Occasion", row.name)
	if not doc.subscription_active():
		return
	if doc.assigned_user and terms_pending(doc.assigned_user):
		return
	interval = max(cint(row.reminder_interval_days) or 7, 1)
	cutoff = add_days(now_datetime(), -interval)
	# Auto reminders go by SMS: it reaches every phone, WhatsApp or not.
	for contributor in select_contributors(doc):
		if contributor.last_reminder_at and get_datetime(contributor.last_reminder_at) > cutoff:
			continue
		try:
			send_reminder(doc, contributor, "SMS")
		except InsufficientCreditsError:
			frappe.log_error(
				title=f"Auto reminders paused for {doc.name}: not enough SMS credits",
				message=f"Payer: {doc.assigned_user}",
			)
			return
		except Exception:
			frappe.log_error(
				title=f"Auto reminder failed for {contributor.contributor_name}", message=frappe.get_traceback()
			)
	frappe.db.commit()  # nosemgrep — persist each occasion's sends + ledger before the next
