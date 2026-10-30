frappe.ui.form.on("Occasion", {
    refresh(frm) {
        if (!frm.is_new()) {
            frm.call("get_invited_count").then(r => {
                render_occasion_statistics(frm, r.message || 0);
            });
            refresh_billing_status(frm);
        } else {
            frappe.call("orion_card.orioncard.doctype.occasion.occasion.get_new_occasion_access")
                .then(r => apply_access(frm, !!r.message));
        }
    },

    card_design(frm) {
        // Preview shows card_preview_image, so follow the design when it's cleared or replaced
        frm.set_value("card_preview_image", frm.doc.card_design || "");
    },

    open_gate_checkin_btn(frm) {
        if (frm.is_new()) {
            frappe.msgprint(__("Save the Occasion first."));
            return;
        }
        frappe.msgprint({
            title: __("Gate Check-in"),
            indicator: "blue",
            message: __("Gate PIN: <b style='font-size:18px;letter-spacing:3px'>{0}</b><br>Share it only with your gate staff. They enter it once on the check-in page.", [frm.doc.gate_pin || "—"])
        });
        window.open(`/gate-checkin?occasion=${encodeURIComponent(frm.doc.name)}`, "_blank");
    },

    generate_cards_btn(frm) {
        with_saved(frm, () => {
            const d = new frappe.ui.Dialog({
                title: __("Generate Cards"),
                fields: [
                    {
                        fieldtype: "HTML",
                        options: `<p class="text-muted">${__("Generate/regenerate QR code cards for contributors who are:")}</p>`
                    },
                    ...status_fields(() => update_count()),
                    { fieldname: "count_html", fieldtype: "HTML" }
                ],
                primary_action_label: __("Generate"),
                primary_action() {
                    const statuses = selected_statuses(d);
                    if (!statuses.length) return;
                    d.hide();
                    frappe.show_alert({ message: __("Generating cards..."), indicator: "blue" });
                    frm.call({ method: "generate_all_cards", doc: frm.doc, args: { statuses }, freeze: true }).then(r => {
                        if (r.message && r.message.no_design) {
                            frappe.msgprint({
                                title: __("Card Numbers Assigned"),
                                indicator: "blue",
                                message: __("Card numbers have been assigned to all guests. Upload a card design under the <b>Card</b> tab to generate card images.")
                            });
                        } else {
                            show_bulk_result(r.message, __("Done"), __("Errors"));
                        }
                        frm.reload_doc();
                    });
                }
            });
            const update_count = () => {
                const statuses = selected_statuses(d);
                const n = (frm.doc.contributors || []).filter(c => statuses.includes(c.payment_status)).length;
                d.fields_dict.count_html.$wrapper.html(`<p><b>${n}</b> ${__("card(s)")}</p>`);
            };
            d.show();
            update_count();
        });
    },

    send_whatsapp_btn(frm) {
        confirm_bulk_send(frm, "WhatsApp", "send_all_whatsapp");
    },

    send_sms_btn(frm) {
        confirm_bulk_send(frm, "SMS", "send_all_sms");
    },

    buy_credits_btn(frm) {
        if (frm._billing && !frm._billing.allow_credit_purchase) {
            show_contact_dialog(frm._billing.contact);
            return;
        }
        open_buy_credits_dialog(frm);
    },

    request_subscription_btn(frm) {
        with_saved(frm, () => frm.call("get_billing_status").then(r => {
            const s = r.message;
            if (s.pending_requests.length) {
                frappe.msgprint(__("Your request {0} is waiting for approval.", [s.pending_requests[0].name]));
                return;
            }
            const d = new frappe.ui.Dialog({
                title: __("Request Card Subscription / Lipia Kadi"),
                fields: [
                    {
                        fieldtype: "HTML",
                        options: `<p class="text-muted">${__("Cards already paid for: {0}. Contributors / guests on the list: {1}.", [s.capacity, s.guests])}</p>`
                    },
                    {
                        fieldname: "number_of_guests", fieldtype: "Int", label: __("Number of guest cards"), reqd: 1,
                        default: Math.max(s.guests - s.capacity, 1),
                        onchange() { update_price(); }
                    },
                    { fieldname: "price_html", fieldtype: "HTML" }
                ],
                primary_action_label: __("Send Request"),
                primary_action(values) {
                    frm.call("request_subscription", { number_of_guests: values.number_of_guests }).then(res => {
                        d.hide();
                        frappe.msgprint({
                            title: __("Request sent"),
                            indicator: "green",
                            message: __("Request {0} for TZS {1} was sent. You will be able to generate and send cards once it is approved.",
                                [res.message.name, format_number(res.message.price, null, 0)])
                        });
                        refresh_billing_status(frm);
                    });
                }
            });
            const update_price = () => {
                const n = d.get_value("number_of_guests") || 0;
                if (n <= 0) {
                    d.fields_dict.price_html.$wrapper.html("");
                    return;
                }
                frappe.call({
                    method: "orion_card.utils.pricing.get_quote",
                    args: { number_of_guests: n, occasion: frm.doc.name }
                }).then(r => {
                    const q = r.message;
                    const locked = q.locked_cards
                        ? `<div class="text-muted small">${__("{0} extra card(s) keep your current rate.", [q.locked_cards])}</div>` : "";
                    const lines = locked + q.lines.map(l =>
                        `<div class="text-muted">${__("Cards {0}–{1}", [l.from_card, l.to_card])}: ${l.cards} × TZS ${format_number(l.price_per_card, null, 0)}</div>`
                    ).join("");
                    d.fields_dict.price_html.$wrapper.html(`
                        ${lines}
                        <div style="font-size:16px;font-weight:700;margin-top:6px">${__("Total")}: TZS ${format_number(q.price, null, 0)}</div>
                        <div class="text-muted small">${__("Includes {0} SMS and {1} WhatsApp credits, added when approved.", [q.sms_credits, q.whatsapp_credits])}</div>`);
                });
            };
            d.show();
            update_price();
        }));
    },

    import_contributors_btn(frm) {
        with_saved(frm, () => {
            const d = new frappe.ui.Dialog({
                title: __("Import Contributors"),
                fields: [
                    {
                        fieldtype: "HTML",
                        options: `<p>${__("Columns: Name, Phone, Pledge, Card Type, Paid so far. Existing contributors are matched by phone (or by name when there is no phone) and updated, not duplicated.")}</p>
                            <p><a href="/api/method/orion_card.orioncard.doctype.occasion.occasion.download_contributor_template">${__("Download the Excel template")}</a></p>`
                    },
                    { fieldname: "file", fieldtype: "Attach", label: __("Excel / CSV file"), reqd: 1 }
                ],
                primary_action_label: __("Import"),
                primary_action(values) {
                    frm.call({ method: "import_contributors", doc: frm.doc, args: { file_url: values.file }, freeze: true })
                        .then(r => {
                            d.hide();
                            const res = r.message;
                            let msg = __("Added: {0}, Updated: {1}", [res.added, res.updated]);
                            if (res.skipped.length) {
                                msg += "<br><br>" + __("Skipped:") + "<br>" + res.skipped.map(frappe.utils.escape_html).join("<br>");
                            }
                            frappe.msgprint({ title: __("Import finished"), message: msg, indicator: res.skipped.length ? "orange" : "green" });
                            frm.reload_doc();
                        });
                }
            });
            d.show();
        });
    },

    export_contributors_btn(frm) {
        if (frm.is_new()) return;
        window.open(
            `/api/method/orion_card.orioncard.doctype.occasion.occasion.export_contributors?occasion=${encodeURIComponent(frm.doc.name)}`
        );
    },

    send_reminders_btn(frm) {
        open_reminder_dialog(frm);
    }
});

