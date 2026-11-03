"""Web-dashboard API — called from /my-occasion and /new-occasion pages."""

import frappe
from frappe import _
from frappe.utils import cint, flt
from orion_card.utils.phone import normalize_phone
from orion_card.permissions import is_staff

# ── Import column maps (mirrors occasion.py) ────────────────────────────────

_IMPORT_COLUMNS = {
    "name": ("name", "jina", "contributor", "contributor name", "mchangiaji"),
    "phone": ("phone", "simu", "namba ya simu", "phone number", "mobile"),
    "pledged": ("pledge", "pledged", "ahadi", "pledged amount"),
    "card_type": ("card type", "aina ya kadi", "kadi", "card"),
    "paid": ("paid so far", "paid", "amelipa", "imelipwa", "paid amount"),
}
_BUDGET_COLUMNS = {
    "particular":  ("particular", "category", "item", "kipengele", "particulars"),
    "description": ("description", "maelezo", "details", "desc"),
    "budgeted":    ("budgeted amount", "budgeted", "budget", "planned", "bajeti"),
    "actual":      ("actual spent", "actual", "spent", "kilichotumika", "actual amount"),
    "notes":       ("notes", "maelezo ya ziada", "remarks", "note"),
}
_CARD_TYPES = ("SINGLE", "DOUBLE", "VIP", "TABLE")


def _find_col(header, aliases):
    for i, h in enumerate(header):
        if h in aliases:
            return i
    return None


def _read_spreadsheet(file_url: str, doc) -> list:
    file_doc = frappe.get_doc("File", {"file_url": file_url})
    attached_here = (
        file_doc.attached_to_doctype == "Occasion"
        and file_doc.attached_to_name == doc.name
    )
    if not (attached_here or file_doc.owner == frappe.session.user or is_staff()):
        frappe.throw(_("You can only import a file you uploaded."), frappe.PermissionError)
    content = file_doc.get_content()
    extension = (file_doc.file_name or file_url).rsplit(".", 1)[-1].lower()
    if extension == "xlsx":
        from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file
        return read_xlsx_file_from_attached_file(fcontent=content)
    if extension == "xls":
        from frappe.utils.xlsxutils import read_xls_file_from_attached_file
        return read_xls_file_from_attached_file(content)
    if extension == "csv":
        from frappe.utils.csvutils import read_csv_content
        return read_csv_content(content)
    frappe.throw(_("Upload an .xlsx, .xls or .csv file."))


def _require_occasion_write(name):
    doc = frappe.get_doc("Occasion", name)
    doc.check_permission("write")
    return doc


def _fix_budget_particulars(doc):
    """Back-fill particular from description for rows saved before particular was mandatory."""
    for item in doc.budget_items:
        if not (item.particular or "").strip():
            item.particular = (item.description or item.notes or "—")[:140]


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
    _require_occasion_write(occasion)
    from orion_card.orioncard.doctype.occasion.occasion import card_admits
    card_type = card_type or "SINGLE"
    table_size = frappe.db.get_value("Occasion", occasion, "table_size")

    # Sequential guest code — same algorithm as Occasion._generate_unique_code
    result = frappe.db.sql(
        "SELECT COALESCE(MAX(CAST(guest_code AS UNSIGNED)), 0) FROM `tabOccasion Contributor` "
        "WHERE guest_code REGEXP '^[0-9]+$'"
    )
    guest_code = str(int(result[0][0] if result else 0) + 1)
    base = frappe.utils.get_url().rstrip("/")
    download_url = f"{base}/invitee/download/occasion-card/{guest_code}"

    # Insert the child row directly — bypasses the parent's validate() so the
    # subscription check (_assert_access_for_new_rows) is never reached.
    child = frappe.new_doc("Occasion Contributor")
    child.parent = occasion
    child.parentfield = "contributors"
    child.parenttype = "Occasion"
    child.contributor_name = contributor_name
    child.phone = phone or None
    child.card_type = card_type
    child.admits = card_admits(card_type, None, table_size)
    child.guest_code = guest_code
    child.download_url = download_url
    child.insert(ignore_permissions=True)

    return {"status": "ok", "row_name": child.name, "guest_code": guest_code}


