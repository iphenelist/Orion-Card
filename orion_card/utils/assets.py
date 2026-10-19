import os

import frappe


def asset_version(path: str) -> str:
	"""Cache-busting version for a file in orion_card/public: its last-modified
	time. build_version only changes on `bench build`, so after editing CSS/JS
	browsers kept serving stale copies."""
	full = os.path.join(frappe.get_app_path("orion_card", "public"), path)
	try:
		return str(int(os.path.getmtime(full)))
	except OSError:
		return "0"
