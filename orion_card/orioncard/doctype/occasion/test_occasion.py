# Copyright (c) 2026, Innocent P Metumba and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = ["User"]

MANAGER = "occasion.manager.test@example.com"
OTHER_MANAGER = "other.manager.test@example.com"
STAFF = "system.staff.test@example.com"


def make_user(email, roles):
	if not frappe.db.exists("User", email):
		frappe.get_doc({
			"doctype": "User",
			"email": email,
			"first_name": email.split("@")[0],
			"user_type": "System User",
			"send_welcome_email": 0,
			"roles": [{"role": r} for r in roles],
		}).insert(ignore_permissions=True)
	return email


def make_occasion(owner=MANAGER, **kwargs):
	frappe.set_user(owner)
	doc = frappe.get_doc({
		"doctype": "Occasion",
		"occasion_name": kwargs.pop("occasion_name", f"Test Occasion {frappe.generate_hash(length=8)}"),
		"couple_names": "Amina & Baraka",
		"occasion_date": frappe.utils.add_days(frappe.utils.today(), 30),
		"occasion_time": "Saa 12:00 jioni",
		"venue_name": "Diamond Jubilee",
		**kwargs,
	})
	doc.insert()
	frappe.set_user("Administrator")
	return doc


TIER_FIELDS = ("from_card", "to_card", "price_per_card", "profit_per_card",
			   "sms_credits_per_card", "whatsapp_credits_per_card")
# Prices that rise after card 100, so top-ups have an earlier rate worth keeping.
RISING_TIERS = ((1, 100, 900, 400, 10, 3), (101, 0, 1200, 400, 14, 6))


def set_card_tiers(tiers):
	"""Replace the Card Price Tiers; returns the previous ones for cleanup."""
	settings = frappe.get_single("OrionCard Settings")
	previous = [tuple(row.get(f) for f in TIER_FIELDS) for row in settings.card_price_tiers]
	settings.set("card_price_tiers", [dict(zip(TIER_FIELDS, tier)) for tier in tiers])
	settings.flags.ignore_permissions = True
	settings.save()
	return previous


def approve_subscription(occasion, guests=10):
	sub = frappe.get_doc({
		"doctype": "Occasion Subscription",
		"applicant_name": "Test",
		"email": occasion.assigned_user,
		"user": occasion.assigned_user,
		"occasion": occasion.name,
		"occasion_date": occasion.occasion_date,
		"number_of_guests": guests,
	})
	sub.flags.requested_from_occasion = True
	sub.insert(ignore_permissions=True)
	sub.submit()
	return sub


