"""How many messages each guest may receive.

Everything is sent by hand. On each channel (SMS and WhatsApp) a guest gets at
most `max_invites_per_guest` invitations (default 2) and
`max_reminders_per_guest` contribution reminders (default 3): the 5 messages
per channel a card's credits pay for. Only successful sends count, so a failed
attempt never uses one up.
"""

import frappe
from frappe import _
from frappe.utils import cint

from orion_card.utils.credits import contact_line

INVITATION, REMINDER = "Invitation", "Contribution Reminder"
DEFAULT_LIMITS = {INVITATION: 2, REMINDER: 3}
LIMIT_FIELDS = {INVITATION: "max_invites_per_guest", REMINDER: "max_reminders_per_guest"}
# Invitations are logged by guest code, reminders by contributor ID.
KEY_FIELDS = {INVITATION: "guest_code", REMINDER: "contributor_id"}
NAMES = {INVITATION: ("mwaliko", "invitation"), REMINDER: ("kikumbusho", "reminder")}


class MessageLimitError(frappe.ValidationError):
	pass


def message_limit(message_type: str) -> int:
	# 0 / unset means the default: to stop a channel, switch its sending off instead.
	return cint(frappe.db.get_single_value("OrionCard Settings", LIMIT_FIELDS[message_type])) \
		or DEFAULT_LIMITS[message_type]


def sent_counts(occasion: str, channel: str, message_type: str = INVITATION) -> dict:
	"""guest_code (invitations) or contributor_id (reminders) -> successful sends."""
	key = KEY_FIELDS[message_type]
	rows = frappe.db.sql(
		f"""
		select `{key}`, count(*) from `tabOccasion Guest Invite Log`
		where occasion=%s and channel=%s and success=1 and message_type=%s and ifnull(`{key}`, '')!=''
		group by `{key}`
		""",
		(occasion, channel, message_type),
	)
	return {k: cint(count) for k, count in rows}


def limit_message(name: str, channel: str, message_type: str, limit: int) -> str:
	sw, en = contact_line()
	what_sw, what_en = NAMES[message_type]
	return _(
		"{0} ameshapokea {1} kwa {2} mara {3}, ambayo ndiyo kikomo. {4} / "
		"{0} has already received the {5} by {2} {3} times, the limit. {6}"
	).format(name, what_sw, channel, limit, sw, what_en, en)


def assert_within_limit(occasion_doc, row, channel: str, message_type: str):
	limit = message_limit(message_type)
	sent = sent_counts(occasion_doc.name, channel, message_type).get(row.get(KEY_FIELDS[message_type]), 0)
	if sent >= limit:
		frappe.throw(limit_message(row.contributor_name, channel, message_type, limit), exc=MessageLimitError,
					 title=_("Message limit reached"))
