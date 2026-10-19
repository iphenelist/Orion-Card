// OrionCard: make Occasion Managers accept a new Terms & Conditions version
// before they keep working. The server enforces this too (sending and buying
// credits refuse while acceptance is pending); this is the friendly prompt.
(function () {
	function show_terms_modal() {
		frappe.call("orion_card.api.auth.get_pending_terms").then((r) => {
			const t = r.message || {};
			if (!t.pending) return;
			const lang = (frappe.boot.lang || "").startsWith("en") ? "en" : "sw";
			const body = (sw, en) => (lang === "en" ? en || sw : sw || en);
			const d = new frappe.ui.Dialog({
				title: __("Updated Terms & Conditions (v{0})", [t.terms_version]),
				size: "large",
				static: true,
				fields: [
					{
						fieldtype: "HTML",
						options: `
							<p>${__("We have updated our Terms & Conditions and Privacy Policy. Please read and accept them to keep using OrionCard.")}</p>
							<div style="max-height:50vh;overflow:auto;border:1px solid var(--border-color);border-radius:8px;padding:12px 16px;">
								${body(t.terms_content_sw, t.terms_content_en)}
								<hr>
								${body(t.privacy_content_sw, t.privacy_content_en)}
							</div>
							<p class="text-muted small" style="margin-top:8px">
								<a href="/terms" target="_blank">/terms</a> · <a href="/privacy" target="_blank">/privacy</a>
							</p>`,
					},
					{
						fieldname: "agree",
						fieldtype: "Check",
						label: __("Nimesoma na kukubali / I have read and accept the Terms & Privacy Policy"),
					},
				],
				primary_action_label: __("Accept"),
				primary_action(values) {
					if (!values.agree) {
						frappe.msgprint(__("Tick the box to accept."));
						return;
					}
					frappe.call({ method: "orion_card.api.auth.accept_terms", type: "POST" }).then(() => {
						frappe.boot.orioncard_terms_pending = false;
						d.hide();
						frappe.show_alert({ message: __("Thank you!"), indicator: "green" });
					});
				},
				secondary_action_label: __("Log out"),
				secondary_action() {
					frappe.app.logout();
				},
			});
			d.show();
			d.$wrapper.find(".modal-header .btn-modal-close").hide();
		});
	}

	$(document).on("startup", () => {
		if (frappe.boot && frappe.boot.orioncard_terms_pending) show_terms_modal();
	});
})();
