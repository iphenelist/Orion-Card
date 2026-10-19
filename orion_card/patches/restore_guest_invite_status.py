import frappe


def execute():
	"""Turn the legacy whatsapp_sent/sms_sent snapshot (backup_guest_invite_status,
	pre_model_sync) into Occasion Guest Invite Log rows now that the new child
	table exists."""
	backup_table_exists = frappe.db.sql("SHOW TABLES LIKE '_orion_card_guest_invite_backup'")
	if not backup_table_exists:
		return

	rows = frappe.db.sql(
		"SELECT occasion, guest_code, whatsapp_sent, sent_at, sms_sent, sms_sent_at FROM `_orion_card_guest_invite_backup`",
		as_dict=True,
	)
	for row in rows:
		if row.whatsapp_sent:
			_insert_log(row.occasion, row.guest_code, "WhatsApp", row.sent_at)
		if row.sms_sent:
			_insert_log(row.occasion, row.guest_code, "SMS", row.sms_sent_at)

	frappe.db.commit()
	frappe.db.sql_ddl("DROP TABLE `_orion_card_guest_invite_backup`")
	_drop_legacy_columns()


def _drop_legacy_columns():
	"""The legacy columns are no longer part of the Occasion Guest doctype;
	their data now lives in Occasion Guest Invite Log, so drop them from the
	table too instead of leaving them as dead columns."""
	columns = frappe.db.get_table_columns("Occasion Guest")
	legacy_columns = [
		c for c in ("whatsapp_sent", "sent_at", "sms_sent", "sms_sent_at") if c in columns
	]
	if not legacy_columns:
		return

	frappe.db.commit()
	drop_clause = ", ".join(f"DROP COLUMN `{c}`" for c in legacy_columns)
	frappe.db.sql_ddl(f"ALTER TABLE `tabOccasion Guest` {drop_clause}")


def _insert_log(occasion, guest_code, channel, sent_at):
	frappe.get_doc({
		"doctype": "Occasion Guest Invite Log",
		"occasion": occasion,
		"guest_code": guest_code,
		"channel": channel,
		"sent_at": sent_at or frappe.utils.now(),
		"success": 1,
		"response": f"Migrated from legacy {channel.lower()}_sent flag",
	}).insert(ignore_permissions=True)
