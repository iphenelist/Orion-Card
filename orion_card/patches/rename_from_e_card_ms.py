"""The app was renamed from e_card_ms ("E Card") to orion_card ("OrionCard").

Frappe can't start at all while installed_apps still names a package that no
longer exists, so three things are fixed first with plain SQL, before
`bench migrate` (see orion_card/rename_from_e_card_ms.sql): installed_apps,
Installed Application and the Patch Log. This patch (first in
pre_model_sync, so before the new doctype JSON is synced) does the rest.
"""

import frappe

OLD_APP, NEW_APP = "e_card_ms", "orion_card"
OLD_MODULE, NEW_MODULE = "E Card", "OrionCard"
OLD_SETTINGS, NEW_SETTINGS = "E Card Settings", "OrionCard Settings"


def execute():
	_rename_module()
	_replace_in_columns("app", OLD_APP, NEW_APP)
	_replace_in_columns("app_name", OLD_APP, NEW_APP)
	frappe.db.sql(
		"update `tabScheduled Job Type` set method = concat(%s, substring(method, %s)) where method like %s",
		(NEW_APP, len(OLD_APP) + 1, f"{OLD_APP}.%"),
	)
	_rename_settings_doctype()
	# The workspace is re-created from orioncard.json by the model sync.
	if frappe.db.exists("Workspace", OLD_MODULE):
		frappe.delete_doc("Workspace", OLD_MODULE, force=True, ignore_permissions=True)
	frappe.clear_cache()


def _rename_module():
	if frappe.db.exists("Module Def", OLD_MODULE) and not frappe.db.exists("Module Def", NEW_MODULE):
		frappe.db.sql(
			"update `tabModule Def` set name=%s, module_name=%s, app_name=%s where name=%s",
			(NEW_MODULE, NEW_MODULE, NEW_APP, OLD_MODULE),
		)
	_replace_in_columns("module", OLD_MODULE, NEW_MODULE)


def _replace_in_columns(column, old, new):
	"""Every table that has `column`: replace the exact value old with new."""
	tables = frappe.db.sql(
		"""select table_name from information_schema.columns
		where table_schema = database() and column_name = %s and table_name like 'tab%%'""",
		column,
	)
	for (table,) in tables:
		frappe.db.sql(f"update `{table}` set `{column}` = %s where `{column}` = %s", (new, old))


def _rename_settings_doctype():
	if not frappe.db.exists("DocType", OLD_SETTINGS) or frappe.db.exists("DocType", NEW_SETTINGS):
		return
	# Updates links to the DocType (Version, Comment, File, child-table
	# parenttype...) and tabSingles; files are not touched inside a patch.
	frappe.rename_doc("DocType", OLD_SETTINGS, NEW_SETTINGS, force=True)
	frappe.db.sql("update tabSingles set doctype=%s where doctype=%s", (NEW_SETTINGS, OLD_SETTINGS))
	_move_passwords()
	_move_child_rows()
	frappe.db.sql("delete from `__UserSettings` where doctype=%s", OLD_SETTINGS)


def _move_child_rows():
	"""rename_doc updates parenttype of the settings' child rows (credit
	packages, card price tiers) but not `parent`, which for a Single is the
	doctype name too."""
	tables = frappe.db.sql(
		"""select table_name from information_schema.columns
		where table_schema = database() and column_name = 'parenttype' and table_name like 'tab%%'"""
	)
	for (table,) in tables:
		frappe.db.sql(
			f"update `{table}` set parent=%s, parenttype=%s where parent=%s and parenttype in (%s, %s)",
			(NEW_SETTINGS, NEW_SETTINGS, OLD_SETTINGS, OLD_SETTINGS, NEW_SETTINGS),
		)


def _move_passwords():
	"""Stored passwords (SMS/WhatsApp/Abliner API keys) are keyed by doctype and
	name, which rename_doc leaves alone: move them or they are lost."""
	frappe.db.sql(
		"update `__Auth` set doctype=%s, name=if(name=%s, %s, name) where doctype=%s",
		(NEW_SETTINGS, OLD_SETTINGS, NEW_SETTINGS, OLD_SETTINGS),
	)