@frappe.whitelist()
def update_contributor(occasion, row_name, contributor_name, phone=None, card_type="SINGLE"):
    _require_occasion_write(occasion)
    # Verify the row belongs to this occasion before writing — avoids the need
    # to load the full parent doc (which triggers _assert_access_for_new_rows
    # and throws Subscription Required even for already-saved rows).
    if not frappe.db.exists("Occasion Contributor", {"name": row_name, "parent": occasion}):
        frappe.throw(_("Contributor not found on this Occasion."))
    from orion_card.orioncard.doctype.occasion.occasion import card_admits
    card_type = card_type or "SINGLE"
    table_size = frappe.db.get_value("Occasion", occasion, "table_size")
    frappe.db.set_value("Occasion Contributor", row_name, {
        "contributor_name": contributor_name,
        "phone": phone or None,
        "card_type": card_type,
        "admits": card_admits(card_type, None, table_size),
    })
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
def add_budget_item(occasion, particular, description, budgeted_amount=0, actual_amount=0, notes=None):
    _require_occasion_write(occasion)
    # Insert the child row directly to bypass the parent's subscription check.
    child = frappe.new_doc("Occasion Budget Item")
    child.parent = occasion
    child.parentfield = "budget_items"
    child.parenttype = "Occasion"
    child.particular = particular
    child.description = description
    child.budgeted_amount = flt(budgeted_amount)
    child.actual_amount = flt(actual_amount)
    child.notes = notes or None
    child.insert(ignore_permissions=True)
    return {"status": "ok"}


@frappe.whitelist()
def update_budget_item(occasion, row_name, particular, description, budgeted_amount=0, actual_amount=0, notes=None):
    doc = _require_occasion_write(occasion)
    for row in doc.budget_items:
        if row.name == row_name:
            row.particular = particular
            row.description = description
            row.budgeted_amount = flt(budgeted_amount)
            row.actual_amount = flt(actual_amount)
            row.notes = notes or None
            break
    _fix_budget_particulars(doc)
    doc.save()
    return {"status": "ok"}


@frappe.whitelist()
def remove_budget_item(occasion, row_name):
    doc = _require_occasion_write(occasion)
    doc.budget_items = [r for r in doc.budget_items if r.name != row_name]
    _fix_budget_particulars(doc)
    doc.save()
    return {"status": "ok"}


# ── Import from spreadsheet ─────────────────────────────────────────────────

@frappe.whitelist()
def import_contributors(occasion: str, file_url: str):
    doc = frappe.get_doc("Occasion", occasion)
    doc.check_permission("write")
    rows = _read_spreadsheet(file_url, doc)
    if not rows:
        frappe.throw(_("The file is empty."))
    header = [str(h or "").strip().lower() for h in rows[0]]
    col = {key: _find_col(header, aliases) for key, aliases in _IMPORT_COLUMNS.items()}
    if col["name"] is None:
        frappe.throw(_("The file must have a 'Name' column. Download the template to see the expected columns."))

    from orion_card.orioncard.doctype.occasion.occasion import card_admits

    # Build lookup maps from DB rows (not doc in-memory) to avoid triggering validate()
    db_rows = frappe.get_all(
        "Occasion Contributor",
        filters={"parent": occasion},
        fields=["name", "contributor_name", "phone", "card_type", "pledged_amount", "paid_amount"],
    )
    by_phone = {normalize_phone(r.phone): r for r in db_rows if r.phone}
    by_name  = {r.contributor_name.strip().lower(): r for r in db_rows}
    table_size = frappe.db.get_value("Occasion", occasion, "table_size")
    base = frappe.utils.get_url().rstrip("/")

    # Sequential guest code — same as Occasion._generate_unique_code
    result = frappe.db.sql(
        "SELECT COALESCE(MAX(CAST(guest_code AS UNSIGNED)), 0) FROM `tabOccasion Contributor` "
        "WHERE guest_code REGEXP '^[0-9]+$'"
    )
    next_code = int(result[0][0] if result else 0) + 1

    added, updated, skipped = 0, 0, []
    for line_no, row in enumerate(rows[1:], start=2):
        def value(key, _row=row, _col=col):
            i = _col[key]
            return _row[i] if i is not None and i < len(_row) else None
        name = str(value("name") or "").strip()
        if not name:
            if any(cell not in (None, "") for cell in row):
                skipped.append(_("Row {0}: missing name").format(line_no))
            continue
        phone = str(value("phone") or "").strip()
        if phone.endswith(".0"):
            phone = phone[:-2]
        try:
            pledged = flt(value("pledged") or 0)
            paid_so_far = flt(value("paid") or 0)
        except Exception:
            skipped.append(_("Row {0}: amounts must be numbers").format(line_no))
            continue
        card_type = str(value("card_type") or "SINGLE").strip().upper()
        if card_type not in _CARD_TYPES:
            card_type = "SINGLE"

        existing = by_phone.get(normalize_phone(phone)) if phone else by_name.get(name.lower())
        if existing:
            update_vals = {
                "contributor_name": name,
                "card_type": card_type,
                "admits": card_admits(card_type, None, table_size),
            }
            if phone and not existing.phone:
                update_vals["phone"] = phone
                by_phone[normalize_phone(phone)] = existing
            if pledged:
                update_vals["pledged_amount"] = pledged
            if paid_so_far:
                update_vals["paid_amount"] = paid_so_far
            frappe.db.set_value("Occasion Contributor", existing.name, update_vals)
            updated += 1
            continue

        guest_code = str(next_code)
        next_code += 1
        child = frappe.new_doc("Occasion Contributor")
        child.parent = occasion
        child.parentfield = "contributors"
        child.parenttype = "Occasion"
        child.contributor_name = name
        child.phone = phone or None
        child.pledged_amount = pledged
        child.paid_amount = max(paid_so_far, 0)
        child.card_type = card_type
        child.admits = card_admits(card_type, None, table_size)
        child.guest_code = guest_code
        child.download_url = f"{base}/invitee/download/occasion-card/{guest_code}"
        child.insert(ignore_permissions=True)
        if phone:
            by_phone[normalize_phone(phone)] = child
        by_name[name.lower()] = child
        added += 1

    return {"added": added, "updated": updated, "skipped": skipped}


