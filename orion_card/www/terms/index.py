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
	context.title = "Vigezo na Masharti — OrionCard"
	context.heading_sw, context.heading_en = "Vigezo na Masharti", "Terms & Conditions"
	context.body_sw, context.body_en = docs["terms_content_sw"], docs["terms_content_en"]
