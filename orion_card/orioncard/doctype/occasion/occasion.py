import random
import secrets
import string
from collections import defaultdict

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate

from orion_card.permissions import is_staff
from orion_card.utils.credits import has_free_access
from orion_card.utils.phone import normalize_phone

CONTRIBUTOR_ID_PREFIX = "C-"
CARD_TYPES = ("SINGLE", "DOUBLE", "VIP", "TABLE")
PAYMENT_STATUSES = ("Fully Paid", "Partially Paid", "Not Paid")
# Bulk card generation/sending goes to fully paid contributors unless the
# manager also ticks the other statuses.
DEFAULT_SEND_STATUSES = ("Fully Paid",)

SUBSCRIPTION_REQUIRED = (
    "Lipia kadi za tukio hili kwanza, kwenye kichupo cha Subscription & Gate. Kabla ya hapo unaweza "
    "kuunda tukio na kupakia muundo wa kadi tu. / Pay for this event's cards first, under the "
    "Subscription & Gate tab. Until then you can only create the event and upload the card design."
)
FIXED_CARD_ADMITS = {"SINGLE": 1, "VIP": 1, "DOUBLE": 2}
DEFAULT_TABLE_SIZE = 10


class CardLimitError(frappe.ValidationError):
    pass


def card_admits(card_type: str | None, admits=None, table_size=None) -> int:
    """How many people one card lets in at the gate. TABLE cards keep their own
    size when set (2 or more), otherwise use the Occasion's table size."""
    fixed = FIXED_CARD_ADMITS.get(card_type or "SINGLE")
    if fixed:
        return fixed
    if cint(admits) >= 2:
        return cint(admits)
    return max(cint(table_size) or DEFAULT_TABLE_SIZE, 1)


def get_permission_query_conditions(user=None):
    """Occasion list/report views: everyone sees only the Occasions they created
    (or that a System Manager assigned to them); staff see all."""
    if not user:
        user = frappe.session.user
    if is_staff(user):
        return ""
    user = frappe.db.escape(user)
    return f"(`tabOccasion`.`owner` = {user} or `tabOccasion`.`assigned_user` = {user})"


def has_permission(doc, ptype="read", user=None):
    """Direct Occasion access: only its creator or assigned user, unless staff.
    Creating is allowed by role (Occasion Manager) — validate() then assigns
    the new Occasion to its creator."""
    if not user:
        user = frappe.session.user
    if is_staff(user):
        return True
    if ptype == "create" or doc.is_new():
        return True
    # Always check the stored values: on frm.call() the doc is rebuilt from the
    # browser's copy, where permlevel-1 assigned_user was stripped (so it comes
    # back as None) and owner/assigned_user could be spoofed by the client.
    owner, assigned_user = frappe.db.get_value("Occasion", doc.name, ["owner", "assigned_user"]) or (None, None)
    return user in (owner, assigned_user)