frappe.ui.form.on("Occasion Contributor", {
    send_reminder(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        if (!row.contributor_id) {
            frappe.msgprint(__("Save the Occasion first."));
            return;
        }
        open_reminder_dialog(frm, [row.contributor_id]);
    },

    paid_amount(frm, cdt, cdn) {
        update_payment_status(cdt, cdn);
    },

    pledged_amount(frm, cdt, cdn) {
        update_payment_status(cdt, cdn);
    },

    generate_card(frm, cdt, cdn) {
        const row = locals[cdt][cdn];
        with_saved(frm, () => {
            frappe.show_alert({ message: __("Generating card for {0}", [row.contributor_name]), indicator: "blue" });
            frappe.call({
                method: "orion_card.utils.card_composer.compose_single_guest",
                args: { occasion_name: frm.doc.name, guest_row_name: row.name },
                callback(r) {
                    if (!r.exc) {
                        frappe.show_alert({ message: __("Card generated!"), indicator: "green" });
                        frm.reload_doc();
                    }
                }
            });
        });
    },

    send_whatsapp(frm, cdt, cdn) {
        send_single_card(frm, locals[cdt][cdn], "WhatsApp", "orion_card.api.whatsapp.send_single");
    },

    send_sms(frm, cdt, cdn) {
        send_single_card(frm, locals[cdt][cdn], "SMS", "orion_card.api.sms.send_single");
    }
});

// Mirrors Occasion._compute_contributions so the row updates before saving.
function update_payment_status(cdt, cdn) {
    const row = locals[cdt][cdn];
    const paid = Math.max(flt(row.paid_amount), 0), pledged = flt(row.pledged_amount);
    frappe.model.set_value(cdt, cdn, "balance", Math.max(pledged - paid, 0));
    frappe.model.set_value(cdt, cdn, "payment_status",
        paid <= 0 ? "Not Paid" : paid >= pledged ? "Fully Paid" : "Partially Paid");
}

