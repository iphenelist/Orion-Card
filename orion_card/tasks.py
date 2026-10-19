import frappe


def process_subscriptions():
    """Hourly job: for every Occasion Subscription whose send schedule has started,
    send/re-send WhatsApp and SMS invitations to its Occasion's contributors
    whose card has been generated, up to
    the configured repeat count and interval."""
    now = frappe.utils.now_datetime()
    subscriptions = frappe.get_all(
        "Occasion Subscription",
        filters={"occasion": ["is", "set"], "send_start_date": ["<=", now], "docstatus": 1},
        fields=["name", "occasion", "repeat_count", "repeat_interval_days"],
    )
    for subscription in subscriptions:
        _process_occasion(subscription)
        frappe.db.commit()  # nosemgrep — keep each occasion's sends + credit ledger


def process_contribution_reminders():
    from orion_card.api.reminders import process_auto_reminders

    process_auto_reminders()


def _process_occasion(subscription):
    from orion_card.api.sms import send_invitation as send_sms_invitation
    from orion_card.api.whatsapp import send_invitation as send_whatsapp_invitation
    from orion_card.legal import terms_pending

    occasion = frappe.get_doc("Occasion", subscription.occasion)
    if occasion.assigned_user and terms_pending(occasion.assigned_user):
        return
    for guest in occasion.contributors:
        if not guest.card_image or not guest.phone:
            continue
        _maybe_send(guest, occasion, "WhatsApp", send_whatsapp_invitation, subscription)
        _maybe_send(guest, occasion, "SMS", send_sms_invitation, subscription)


def _maybe_send(guest, occasion, channel, send_fn, subscription):
    from orion_card.utils.credits import InsufficientCreditsError

    # Only successful invitations count towards the repeat limit: a failed
    # attempt (gateway down, no credits) must not use up the guest's quota.
    sent_at_values = frappe.get_all(
        "Occasion Guest Invite Log",
        filters={
            "occasion": occasion.name,
            "guest_code": guest.guest_code,
            "channel": channel,
            "success": 1,
            "message_type": "Invitation",
        },
        pluck="sent_at",
    )
    if len(sent_at_values) >= (subscription.repeat_count or 0):
        return

    last_sent_at = max(sent_at_values, default=None)
    if last_sent_at:
        days_since_last_send = (frappe.utils.now_datetime() - last_sent_at).days
        if days_since_last_send < (subscription.repeat_interval_days or 0):
            return

    try:
        send_fn(occasion, guest)
    except InsufficientCreditsError:
        frappe.log_error(
            title=f"Auto-send {channel} skipped for {occasion.name}: not enough credits",
            message=f"Payer: {occasion.assigned_user}",
        )
    except Exception:
        frappe.log_error(
            title=f"Auto-send {channel} failed for {guest.contributor_name}",
            message=frappe.get_traceback(),
        )
