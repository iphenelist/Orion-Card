"""Web-dashboard API — called from /my-occasion and /new-occasion pages."""

import frappe
from frappe import _
from frappe.utils import cint, flt


def _require_occasion_write(name):
    doc = frappe.get_doc("Occasion", name)
    doc.check_permission("write")
    return doc


# ── Basic occasion details ──────────────────────────────────────────────────

@frappe.whitelist()
def save_occasion_details(
    name,
    couple_names,
    occasion_date=None,
    occasion_time=None,
    venue_name=None,
    venue_address=None,
    venue_location=None,
    dress_code=None,
    contact_1=None,
    contact_2=None,
    status=None,
):
    doc = _require_occasion_write(name)
    doc.couple_names = couple_names or doc.couple_names
    doc.occasion_date = occasion_date or None
    doc.occasion_time = occasion_time or None
    doc.venue_name = venue_name or None
    doc.venue_address = venue_address or None
    doc.venue_location = venue_location or None
    doc.dress_code = dress_code or None
    doc.contact_1 = contact_1 or None
    doc.contact_2 = contact_2 or None
    if status and status in ("Draft", "Active", "Completed"):
        doc.status = status
    doc.save()
    return {"status": "ok"}


# ── Gate settings ───────────────────────────────────────────────────────────

@frappe.whitelist()
def save_gate_settings(name, allow_reentry=0, table_size=None):
    doc = _require_occasion_write(name)
    doc.allow_reentry = cint(allow_reentry)
    if table_size:
        doc.table_size = cint(table_size)
    doc.save()
    return {"status": "ok"}


# ── Contributors ────────────────────────────────────────────────────────────

@frappe.whitelist()
def add_contributor(occasion, contributor_name, phone, card_type="SINGLE"):
    doc = _require_occasion_write(occasion)
    row = doc.append("contributors", {
        "contributor_name": contributor_name,
        "phone": phone,
        "card_type": card_type,
    })
    doc.save()
    return {"status": "ok", "row_name": row.name, "guest_code": row.guest_code}


@frappe.whitelist()
def update_contributor(occasion, row_name, contributor_name, phone=None, card_type="SINGLE"):
    _require_occasion_write(occasion)
    # Save directly on the child row to avoid the parent's subscription
    # validator (_assert_access_for_new_rows), which is irrelevant here —
    # we are only editing fields on an already-saved row.
    row = frappe.get_doc("Occasion Contributor", row_name)
    if row.parent != occasion or row.parenttype != "Occasion":
        frappe.throw(_("Contributor not found on this Occasion."))
    from orion_card.orioncard.doctype.occasion.occasion import card_admits
    table_size = frappe.db.get_value("Occasion", occasion, "table_size")
    row.contributor_name = contributor_name
    row.phone = phone or None
    row.card_type = card_type or "SINGLE"
    row.admits = card_admits(row.card_type, row.admits, table_size)
    row.save(ignore_permissions=True)
    return {"status": "ok"}


@frappe.whitelist()
def remove_contributor(occasion, row_name):
    doc = _require_occasion_write(occasion)
    doc.contributors = [r for r in doc.contributors if r.name != row_name]
    doc.save()
    return {"status": "ok"}


# ── Bulk actions ────────────────────────────────────────────────────────────

@frappe.whitelist()
def generate_all_cards(occasion, statuses=None):
    doc = _require_occasion_write(occasion)
    return doc.generate_all_cards(statuses=frappe.parse_json(statuses) if statuses else None)


@frappe.whitelist()
def send_all_whatsapp(occasion, resend=0, statuses=None):
    doc = _require_occasion_write(occasion)
    return doc.send_all_whatsapp(resend=cint(resend), statuses=frappe.parse_json(statuses) if statuses else None)


@frappe.whitelist()
def send_all_sms(occasion, resend=0, statuses=None):
    doc = _require_occasion_write(occasion)
    return doc.send_all_sms(resend=cint(resend), statuses=frappe.parse_json(statuses) if statuses else None)


@frappe.whitelist()
def send_reminders(occasion, channel="SMS"):
    from orion_card.api.reminders import send_reminders as _send
    return _send(occasion, channel=channel)


# ── Card design ─────────────────────────────────────────────────────────────

@frappe.whitelist()
def save_card_design(occasion, file_url):
    doc = _require_occasion_write(occasion)
    doc.card_design = file_url
    doc.card_preview_image = file_url
    doc.save()
    return {"status": "ok"}


# ── Budget ──────────────────────────────────────────────────────────────────

@frappe.whitelist()
def save_budget_settings(occasion, total_budget=0, contribution_deadline=None, payment_instructions=None):
    doc = _require_occasion_write(occasion)
    doc.total_budget = flt(total_budget)
    doc.contribution_deadline = contribution_deadline or None
    doc.payment_instructions = payment_instructions or None
    doc.save()
    return {"status": "ok"}


@frappe.whitelist()
def add_budget_item(occasion, category, description, budgeted_amount=0, actual_amount=0, notes=None):
    doc = _require_occasion_write(occasion)
    doc.append("budget_items", {
        "category": category,
        "description": description,
        "budgeted_amount": flt(budgeted_amount),
        "actual_amount": flt(actual_amount),
        "notes": notes or None,
    })
    doc.save()
    return {"status": "ok"}


@frappe.whitelist()
def update_budget_item(occasion, row_name, category, description, budgeted_amount=0, actual_amount=0, notes=None):
    doc = _require_occasion_write(occasion)
    for row in doc.budget_items:
        if row.name == row_name:
            row.category = category
            row.description = description
            row.budgeted_amount = flt(budgeted_amount)
            row.actual_amount = flt(actual_amount)
            row.notes = notes or None
            break
    doc.save()
    return {"status": "ok"}


@frappe.whitelist()
def remove_budget_item(occasion, row_name):
    doc = _require_occasion_write(occasion)
    doc.budget_items = [r for r in doc.budget_items if r.name != row_name]
    doc.save()
    return {"status": "ok"}


# ── Create occasion ─────────────────────────────────────────────────────────

@frappe.whitelist()
def create_occasion(
    occasion_name,
    couple_names,
    occasion_date=None,
    occasion_time=None,
    venue_name=None,
    venue_address=None,
    dress_code=None,
    contact_1=None,
    contact_2=None,
):
    if frappe.db.exists("Occasion", occasion_name):
        frappe.throw(_("Tukio lenye jina hili tayari lipo. Chagua jina jingine."))

    doc = frappe.new_doc("Occasion")
    doc.occasion_name = occasion_name
    doc.couple_names = couple_names
    doc.occasion_date = occasion_date or None
    doc.occasion_time = occasion_time or None
    doc.venue_name = venue_name or None
    doc.venue_address = venue_address or None
    doc.dress_code = dress_code or None
    doc.contact_1 = contact_1 or None
    doc.contact_2 = contact_2 or None
    doc.insert()
    return {"status": "ok", "name": doc.name}
