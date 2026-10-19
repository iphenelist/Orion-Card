import frappe


def execute():
	"""Snapshot the legacy whatsapp_sent/sms_sent flags before they're dropped
	from Occasion Guest, so restore_guest_invite_status (post_model_sync) can
	turn them into Occasion Guest Invite Log rows on the new child table."""
	if not frappe.db.table_exists("Occasion Guest"):
		return

	columns = frappe.db.get_table_columns("Occasion Guest")
	if "whatsapp_sent" not in columns and "sms_sent" not in columns:
		return

	frappe.db.sql_ddl("DROP TABLE IF EXISTS `_orion_card_guest_invite_backup`")
	frappe.db.sql_ddl(f"""
		CREATE TABLE `_orion_card_guest_invite_backup` AS
		SELECT
			`parent` AS occasion,
			`guest_code`,
			{"whatsapp_sent" if "whatsapp_sent" in columns else "0"} AS whatsapp_sent,
			{"sent_at" if "sent_at" in columns else "NULL"} AS sent_at,
			{"sms_sent" if "sms_sent" in columns else "0"} AS sms_sent,
			{"sms_sent_at" if "sms_sent_at" in columns else "NULL"} AS sms_sent_at
		FROM `tabOccasion Guest`
		WHERE {"whatsapp_sent = 1" if "whatsapp_sent" in columns else "0"}
			OR {"sms_sent = 1" if "sms_sent" in columns else "0"}
	""")
