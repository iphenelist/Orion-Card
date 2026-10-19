# Copyright (c) 2026, Innocent P M and Contributors
# See license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase

EXTRA_TEST_RECORD_DEPENDENCIES = []
IGNORE_TEST_RECORD_DEPENDENCIES = []


def _response(status, body):
	response = MagicMock()
	response.status_code = status
	response.ok = 200 <= status < 300
	response.json.return_value = body
	response.text = frappe.as_json(body)
	return response


class IntegrationTestOrionCardSettings(IntegrationTestCase):
	def setUp(self):
		settings = frappe.get_single("OrionCard Settings")
		settings.sms_provider = "RodSMS"
		settings.rodsms_api_key = "rodsms_live_test_key"
		settings.rodsms_sender_id = "ECARD"
		settings.rodsms_base_url = "https://rodsms.com/api/v1"
		settings.save()

	def test_rodsms_send_request(self):
		from orion_card.api.sms import send_sms

		ok = _response(202, {"success": True, "data": {"id": "msg_42", "estimated_segments": 1, "reserved_credits": 1},
							 "request_id": "req_1"})
		with patch("orion_card.api.sms.requests.request", return_value=ok) as request:
			data = send_sms("0712 345 678", "Habari")
		self.assertEqual(data["id"], "msg_42")
		method, url = request.call_args.args
		kwargs = request.call_args.kwargs
		self.assertEqual((method, url), ("POST", "https://rodsms.com/api/v1/messages"))
		self.assertEqual(kwargs["headers"]["Authorization"], "Bearer rodsms_live_test_key")
		self.assertEqual(kwargs["json"], {"sender_id": "ECARD", "recipient": "255712345678",
										  "message": "Habari", "sms_type": "transactional"})

	def test_rodsms_errors_are_explained(self):
		from orion_card.api.sms import send_sms

		no_credit = _response(402, {"success": False, "error": {"code": "insufficient_credits", "message": "Not enough"},
									"request_id": "req_2"})
		with patch("orion_card.api.sms.requests.request", return_value=no_credit):
			with self.assertRaises(frappe.ValidationError) as ctx:
				send_sms("0712345678", "Habari")
		self.assertIn("run out of SMS credits", str(ctx.exception))

	def test_rodsms_unreachable_is_explained(self):
		import requests

		from orion_card.api.sms import send_sms

		reset = requests.ConnectionError("Connection aborted.")
		with patch("orion_card.api.sms.requests.request", side_effect=reset), patch("frappe.log_error"):
			with self.assertRaises(frappe.ValidationError) as ctx:
				send_sms("0712345678", "Habari")
		self.assertIn("Could not reach RodSMS", str(ctx.exception))

	def test_failed_rodsms_send_refunds_orioncard_credits(self):
		"""A RodSMS rejection must not cost the customer OrionCard credits."""
		from orion_card.api.messaging import send_message
		from orion_card.utils.credits import add, get_balance

		user = "Administrator"
		add(user, "SMS", 5)
		before = get_balance(user, "SMS")
		occasion = frappe._dict(name=None, assigned_user=user, couple_names="A & B")
		bad_sender = _response(403, {"success": False, "error": {"code": "sender_id_unusable", "message": "x"}})
		with (
			patch("orion_card.api.sms.requests.request", return_value=bad_sender),
			patch("orion_card.api.messaging.log_message"),
		):
			self.assertRaises(frappe.ValidationError, send_message, occasion, "SMS", "0712345678", "Habari")
		self.assertEqual(get_balance(user, "SMS"), before)