class Occasion(Document):

    def validate(self):
        # assigned_user is permlevel 1: Frappe resets it for non-staff *after*
        # before_insert, so the creator is assigned here instead.
        if self.is_new() and not self.assigned_user and not is_staff():
            self.assigned_user = frappe.session.user
        if not self.gate_pin:
            self.gate_pin = "".join(secrets.choice(string.digits) for _digit in range(6))

        self._assert_access_for_new_rows()
        self._compute_budget()
        self._compute_contributions()
        for contributor in self.contributors:
            if not contributor.guest_code:
                contributor.guest_code = self._generate_unique_code()
            contributor.admits = card_admits(contributor.card_type, contributor.admits, self.table_size)

    def before_save(self):
        if not self.is_new() and self.has_value_changed("card_design"):
            # Design cleared or replaced: drop the old preview so it can't outlive it
            self.card_preview_image = self.card_design
        elif self.card_design and not self.card_preview_image:
            # Sane default until the layout designer generates a styled composite
            self.card_preview_image = self.card_design

        base = frappe.utils.get_url().rstrip("/")
        for contributor in self.contributors:
            if contributor.guest_code and not contributor.download_url:
                contributor.download_url = f"{base}/invitee/download/occasion-card/{contributor.guest_code}"

    def _assert_access_for_new_rows(self):
        """Contributors and budget lines need a card subscription. Rows that are
        already saved stay editable, so older events keep working."""
        if self.has_full_access():
            return
        for table, doctype in (("contributors", "Occasion Contributor"), ("budget_items", "Occasion Budget Item")):
            saved = set() if self.is_new() else set(
                frappe.get_all(doctype, filters={"parent": self.name, "parenttype": "Occasion"}, pluck="name")
            )
            if any(row.name not in saved for row in self.get(table)):
                frappe.throw(_(SUBSCRIPTION_REQUIRED), title=_("Subscription required"))

    def _generate_unique_code(self):
        in_this_doc = {c.guest_code for c in self.contributors if c.guest_code}
        for _attempt in range(100):
            code = ''.join(random.choices(string.digits, k=6))
            if code not in in_this_doc and not frappe.db.exists("Occasion Contributor", {"guest_code": code}):
                return code
        frappe.throw("Could not generate a unique guest code. Please try again.")

    # ------------------------------------------------------------ budget & contributions

    def _compute_budget(self):
        self.total_budget = sum(flt(row.budgeted_amount) for row in self.budget_items)
        self.total_spent = sum(flt(row.actual_amount) for row in self.budget_items)

    def _compute_contributions(self):
        existing_ids = [c.contributor_id for c in self.contributors if c.contributor_id]
        duplicates = {cid for cid in existing_ids if existing_ids.count(cid) > 1}
        if duplicates:
            frappe.throw(_("Duplicate contributor ID(s): {0}").format(", ".join(sorted(duplicates))))

        next_number = max(
            (cint(cid[len(CONTRIBUTOR_ID_PREFIX):]) for cid in existing_ids if cid.startswith(CONTRIBUTOR_ID_PREFIX)),
            default=0,
        ) + 1
        for contributor in self.contributors:
            if not contributor.contributor_id:
                contributor.contributor_id = f"{CONTRIBUTOR_ID_PREFIX}{next_number:04d}"
                next_number += 1

        for contributor in self.contributors:
            contributor.paid_amount = max(flt(contributor.paid_amount), 0)
            pledged = flt(contributor.pledged_amount)
            contributor.balance = max(pledged - contributor.paid_amount, 0)
            if contributor.paid_amount <= 0:
                contributor.payment_status = "Not Paid"
            elif contributor.paid_amount >= pledged:
                # Includes a payment with no pledge recorded: nothing left to pay.
                contributor.payment_status = "Fully Paid"
            else:
                contributor.payment_status = "Partially Paid"

        self.total_pledged = sum(flt(c.pledged_amount) for c in self.contributors)
        self.total_collected = sum(flt(c.paid_amount) for c in self.contributors)
        self.outstanding_pledges = sum(flt(c.balance) for c in self.contributors)
        self.funding_gap = flt(self.total_budget) - flt(self.total_collected)

    @frappe.whitelist()
    def import_contributors(self, file_url: str):
        """Add contributors from an uploaded Excel/CSV that follows the template.
        Matches existing contributors by phone first, then by name (case-insensitive)
        for rows without a phone, so re-importing the same file doesn't create duplicates."""
        self.check_permission("write")
        rows = _read_spreadsheet(file_url, self)
        if not rows:
            frappe.throw(_("The file is empty."))

        header = [str(h or "").strip().lower() for h in rows[0]]
        col = {key: _find_column(header, aliases) for key, aliases in IMPORT_COLUMNS.items()}
        if col["name"] is None:
            frappe.throw(_("The file must have a 'Name' column. Download the template to see the expected columns."))

        by_phone = {normalize_phone(c.phone): c for c in self.contributors if c.phone}
        by_name = {c.contributor_name.strip().lower(): c for c in self.contributors}
        added, updated, skipped = 0, 0, []
        for line_no, row in enumerate(rows[1:], start=2):
            value = lambda key: (row[col[key]] if col[key] is not None and col[key] < len(row) else None)  # noqa: E731
            name = str(value("name") or "").strip()
            if not name:
                if any(cell not in (None, "") for cell in row):
                    skipped.append(_("Row {0}: missing name").format(line_no))
                continue
            phone = str(value("phone") or "").strip()
            if phone.endswith(".0"):  # Excel turns 0712... into 712345678.0
                phone = phone[:-2]
            try:
                pledged = flt(value("pledged") or 0)
                paid_so_far = flt(value("paid") or 0)
            except Exception:
                skipped.append(_("Row {0}: amounts must be numbers").format(line_no))
                continue
            card_type = str(value("card_type") or "SINGLE").strip().upper()
            if card_type not in CARD_TYPES:
                card_type = "SINGLE"

            existing = by_phone.get(normalize_phone(phone)) if phone else by_name.get(name.lower())
            if existing:
                existing.contributor_name = name
                if phone and not existing.phone:
                    existing.phone = phone
                    by_phone[normalize_phone(phone)] = existing
                if pledged:
                    existing.pledged_amount = pledged
                if paid_so_far:
                    existing.paid_amount = paid_so_far
                existing.card_type = card_type
                updated += 1
                continue

            contributor = self.append("contributors", {
                "contributor_name": name,
                "phone": phone,
                "pledged_amount": pledged,
                "paid_amount": max(paid_so_far, 0),
                "card_type": card_type,
            })
            if phone:
                by_phone[normalize_phone(phone)] = contributor
            by_name[name.lower()] = contributor
            added += 1

        self.save()
        return {"added": added, "updated": updated, "skipped": skipped}

    # ------------------------------------------------------------ subscription & sending

    def paid_guest_capacity(self) -> int:
        """Guests covered by approved (submitted) card subscriptions for this Occasion."""
        if self.is_new():
            return 0
        return cint(frappe.db.sql(
            "select coalesce(sum(number_of_guests), 0) from `tabOccasion Subscription` "
            "where occasion=%s and docstatus=1",
            self.name,
        )[0][0])

    def manager(self) -> str:
        return self.assigned_user or self.owner or frappe.session.user

    def subscription_active(self) -> bool:
        """An approved card subscription, or free access a System Manager gave
        the Occasion's manager. Doesn't depend on who is logged in, so the
        scheduler can use it too."""
        return bool(self.paid_guest_capacity()) or has_free_access(self.manager())

    def has_full_access(self) -> bool:
        return is_staff() or self.subscription_active()

    def cards_issued(self) -> int:
        return sum(1 for c in self.contributors if c.card_image)

    def can_issue_card(self, contributor) -> bool:
        """Regenerating an existing card is always fine; a new card needs room
        in the approved subscription (staff are exempt)."""
        if contributor.card_image or is_staff() or has_free_access(self.manager()):
            return True
        return self.cards_issued() < self.paid_guest_capacity()

    def select_guests(self, statuses=None) -> list:
        """Contributors whose payment status is one of `statuses` (default:
        fully paid only) — the recipients of bulk card generation/sending."""
        statuses = frappe.parse_json(statuses) if isinstance(statuses, str) else statuses
        wanted = {s for s in (statuses or DEFAULT_SEND_STATUSES) if s in PAYMENT_STATUSES}
        return [c for c in self.contributors if c.payment_status in wanted]

    def assert_can_send(self):
        """Card generation and every outgoing message need an approved card
        subscription (staff are exempt) and, for managers, accepted Terms."""
        from orion_card.legal import assert_terms_accepted

        assert_terms_accepted()
        if not self.has_full_access():
            frappe.throw(_(SUBSCRIPTION_REQUIRED), title=_("Subscription required"))

    @frappe.whitelist()
    def get_billing_status(self):
        from orion_card.utils import credits
        from orion_card.utils.invites import INVITATION, REMINDER, message_limit

        payer = self.assigned_user or frappe.session.user
        pending = frappe.get_all(
            "Occasion Subscription",
            filters={"occasion": self.name, "docstatus": 0},
            fields=["name", "number_of_guests", "subscription_price"],
        )
        return {
            "capacity": self.paid_guest_capacity(),
            "guests": len(self.contributors),
            "cards_issued": self.cards_issued(),
            "pending_requests": pending,
            "balances": credits.get_balances(payer),
            "is_staff": is_staff(),
            "full_access": self.has_full_access(),
            # Free access is never named to the manager: their form just shows unlimited cards.
            "unlimited_cards": has_free_access(self.manager()),
            "gate_pin": self.gate_pin,
            "allow_credit_purchase": credits.purchase_enabled(),
            "contact": credits.support_contact(),
            "message_limits": {t: message_limit(t) for t in (INVITATION, REMINDER)},
        }

    @frappe.whitelist()
    def request_subscription(self, number_of_guests: int | None = None):
        """Occasion Manager asks to pay for cards; a System Manager approves by submitting."""
        self.check_permission("write")
        number_of_guests = cint(number_of_guests) or max(len(self.contributors) - self.paid_guest_capacity(), 0)
        if number_of_guests <= 0:
            frappe.throw(_("Enter how many guest cards you need."))
        if frappe.db.exists("Occasion Subscription", {"occasion": self.name, "docstatus": 0}):
            frappe.throw(_("A subscription request for this occasion is already waiting for approval."))

        user = self.assigned_user or frappe.session.user
        user_doc = frappe.get_doc("User", user)
        subscription = frappe.get_doc({
            "doctype": "Occasion Subscription",
            "applicant_name": user_doc.full_name or user,
            "email": user_doc.email,
            # The Phone field only accepts international format (+255...).
            "phone": ("+" + normalize_phone(user_doc.mobile_no)) if user_doc.mobile_no else None,
            "user": user,
            "occasion": self.name,
            "occasion_date": self.occasion_date,
            "number_of_guests": number_of_guests,
            "status": "Pending",
        })
        subscription.flags.requested_from_occasion = True
        subscription.insert(ignore_permissions=True)
        return {"name": subscription.name, "price": subscription.subscription_price}

    def issue_card(self, contributor):
        """Compose (or recompose) one contributor's card, within the subscription."""
        from orion_card.utils.card_composer import compose_card

        if not self.can_issue_card(contributor):
            # Raised, not thrown: bulk runs collect it per row instead of popping a dialog each time.
            raise CardLimitError(_("beyond your subscription of {0} cards — request more cards first.").format(
                self.paid_guest_capacity()
            ))
        if not contributor.guest_code:
            contributor.guest_code = self._generate_unique_code()
        compose_card(self, contributor)
        frappe.db.set_value("Occasion Contributor", contributor.name, {
            "guest_code": contributor.guest_code,
            "card_image": contributor.card_image,
            "download_url": contributor.download_url,
        }, update_modified=False)

    @frappe.whitelist()
    def generate_all_cards(self, statuses=None):
        """Bulk generate QR + composed card images for the selected contributors"""
        self.check_permission("write")
        self.assert_can_send()
        results = {"success": 0, "failed": 0, "errors": []}
        for contributor in self.select_guests(statuses):
            try:
                self.issue_card(contributor)
                results["success"] += 1
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"{contributor.contributor_name}: {e}")
        self.save()
        return results

    def guests_to_invite(self, channel: str, statuses=None, resend=False) -> list:
        """Selected contributors with a phone who can get this channel's
        invitation: those not invited yet, or with `resend` everyone still
        under the per-guest limit."""
        from orion_card.utils.invites import INVITATION, message_limit, sent_counts

        counts = sent_counts(self.name, channel, INVITATION)
        most = message_limit(INVITATION) if cint(resend) else 1
        return [c for c in self.select_guests(statuses) if c.phone and counts.get(c.guest_code, 0) < most]

    def _send_all(self, channel: str, send_fn, statuses=None, resend=False) -> dict:
        from orion_card.utils.credits import InsufficientCreditsError, support_contact

        self.check_permission("write")
        self.assert_can_send()
        results = {"success": 0, "failed": 0, "errors": [], "credits_out": False}
        for contributor in self.guests_to_invite(channel, statuses, resend):
            try:
                if not contributor.card_image:
                    self.issue_card(contributor)
                send_fn(self, contributor)
                results["success"] += 1
            except InsufficientCreditsError as e:
                results["failed"] += 1
                results["errors"].append(str(e))
                results["credits_out"] = True
                break
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"{contributor.contributor_name}: {e}")
        if results["credits_out"]:
            results["contact"] = support_contact()
        return results

    @frappe.whitelist()
    def send_all_whatsapp(self, statuses=None, resend=0):
        """Send WhatsApp invitations to the selected contributors not invited yet
        (with `resend`, also again to those under the per-guest limit)."""
        from orion_card.api.whatsapp import send_invitation
        return self._send_all("WhatsApp", send_invitation, statuses, resend)

    @frappe.whitelist()
    def send_all_sms(self, statuses=None, resend=0):
        """Send SMS invitations to the selected contributors not invited yet
        (with `resend`, also again to those under the per-guest limit)."""
        from orion_card.api.sms import send_invitation
        return self._send_all("SMS", send_invitation, statuses, resend)

    @frappe.whitelist()
    def get_invited_count(self) -> int:
        """Count of distinct guests who have received at least one WhatsApp/SMS invite"""
        rows = frappe.db.sql(
            "SELECT COUNT(DISTINCT guest_code) FROM `tabOccasion Guest Invite Log` "
            "WHERE occasion = %s AND success = 1 AND message_type = 'Invitation'",
            self.name,
        )
        return rows[0][0] if rows else 0

    @frappe.whitelist()
    def get_timeseries(self) -> dict:
        """Cumulative series for the statistics line charts: contributions
        collected (by the day Paid Amount was raised), guests invited (first successful
        invitation per guest, by day) and gate arrivals (by check-in time)."""
        self.check_permission("read")

        collected = self._collected_by_day()

        first_invite = frappe.db.sql(
            """
            select min(sent_at) from `tabOccasion Guest Invite Log`
            where occasion=%s and success=1 and message_type='Invitation' and guest_code is not null
            group by guest_code
            """,
            self.name,
        )
        invited = defaultdict(int)
        for (sent_at,) in first_invite:
            if sent_at:
                invited[str(getdate(sent_at))] += 1

        check_ins = sorted(
            frappe.utils.get_datetime(c.check_in_time) for c in self.contributors if c.checked_in and c.check_in_time
        )
        arrivals = defaultdict(int)
        # Arrivals happen within hours on the day: bucket by 15 minutes then;
        # by day when check-ins span several days (re-entry, multi-day events).
        same_day = check_ins and check_ins[0].date() == check_ins[-1].date()
        for moment in check_ins:
            if same_day:
                key = moment.replace(minute=moment.minute - moment.minute % 15, second=0, microsecond=0)
                arrivals[key.strftime("%H:%M")] += 1
            else:
                arrivals[str(moment.date())] += 1

        def cumulative(buckets):
            total, points = 0, []
            for key in sorted(buckets):
                total += buckets[key]
                points.append({"x": key, "y": total})
            return points

        return {
            "collected": cumulative(collected),
            "invited": cumulative(invited),
            "arrivals": cumulative(arrivals),
            "arrivals_by_time": bool(same_day),
            "guests": len(self.contributors),
            "pledged": flt(self.total_pledged),
        }

    def _collected_by_day(self) -> dict:
        """Money collected per day, from the Paid Amount changes in this
        Occasion's version history. Whatever the history can't explain (amounts
        entered when the Occasion was created, or before tracking) is put on
        the creation day, so the series always ends at Total Collected."""
        collected = defaultdict(float)
        versions = frappe.get_all(
            "Version",
            filters={"ref_doctype": "Occasion", "docname": self.name},
            fields=["creation", "data"],
            order_by="creation asc",
        )
        for version in versions:
            data = frappe.parse_json(version.data or "{}") or {}
            day = str(getdate(version.creation))
            for table, _idx, _row, changes in data.get("row_changed") or []:
                if table != "contributors":
                    continue
                for field, old, new in changes:
                    if field == "paid_amount":
                        collected[day] += flt(new) - flt(old)
            for table, row in data.get("added") or []:
                if table == "contributors":
                    collected[day] += flt((row or {}).get("paid_amount"))
            for table, row in data.get("removed") or []:
                if table == "contributors":
                    collected[day] -= flt((row or {}).get("paid_amount"))
        unexplained = flt(self.total_collected) - sum(collected.values())
        if abs(unexplained) >= 0.01:
            collected[str(getdate(self.creation))] += unexplained
        return {day: amount for day, amount in collected.items() if abs(amount) >= 0.01}


