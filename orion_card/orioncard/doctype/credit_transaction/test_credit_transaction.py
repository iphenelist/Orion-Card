# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import hashlib
import hmac
import json
import time
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

from orion_card.utils import credits

IGNORE_TEST_RECORD_DEPENDENCIES = ["User", "Occasion"]
BUYER = "credit.buyer.test@example.com"
WEBHOOK_SECRET = "whsec_test_secret"


class IntegrationTestCreditTransaction(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		if not frappe.db.exists("User", BUYER):
			frappe.get_doc({
				"doctype": "User", "email": BUYER, "first_name": "Buyer", "send_welcome_email": 0,
				"user_type": "System User", "roles": [{"role": "Occasion Manager"}],
			}).insert(ignore_permissions=True)
		settings = frappe.get_single("OrionCard Settings")
		settings.enable_credit_billing = 1
		settings.abliner_webhook_secret = WEBHOOK_SECRET
		settings.save()

	def test_sms_parts(self):
		self.assertEqual(credits.sms_parts("a" * 160), 1)
		self.assertEqual(credits.sms_parts("a" * 161), 2)
		self.assertEqual(credits.sms_parts("a" * 306), 2)
		self.assertEqual(credits.sms_parts("a" * 307), 3)
		self.assertEqual(credits.sms_parts("€" * 80), 1, "extension chars count double: 160 septets")
		self.assertEqual(credits.sms_parts("🎉" + "a" * 69), 1)
		self.assertEqual(credits.sms_parts("🎉" + "a" * 70), 2, "emoji switches to 70-char UCS-2 parts")

	def test_ledger_and_insufficient_balance(self):
		start = credits.get_balance(BUYER, "SMS")
		credits.add(BUYER, "SMS", 5, remarks="test")
		credits.consume(BUYER, "SMS", 3)
		self.assertEqual(credits.get_balance(BUYER, "SMS"), start + 2)
		self.assertRaises(
			credits.InsufficientCreditsError, credits.consume, BUYER, "SMS", start + 3
		)
		last = frappe.get_all(
			"Credit Transaction", filters={"user": BUYER, "channel": "SMS"},
			fields=["transaction_type", "credits", "balance_after"], order_by="creation desc", limit=1,
		)[0]
		self.assertEqual((last.transaction_type, last.credits, last.balance_after), ("Usage", -3, start + 2))

	def _purchase(self, credit_count=100):
		doc = frappe.get_doc({
			"doctype": "Credit Purchase", "user": BUYER, "channel": "WhatsApp", "credits": credit_count,
			"unit_price": 75, "amount": credit_count * 75, "status": "Pending", "gateway": "Abliner",
		}).insert(ignore_permissions=True)
		return doc

	def _callback(self, payload, secret=WEBHOOK_SECRET, timestamp=None):
		from orion_card.api.payments import payment_callback

		body = json.dumps(payload)
		timestamp = str(timestamp or int(time.time()))
		signature = hmac.new(secret.encode(), f"{timestamp}.{body}".encode(), hashlib.sha256).hexdigest()
		headers = {"X-Webhook-Signature": signature, "X-Webhook-Timestamp": timestamp}
		request = frappe._dict(get_data=lambda as_text=True: body)
		frappe.local.response = frappe._dict()
		with (
			patch.object(frappe, "request", request, create=True),
			patch("frappe.get_request_header", side_effect=lambda key, default=None: headers.get(key, default)),
			patch("frappe.db.commit"),
		):
			result = payment_callback()
		return result, frappe.local.response.get("http_status_code")

	def test_webhook_credits_once(self):
		purchase = self._purchase()
		start = credits.get_balance(BUYER, "WhatsApp")
		payload = {"event": "transaction.completed",
				   "data": {"customer_reference": purchase.name, "id": "abl_123", "status": "completed", "amount": 7500}}

		result, _status = self._callback(payload)
		self.assertEqual(result["status"], "success", result)
		self.assertEqual(credits.get_balance(BUYER, "WhatsApp"), start + 100)
		self.assertEqual(frappe.db.get_value("Credit Purchase", purchase.name, "status"), "Paid")

		result, _status = self._callback(payload)
		self.assertEqual(result["message"], "Already processed")
		self.assertEqual(credits.get_balance(BUYER, "WhatsApp"), start + 100, "duplicate webhook must not re-credit")

	def test_webhook_rejects_bad_signature_and_stale_timestamp(self):
		purchase = self._purchase()
		payload = {"event": "transaction.completed", "data": {"customer_reference": purchase.name, "status": "completed"}}

		_result, status = self._callback(payload, secret="whsec_wrong")
		self.assertEqual(status, 401)
		_result, status = self._callback(payload, timestamp=int(time.time()) - 3600)
		self.assertEqual(status, 401)
		self.assertEqual(frappe.db.get_value("Credit Purchase", purchase.name, "status"), "Pending")

	def test_manual_mark_paid_adds_credits_once(self):
		purchase = self._purchase(credit_count=10)
		start = credits.get_balance(BUYER, "WhatsApp")
		purchase.status = "Paid"
		purchase.save()
		purchase.reload()
		purchase.save()
		self.assertEqual(credits.get_balance(BUYER, "WhatsApp"), start + 10)
		self.assertTrue(frappe.db.get_value("Credit Purchase", purchase.name, "credited"))

	def test_manager_has_no_ledger_access(self):
		credits.add(BUYER, "SMS", 1)
		frappe.set_user(BUYER)
		try:
			self.assertFalse(frappe.has_permission("Credit Transaction", "read"))
			self.assertEqual(credits.get_balance(BUYER, "SMS") >= 1, True, "balance still readable via the app API")
		finally:
			frappe.set_user("Administrator")

	def test_receipt_pdf_and_whatsapp(self):
		from orion_card import receipts

		purchase = self._purchase(credit_count=500)
		purchase.db_set({"status": "Paid", "phone": "0712000999", "gateway_reference": "ABL-123"})
		ctx = receipts.receipt_context(frappe.get_doc("Credit Purchase", purchase.name))
		self.assertEqual(ctx["total"], 37_500)
		self.assertEqual(ctx["items"][0]["qty"], 500)

		with (
			patch("orion_card.api.whatsapp.send_text", return_value={"success": True}) as text,
			patch("orion_card.api.whatsapp.send_document", return_value={"success": True}) as document,
		):
			result = receipts.send_receipt("Credit Purchase", purchase.name)
		self.assertTrue(result["whatsapp"])
		self.assertTrue(result["url"].endswith(".pdf"))
		sent_via = text if text.called else document
		self.assertIn("RC-" + purchase.name, sent_via.call_args.args[-1] if text.called else sent_via.call_args.kwargs["caption"])
		self.assertTrue(frappe.db.get_value("Credit Purchase", purchase.name, "receipt_url"))
		# Receipts are system messages: they never use the customer's credits.
		self.assertFalse(frappe.get_all("Credit Transaction", filters={"user": BUYER, "transaction_type": "Usage",
																		"creation": [">", purchase.creation]}))

	def test_receipt_url_is_public_check(self):
		from orion_card.receipts import is_public_url

		self.assertFalse(is_public_url("http://localhost:8002/files/r.pdf"))
		self.assertFalse(is_public_url("http://192.168.1.178:8002/files/r.pdf"))
		self.assertFalse(is_public_url("http://project:8002/files/r.pdf"))
		self.assertTrue(is_public_url("https://ecard.co.tz/files/r.pdf"))

	def test_pending_welcome_email_is_sent_once_email_works(self):
		from frappe.core.doctype.user.user import User

		from orion_card.api.auth import send_pending_welcome_emails, sign_up

		email = "pending.welcome@example.com"
		frappe.set_user("Guest")
		try:
			with (
				patch.object(User, "send_welcome_mail_to_user") as welcome,
				patch.object(frappe.local, "login_manager", create=True) as login_manager,
			):
				res = sign_up(full_name="Pending Welcome", email=email, password="Kadi-Yangu-2026",
							  phone="0712000888", accept_terms=1)
		finally:
			frappe.set_user("Administrator")
		# The password is chosen on the form: no set-password email, logged straight in.
		self.assertEqual(res["status"], "ok")
		self.assertEqual(res["redirect_to"], "/app/occasion")
		welcome.assert_not_called()
		login_manager.login_as.assert_called_once_with(email)
		from frappe.utils.password import check_password
		self.assertEqual(check_password(email, "Kadi-Yangu-2026"), email)

		# Users created elsewhere while email was down are still caught up by the job.
		frappe.db.set_value("Message Credit Account", email, "welcome_email_pending", 1)

		with (
			patch("frappe.email.doctype.email_account.email_account.EmailAccount.find_default_outgoing", return_value=None),
			patch.object(User, "send_welcome_mail_to_user") as send,
		):
			send_pending_welcome_emails()
		send.assert_not_called()
		self.assertTrue(frappe.db.get_value("Message Credit Account", email, "welcome_email_pending"))

		with (
			patch("frappe.email.doctype.email_account.email_account.EmailAccount.find_default_outgoing", return_value=object()),
			patch.object(User, "send_welcome_mail_to_user") as send,
			patch("frappe.db.commit"),
		):
			send_pending_welcome_emails()
			send_pending_welcome_emails()
		self.assertEqual(send.call_count, 1, "sent exactly once")
		self.assertFalse(frappe.db.get_value("Message Credit Account", email, "welcome_email_pending"))