function send_single_card(frm, row, channel, method) {
    if (!row.phone) {
        frappe.msgprint(__("Add a phone number for {0} first.", [row.contributor_name]));
        return;
    }
    with_saved(frm, () => {
        let msg = __("Send the card to {0} ({1}) by {2}?", [row.contributor_name, row.phone, channel]);
        if (row.payment_status !== "Fully Paid") {
            msg += `<br><br><span class="text-warning">${__("Payment status: {0}.", [__(row.payment_status)])}</span>`;
        }
        frappe.confirm(msg, () => frappe.call({
            method,
            args: { occasion_name: frm.doc.name, guest_code: row.guest_code },
            freeze: true,
            callback(r) {
                if (!r.exc) {
                    frappe.show_alert({ message: __("{0} sent!", [channel]), indicator: "green" });
                    frm.reload_doc();
                }
            }
        }));
    });
}

// Which payment statuses a bulk card action covers. Fully paid by default;
// the manager decides whether partially paid (and unpaid / invite-only)
// contributors get their card too.
function status_fields(onchange) {
    return [
        { fieldname: "fully_paid", fieldtype: "Check", label: __("Fully Paid"), default: 1, onchange },
        { fieldname: "partially_paid", fieldtype: "Check", label: __("Partially Paid — include them too?"), default: 0, onchange },
        {
            fieldname: "not_paid", fieldtype: "Check", label: __("Not Paid"), default: 0, onchange,
            description: __("Tick this for invited guests who have no pledge.")
        },
    ];
}

function selected_statuses(d) {
    const s = [];
    if (d.get_value("fully_paid")) s.push("Fully Paid");
    if (d.get_value("partially_paid")) s.push("Partially Paid");
    if (d.get_value("not_paid")) s.push("Not Paid");
    return s;
}

// ------------------------------------------------------------------ helpers

function with_saved(frm, fn) {
    if (frm.is_new() || frm.is_dirty()) {
        frm.save().then(fn);
    } else {
        fn();
    }
}

function show_bulk_result(res, done_label, error_title) {
    frappe.show_alert({
        message: `${done_label}: ${res.success} ${__("success")}, ${res.failed} ${__("failed")}`,
        indicator: res.failed > 0 ? "orange" : "green"
    });
    if (res.credits_out) {
        show_contact_dialog(res.contact, frappe.utils.escape_html(res.errors[res.errors.length - 1] || ""));
        return;
    }
    if (res.errors.length) {
        frappe.msgprint({
            title: error_title,
            message: res.errors.map(frappe.utils.escape_html).join("<br>"),
            indicator: "red"
        });
    }
}

// Customers can't buy credits themselves (unless OrionCard Settings allows
// it): when credits run out they call OrionCard, who adds them on the
// customer's Message Credit Account.
function show_contact_dialog(contact, reason) {
    contact = contact || {};
    const phone = (contact.phone || "").trim();
    const wa = phone.replace(/\D/g, "").replace(/^0/, "255");
    const esc = frappe.utils.escape_html;
    let html = reason ? `<p>${reason}</p>` : `<p>${__("Ili kuongezewa credits au mialiko, wasiliana na OrionCard. / To get more credits or invitations, contact OrionCard.")}</p>`;
    if (phone) {
        html += `<p style="font-size:20px;font-weight:700;margin:12px 0 4px"><a href="tel:${esc(phone.replace(/\s/g, ""))}">${esc(phone)}</a></p>
            <p><a href="https://wa.me/${wa}" target="_blank" rel="noopener">${__("Chat on WhatsApp")}</a></p>`;
    }
    if (contact.email) {
        html += `<p><a href="mailto:${esc(contact.email)}">${esc(contact.email)}</a></p>`;
    }
    frappe.msgprint({ title: __("Wasiliana na OrionCard / Contact OrionCard"), indicator: "orange", message: html });
}

function credit_line(channel, c, billing) {
    if (!billing) return `${channel}: ${c.messages} ${__("message(s)")}`;
    const short = c.needed > c.available;
    return `<div style="margin:4px 0">${channel}: <b>${c.messages}</b> ${__("message(s)")} ·
        ${__("credits needed")} <b>${c.needed}</b> · ${__("available")}
        <b style="color:${short ? "var(--red-600, #d03b3b)" : "inherit"}">${c.available}</b></div>`;
}

