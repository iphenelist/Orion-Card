// Copyright (c) 2026, Innocent P M and contributors
// For license information, please see license.txt

frappe.ui.form.on("Message Credit Account", {
	refresh(frm) {
		if (frm.is_new() || !frappe.user.has_role("System Manager")) return;
		// Customers who ran out contact OrionCard; their credits are added here.
		frm.add_custom_button(__("Add / remove credits"), () => {
			frappe.prompt(
				[
					{ fieldname: "channel", fieldtype: "Select", label: __("Credit type"), options: ["SMS", "WhatsApp"], default: "SMS", reqd: 1 },
					{
						fieldname: "credits", fieldtype: "Int", label: __("Credits"), reqd: 1,
						description: __("A negative number takes credits away."),
					},
					{ fieldname: "remarks", fieldtype: "Small Text", label: __("Reason / note") },
				],
				(values) => {
					frappe.call({
						method: "orion_card.utils.credits.admin_adjust",
						args: { user: frm.doc.user, ...values },
						freeze: true,
					}).then((r) => {
						frappe.show_alert({
							message: __("{0} {1} credits. New balance: {2}", [values.credits, values.channel, r.message]),
							indicator: "green",
						}, 7);
						frm.reload_doc();
					});
				},
				__("Add / remove credits"),
				__("Save"),
			);
		});
		frm.add_custom_button(__("Give free access & credits"), () => {
			const d = new frappe.ui.Dialog({
				title: __("Give free access & credits"),
				fields: [
					{
						fieldtype: "HTML",
						options: `<p class="text-muted">${__(
							"{0} can then add contributors, generate cards and send messages without paying for a card subscription. Messages use the credits below.",
							[frappe.utils.escape_html(frm.doc.user)]
						)}</p>`,
					},
					{ fieldname: "sms_credits", fieldtype: "Int", label: __("Free SMS credits"), default: 0 },
					{ fieldname: "col", fieldtype: "Column Break" },
					{ fieldname: "whatsapp_credits", fieldtype: "Int", label: __("Free WhatsApp credits"), default: 0 },
					{ fieldname: "sec", fieldtype: "Section Break" },
					{ fieldname: "note", fieldtype: "Small Text", label: __("Reason / note"), default: frm.doc.free_access_note },
				],
				primary_action_label: __("Give access"),
				primary_action(values) {
					frappe.call({
						method: "orion_card.utils.credits.grant_free_access",
						args: { user: frm.doc.user, ...values },
						freeze: true,
					}).then((r) => {
						d.hide();
						frappe.show_alert({
							message: __("Free access given. Balance: {0} SMS, {1} WhatsApp", [
								r.message.sms_balance, r.message.whatsapp_balance,
							]),
							indicator: "green",
						}, 7);
						frm.reload_doc();
					});
				},
			});
			d.show();
		});
	},
});