@frappe.whitelist()
def get_new_occasion_access() -> bool:
    """Whether the current user may add contributors before the first save."""
    return is_staff() or has_free_access(frappe.session.user)


# ---------------------------------------------------------------- spreadsheet helpers

IMPORT_COLUMNS = {
    "name": ("name", "jina", "contributor", "contributor name", "mchangiaji"),
    "phone": ("phone", "simu", "namba ya simu", "phone number", "mobile"),
    "pledged": ("pledge", "pledged", "ahadi", "pledged amount"),
    "card_type": ("card type", "aina ya kadi", "kadi", "card"),
    "paid": ("paid so far", "paid", "amelipa", "imelipwa", "paid amount"),
}
TEMPLATE_HEADER = ["Name", "Phone", "Pledge", "Card Type", "Paid so far"]


def _find_column(header, aliases):
    for i, h in enumerate(header):
        if h in aliases:
            return i
    return None


def _read_spreadsheet(file_url: str, occasion) -> list:
    file_doc = frappe.get_doc("File", {"file_url": file_url})
    attached_here = file_doc.attached_to_doctype == "Occasion" and file_doc.attached_to_name == occasion.name
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


@frappe.whitelist()
def download_contributor_template():
    from frappe.utils.xlsxutils import build_xlsx_response

    build_xlsx_response(
        [TEMPLATE_HEADER, ["Mfano: Juma Ali", "0712345678", 100000, "SINGLE", 50000]],
        "contributors_template",
    )


@frappe.whitelist()
def export_contributors(occasion: str):
    from frappe.utils.xlsxutils import build_xlsx_response

    doc = frappe.get_doc("Occasion", occasion)
    doc.check_permission("read")
    data = [["ID", "Name", "Phone", "Card Type", "Pledge", "Paid", "Balance", "Status", "Guest Code"]]
    for c in doc.contributors:
        data.append([
            c.contributor_id, c.contributor_name, c.phone, c.card_type, flt(c.pledged_amount),
            flt(c.paid_amount), flt(c.balance), c.payment_status, c.guest_code or "",
        ])
    build_xlsx_response(data, frappe.scrub(f"{doc.name} contributors"))