function confirm_bulk_send(frm, channel, method) {
    with_saved(frm, () => {
        let d = null;
        let shortfall = 0, contact = null, buy_allowed = false;
        d = new frappe.ui.Dialog({
            title: __("Send Cards by {0}", [channel]),
            fields: [
                {
                    fieldtype: "HTML",
                    options: `<p class="text-muted">${__("Send the invitation card to contributors who have not received it yet and are:")}</p>`
                },
                ...status_fields(() => refresh_estimate()),
                {
                    fieldname: "resend", fieldtype: "Check", default: 0, onchange: () => refresh_estimate(),
                    label: __("Also send again to guests already invited"),
                    description: __("Each guest gets the {0} invitation at most {1} times.",
                        [channel, (frm._billing && frm._billing.message_limits.Invitation) || 2])
                },
                { fieldname: "estimate_html", fieldtype: "HTML" }
            ],
            primary_action_label: __("Send"),
            primary_action() {
                const statuses = selected_statuses(d);
                if (!statuses.length) return;
                d.hide();
                frappe.show_alert({ message: __("Sending..."), indicator: "blue" });
                const args = { statuses, resend: d.get_value("resend") ? 1 : 0 };
                frm.call({ method, doc: frm.doc, args, freeze: true, freeze_message: __("Sending...") }).then(res => {
                    show_bulk_result(res.message, __("Sent"), __("{0} Errors", [channel]));
                    refresh_billing_status(frm);
                    frm.reload_doc();
                });
            }
        });
        const refresh_estimate = () => {
            // onchange also fires while the dialog is still being built.
            if (!d) return;
            const statuses = selected_statuses(d);
            const $out = d.fields_dict.estimate_html.$wrapper;
            if (!statuses.length) {
                $out.html(`<p class="text-muted">${__("Tick at least one status.")}</p>`);
                d.get_primary_btn().prop("disabled", true);
                return;
            }
            frappe.call({
                method: "orion_card.api.messaging.estimate",
                args: {
                    occasion_name: frm.doc.name, channel, purpose: "Invitation", statuses,
                    resend: d.get_value("resend") ? 1 : 0
                }
            }).then(r => {
                const est = r.message;
                const c = est.channels[channel];
                contact = est.contact;
                buy_allowed = est.allow_credit_purchase;
                shortfall = c.needed - c.available;
                d.get_primary_btn().prop("disabled", !c.messages);
                if (!c.messages) {
                    $out.html(d.get_value("resend")
                        ? `<p>${__("Everyone selected has received all {0} {1} invitations (or has no phone number).", [c.limit, channel])}
                            <a href="#" class="ec-contact">${__("Need more? Contact OrionCard")}</a></p>`
                        : `<p>${__("Everyone selected has already received a {0} invitation (or has no phone number). Tick \"Also send again\" to remind them.", [channel])}</p>`);
                    return;
                }
                let html = credit_line(channel, c, est.billing);
                if (est.billing && c.needed > c.available) {
                    html += `<p style="margin-top:8px">${__("Not enough credits — only the first messages will go out.")}
                        <a href="#" class="ec-buy-credits">${buy_allowed ? __("Buy credits") : __("Contact OrionCard for more credits")}</a></p>`;
                }
                $out.html(html);
            });
        };
        d.$wrapper.on("click", ".ec-buy-credits, .ec-contact", (e) => {
            e.preventDefault();
            d.hide();
            if (buy_allowed && $(e.currentTarget).hasClass("ec-buy-credits")) {
                open_buy_credits_dialog(frm, channel, shortfall);
            } else {
                show_contact_dialog(contact);
            }
        });
        d.show();
        refresh_estimate();
    });
}

