# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CreditPurchase(Document):
	def on_update(self):
		# A System Manager marking a manual (or gateway-confirmed) purchase as Paid
		# adds the credits exactly once; credit_purchase() is idempotent via `credited`.
		if self.status == "Paid" and not self.credited:
			from orion_card.utils.credits import credit_purchase

			credit_purchase(self.name)
