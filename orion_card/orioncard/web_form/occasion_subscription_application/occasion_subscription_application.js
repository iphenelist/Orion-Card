frappe.ready(function () {
	// Graduated card pricing (e.g. cards 1–100 at 900, 101+ at 1,200) lives in
	// OrionCard Settings, so the live estimate asks the server for a quote.
	let timer = null;

	function update_subscription_price() {
		clearTimeout(timer);
		timer = setTimeout(() => {
			const guests = cint(frappe.web_form.get_value("number_of_guests")) || 0;
			if (guests <= 0) {
				frappe.web_form.set_value("subscription_price", 0);
				return;
			}
			frappe.call({
				method: "orion_card.utils.pricing.get_quote",
				args: { number_of_guests: guests },
				callback(r) {
					if (r.message) frappe.web_form.set_value("subscription_price", r.message.price);
				},
			});
		}, 300);
	}

	// frappe.web_form.on() only fires on blur (it hooks the field's model-commit,
	// not keystrokes) — bind the raw input too so the estimate updates live as
	// the applicant types, not just after they click away.
	const guests_field = frappe.web_form.get_field("number_of_guests");
	if (guests_field && guests_field.$input) {
		guests_field.$input.on("input", update_subscription_price);
	}

	frappe.web_form.events.on("after_load", update_subscription_price);
	frappe.web_form.on("number_of_guests", update_subscription_price);
});