function open_buy_credits_dialog(frm, channel, shortfall) {
    frappe.call("orion_card.api.payments.get_credit_page_data").then(r => {
        const data = r.message;
        const CUSTOM = __("Custom amount");
        const money = (n) => `${data.currency} ${format_number(n, null, 0)}`;
        const package_options = (ch) => [
            ...data.packages[ch].map(p => ({ value: p.label, label: `${p.label} — ${format_number(p.credits, null, 0)} ${__("credits")} · ${money(p.amount)}` })),
            { value: CUSTOM, label: CUSTOM },
        ];
        let polling = null;

        const d = new frappe.ui.Dialog({
            title: __("Buy Credits / Nunua Credits"),
            fields: [
                { fieldname: "balance_html", fieldtype: "HTML" },
                {
                    fieldname: "channel", fieldtype: "Select", label: __("Credit type"), reqd: 1,
                    options: ["SMS", "WhatsApp"], default: channel || "SMS",
                    onchange() { set_packages(); }
                },
                { fieldname: "package", fieldtype: "Select", label: __("Package"), reqd: 1, onchange() { update_total(); } },
                {
                    fieldname: "credit_count", fieldtype: "Int", label: __("Number of credits"),
                    depends_on: `eval:doc.package === ${JSON.stringify(CUSTOM)}`,
                    description: __("Minimum {0}", [data.min_custom]),
                    onchange() { update_total(); }
                },
                { fieldname: "total_html", fieldtype: "HTML" },
                {
                    fieldname: "phone", fieldtype: "Data", options: "Phone", label: __("Mobile money number"),
                    default: data.phone, hidden: data.online_payment ? 0 : 1,
                    description: __("You will get a prompt on this phone to enter your PIN.")
                },
                {
                    fieldname: "accept_terms", fieldtype: "Check",
                    label: __("I accept the credit purchase <a href='/terms' target='_blank'>Terms</a> / Nakubali masharti")
                },
                { fieldname: "status_html", fieldtype: "HTML" },
            ],
            primary_action_label: data.online_payment ? __("Pay") : __("Place order"),
            primary_action(values) {
                const sel = selection();
                if (!sel.credits) return show_status("red", __("Choose a package or enter the number of credits."));
                if (!values.accept_terms) return show_status("red", __("Tick the box to accept the terms."));
                if (data.online_payment && (values.phone || "").replace(/\D/g, "").length < 9) {
                    return show_status("red", __("Enter the mobile money number to pay with."));
                }
                d.get_primary_btn().prop("disabled", true);
                frappe.call({
                    method: "orion_card.api.payments.create_purchase",
                    type: "POST",
                    args: {
                        channel: values.channel,
                        credit_count: sel.credits,
                        package: sel.package,
                        phone: data.online_payment ? values.phone : null,
                        accept_terms: 1,
                    },
                }).then(res => {
                    const p = res.message;
                    if (p.manual) {
                        show_status("blue", `${__("Order {0} placed.", [p.purchase])}<br>${frappe.utils.escape_html(p.message).replace(/\n/g, "<br>")}`);
                        d.get_primary_btn().hide();
                        return;
                    }
                    show_status("blue", `${frappe.utils.escape_html(p.message)} <span class="text-muted">(${p.purchase})</span>`);
                    poll(p.purchase, 0);
                }, () => d.get_primary_btn().prop("disabled", false));  // server message already shown
            },
        });

        const selection = () => {
            const ch = d.get_value("channel") || channel || "SMS";
            const pkg = data.packages[ch].find(p => p.label === d.get_value("package"));
            if (pkg) return { credits: pkg.credits, amount: pkg.amount, package: pkg.label };
            const n = cint(d.get_value("credit_count"));
            return { credits: n >= data.min_custom ? n : 0, amount: n * data.prices[ch], package: null };
        };
        const update_total = () => {
            const sel = selection();
            d.fields_dict.total_html.$wrapper.html(sel.credits
                ? `<div style="font-size:16px;font-weight:700;margin:4px 0 10px">${__("Total")}: ${money(sel.amount)}</div>`
                : "");
        };
        const set_packages = () => {
            const ch = d.get_value("channel") || channel || "SMS";
            const opts = package_options(ch);
            d.set_df_property("package", "options", opts);
            // Pre-pick the smallest package that covers what's missing for this send.
            const fit = shortfall > 0 && data.packages[ch].find(p => p.credits >= shortfall);
            if (shortfall > 0 && !fit) d.set_value("credit_count", Math.max(shortfall, data.min_custom));
            d.set_value("package", fit ? fit.label : (shortfall > 0 ? CUSTOM : opts[0].value));
            update_total();
        };
        const render_balance = (b) => d.fields_dict.balance_html.$wrapper.html(
            `<div style="margin-bottom:8px">${__("SMS credits")}: <b>${b.sms_balance}</b> · ${__("WhatsApp credits")}: <b>${b.whatsapp_balance}</b></div>`
        );
        const show_status = (color, html) => d.fields_dict.status_html.$wrapper.html(
            `<div class="alert alert-${{ red: "danger", blue: "info", green: "success" }[color]}" style="margin:8px 0 0">${html}</div>`
        );
        const poll = (purchase, attempt) => {
            if (attempt > 45) {
                polling = null;
                show_status("blue", __("Still waiting for the payment ({0}). Your credits are added automatically once it goes through — you can close this window.", [purchase]));
                return;
            }
            polling = setTimeout(() => {
                frappe.call({ method: "orion_card.api.payments.get_purchase_status", args: { purchase }, freeze: false })
                    .then(s => {
                        s = s.message;
                        if (s.status === "Paid") {
                            polling = null;
                            render_balance(s.balances);
                            show_status("green", __("Payment received — {0} {1} credits added.", [format_number(s.credits, null, 0), s.channel]));
                            d.set_primary_action(__("Done"), () => d.hide());
                            d.get_primary_btn().prop("disabled", false);
                            refresh_billing_status(frm);
                        } else if (s.status === "Failed" || s.status === "Cancelled") {
                            polling = null;
                            show_status("red", __("The payment did not go through. Check your balance and try again."));
                            d.get_primary_btn().prop("disabled", false);
                        } else {
                            poll(purchase, attempt + 1);
                        }
                    }, () => poll(purchase, attempt + 1));  // network blip: keep polling
            }, 4000);
        };

        d.onhide = () => { clearTimeout(polling); polling = null; refresh_billing_status(frm); };
        d.show();
        render_balance(data.balances);
        set_packages();
    });
}

