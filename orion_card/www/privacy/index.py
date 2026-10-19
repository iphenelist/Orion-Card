import frappe

no_cache = 1


def get_context(context):
	from orion_card.legal import get_legal_documents

	docs = get_legal_documents()
	context.body_class = "ec-body"
	context.no_breadcrumbs = 1
	context.ec_business_name = frappe.db.get_single_value("OrionCard Settings", "business_legal_name")
	context.version = docs["terms_version"]
	context.effective_date = docs["effective_date"]
	context.title = "Sera ya Faragha — OrionCard"
	context.heading_sw, context.heading_en = "Sera ya Faragha", "Privacy Policy"
	context.body_sw, context.body_en = docs["privacy_content_sw"], docs["privacy_content_en"]
