import frappe
from frappe import _
from frappe.model.document import Document

from orion_card.permissions import is_staff


def get_permission_query_conditions(user=None):
	"""Restrict Occasion Subscription list/report views to the applicant's own record, unless staff."""
	if not user:
		user = frappe.session.user
	if is_staff(user):
		return ""
	return f"`tabOccasion Subscription`.`user` = {frappe.db.escape(user)}"


def has_permission(doc, ptype="read", user=None):
	"""Restrict direct Occasion Subscription access to the applicant, unless staff."""
	if not user:
		user = frappe.session.user
	if is_staff(user):
		return True
	return doc.user == user


class OccasionSubscription(Document):

	def validate(self):
		self._apply_pricing()

	def _apply_pricing(self):
		"""Graduated card pricing from OrionCard Settings. A top-up may keep the
		rate of the last paid card for up to 20% (configurable) of the cards
		already paid; see orion_card.utils.pricing."""
		from orion_card.utils.pricing import public_quote, quote_for_occasion

		if frappe.utils.cint(self.number_of_guests) <= 0:
			frappe.throw(_("Number of guests must be at least 1."))
		if self.payment_status == "Paid" and self.subscription_price:
			# Keep the price the customer actually paid, even if tiers changed since.
			return
		q = quote_for_occasion(self.number_of_guests, self.occasion, exclude=self.name)
		self.locked_rate_cards = q["locked_cards"]
		self.price_lines = frappe.as_json(public_quote(q)["lines"])
		self.subscription_price = q["price"]
		self.sms_credits_included = q["sms_credits"]
		self.whatsapp_credits_included = q["whatsapp_credits"]
		self.price_breakdown = "\n".join(
			f"Cards {line['from_card']}–{line['to_card']}: {line['cards']} × "
			f"{frappe.utils.fmt_money(line['price_per_card'], precision=0, currency='TZS')}"
			for line in q["lines"]
		)
		# Internal: never shown to customers (permlevel 1, System Manager only).
		self.profit_amount = q["profit"]
		self.message_budget = q["price"] - q["profit"]

	def on_submit_grant_credits(self):
		"""Approval adds the subscription's included SMS / WhatsApp credits to the customer."""
		from orion_card.utils import credits

		if self.credits_granted or not self.user:
			return
		for channel, amount in (("SMS", self.sms_credits_included), ("WhatsApp", self.whatsapp_credits_included)):
			if frappe.utils.cint(amount) > 0:
				credits.add(self.user, channel, amount, transaction_type="Card Subscription",
							reference_doctype=self.doctype, reference_name=self.name)
		self.db_set("credits_granted", 1)

	def on_cancel(self):
		"""Take back the included credits. Fails if the customer already used them."""
		from orion_card.utils import credits

		if not self.credits_granted or not self.user:
			return
		for channel, amount in (("SMS", self.sms_credits_included), ("WhatsApp", self.whatsapp_credits_included)):
			if frappe.utils.cint(amount) > 0:
				credits.add(self.user, channel, -frappe.utils.cint(amount), transaction_type="Card Subscription",
							reference_doctype=self.doctype, reference_name=self.name, remarks="Subscription cancelled")
		self.db_set("credits_granted", 0)

	def before_submit(self):
		"""User creation is deliberately deferred until a System Manager submits
		this Subscription (i.e. approves it) — not at web-form insert time."""
		if not self.user:
			self.user = self._get_or_create_user()

	def _get_or_create_user(self) -> str:
		if frappe.db.exists("User", self.email):
			user = frappe.get_doc("User", self.email)
			existing_roles = [r.role for r in user.roles]
			missing_roles = [r for r in ("Occasion Manager", "Desk User") if r not in existing_roles]
			if missing_roles:
				user.append_roles(*missing_roles)
				user.save(ignore_permissions=True)
			return user.name

		user = frappe.get_doc({
			"doctype": "User",
			"email": self.email,
			"first_name": self.applicant_name,
			"send_welcome_email": 1,
			"user_type": "System User",
			# "Occasion Manager" sees only Occasions assigned to them (and their
			# own Subscriptions / credits) — never other users' data or reports.
			# "Desk User" is set explicitly (rather than relying on
			# Role.desk_access propagation) so desk login works regardless of
			# that background sync.
			"roles": [{"role": "Occasion Manager"}, {"role": "Desk User"}],
		})
		user.insert(ignore_permissions=True)
		return user.name

	@frappe.whitelist()
	def create_occasion(self) -> str:
		"""Whitelisted: create a new Occasion for this applicant, linked via
		assigned_user to the User created on submit. Shown as a form button
		once the User exists and no Occasion is linked yet."""
		if self.docstatus != 1:
			frappe.throw("Submit this Subscription before creating an Occasion.")
		if not self.user:
			frappe.throw("No User is linked to this Subscription yet.")
		if self.occasion:
			frappe.throw(f"An Occasion ({self.occasion}) is already linked to this Subscription.")

		occasion = frappe.get_doc({
			"doctype": "Occasion",
			"occasion_name": f"{self.applicant_name}'s Occasion ({frappe.utils.now_datetime().strftime('%Y%m%d%H%M%S')})",
			"couple_names": self.applicant_name,
			"occasion_date": self.occasion_date,
			"occasion_time": "TBD",
			"venue_name": "TBD",
			"assigned_user": self.user,
		})
		occasion.insert(ignore_permissions=True)

		# db_set (not self.save()) so this works cleanly on a submitted document
		# without fighting the submit-lifecycle's field lock/hook routing.
		self.db_set("occasion", occasion.name, update_modified=True)
		self._link_occasion_to_applicant()

		return occasion.name

	def on_submit(self):
		"""Approving adds the included credits and, for a Subscription a manager
		requested from their own Occasion (request_subscription), unlocks card
		generation/sending."""
		from orion_card.receipts import queue_receipt

		self.on_submit_grant_credits()
		if self.occasion:
			self.db_set("status", "Active")
		queue_receipt(self.doctype, self.name)

	def on_update(self):
		"""Fallback for a draft doc whose occasion link was set directly
		(e.g. by a System Manager editing the field by hand) rather than via
		create_occasion() — the normal path for a submitted Subscription.
		Skipped for Subscriptions a manager requests from their own Occasion:
		those are already linked and only become Active once submitted."""
		if self.flags.requested_from_occasion:
			return
		before = self.get_doc_before_save()
		occasion_newly_linked = self.occasion and (not before or not before.occasion)
		if occasion_newly_linked:
			self._link_occasion_to_applicant()

	def _link_occasion_to_applicant(self):
		frappe.db.set_value("Occasion", self.occasion, "assigned_user", self.user)
		frappe.db.set_value("Occasion Subscription", self.name, "status", "Active")

		occasion_name = frappe.db.get_value("Occasion", self.occasion, "occasion_name")
		base = frappe.utils.get_url().rstrip("/")
		occasion_link = f"{base}/app/occasion/{self.occasion}"

		# Linking the Occasion (assigned_user + status, above) must stick even if
		# no outgoing Email Account is configured yet — don't let a notification
		# failure roll back the actual linking.
		try:
			frappe.sendmail(
				recipients=[self.email],
				subject=f"Your occasion '{occasion_name}' is ready",
				message=(
					f"Habari {self.applicant_name},<br><br>"
					f"Your occasion <b>{occasion_name}</b> has been set up. "
					f"You can manage its guests and cards here:<br>"
					f"<a href='{occasion_link}'>{occasion_link}</a>"
				),
			)
		except Exception:
			frappe.log_error(
				title=f"Failed to email Occasion link to {self.email}",
				message=frappe.get_traceback(),
			)