function open_reminder_dialog(frm, contributor_ids) {
    with_saved(frm, () => {
        let d = null;
        const limit = (frm._billing && frm._billing.message_limits["Contribution Reminder"]) || 3;
        d = new frappe.ui.Dialog({
            title: contributor_ids ? __("Send Reminder") : __("Send Contribution Reminders"),
            fields: [
                {
                    fieldtype: "HTML",
                    options: `<p class="text-muted">${__("Each contributor with a balance can get {0} reminders by SMS and {0} by WhatsApp.", [limit])}</p>`
                },
                {
                    fieldname: "channel", fieldtype: "Select", label: __("Send by"), default: "SMS",
                    options: "SMS\nWhatsApp\nBoth", onchange: () => refresh_estimate()
                },
                {
                    fieldname: "not_paid", fieldtype: "Check", label: __("Not Paid"), default: 1,
                    hidden: !!contributor_ids, onchange: () => refresh_estimate()
                },
                {
                    fieldname: "partially_paid", fieldtype: "Check", label: __("Partially Paid"), default: 1,
                    hidden: !!contributor_ids, onchange: () => refresh_estimate()
                },
                { fieldname: "preview_html", fieldtype: "HTML" },
                { fieldname: "estimate_html", fieldtype: "HTML" }
            ],
            primary_action_label: __("Send"),
            primary_action(values) {
                frappe.call({
                    method: "orion_card.api.reminders.send_reminders",
                    args: {
                        occasion: frm.doc.name,
                        channel: values.channel,
                        statuses: statuses(),
                        contributor_ids: contributor_ids || null
                    },
                    freeze: true,
                    freeze_message: __("Sending reminders...")
                }).then(r => {
                    d.hide();
                    show_bulk_result(r.message, __("Reminders sent"), __("Reminder Errors"));
                    frm.reload_doc();
                });
            }
        });
        const statuses = () => {
            const s = [];
            if (d.get_value("not_paid")) s.push("Not Paid");
            if (d.get_value("partially_paid")) s.push("Partially Paid");
            return s;
        };
        const refresh_estimate = () => {
            // onchange also fires while the dialog is still being built.
            if (!d || !d.get_value("channel")) return;
            frappe.call({
                method: "orion_card.api.messaging.estimate",
                args: { occasion_name: frm.doc.name, channel: d.get_value("channel"), purpose: "Reminder", statuses: statuses() }
            }).then(r => {
                const est = r.message;
                let html = "";
                for (const [ch, c] of Object.entries(est.channels)) {
                    html += c.messages ? credit_line(ch, c, est.billing)
                        : `<div style="margin:4px 0">${ch}: ${__("everyone selected has had all {0} reminders (or has paid).", [c.limit])}</div>`;
                }
                if (contributor_ids) html = "";  // single-contributor send: estimate covers everyone, skip it
                d.fields_dict.estimate_html.$wrapper.html(html);
            });
        };
        frappe.call({
            method: "orion_card.api.reminders.preview",
            args: { occasion: frm.doc.name, contributor_id: contributor_ids ? contributor_ids[0] : null }
        }).then(r => {
            d.fields_dict.preview_html.$wrapper.html(
                `<label class="control-label">${__("Message preview")}</label>
                 <div style="white-space:pre-wrap;padding:10px;border-radius:8px;background:var(--control-bg);font-size:13px">${frappe.utils.escape_html(r.message)}</div>`
            );
        });
        d.show();
        refresh_estimate();
    });
}

// Until the event's cards are paid for, only the event details and card
// design can be edited; the server enforces the same rule on save.
const SUBSCRIPTION_FEATURES = [
    "import_contributors_btn", "send_reminders_btn",
    "generate_cards_btn", "send_whatsapp_btn", "send_sms_btn",
];

function apply_access(frm, full_access) {
    frm._full_access = full_access;
    frm.set_df_property("contributors", "read_only", full_access ? 0 : 1);
    frm.set_df_property("budget_items", "read_only", full_access ? 0 : 1);
    frm.toggle_display(SUBSCRIPTION_FEATURES, full_access);
    if (full_access) {
        frm.set_intro("");
        return;
    }
    frm.set_intro(
        __("Pay for this event's cards to add contributors and a budget, generate cards and send messages. Until then you can set up the event and upload your card design.")
        + ` <a href="#" class="ec-open-subscription">${__("Request Card Subscription")}</a>`,
        "orange"
    );
    frm.layout.wrapper.find(".ec-open-subscription").off("click").on("click", (e) => {
        e.preventDefault();
        if (frm.is_new()) {
            frappe.msgprint(__("Save the Occasion first."));
            return;
        }
        frm.trigger("request_subscription_btn");
    });
}

