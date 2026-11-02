"""Background job for bulk invitation sends.

Runs in the 'long' RQ worker so bulk sends never block the web process.
Progress is broadcast via Frappe realtime (to the user who started the job)
and cached in Redis (so a page reload can recover the current state).
"""

import random
import time

import frappe

CACHE_KEY_PREFIX = "orion_card:bulk_send"
CACHE_TTL = 7200  # 2 hours


def _cache_key(occasion_name: str, channel: str) -> str:
	return f"{CACHE_KEY_PREFIX}:{occasion_name}:{channel}"


def _publish(occasion_name: str, channel: str, state: dict, user: str):
	"""Broadcast current state to the launching user and store it in cache."""
	frappe.publish_realtime(
		event="bulk_send_progress",
		message={"occasion": occasion_name, "channel": channel, **state},
		user=user,
	)
	frappe.cache().set_value(_cache_key(occasion_name, channel), state, expires_in_sec=CACHE_TTL)


def run_bulk_send(
	occasion_name: str,
	channel: str,
	statuses,
	resend: int,
	launched_by: str,
	sms_fallback: bool = False,
):
	"""Entry point called by frappe.enqueue().

	sms_fallback: when True and channel is WhatsApp, failed WhatsApp sends are
	retried automatically over SMS (if SMS is enabled in OrionCard Settings).
	"""
	from orion_card.utils.credits import InsufficientCreditsError, support_contact

	frappe.set_user(launched_by)

	occasion = frappe.get_doc("Occasion", occasion_name)
	guests = occasion.guests_to_invite(channel, statuses, resend)
	total = len(guests)

	if channel == "WhatsApp":
		from orion_card.api.whatsapp import send_invitation as _send_wa
		send_fn = _send_wa
	else:
		from orion_card.api.sms import send_invitation as _send_sms
		send_fn = _send_sms

	sms_fallback_active = (
		sms_fallback
		and channel == "WhatsApp"
		and _channel_enabled("SMS")
	)
	if sms_fallback_active:
		from orion_card.api.sms import send_invitation as _send_sms_fallback

	state = {
		"total": total,
		"success": 0,
		"failed": 0,
		"errors": [],
		"done": False,
		"credits_out": False,
	}
	_publish(occasion_name, channel, state, launched_by)

	for i, contributor in enumerate(guests):
		try:
			if not contributor.card_image and occasion.card_design:
				occasion.issue_card(contributor)
			send_fn(occasion, contributor)
			state["success"] += 1

		except InsufficientCreditsError as e:
			state["failed"] += 1
			state["errors"].append(str(e))
			state["credits_out"] = True
			_publish(occasion_name, channel, state, launched_by)
			break

		except Exception as e:
			if sms_fallback_active:
				try:
					_send_sms_fallback(occasion, contributor)
					state["success"] += 1
				except Exception as sms_err:
					state["failed"] += 1
					state["errors"].append(
						f"{contributor.contributor_name} (WA+SMS): {str(sms_err)[:120]}"
					)
			else:
				state["failed"] += 1
				state["errors"].append(
					f"{contributor.contributor_name}: {str(e)[:120]}"
				)

		_publish(occasion_name, channel, state, launched_by)

		if i < total - 1:
			delay = random.uniform(5.0, 7.0) if channel == "WhatsApp" else 1.0
			time.sleep(delay)

	state["done"] = True
	if state["credits_out"]:
		state["contact"] = support_contact()
	_publish(occasion_name, channel, state, launched_by)


def _channel_enabled(channel: str) -> bool:
	from orion_card.api.messaging import channel_enabled
	return channel_enabled(channel)


@frappe.whitelist()
def get_status(occasion_name: str, channel: str) -> dict | None:
	"""Return the cached state of a running or recently finished bulk send.

	Returns None when no job has run for this occasion+channel combination,
	or when the cache has expired (2 hours after the job finished).
	"""
	occasion = frappe.get_doc("Occasion", occasion_name)
	occasion.check_permission("read")
	return frappe.cache().get_value(_cache_key(occasion_name, channel))
