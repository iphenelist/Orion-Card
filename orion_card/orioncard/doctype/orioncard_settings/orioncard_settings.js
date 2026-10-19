// Copyright (c) 2026, Innocent P M and contributors
// For license information, please see license.txt

frappe.ui.form.on("OrionCard Settings", {
	refresh(frm) {
		frm.set_intro(
			__("Message credits are charged per SMS part (160 characters) and per WhatsApp message. Packages are priced as credits × price per credit."),
			"blue"
		);
	},

	send_test_sms_btn(frm) {
		run_test(frm, "send_test_sms", __("Test SMS sent."));
	},

	check_sms_balance_btn(frm) {
		const go = () =>
			frm.call({ method: "check_sms_balance", doc: frm.doc, freeze: true }).then((r) => {
				if (r.exc) return;
				const data = r.message || {};
				const ids = (Array.isArray(data.sender_ids) ? data.sender_ids : [])
					.map((s) => frappe.utils.escape_html(typeof s === "string" ? s : s.sender_id || s.name || JSON.stringify(s)))
					.join(", ");
				frappe.msgprint({
					title: __("RodSMS account"),
					indicator: "blue",
					message: `<p><b>${__("Balance")}</b></p><pre style="white-space:pre-wrap">${frappe.utils.escape_html(JSON.stringify(data.balance, null, 2))}</pre>
						<p><b>${__("Approved Sender IDs")}</b>: ${ids || "—"}</p>`,
				});
			});
		frm.is_dirty() ? frm.save().then(go) : go();
	},

	send_test_whatsapp_btn(frm) {
		run_test(frm, "send_test_whatsapp", __("Test WhatsApp sent."));
	},

	reset_legal_text_btn(frm) {
		frappe.confirm(
			__("Replace the Terms & Privacy text (Swahili and English) with the default text? Your edits will be lost."),
			() =>
				frm.call({ method: "reset_legal_text", doc: frm.doc, freeze: true }).then(() => {
					frappe.show_alert({ message: __("Default text restored."), indicator: "green" });
					frm.reload_doc();
				})
		);
	},
});

function run_test(frm, method, success_message) {
	const go = () =>
		frm.call({ method, doc: frm.doc, freeze: true, freeze_message: __("Sending...") }).then((r) => {
			if (!r.exc) {
				frappe.msgprint({
					title: success_message,
					message: `<pre style="white-space:pre-wrap">${frappe.utils.escape_html(JSON.stringify(r.message, null, 2))}</pre>`,
					indicator: "green",
				});
			}
		});
	// Test sends read the saved token, so save pending edits first.
	frm.is_dirty() ? frm.save().then(go) : go();
}