function refresh_billing_status(frm) {
    const field = frm.get_field("subscription_status_html");
    if (!field) return;
    frm.call("get_billing_status").then(r => {
        const s = r.message;
        frm._billing = s;
        frm.toggle_display("buy_credits_btn", s.allow_credit_purchase);
        const more = s.allow_credit_purchase ? "" :
            `<div class="text-muted small">${__("Need more credits?")} <a href="#" class="ec-contact">${__("Contact OrionCard")}</a></div>`;
        const pending = s.pending_requests.length
            ? `<div class="text-warning">${__("Request {0} waiting for approval", [s.pending_requests[0].name])}</div>` : "";
        apply_access(frm, s.full_access);
        const cards = s.is_staff
            ? __("Staff account — no card subscription needed")
            : s.unlimited_cards
                ? __("Card subscription active · generated: {0} · contributors / guests on list: {1}", [s.cards_issued, s.guests])
                : s.capacity
                    ? __("Cards paid for: <b>{0}</b> · generated: {1} · contributors / guests on list: {2}", [s.capacity, s.cards_issued, s.guests])
                    : `<span class="text-danger">${__("No approved card subscription yet")}</span>`;
        field.$wrapper.html(`
            <div style="line-height:1.9">
                <div>${cards}</div>${pending}
                <div>${__("SMS credits")}: <b>${s.balances.sms_balance}</b> · ${__("WhatsApp credits")}: <b>${s.balances.whatsapp_balance}</b></div>
                ${more}
            </div>`);
        field.$wrapper.find(".ec-contact").on("click", (e) => {
            e.preventDefault();
            show_contact_dialog(s.contact);
        });
    });
}

function render_occasion_statistics(frm, invitedCount) {
    const $wrapper = frm.get_field("statistics_html").$wrapper;
    const guests = frm.doc.contributors || [];

    const total     = guests.length;
    const confirmed = guests.filter(g => g.rsvp_status === "Confirmed").length;
    const pending    = guests.filter(g => g.rsvp_status === "Pending").length;
    const declined   = guests.filter(g => g.rsvp_status === "Declined").length;
    const sent       = invitedCount || 0;
    const checkedIn  = guests.filter(g => g.checked_in).length;
    const peopleIn   = guests.reduce((n, g) => n + (g.entered_count || (g.checked_in ? 1 : 0)), 0);
    const peopleAll  = guests.reduce((n, g) => n + (g.admits || 1), 0);

    // Validated categorical/status palette — see dataviz skill references/palette.md.
    // Stat tiles use text-safe steps; the two pies use the fixed status triad
    // (good/warning/critical) and a highlight-vs-neutral pair, both legend-labeled.
    const stats = [
        { label: __("Total Guests"),   value: total,     v: "--stat-blue" },
        { label: __("Confirmed"),      value: confirmed, v: "--stat-good" },
        { label: __("Pending"),        value: pending,   v: "--stat-orange" },
        { label: __("Declined"),       value: declined,  v: "--stat-critical" },
        { label: __("Invited"),        value: sent,       v: "--stat-aqua" },
        { label: __("Checked In"),     value: checkedIn, v: "--stat-yellow" },
        { label: __("People In"),      value: `${peopleIn}/${peopleAll}`, v: "--stat-yellow" }
    ];

    const cardsHtml = stats
        .map(
            s => `
        <div class="occ-stat-card">
            <div class="occ-stat-num" style="color:var(${s.v});">${s.value}</div>
            <div class="occ-stat-label">${s.label}</div>
        </div>`
        )
        .join("");

    $wrapper.html(`
        <style>
            .occasion-stats {
                --stat-blue:     #2a78d6;
                --stat-orange:   #eb6834;
                --stat-aqua:     #1baf7a;
                --stat-yellow:   #eda100;
                --stat-good:     #006300;
                --stat-warning:  #fab219;
                --stat-critical: #d03b3b;
                --stat-neutral:  #c3c2b7;
                padding: 6px 0 16px;
            }
            @media (prefers-color-scheme: dark) {
                :root:where(:not([data-theme="light"])) .occasion-stats {
                    --stat-blue: #3987e5; --stat-orange: #d95926; --stat-aqua: #199e70;
                    --stat-yellow: #c98500; --stat-good: #0ca30c; --stat-warning: #fab219;
                    --stat-critical: #d03b3b; --stat-neutral: #383835;
                }
            }
            [data-theme="dark"] .occasion-stats {
                --stat-blue: #3987e5; --stat-orange: #d95926; --stat-aqua: #199e70;
                --stat-yellow: #c98500; --stat-good: #0ca30c; --stat-warning: #fab219;
                --stat-critical: #d03b3b; --stat-neutral: #383835;
            }
            .occ-stat-row { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:22px; }
            .occ-stat-card {
                flex:1; min-width:130px; background:var(--card-bg,#fff);
                border:1px solid var(--border-color,#d1d5db); border-radius:10px;
                padding:14px 12px; text-align:center;
            }
            .occ-stat-num { font-size:26px; font-weight:800; line-height:1.2; }
            .occ-stat-label { font-size:12px; color:var(--text-muted,#6b7280); margin-top:4px; font-weight:600; }
            .occ-chart-row { display:flex; gap:24px; flex-wrap:wrap; }
            .occ-chart-col { flex:1; min-width:260px; }
            .occ-chart-title { font-size:13px; font-weight:700; margin-bottom:6px; }
            .occ-money { margin-bottom:22px; }
            .occ-bar-row { margin-bottom:12px; }
            .occ-bar-head { display:flex; justify-content:space-between; font-size:12px; font-weight:600; margin-bottom:4px; }
            .occ-bar-head span:last-child { color:var(--text-muted,#6b7280); }
            .occ-bar { height:10px; border-radius:6px; background:var(--stat-neutral); overflow:hidden; }
            .occ-bar > div { height:100%; border-radius:6px; transition:width .6s ease; }
        </style>
        <div class="occasion-stats">
            <div class="occ-stat-row">${cardsHtml}</div>
            ${budget_progress_html(frm)}
            <div class="occ-chart-row">
                <div class="occ-chart-col">
                    <div class="occ-chart-title">${__("Contributions collected (TZS, cumulative)")}</div>
                    <div class="occ-line" data-series="collected"></div>
                </div>
                <div class="occ-chart-col">
                    <div class="occ-chart-title">${__("Guests invited (cumulative)")}</div>
                    <div class="occ-line" data-series="invited"></div>
                </div>
                <div class="occ-chart-col">
                    <div class="occ-chart-title occ-arrivals-title">${__("Arrivals at the gate (cumulative)")}</div>
                    <div class="occ-line" data-series="arrivals"></div>
                </div>
            </div>
        </div>
    `);

    if (frm.is_new()) return;
    frm.call("get_timeseries").then(r => {
        frm._occ_timeseries = r.message;
        draw_occasion_lines(frm);
    });
}