class IntegrationTestOccasion(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		make_user(MANAGER, ["Occasion Manager", "Desk User"])
		make_user(OTHER_MANAGER, ["Occasion Manager", "Desk User"])
		make_user(STAFF, ["System Manager", "Desk User"])
		# Managers must have accepted the current Terms to send.
		from orion_card.legal import record_acceptance

		for user in (MANAGER, OTHER_MANAGER):
			record_acceptance(user, "Sign-up")

	def tearDown(self):
		frappe.set_user("Administrator")

	# ------------------------------------------------------------ ownership & permissions

	def test_creator_is_assigned_and_isolated(self):
		occasion = make_occasion()
		self.assertEqual(occasion.assigned_user, MANAGER)
		self.assertEqual(len(occasion.gate_pin), 6)

		frappe.set_user(OTHER_MANAGER)
		self.assertFalse(frappe.has_permission("Occasion", "read", doc=occasion.name))
		self.assertNotIn(occasion.name, frappe.get_list("Occasion", pluck="name"))

		frappe.set_user(STAFF)
		self.assertTrue(frappe.has_permission("Occasion", "read", doc=occasion.name))
		self.assertIn(occasion.name, frappe.get_list("Occasion", pluck="name"))

	def test_manager_can_open_own_occasion_form(self):
		from frappe.desk.form.load import getdoc

		occasion = make_occasion()
		frappe.set_user(STAFF)
		# Assigned (not created) by the manager: access must come from assigned_user.
		frappe.db.set_value("Occasion", occasion.name, {"owner": STAFF, "assigned_user": MANAGER})
		frappe.set_user(MANAGER)
		getdoc("Occasion", occasion.name)
		self.assertTrue(frappe.response.docinfo.permissions.get("write"))

	# ------------------------------------------------------------ subscription gate & free access

	def test_without_subscription_only_event_and_design_are_editable(self):
		occasion = make_occasion()
		frappe.set_user(MANAGER)
		doc = frappe.get_doc("Occasion", occasion.name)
		doc.venue_name = "Mlimani City"
		doc.card_design = "/files/design.png"
		doc.save()  # event details and the card design are allowed

		doc.append("contributors", {"contributor_name": "Juma", "phone": "0712000061"})
		self.assertRaises(frappe.ValidationError, doc.save)
		doc.reload()
		doc.append("budget_items", {"category": "Ukumbi", "budgeted_amount": 1000})
		self.assertRaises(frappe.ValidationError, doc.save)
		doc.reload()
		self.assertRaises(frappe.ValidationError, doc.generate_all_cards)
		self.assertRaises(frappe.ValidationError, doc.send_all_sms)
		self.assertFalse(doc.get_billing_status()["full_access"])

		# A new event can't start with contributors either.
		self.assertRaises(frappe.ValidationError, frappe.get_doc({
			"doctype": "Occasion", "occasion_name": f"Gated {frappe.generate_hash(length=6)}",
			"couple_names": "A & B", "occasion_date": frappe.utils.add_days(frappe.utils.today(), 30),
			"occasion_time": "Saa 2", "venue_name": "Ukumbi",
			"contributors": [{"contributor_name": "Juma"}],
		}).insert)

		frappe.set_user("Administrator")
		approve_subscription(occasion)
		frappe.set_user(MANAGER)
		doc = frappe.get_doc("Occasion", occasion.name)
		doc.append("contributors", {"contributor_name": "Juma", "phone": "0712000061"})
		doc.append("budget_items", {"category": "Ukumbi", "budgeted_amount": 1000})
		doc.save()
		self.assertTrue(doc.get_billing_status()["full_access"])

	def test_rows_saved_before_the_gate_stay_editable(self):
		occasion = make_occasion()
		occasion.append("contributors", {"contributor_name": "Zamani", "pledged_amount": 1000})
		occasion.save()  # as Administrator, like data from before the gate

		frappe.set_user(MANAGER)
		doc = frappe.get_doc("Occasion", occasion.name)
		doc.contributors[0].paid_amount = 400
		doc.save()
		self.assertEqual(doc.contributors[0].payment_status, "Partially Paid")

	def test_free_access_and_complimentary_credits(self):
		from orion_card.utils.credits import get_balance, grant_free_access

		user = make_user("free.access.test@example.com", ["Occasion Manager", "Desk User"])
		from orion_card.legal import record_acceptance

		record_acceptance(user, "Sign-up")
		frappe.set_user(MANAGER)
		self.assertRaises(frappe.PermissionError, grant_free_access, user, 10, 5)

		frappe.set_user("Administrator")
		sms_before, wa_before = get_balance(user, "SMS"), get_balance(user, "WhatsApp")
		grant_free_access(user, sms_credits=10, whatsapp_credits=5, note="Mteja wa majaribio")
		self.assertEqual(get_balance(user, "SMS"), sms_before + 10)
		self.assertEqual(get_balance(user, "WhatsApp"), wa_before + 5)
		self.assertEqual(
			frappe.db.count("Credit Transaction", {"user": user, "transaction_type": "Complimentary"}), 2
		)

		try:
			occasion = make_occasion(owner=user)
			frappe.set_user(user)
			doc = frappe.get_doc("Occasion", occasion.name)
			for i in range(3):
				doc.append("contributors", {"contributor_name": f"Bure {i}", "phone": f"07120007{i:02d}", "paid_amount": 100})
			doc.save()
			status = doc.get_billing_status()
			self.assertTrue(status["full_access"])
			self.assertTrue(status["unlimited_cards"])
			self.assertEqual(status["capacity"], 0, "no subscription was bought")

			# No card limit without a subscription, and sending works on the free credits.
			with patch("orion_card.utils.card_composer.compose_card",
					   side_effect=lambda occ, row: row.update({"card_image": "/files/x.jpg"})):
				self.assertEqual(doc.generate_all_cards()["success"], 3)
			doc.reload()
			with patch("orion_card.api.messaging._gateway_send", return_value={"success": True}):
				self.assertEqual(doc.send_all_whatsapp()["success"], 3)
			self.assertEqual(get_balance(user, "WhatsApp"), wa_before + 5 - 3)

			# Taking free access away locks new contributors again.
			frappe.set_user("Administrator")
			frappe.db.set_value("Message Credit Account", user, "free_access", 0)
			frappe.set_user(user)
			doc.reload()
			doc.append("contributors", {"contributor_name": "Baadaye"})
			self.assertRaises(frappe.ValidationError, doc.save)
		finally:
			frappe.set_user("Administrator")
			frappe.db.set_value("Message Credit Account", user, "free_access", 0)

	def test_manager_sees_only_own_occasions_and_no_other_doctypes(self):
		mine = make_occasion()
		frappe.set_user(OTHER_MANAGER)
		theirs = frappe.get_doc({
			"doctype": "Occasion", "occasion_name": f"Other {frappe.generate_hash(length=6)}",
			"couple_names": "C & D", "occasion_date": frappe.utils.add_days(frappe.utils.today(), 30),
			"occasion_time": "Saa 2 usiku", "venue_name": "Ukumbi",
		}).insert()
		self.assertEqual(theirs.owner, OTHER_MANAGER)
		self.assertIn(theirs.name, frappe.get_list("Occasion", pluck="name"))
		self.assertNotIn(mine.name, frappe.get_list("Occasion", pluck="name"))

		frappe.set_user(MANAGER)
		self.assertNotIn(theirs.name, frappe.get_list("Occasion", pluck="name"))
		self.assertFalse(frappe.has_permission("Occasion", "write", doc=theirs.name))
		for doctype in ("Occasion Subscription", "Message Credit Account", "Credit Transaction",
						"Credit Purchase", "Occasion Guest Invite Log", "Terms Acceptance", "OrionCard Settings"):
			self.assertFalse(frappe.has_permission(doctype, "read"), doctype)

	# ------------------------------------------------------------ contributions

	def test_contribution_totals_and_status(self):
		occasion = make_occasion()
		occasion.append("budget_items", {"category": "Ukumbi", "budgeted_amount": 1_000_000, "actual_amount": 400_000})
		occasion.append("contributors", {"contributor_name": "Juma", "phone": "0712000001", "pledged_amount": 100_000})
		occasion.append("contributors", {"contributor_name": "Neema", "phone": "0712000002", "pledged_amount": 200_000})
		occasion.append("contributors", {"contributor_name": "Grace", "phone": "0712000003", "pledged_amount": 50_000})
		occasion.save()

		ids = {c.contributor_id: c.contributor_name for c in occasion.contributors}
		self.assertEqual(ids, {"C-0001": "Juma", "C-0002": "Neema", "C-0003": "Grace"})
		codes = [c.guest_code for c in occasion.contributors]
		self.assertTrue(all(codes) and len(set(codes)) == 3, "every contributor gets a card code")

		# The manager types in what each contributor has paid.
		by_name = {c.contributor_name: c for c in occasion.contributors}
		by_name["Juma"].paid_amount = 100_000
		by_name["Neema"].paid_amount = 50_000
		occasion.save()

		by_name = {c.contributor_name: c for c in occasion.contributors}
		self.assertEqual(by_name["Juma"].payment_status, "Fully Paid")
		self.assertEqual(by_name["Neema"].payment_status, "Partially Paid")
		self.assertEqual(by_name["Neema"].balance, 150_000)
		self.assertEqual(by_name["Grace"].payment_status, "Not Paid")
		self.assertEqual(occasion.total_pledged, 350_000)
		self.assertEqual(occasion.total_collected, 150_000)
		self.assertEqual(occasion.outstanding_pledges, 200_000)
		self.assertEqual(occasion.total_budget, 1_000_000)
		self.assertEqual(occasion.total_spent, 400_000)
		self.assertEqual(occasion.funding_gap, 850_000)

		# Collected-over-time chart is rebuilt from the version history.
		series = occasion.get_timeseries()["collected"]
		self.assertEqual(series[-1]["y"], 150_000)

		# Paying more than pledged, or with no pledge, counts as fully paid.
		by_name["Neema"].paid_amount = 250_000
		occasion.save()
		self.assertEqual(by_name["Neema"].payment_status, "Fully Paid")
		self.assertEqual(by_name["Neema"].balance, 0)

	def test_bulk_selection_by_payment_status(self):
		occasion = make_occasion()
		occasion.append("contributors", {"contributor_name": "Full", "phone": "0712000041", "pledged_amount": 1000, "paid_amount": 1000})
		occasion.append("contributors", {"contributor_name": "Part", "phone": "0712000042", "pledged_amount": 1000, "paid_amount": 400})
		occasion.append("contributors", {"contributor_name": "None", "phone": "0712000043", "pledged_amount": 1000})
		occasion.append("contributors", {"contributor_name": "No Phone", "pledged_amount": 1000, "paid_amount": 1000})
		occasion.save()

		names = lambda rows: [c.contributor_name for c in rows]  # noqa: E731
		self.assertEqual(names(occasion.select_guests()), ["Full", "No Phone"], "fully paid by default")
		self.assertEqual(names(occasion.select_guests(["Fully Paid", "Partially Paid"])), ["Full", "Part", "No Phone"])
		self.assertEqual(names(occasion.select_guests('["Not Paid"]')), ["None"])
		self.assertEqual(names(occasion.guests_to_invite("SMS")), ["Full"], "no phone, no message")

	def test_cards_are_limited_to_the_subscription(self):
		occasion = make_occasion()
		for i in range(3):
			occasion.append("contributors", {"contributor_name": f"G{i}", "phone": f"07120005{i:02d}",
											 "pledged_amount": 1000, "paid_amount": 1000})
		occasion.save()
		approve_subscription(occasion, guests=2)

		frappe.set_user(MANAGER)
		occasion = frappe.get_doc("Occasion", occasion.name)
		with patch("orion_card.utils.card_composer.compose_card", side_effect=lambda occ, row: row.update({"card_image": "/files/x.jpg"})):
			res = occasion.generate_all_cards()
			self.assertEqual((res["success"], res["failed"]), (2, 1))
			self.assertIn("subscription of 2 cards", res["errors"][0])
			# Regenerating an existing card does not need more room.
			res = occasion.generate_all_cards()
			self.assertEqual((res["success"], res["failed"]), (2, 1))

	def test_import_contributors_from_csv_is_idempotent(self):
		occasion = make_occasion()
		content = "Name,Phone,Pledge,Card Type,Paid so far\nJuma Ali,0712000001,100000,single,40000\nNeema,0712000002,50000,VIP,0\n,,,,\n"
		file_doc = frappe.get_doc({
			"doctype": "File",
			"file_name": "contributors.csv",
			"content": content,
			"attached_to_doctype": "Occasion",
			"attached_to_name": occasion.name,
			"is_private": 1,
		}).insert(ignore_permissions=True)

		res = occasion.import_contributors(file_doc.file_url)
		self.assertEqual((res["added"], res["updated"]), (2, 0))
		occasion.reload()
		juma = next(c for c in occasion.contributors if c.contributor_name == "Juma Ali")
		self.assertEqual(juma.paid_amount, 40_000)
		self.assertEqual(juma.payment_status, "Partially Paid")
		self.assertTrue(juma.guest_code)

		res = occasion.import_contributors(file_doc.file_url)
		self.assertEqual((res["added"], res["updated"]), (0, 2))
		occasion.reload()
		self.assertEqual(len(occasion.contributors), 2)

	# ------------------------------------------------------------ pay-to-send & credits

	def test_sending_requires_subscription_and_credits(self):
		from orion_card.utils.credits import add, get_balance

		occasion = make_occasion()
		occasion.append("contributors", {"contributor_name": "Rehema", "phone": "0712000010", "card_type": "SINGLE",
										 "pledged_amount": 1000, "paid_amount": 1000, "card_image": "/files/x.jpg"})
		occasion.save()

		frappe.set_user(MANAGER)
		occasion = frappe.get_doc("Occasion", occasion.name)
		self.assertRaises(frappe.ValidationError, occasion.send_all_sms)

		frappe.set_user("Administrator")
		approve_subscription(occasion)
		add(MANAGER, "SMS", 10)
		start = get_balance(MANAGER, "SMS")

		frappe.set_user(MANAGER)
		occasion = frappe.get_doc("Occasion", occasion.name)
		with patch("orion_card.api.messaging._gateway_send", return_value={"success": True}):
			res = occasion.send_all_sms()
		self.assertEqual(res["success"], 1)
		from orion_card.api.sms import build_invitation_message
		from orion_card.utils.credits import sms_parts

		parts = sms_parts(build_invitation_message(occasion, occasion.contributors[0]))
		self.assertEqual(get_balance(MANAGER, "SMS"), start - parts)

		# Already invited: a second bulk send does nothing.
		with patch("orion_card.api.messaging._gateway_send", return_value={"success": True}):
			self.assertEqual(occasion.send_all_sms()["success"], 0)

	def test_failed_send_refunds_and_allows_retry(self):
		from orion_card.utils.credits import add, get_balance

		occasion = make_occasion()
		occasion.append("contributors", {"contributor_name": "Rehema", "phone": "0712000011", "paid_amount": 500,
										 "card_image": "/files/x.jpg"})
		occasion.save()
		approve_subscription(occasion)
		add(MANAGER, "WhatsApp", 3)
		start = get_balance(MANAGER, "WhatsApp")

		frappe.set_user(MANAGER)
		occasion = frappe.get_doc("Occasion", occasion.name)
		with patch("orion_card.api.messaging._gateway_send", side_effect=Exception("gateway down")):
			res = occasion.send_all_whatsapp()
		self.assertEqual(res["failed"], 1)
		self.assertEqual(get_balance(MANAGER, "WhatsApp"), start)

		with patch("orion_card.api.messaging._gateway_send", return_value={"success": True}):
			res = occasion.send_all_whatsapp()
		self.assertEqual(res["success"], 1, "a failed attempt must not count as already invited")
		self.assertEqual(get_balance(MANAGER, "WhatsApp"), start - 1)

	def test_whatsapp_card_image_follows_setting(self):
		from orion_card.api import messaging
		from orion_card.utils.credits import add

		occasion = make_occasion()
		occasion.append("contributors", {"contributor_name": "Picha", "phone": "0712000051", "paid_amount": 100,
										 "card_image": "/files/picha.jpg"})
		occasion.save()
		approve_subscription(occasion)
		add(MANAGER, "WhatsApp", 5)
		original = frappe.db.get_single_value("OrionCard Settings", "whatsapp_send_card_image")
		try:
			for enabled, expected in ((0, None), (1, "/files/picha.jpg")):
				frappe.db.set_single_value("OrionCard Settings", "whatsapp_send_card_image", enabled)
				frappe.db.delete("Occasion Guest Invite Log", {"occasion": occasion.name})
				frappe.set_user(MANAGER)
				doc = frappe.get_doc("Occasion", occasion.name)
				with patch.object(messaging, "_gateway_send", return_value={"success": True}) as send:
					self.assertEqual(doc.send_all_whatsapp()["success"], 1)
				frappe.set_user("Administrator")
				image_url = send.call_args.kwargs["image_url"]
				if expected:
					self.assertTrue(image_url.startswith("http") and image_url.endswith(expected), image_url)
				else:
					self.assertIsNone(image_url)
		finally:
			frappe.set_user("Administrator")
			frappe.db.set_single_value("OrionCard Settings", "whatsapp_send_card_image", original or 0)

	def test_insufficient_credits_stops_bulk_send(self):
		occasion = make_occasion(occasion_name=f"Broke {frappe.generate_hash(length=6)}")
		for i in range(3):
			occasion.append("contributors", {"contributor_name": f"G{i}", "phone": f"07120001{i:02d}",
											 "paid_amount": 100, "card_image": "/files/x.jpg"})
		occasion.save()
		approve_subscription(occasion)
		frappe.db.set_value("Message Credit Account", MANAGER, "whatsapp_balance", 1)

		frappe.set_user(MANAGER)
		occasion = frappe.get_doc("Occasion", occasion.name)
		with patch("orion_card.api.messaging._gateway_send", return_value={"success": True}) as send:
			res = occasion.send_all_whatsapp()
		self.assertEqual(res["success"], 1)
		self.assertEqual(send.call_count, 1)
		self.assertIn("credits", res["errors"][0])

	def test_sms_invitation_fits_two_parts(self):
		from orion_card.api.sms import build_invitation_message
		from orion_card.utils.credits import sms_parts

		occasion = make_occasion(
			occasion_name="Sherehe ya Kumbukumbu ya Miaka Hamsini ya Ndoa ya Mzee Abdallah na Bi. Mwanaisha 🎉",
			venue_name="Ukumbi Mkubwa wa Mikutano wa Kimataifa wa Julius Nyerere, Barabara ya Shaaban Robert",
			couple_names="Familia ya Mzee Abdallah “Babu” Mwinyimkuu",
			dress_code="Kitenge",
		)
		guest = frappe._dict(contributor_name="Mwanahawa Abdallah Mwinyimkuu Salim", card_type="DOUBLE",
							 guest_code="123456")
		text = build_invitation_message(occasion, guest)
		self.assertLessEqual(sms_parts(text), 2, text)
		self.assertIn("/k/123456", text)
		self.assertIn("Namba: 123456", text)
		self.assertNotIn("Kitenge", text, "no dress code in the SMS")
		self.assertNotIn("🎉", text)

		short = build_invitation_message(make_occasion(), frappe._dict(contributor_name="Juma", card_type="SINGLE",
																	   guest_code="654321"))
		self.assertIn("Umealikwa kwenye Test Occasion", short, "short names are kept whole")

	def test_two_invitations_per_guest_per_channel(self):
		from orion_card.api.sms import send_single
		from orion_card.utils.credits import add
		from orion_card.utils.invites import MessageLimitError

		occasion = make_occasion()
		occasion.append("contributors", {"contributor_name": "Rehema", "phone": "0712000061", "paid_amount": 100,
										 "pledged_amount": 100, "card_image": "/files/x.jpg"})
		occasion.save()
		approve_subscription(occasion)
		add(MANAGER, "SMS", 20)
		add(MANAGER, "WhatsApp", 5)

		frappe.set_user(MANAGER)
		occasion = frappe.get_doc("Occasion", occasion.name)
		with patch("orion_card.api.messaging._gateway_send", return_value={"success": True}):
			self.assertEqual(occasion.send_all_sms()["success"], 1)
			self.assertEqual(occasion.send_all_sms()["success"], 0, "already invited")
			self.assertEqual(occasion.send_all_sms(resend=1)["success"], 1, "second of 2")
			self.assertEqual(occasion.send_all_sms(resend=1)["success"], 0, "limit reached")
			self.assertRaises(MessageLimitError, send_single, occasion.name, occasion.contributors[0].guest_code)
			self.assertEqual(occasion.send_all_whatsapp(resend=1)["success"], 1, "WhatsApp has its own 2")

	def test_three_reminders_per_contributor_per_channel(self):
		from orion_card.api.reminders import send_reminders
		from orion_card.utils.credits import add

		occasion = make_occasion()
		occasion.append("contributors", {"contributor_name": "Deni", "phone": "0712000091", "pledged_amount": 50_000,
										 "paid_amount": 10_000})
		occasion.save()
		approve_subscription(occasion)
		add(MANAGER, "SMS", 30)
		add(MANAGER, "WhatsApp", 5)
		contributor_id = occasion.contributors[0].contributor_id

		frappe.set_user(MANAGER)
		with patch("orion_card.api.messaging._gateway_send", return_value={"success": True}):
			sent = [send_reminders(occasion.name, "SMS")["success"] for _attempt in range(4)]
			self.assertEqual(sent, [1, 1, 1, 0], "3 reminders, then bulk sends skip them")
			one = send_reminders(occasion.name, "SMS", contributor_ids=[contributor_id])
			self.assertEqual((one["success"], one["failed"]), (0, 1))
			self.assertIn("kikomo", one["errors"][0])
			self.assertEqual(send_reminders(occasion.name, "WhatsApp")["success"], 1, "WhatsApp has its own 3")
		self.assertFalse(frappe.get_hooks("scheduler_events").get("cron", {}).get("0 * * * *"),
						 "nothing is sent automatically")

	def test_running_out_points_to_support_contact(self):
		from orion_card.api.payments import create_purchase

		occasion = make_occasion()
		occasion.append("contributors", {"contributor_name": "Out", "phone": "0712000081", "paid_amount": 100,
										 "pledged_amount": 100, "card_image": "/files/x.jpg"})
		occasion.save()
		approve_subscription(occasion)
		frappe.db.set_value("Message Credit Account", MANAGER, "sms_balance", 0)
		settings = {f: frappe.db.get_single_value("OrionCard Settings", f) for f in ("support_phone", "allow_credit_purchase")}
		frappe.db.set_single_value("OrionCard Settings", {"support_phone": "0754 000 111", "allow_credit_purchase": 0})
		self.addCleanup(frappe.db.set_single_value, "OrionCard Settings", settings)

		frappe.set_user(MANAGER)
		occasion = frappe.get_doc("Occasion", occasion.name)
		with patch("orion_card.api.messaging._gateway_send", return_value={"success": True}):
			res = occasion.send_all_sms()
		self.assertTrue(res["credits_out"])
		self.assertEqual(res["contact"]["phone"], "0754 000 111")
		self.assertIn("0754 000 111", res["errors"][0])
		self.assertNotIn("/credits", res["errors"][0])
		self.assertRaises(frappe.ValidationError, create_purchase, "SMS", 100, accept_terms=1)

	# ------------------------------------------------------------ reminders & gate

	def test_reminder_message_and_selection(self):
		from orion_card.api.reminders import build_reminder_message, select_contributors

		occasion = make_occasion(payment_instructions="M-Pesa 0712 000 000")
		occasion.append("contributors", {"contributor_name": "Neema", "phone": "0712000002", "pledged_amount": 200_000})
		occasion.append("contributors", {"contributor_name": "Paid", "phone": "0712000003", "pledged_amount": 1000})
		occasion.append("contributors", {"contributor_name": "No Phone", "pledged_amount": 1000})
		occasion.save()
		occasion.contributors[1].paid_amount = 1000
		occasion.save()

		rows = select_contributors(occasion)
		self.assertEqual([c.contributor_name for c in rows], ["Neema"])
		message = build_reminder_message(occasion, rows[0])
		self.assertIn("Neema", message)
		self.assertIn("200,000", message)
		self.assertIn("M-Pesa 0712 000 000", message)
		self.assertIn("Amina & Baraka", message)

	def test_invitation_text_has_no_hardcoded_afternoon(self):
		from orion_card.api import sms, whatsapp

		occasion = make_occasion(occasion_time="Saa 4:00 asubuhi")
		guest = frappe._dict(contributor_name="Rehema", card_type="SINGLE", guest_code="111222")
		for module in (sms, whatsapp):
			text = module.build_invitation_message(occasion, guest)
			self.assertIn("Saa 4:00 asubuhi", text)
			self.assertNotIn("ALASIRI", text)

	def test_gate_requires_pin_for_guests(self):
		validate_guest = frappe.get_attr("orion_card.www.gate-checkin.index.validate_guest")

		occasion = make_occasion()
		occasion.append("contributors", {"contributor_name": "Rehema", "phone": "0712000020"})
		occasion.save()
		code = occasion.contributors[0].guest_code

		frappe.set_user("Guest")
		res = validate_guest(code, occasion.name)
		self.assertEqual(res["status"], "PIN Required")
		res = validate_guest(code, occasion.name, pin="000000" if occasion.gate_pin != "000000" else "111111")
		self.assertEqual(res["status"], "PIN Required")
		with patch("frappe.db.commit"):
			res = validate_guest(code, occasion.name, pin=occasion.gate_pin)
		self.assertEqual(res["status"], "Valid")
		with patch("frappe.db.commit"):
			res = validate_guest(code, occasion.name, pin=occasion.gate_pin)
		self.assertEqual(res["status"], "Already Used")

	def test_double_and_table_cards_admit_several_people(self):
		validate_guest = frappe.get_attr("orion_card.www.gate-checkin.index.validate_guest")

		occasion = make_occasion(table_size=8)
		occasion.append("contributors", {"contributor_name": "Wawili", "phone": "0712000031", "card_type": "DOUBLE"})
		occasion.append("contributors", {"contributor_name": "Meza A", "phone": "0712000032", "card_type": "TABLE"})
		occasion.append("contributors", {"contributor_name": "Meza B", "phone": "0712000033", "card_type": "TABLE", "admits": 3})
		occasion.append("contributors", {"contributor_name": "Mmoja", "phone": "0712000034", "card_type": "VIP", "admits": 5})
		occasion.save()
		self.assertEqual([c.admits for c in occasion.contributors], [2, 8, 3, 1])
		double, table_a, table_b, vip = (c.guest_code for c in occasion.contributors)

		def scan(code):
			with patch("frappe.db.commit"):
				return validate_guest(code, occasion.name, pin=occasion.gate_pin)

		self.assertEqual((scan(double)["status"], scan(double)["entered"]), ("Valid", 2))
		res = scan(double)
		self.assertEqual((res["status"], res["entered"], res["admits"]), ("Already Used", 2, 2))

		for expected in (1, 2, 3):
			self.assertEqual(scan(table_b)["entered"], expected)
		self.assertEqual(scan(table_b)["status"], "Already Used")
		self.assertEqual(scan(table_a)["admits"], 8)

		self.assertEqual(scan(vip)["status"], "Valid")
		self.assertEqual(scan(vip)["status"], "Already Used")
		self.assertEqual(frappe.db.get_value("Occasion Contributor", {"guest_code": double}, "entered_count"), 2)

	def test_new_terms_version_blocks_sending_until_accepted(self):
		from orion_card.legal import record_acceptance, terms_pending

		occasion = make_occasion()
		approve_subscription(occasion)
		original = frappe.db.get_single_value("OrionCard Settings", "terms_version")
		frappe.db.set_single_value("OrionCard Settings", "terms_version", "test-2.0")
		try:
			self.assertTrue(terms_pending(MANAGER))
			self.assertFalse(terms_pending(STAFF), "staff never need to re-accept")
			frappe.set_user(MANAGER)
			doc = frappe.get_doc("Occasion", occasion.name)
			self.assertRaises(frappe.ValidationError, doc.assert_can_send)

			record_acceptance(MANAGER, "Re-acceptance")
			self.assertFalse(terms_pending(MANAGER))
			doc.assert_can_send()
		finally:
			frappe.set_user("Administrator")
			frappe.db.set_single_value("OrionCard Settings", "terms_version", original)

	# ------------------------------------------------------------ graduated card pricing

	def test_graduated_card_pricing(self):
		from orion_card.install import DEFAULT_CARD_TIERS
		from orion_card.utils.pricing import quote

		self.addCleanup(set_card_tiers, set_card_tiers(DEFAULT_CARD_TIERS))
		self.assertEqual(quote(1)["price"], 1200)
		self.assertEqual(quote(100)["price"], 120_000)
		self.assertEqual(quote(101)["price"], 121_000, "only card 101 costs 1,000 — no price cliff")
		q = quote(120)
		self.assertEqual((q["price"], q["profit"]), (140_000, 100 * 600 + 20 * 400))
		self.assertEqual((q["sms_credits"], q["whatsapp_credits"]), (120 * 10, 120 * 5))
		self.assertEqual(quote(250)["price"], 100 * 1200 + 150 * 1000)
		# Top-ups carry on from the cards already paid; a cheaper tier has no rate to keep.
		self.assertEqual(quote(50, already_paid=200, locked_allowance=40)["price"], 50_000, "200 paid + 50 = 50 x 1,000")
		self.assertEqual(quote(50, already_paid=200, locked_allowance=40)["locked_cards"], 0)
		self.assertEqual(quote(60, already_paid=60, locked_allowance=12)["price"], 40 * 1200 + 20 * 1000, "cards 61-100 at 1,200, 101-120 at 1,000")

	def test_top_up_keeps_earlier_rate_when_prices_rise(self):
		from orion_card.utils.pricing import quote

		self.addCleanup(set_card_tiers, set_card_tiers(RISING_TIERS))
		# Top-ups keep the old rate for at most `locked_allowance` cards; only
		# cards that would otherwise cost more use the allowance.
		self.assertEqual(quote(20, already_paid=100, locked_allowance=20)["price"], 18_000, "100 paid + 20 = 20 x 900")
		self.assertEqual(quote(30, already_paid=100, locked_allowance=20)["price"], 30_000, "20 x 900 + 10 x 1,200")
		self.assertEqual(quote(40, already_paid=60, locked_allowance=12)["price"], 36_000, "cards 61-100 are 900 anyway")
		self.assertEqual(quote(40, already_paid=60, locked_allowance=12)["locked_cards"], 0, "allowance not used inside tier 1")
		self.assertEqual(quote(30, already_paid=80, locked_allowance=16)["price"], 20 * 900 + 10 * 900, "cards 81-100 at 900 + 10 extra kept at 900")
		self.assertEqual(quote(10, already_paid=150, locked_allowance=30)["price"], 12_000, "already at 1,200: nothing cheaper to keep")
		self.assertEqual(quote(499, already_paid=1, locked_allowance=0)["price"], 99 * 900 + 400 * 1200, "no loophole via a 1-guest booking")

	def test_public_quote_hides_profit(self):
		from orion_card.install import DEFAULT_CARD_TIERS
		from orion_card.utils.pricing import get_quote

		self.addCleanup(set_card_tiers, set_card_tiers(DEFAULT_CARD_TIERS))
		frappe.set_user("Guest")
		q = get_quote(150)
		self.assertEqual(q["price"], 170_000)
		self.assertNotIn("profit", frappe.as_json(q))

	def test_subscription_price_credits_and_private_profit(self):
		from orion_card.utils.credits import get_balance

		self.addCleanup(set_card_tiers, set_card_tiers(RISING_TIERS))
		occasion = make_occasion()
		first = approve_subscription(occasion, guests=80)
		self.assertEqual(first.subscription_price, 72_000)
		self.assertEqual(first.profit_amount, 32_000)
		self.assertEqual(first.message_budget, 40_000)

		sms_before = get_balance(MANAGER, "SMS")
		wa_before = get_balance(MANAGER, "WhatsApp")
		# 80 paid -> up to 16 extra cards keep 900. Cards 81-100 are 900 anyway,
		# cards 101-116 keep 900, cards 117-120 pay 1,200.
		second = approve_subscription(occasion, guests=40)
		self.assertEqual(second.locked_rate_cards, 16)
		self.assertEqual(second.subscription_price, 36 * 900 + 4 * 1200)
		self.assertEqual(get_balance(MANAGER, "SMS"), sms_before + 36 * 10 + 4 * 14)
		self.assertEqual(get_balance(MANAGER, "WhatsApp"), wa_before + 36 * 3 + 4 * 6)
		self.assertEqual(occasion.paid_guest_capacity(), 120)

		# The allowance is shared by all top-ups: 120 paid -> 24 allowed, 16 used, 8 left.
		from orion_card.utils.pricing import quote_for_occasion

		third = quote_for_occasion(10, occasion.name)
		self.assertEqual((third["locked_cards"], third["price"]), (8, 8 * 900 + 2 * 1200))

		frappe.set_user(MANAGER)
		doc = frappe.get_doc("Occasion Subscription", second.name)
		self.assertFalse(doc.has_permlevel_access_to("profit_amount", permission_type="read"))
		frappe.set_user("Administrator")

		second.reload()
		second.cancel()
		self.assertEqual(get_balance(MANAGER, "SMS"), sms_before)
		self.assertEqual(get_balance(MANAGER, "WhatsApp"), wa_before)

	def test_card_payment_webhook_approves_subscription(self):
		from orion_card.api import payments
		from orion_card.install import DEFAULT_CARD_TIERS
		from orion_card.utils.credits import get_balance

		self.addCleanup(set_card_tiers, set_card_tiers(DEFAULT_CARD_TIERS))
		occasion = make_occasion()
		frappe.set_user(MANAGER)
		occasion = frappe.get_doc("Occasion", occasion.name)
		req = occasion.request_subscription(number_of_guests=10)
		frappe.set_user("Administrator")
		frappe.db.set_value("Occasion Subscription", req["name"], {"payment_status": "Pending", "gateway_reference": "abl_sub_1"})
		sms_before = get_balance(MANAGER, "SMS")

		with patch("frappe.db.commit"), patch("orion_card.receipts.queue_receipt"):
			result = payments._resolve_subscription(req["name"], "transaction.completed", "completed", "abl_sub_1")
			again = payments._resolve_subscription(req["name"], "transaction.completed", "completed", "abl_sub_1")
		self.assertEqual(result["status"], "success")
		self.assertEqual(again["message"], "Already processed")
		sub = frappe.get_doc("Occasion Subscription", req["name"])
		self.assertEqual((sub.docstatus, sub.payment_status, sub.subscription_price), (1, "Paid", 12_000))
		self.assertEqual(get_balance(MANAGER, "SMS"), sms_before + 100)
		self.assertEqual(occasion.paid_guest_capacity(), 10)
		self.assertEqual(payments._find_payment_target("", "abl_sub_1"), ("Occasion Subscription", req["name"]))
