frappe.ui.form.on("Bulk SMS", {
	refresh(frm) {
		frm.fields_dict.recipients.grid.add_custom_button(__("Send to All"), function () {
			send_bulk(frm);
		});
		frm.fields_dict.recipients.grid.add_custom_button(__("Upload CSV"), function () {
			upload_recipients_csv(frm);
		});
		frm.fields_dict.recipients.grid.add_custom_button(__("Download Template"), function () {
			download_csv_template();
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

function upload_recipients_csv(frm) {
	const input = document.createElement("input");
	input.type = "file";
	input.accept = ".csv,.txt,.tsv";
	input.onchange = function (e) {
		const file = e.target.files[0];
		if (!file) return;
		const reader = new FileReader();
		reader.onload = function (ev) {
			const rows = parse_csv(ev.target.result);
			if (!rows.length) {
				frappe.msgprint(__("No valid data found in file."));
				return;
			}
			let added = 0;
			rows.forEach(function (row) {
				const name_val = (row[0] || "").trim();
				const phone_val = (row[1] || "").trim();
				if (name_val && phone_val) {
					const child = frm.add_child("recipients");
					child.recipient_name = name_val;
					child.phone_no = phone_val;
					added++;
				}
			});
			frm.refresh_field("recipients");
			frappe.show_alert({
				message: __("{0} recipient(s) added.", [added]),
				indicator: "green",
			});
		};
		reader.readAsText(file);
	};
	input.click();
}

function parse_csv(text) {
	const lines = text.split(/\r?\n/).filter((l) => l.trim());
	if (!lines.length) return [];
	const sep = lines[0].includes("\t") ? "\t" : ",";
	const rows = [];
	lines.forEach(function (line, idx) {
		if (idx === 0 && /name|recipient|phone/i.test(line)) return; // skip header
		const cols = line.split(sep).map((c) => c.replace(/^"|"$/g, "").trim());
		if (cols.length >= 2) rows.push(cols);
	});
	return rows;
}

function download_csv_template() {
	const content = "Name,Phone Number\nJohn Doe,+255712345678\nJane Smith,+255787654321\n";
	const blob = new Blob([content], { type: "text/csv" });
	const url = URL.createObjectURL(blob);
	const a = document.createElement("a");
	a.href = url;
	a.download = "bulk_sms_recipients_template.csv";
	a.click();
	URL.revokeObjectURL(url);
}

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
