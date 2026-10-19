# Copyright (c) 2026, Innocent P M and contributors
# For license information, please see license.txt

"""Owner-only view of what the system earns, month by month.

Card subscriptions: price paid, the owner's profit (Card Price Tiers'
profit per card) and the message budget handed back to the customer as
credits. Credit sales: money from SMS / WhatsApp credit purchases.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
	frappe.only_for("System Manager")
	filters = frappe._dict(filters or {})
	params = {"from_date": getdate(filters.from_date), "to_date": getdate(filters.to_date)}

	months = {}

	def month(key):
		return months.setdefault(str(key), frappe._dict(
			month=str(key), subscriptions=0, cards=0, card_revenue=0.0, profit=0.0, message_budget=0.0,
			credit_sales=0.0, sms_credits_sold=0, whatsapp_credits_sold=0,
		))

	for row in frappe.db.sql(
		"""
		select date_format(creation, '%%Y-%%m') as m, count(*) as subscriptions,
			sum(number_of_guests) as cards, sum(subscription_price) as revenue,
			sum(profit_amount) as profit, sum(message_budget) as budget
		from `tabOccasion Subscription`
		where docstatus=1 and date(creation) between %(from_date)s and %(to_date)s
		group by m
		""",
		params,
		as_dict=True,
	):
		m = month(row.m)
		m.subscriptions, m.cards = row.subscriptions, int(row.cards or 0)
		m.card_revenue, m.profit, m.message_budget = flt(row.revenue), flt(row.profit), flt(row.budget)

	for row in frappe.db.sql(
		"""
		select date_format(coalesce(paid_at, creation), '%%Y-%%m') as m, channel,
			sum(amount) as amount, sum(credits) as credits
		from `tabCredit Purchase`
		where status='Paid' and date(coalesce(paid_at, creation)) between %(from_date)s and %(to_date)s
		group by m, channel
		""",
		params,
		as_dict=True,
	):
		m = month(row.m)
		m.credit_sales += flt(row.amount)
		if row.channel == "SMS":
			m.sms_credits_sold += int(row.credits or 0)
		else:
			m.whatsapp_credits_sold += int(row.credits or 0)

	data = sorted(months.values(), key=lambda r: r.month)
	for row in data:
		row.total_income = row.card_revenue + row.credit_sales

	totals = frappe._dict(
		month=_("TOTAL"),
		**{key: sum(r[key] for r in data) for key in (
			"subscriptions", "cards", "card_revenue", "profit", "message_budget", "credit_sales",
			"sms_credits_sold", "whatsapp_credits_sold", "total_income",
		)},
		bold=1,
	)

	columns = [
		{"fieldname": "month", "label": _("Month"), "fieldtype": "Data", "width": 90},
		{"fieldname": "subscriptions", "label": _("Subscriptions"), "fieldtype": "Int", "width": 110},
		{"fieldname": "cards", "label": _("Cards Sold"), "fieldtype": "Int", "width": 100},
		{"fieldname": "card_revenue", "label": _("Card Revenue"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "profit", "label": _("Card Profit"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "message_budget", "label": _("Given as Credits"), "fieldtype": "Currency", "width": 130},
		{"fieldname": "credit_sales", "label": _("Credit Sales"), "fieldtype": "Currency", "width": 120},
		{"fieldname": "sms_credits_sold", "label": _("SMS Credits Sold"), "fieldtype": "Int", "width": 120},
		{"fieldname": "whatsapp_credits_sold", "label": _("WhatsApp Credits Sold"), "fieldtype": "Int", "width": 140},
		{"fieldname": "total_income", "label": _("Total Income"), "fieldtype": "Currency", "width": 130},
	]

	summary = [
		{"value": totals.card_revenue, "label": _("Card Revenue"), "datatype": "Currency", "indicator": "blue"},
		{"value": totals.profit, "label": _("Card Profit"), "datatype": "Currency", "indicator": "green"},
		{"value": totals.credit_sales, "label": _("Credit Sales"), "datatype": "Currency", "indicator": "blue"},
		{"value": totals.total_income, "label": _("Total Income"), "datatype": "Currency", "indicator": "green"},
	]
	chart = {
		"data": {
			"labels": [r.month for r in data],
			"datasets": [
				{"name": _("Card Profit"), "values": [r.profit for r in data]},
				{"name": _("Credit Sales"), "values": [r.credit_sales for r in data]},
			],
		},
		"type": "bar",
		"barOptions": {"stacked": 1},
	}
	return columns, [*data, totals] if data else [], None, chart, summary