// Line charts measure their container, so draw them only while the
// statistics tab is visible (a hidden tab has zero width), and again when
// it is opened.
function draw_occasion_lines(frm) {
    const series = frm._occ_timeseries;
    const $wrapper = frm.get_field("statistics_html").$wrapper;
    if (!series || !$wrapper.is(":visible")) return;

    const isDark = document.documentElement.getAttribute("data-theme") === "dark"
        || (window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
            && document.documentElement.getAttribute("data-theme") !== "light");
    // Categorical slot 1 (blue) — one series per chart, so no legend; the title names it.
    const color = isDark ? "#3987e5" : "#2a78d6";
    const empty = {
        collected: __("No contributions recorded yet."),
        invited: __("No invitations sent yet."),
        arrivals: __("No guests checked in yet."),
    };
    if (series.arrivals_by_time) {
        $wrapper.find(".occ-arrivals-title").text(__("Arrivals at the gate by time (cumulative)"));
    }

    $wrapper.find(".occ-line").each(function () {
        const key = this.dataset.series;
        const points = series[key] || [];
        if (!points.length) {
            $(this).html(`<p class="text-muted small" style="padding:40px 0;text-align:center">${empty[key]}</p>`);
            return;
        }
        $(this).empty();
        new frappe.Chart(this, {
            data: {
                labels: points.map(p => p.x),
                datasets: [{ name: $(this).prev(".occ-chart-title").text(), values: points.map(p => p.y) }],
            },
            type: "line",
            height: 220,
            colors: [color],
            lineOptions: { regionFill: 0, dotSize: 4, hideDots: points.length > 30 ? 1 : 0 },
            axisOptions: { xIsSeries: 1, xAxisMode: "tick", yAxisMode: "span" },
            tooltipOptions: {
                formatTooltipY: v => key === "collected" ? `TZS ${format_number(v, null, 0)}` : format_number(v, null, 0),
            },
        });
    });
}

$(document).on("click", ".form-tabs .nav-link", () => {
    setTimeout(() => {
        if (cur_frm && cur_frm.doctype === "Occasion") draw_occasion_lines(cur_frm);
    }, 60);
});

function budget_progress_html(frm) {
    const d = frm.doc;
    const budget = flt(d.total_budget), collected = flt(d.total_collected), pledged = flt(d.total_pledged);
    const spent = flt(d.total_spent);
    if (!budget && !pledged) return "";
    const pct = (part, whole) => (whole > 0 ? Math.min(100, Math.round((part / whole) * 100)) : 0);
    const money = v => "TZS " + format_number(v, null, 0);
    const contributors = d.contributors || [];
    const fully = contributors.filter(c => c.payment_status === "Fully Paid").length;
    const bar = (label, part, whole, color) => `
        <div class="occ-bar-row">
            <div class="occ-bar-head"><span>${label}</span><span>${money(part)} / ${money(whole)} · ${pct(part, whole)}%</span></div>
            <div class="occ-bar"><div style="width:${pct(part, whole)}%;background:var(${color})"></div></div>
        </div>`;
    return `
        <div class="occ-money">
            <div class="occ-chart-title">${__("Budget & Contributions")}</div>
            ${budget ? bar(__("Collected vs budget"), collected, budget, "--stat-aqua") : ""}
            ${pledged ? bar(__("Collected vs pledged"), collected, pledged, "--stat-blue") : ""}
            ${budget ? bar(__("Spent vs budget"), spent, budget, "--stat-orange") : ""}
            <div class="text-muted small">${__("{0} of {1} contributors fully paid", [fully, contributors.length])}</div>
        </div>`;
}
