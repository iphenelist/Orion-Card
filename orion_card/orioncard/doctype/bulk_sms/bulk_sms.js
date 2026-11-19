frappe.ui.form.on("Bulk SMS", {
	refresh(frm) {
		frm.fields_dict.recipients.grid.add_custom_button(__("Send to All"), function () {
			send_bulk(frm);
		});
	},

	send_bulk_btn(frm) {
		send_bulk(frm);
	},

	send_test_btn(frm) {
		if (!frm.doc.test_phone) {
			frappe.msgprint(__("Please enter a test phone number."));
			return;
		}
		frappe.call({
			method: "orion_card.orioncard.doctype.bulk_sms.bulk_sms.send_test",
			args: { docname: frm.doc.name },
			freeze: true,
			freeze_message: __("Sending test SMS…"),
			callback(r) {
				if (r.message && r.message.status === "success") {
					frappe.show_alert({
						message: __("Test SMS sent to {0}", [r.message.phone]),
						indicator: "green",
					});
				}
			},
		});
	},
});

frappe.ui.form.on("Bulk SMS Recipient", {
	send_now_btn(frm, cdt, cdn) {
		const row = frappe.get_doc(cdt, cdn);
		if (!frm.doc.message) {
			frappe.msgprint(__("Please write a message before sending."));
			return;
		}
		frappe.call({
			method: "orion_card.orioncard.doctype.bulk_sms.bulk_sms.send_to_recipient",
			args: { docname: frm.doc.name, row_name: cdn },
			freeze: true,
			freeze_message: __("Sending SMS to {0}…", [row.phone_no]),
			callback(r) {
				if (r.message && r.message.status === "success") {
					frappe.show_alert({
						message: __("SMS sent to {0}", [r.message.phone]),
						indicator: "green",
					});
					frappe.model.set_value(cdt, cdn, "sent", 1);
					frm.refresh_field("recipients");
				}
			},
		});
	},
});

function send_bulk(frm) {
	if (!frm.doc.message) {
		frappe.msgprint(__("Please write a message before sending."));
		return;
	}
	const unsent = (frm.doc.recipients || []).filter((r) => !r.sent).length;
	if (!unsent) {
		frappe.msgprint(__("All recipients have already been sent."));
		return;
	}
	frappe.confirm(
		__("Send SMS to {0} recipient(s)?", [unsent]),
		function () {
			frappe.call({
				method: "orion_card.orioncard.doctype.bulk_sms.bulk_sms.send_bulk",
				args: { docname: frm.doc.name },
				freeze: true,
				freeze_message: __("Sending bulk SMS…"),
				callback(r) {
					if (!r.message) return;
					const { status, sent, errors } = r.message;
					if (status === "success") {
						frappe.show_alert({
							message: __("SMS sent to {0} recipient(s).", [sent]),
							indicator: "green",
						});
					} else {
						frappe.msgprint({
							title: __("Partial Send"),
							message:
								__("{0} sent. Failures:\n", [sent]) + errors.join("\n"),
							indicator: "orange",
						});
					}
					frm.reload_doc();
				},
			});
		}
	);
}