@frappe.whitelist()
def import_budget_items(occasion: str, file_url: str):
    doc = frappe.get_doc("Occasion", occasion)
    doc.check_permission("write")
    rows = _read_spreadsheet(file_url, doc)
    if not rows:
        frappe.throw(_("The file is empty."))
    header = [str(h or "").strip().lower() for h in rows[0]]
    col = {key: _find_col(header, aliases) for key, aliases in _BUDGET_COLUMNS.items()}
    if col["particular"] is None:
        frappe.throw(_("The file must have a 'Particular' column. Download the template to see the expected columns."))

    # Build lookup from DB rows — bypass validate() subscription check entirely
    db_rows = frappe.get_all(
        "Occasion Budget Item",
        filters={"parent": occasion},
        fields=["name", "particular", "description", "budgeted_amount", "actual_amount", "notes"],
    )
    by_particular = {(r.particular or "").strip().lower(): r for r in db_rows}

    added, updated, skipped = 0, 0, []
    for line_no, row in enumerate(rows[1:], start=2):
        def value(key, _row=row, _col=col):
            i = _col[key]
            return _row[i] if i is not None and i < len(_row) else None
        particular = str(value("particular") or "").strip()
        description = str(value("description") or "").strip()
        notes = str(value("notes") or "").strip()
        # Fall back to description as the item name when Particular is empty
        if not particular:
            if description:
                particular = description[:140]
            else:
                continue  # truly empty row
        try:
            budgeted = flt(value("budgeted") or 0)
            actual = flt(value("actual") or 0)
        except Exception:
            skipped.append(_("Row {0}: amounts must be numbers").format(line_no))
            continue

        existing = by_particular.get(particular.lower())
        if existing:
            update_vals = {}
            if description:
                update_vals["description"] = description
            if budgeted:
                update_vals["budgeted_amount"] = budgeted
            if actual:
                update_vals["actual_amount"] = actual
            if notes:
                update_vals["notes"] = notes
            if update_vals:
                frappe.db.set_value("Occasion Budget Item", existing.name, update_vals)
            updated += 1
            continue

        child = frappe.new_doc("Occasion Budget Item")
        child.parent = occasion
        child.parentfield = "budget_items"
        child.parenttype = "Occasion"
        child.particular = particular
        child.description = description
        child.budgeted_amount = max(budgeted, 0)
        child.actual_amount = max(actual, 0)
        child.notes = notes or None
        child.insert(ignore_permissions=True)
        by_particular[particular.lower()] = child
        added += 1

    return {"added": added, "updated": updated, "skipped": skipped}


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
