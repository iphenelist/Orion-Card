// Copyright (c) 2026, Innocent P M and contributors
// For license information, please see license.txt

frappe.ui.form.on("Credit Purchase", {
	refresh(frm) {
		if (frm.doc.status !== "Paid") return;
		frm.add_custom_button(__("Download Receipt"), () => {
			window.open(
				`/api/method/orion_card.receipts.download_receipt?doctype=Credit%20Purchase&name=${encodeURIComponent(frm.doc.name)}`
			);
		}, __("Receipt"));
		if (frappe.user.has_role("System Manager")) {
			frm.add_custom_button(__("Send Receipt (WhatsApp/Email)"), () => {
				frappe.call({
					method: "orion_card.receipts.resend_receipt",
					args: { doctype: frm.doctype, name: frm.doc.name },
					freeze: true,
				}).then(() => {
					frappe.show_alert({ message: __("Receipt sent"), indicator: "green" });
					frm.reload_doc();
				});
			}, __("Receipt"));
		}
	},
});
