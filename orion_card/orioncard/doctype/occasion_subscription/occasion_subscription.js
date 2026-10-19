frappe.ui.form.on("Occasion Subscription", {
    refresh(frm) {
        if (frm.doc.docstatus === 1) add_receipt_buttons(frm);
    },

    create_occasion_btn(frm) {
        frappe.confirm(
            __("Create a new Occasion for {0}?", [frm.doc.applicant_name]),
            function () {
                frappe.call({
                    method: "create_occasion",
                    doc: frm.doc,
                    freeze: true,
                    freeze_message: __("Creating Occasion..."),
                    callback(r) {
                        if (!r.exc) {
                            frappe.show_alert({ message: __("Occasion created!"), indicator: "green" });
                            frm.reload_doc().then(() => {
                                frappe.set_route("Form", "Occasion", r.message);
                            });
                        }
                    }
                });
            }
        );
    }
});

function add_receipt_buttons(frm) {
    frm.add_custom_button(__("Download Receipt"), () => {
        window.open(`/api/method/orion_card.receipts.download_receipt?doctype=${encodeURIComponent(frm.doctype)}&name=${encodeURIComponent(frm.doc.name)}`);
    }, __("Receipt"));
    if (frappe.user.has_role("System Manager")) {
        frm.add_custom_button(__("Send Receipt (WhatsApp/Email)"), () => {
            frappe.call({
                method: "orion_card.receipts.resend_receipt",
                args: { doctype: frm.doctype, name: frm.doc.name },
                freeze: true,
                freeze_message: __("Sending receipt..."),
            }).then(r => {
                const res = r.message || {};
                frappe.msgprint({
                    title: __("Receipt"),
                    indicator: res.whatsapp || res.email ? "green" : "orange",
                    message: __("WhatsApp: {0}<br>Email: {1}<br><a href='{2}' target='_blank'>{3}</a>", [
                        res.whatsapp ? __("sent") : __("not sent"),
                        res.email ? __("sent") : __("not sent"),
                        res.url || "#",
                        __("Open receipt"),
                    ]),
                });
                frm.reload_doc();
            });
        }, __("Receipt"));
    }
}
