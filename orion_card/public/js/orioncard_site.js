/* OrionCard public site: language toggle (Swahili default, English), mobile
   menu, and small fetch helpers for whitelisted methods. Pages are written in
   Swahili; [data-i18n] elements swap to the English text below and back. */
(function () {
	const EN = {
		"nav.how": "How it works",
		"nav.contrib": "Contributions",
		"nav.features": "Features",
		"nav.pricing": "Pricing",
		"nav.faq": "Questions",
		"nav.login": "Log in",
		"nav.signup": "Sign up free",
		"nav.credits": "Credits",
		"nav.dashboard": "My occasions",
		"footer.tag": "Your event's cards, contributions and guests, in one place.",
		"footer.product": "Product",
		"footer.help": "Help",
		"footer.terms": "Terms & Conditions",
		"footer.privacy": "Privacy Policy",

		"hero.tag": "For weddings, send-offs, kitchen parties and every celebration",
		"hero.title": "Contributions, cards and guests for your celebration, without Excel.",
		"hero.note2": "Free to start. Pay with M-Pesa, Mixx, Airtel or HaloPesa.",
		"hero.p1": "Free to start",
		"hero.p2": "Pay with M-Pesa, Mixx, Airtel or HaloPesa",
		"hero.p3": "Receipts on WhatsApp",
		"hero.now": "just now",
		"hero.bubble": "You're invited to Amina & Baraka's wedding. Card: VIP · Card number: 278179",
		"hero.toast": "Welcome, Mzee Salim Juma!",
		"hero.toast_sub": "Gate · VIP · 5:58 pm",
		"cta.calc": "Work out your price",
		"tour.title": "This is what you'll see inside the system",
		"tour.lede": "Real OrionCard screens, using Amina & Baraka's wedding as the example.",
		"tour.t1": "Contributions",
		"tour.t1d": "Pledges, instalments and each person's balance",
		"tour.t2": "Budget",
		"tour.t2d": "Planned against spent, by category",
		"tour.t3": "Card design",
		"tour.t3d": "Upload Your Invitation card; names and QR codes are added",
		"tour.t4": "Statistics",
		"tour.t4d": "Confirmed, checked in and contributions at a glance",
		"tour.t5": "Credits",
		"tour.t5d": "Buy SMS and WhatsApp with mobile money",
		"tour.note": "Every contributor is a guest. When you send cards, you choose who gets one: only those who paid in full, or those who paid part too.",
		"guest.title": "What your guest gets",
		"guest.lede": "From the invitation message to walking through the gate, on their phone.",
		"guest.c1": "They receive the invitation on WhatsApp or SMS",
		"guest.c2": "They download their card and confirm they're coming",
		"guest.c3": "At the gate, the QR is scanned and they're welcomed",
		"price.title2": "Clear pricing, by your number of guests",
		"price.lede2": "Creating an event, a budget and a contributions list is free. You pay for guest cards, and every card comes with SMS and WhatsApp credits.",
		"calc.label": "How many guests do you have?",
		"calc.guests": "guests",
		"calc.tier_range": "per card, guests {0}–{1}",
		"calc.tier_open": "per card from guest {0}",
		"calc.tier_credits": "+ {0} SMS and {1} WhatsApp credits per card",
		"calc.line": "Cards {0}–{1}",
		"calc.total": "Total to pay",
		"calc.included": "Credits you get:",
		"calc.topup_t": "Adding guests later",
		"calc.topup_d": "You can add up to {0}% of the guests you paid for at the same rate you started with. Beyond that, the normal price applies.",
		"calc.cta": "Get started",
		"pay.title": "How to pay",
		"pay.s1": "Request a card package on your event, or choose credits on the Credits page.",
		"pay.s2": "Enter your mobile money number and confirm with your PIN on your phone.",
		"pay.s3": "Once the payment is confirmed, credits are added and your receipt arrives on WhatsApp.",
		"pay.receipt": "A sample of the receipt you receive",
		"price.extra": "Need more messages? Credit packages",
		"faq.q8": "What if I add guests after paying?",
		"faq.a8": "Request extra cards on your event. Up to {0}% of the cards you paid for are added at the rate you started with; beyond that, the normal price for that number applies.",
		"hero.lede": "Record every pledge and payment, send QR invitation cards by SMS and WhatsApp, then welcome guests at the gate with a phone scan.",
		"hero.note": "Creating an event, a budget and a contributions list is free. You pay for cards and messages only when you send.",
		"hero.card_meta": "Saturday, 14 December<br>Diamond Jubilee, Dar es Salaam<br>6:00 pm",
		"hero.stamp": "✓ Welcome, Rehema!",
		"hero.jina": "Little by little, contributions fill the celebration.",
		"cta.signup": "Sign up free",
		"cta.pricing": "See pricing",

		"how.title": "From the committee meeting to the door",
		"how.lede": "Four steps, on your phone or computer.",
		"how.s1.t": "Sign up",
		"how.s1.d": "Open an account with your email, then create your event.",
		"how.s2.t": "Plan contributions and budget",
		"how.s2.d": "List contributors and their pledges, then enter what each has paid. Payment status works itself out.",
		"how.s3.t": "Send cards",
		"how.s3.d": "Each guest gets a card with their name and a QR code by SMS or WhatsApp. You choose who gets one.",

		"feat.money.t": "Contributions and budget on one page",
		"feat.money.d": "Every contributor, their pledge, what they've paid and their balance. The budget shows what's planned, what's spent and the gap left.",
		"feat.money.l1": "Payment status works itself out: not paid, partly paid or fully paid",
		"feat.money.l2": "Import your Excel list, or export everything for the committee",
		"feat.money.l3": "Send contribution reminders by SMS or WhatsApp",
		"feat.card.t": "Your Invitation card, with each guest's name",
		"feat.card.d": "Upload the card you designed. OrionCard adds each guest's name, card type and QR code.",
		"feat.card.l1": "Send by SMS, or the card picture itself on WhatsApp",
		"feat.card.l2": "Choose who gets a card: only those who paid in full, or those who paid part too",
		"feat.card.l3": "Guests confirm they're coming from their card link",
		"guest.c1t": "The invitation",
		"guest.c2t": "Card and RSVP",
		"guest.c3t": "At the gate",
		"more.title": "Also in OrionCard",
		"more.types.t": "DOUBLE, VIP and TABLE cards",
		"more.types.d": "One card can let in two people, or a whole table of the size you set.",
		"more.pay.t": "Pay with mobile money",
		"more.pay.d": "M-Pesa, Mixx by Yas, Airtel Money and HaloPesa. You confirm with your PIN on your phone.",
		"more.receipt.t": "A receipt for every payment",
		"more.receipt.d": "Receipts for cards and credits arrive on WhatsApp and by email.",
		"how.s4.t": "Welcome guests at the gate",
		"how.s4.d": "Gate staff scan the QR with a phone. Each card gets in once.",

		"contrib.title": "Contributors who finish paying get their card automatically",
		"contrib.lede": "Update what each contributor has paid and their status changes by itself: Not Paid, Partially Paid or Fully Paid.",
		"contrib.t1": "Pledges and instalments for every contributor",
		"contrib.t2": "Balances and payment status calculate themselves",
		"contrib.t3": "Import your existing Excel list",
		"contrib.t4": "Send contribution reminders by SMS or WhatsApp",
		"ledger.title": "Contributions · Amina's wedding",
		"ledger.count": "4 contributors",
		"ledger.progress": "Collected TZS 1,360,000 of 2,000,000",
		"ledger.invited": "Added to guests",
		"status.full": "Fully paid",
		"status.part": "Partly paid",
		"status.none": "Not paid",

		"gate.title": "At the gate, each card gets in once",
		"gate.lede": "Gate staff open the check-in page on their phones and scan. A card that was already used shows up immediately.",
		"gate.t1": "Works on any phone with a camera",
		"gate.t2": "A gate PIN keeps out anyone who isn't staff",
		"gate.t3": "See how many guests have arrived at any moment",
		"phone.ok": "Welcome, Rehema!",
		"phone.in": "Checked in",
		"phone.dup": "Repeats",

		"also.design.t": "Your own card design",
		"also.design.d": "Upload the card you designed in Canva; each guest's name, card type and QR are added for you.",
		"also.rsvp.t": "RSVPs",
		"also.rsvp.d": "Guests confirm whether they're coming from their card link.",
		"also.budget.t": "Budget by category",
		"also.budget.d": "Venue, food, décor and more: planned against spent.",
		"also.auto.t": "Automatic reminders",
		"also.auto.d": "Choose how often contributors with a balance are reminded, up to the deadline.",
		"also.excel.t": "Export to Excel",
		"also.excel.d": "Download every contribution for the committee.",
		"also.privacy.t": "Your data stays yours",
		"also.privacy.d": "Only you see your event. We never sell guest data.",

		"price.title": "Pay only for what you send",
		"price.lede": "Creating an event, planning a budget and recording contributions is free.",
		"price.cards.t": "Invitation cards",
		"price.cards.u": "per guest",
		"price.cards.u_tier": "per card, guests 1–{0}",
		"price.cards.next": "{0} per card from guest {1}",
		"price.cards.credits": "Each card includes {0} SMS and {1} WhatsApp credits",
		"price.cards.ask": "On request",
		"price.cards.ask_u": "based on your number of guests",
		"price.cards.l1": "Named card with QR code",
		"price.cards.l2": "Gate check-in",
		"price.cards.l3": "Guest RSVPs",
		"price.sms.u": "per credit (160 characters)",
		"price.sms.l1": "Reaches any phone",
		"price.sms.l2": "Rejected messages aren't charged",
		"price.wa.u": "per message",
		"price.wa.l1": "Long messages at no extra cost",
		"price.wa.l2": "Card download link included",
		"price.pkg": "Package",

		"faq.title": "Frequently asked questions",
		"faq.q1": "Does OrionCard collect contribution money?",
		"faq.a1": "No. Contributions are paid directly to the organiser. OrionCard only records the pledges and payments you enter, so the committee sees where things stand.",
		"faq.q2": "What if a message isn't delivered?",
		"faq.a2": "Messages rejected by the provider aren't charged. Accepted messages depend on the mobile networks, so we can't guarantee every one is read.",
		"faq.q3": "Why does a long SMS use more than one credit?",
		"faq.a3": "One SMS is 160 characters. Longer messages are split into parts, and each part is 1 credit. Emoji shorten a part to 70 characters. You see the credit count before sending.",
		"faq.q4": "How do I pay?",
		"faq.a4": "With M-Pesa, Mixx by Yas, Airtel Money or HaloPesa. You get a PIN prompt on your phone, and your receipt is sent on WhatsApp once the payment is confirmed.",
		"faq.q5": "Do credits expire?",
		"faq.a5": "No. Credits stay on your account until you use them, on any event.",
		"faq.a5_expiry": "Yes, unused credits expire {0} months after purchase.",
		"faq.q6": "What if the internet drops at the gate?",
		"faq.a6": "The scanning phone needs internet. Keep a printed guest list as a backup on the day.",
		"faq.q7": "Who can see my guests' details?",
		"faq.a7": "Only you and the system administrators. Read the <a href=\"/privacy\">Privacy Policy</a> and <a href=\"/terms\">Terms & Conditions</a>, including the system's limitations.",
		"cta.title": "Start planning your celebration today",
		"cta.lede": "Opening an account is free. You only pay for cards and credits when you need them.",

		"signup.title": "Open your account",
		"signup.lede": "Fill in your details, choose a password, and start planning your event right away.",
		"signup.t1": "Creating events, budgets and contribution lists is free",
		"signup.t2": "You pay for cards and SMS/WhatsApp credits only when you need them",
		"signup.t3": "You pay for cards and messages only when you send",
		"signup.name": "Full name",
		"signup.email": "Email",
		"signup.phone": "Phone number",
		"signup.phone_help": "Used only to support you, never for adverts.",
		"signup.password": "Password",
		"signup.password_help": "At least 8 characters.",
		"signup.confirm_password": "Repeat password",
		"signup.accept": "I have read and accept the <a href=\"/terms\" target=\"_blank\">Terms & Conditions</a> and <a href=\"/privacy\" target=\"_blank\">Privacy Policy</a>, including the system's limitations.",
		"signup.submit": "Open account",
		"signup.have": "Already have an account?",

		"credits.title": "Buy credits",
		"credits.balance": "Credit balance",
		"credits.used": "Used",
		"credits.buy_sms": "Buy SMS credits",
		"credits.buy_wa": "Buy WhatsApp credits",
		"credits.pick_sms": "Choose an SMS package",
		"credits.pick_wa": "Choose a WhatsApp package",
		"credits.custom_label": "Custom quantity",
		"credits.custom_ph": "Or enter your own quantity, e.g. {0}",
		"credits.total": "Total amount due",
		"credits.proceed": "Proceed to payment",
		"credits.phone": "Mobile money number (M-Pesa, Mixx, Airtel, HaloPesa)",
		"credits.phone_help": "You'll get a PIN prompt on this phone.",
		"credits.manual_note": "Online payment isn't switched on yet. If you continue, you'll get payment instructions and credits are added once the payment is confirmed.",
		"credits.accept": "I agree that credits are non-refundable, can't be exchanged for cash, and are used under the <a href=\"/terms\" target=\"_blank\">Terms & Conditions</a>.",
		"credits.pay": "Pay now",
		"credits.recent": "Recent purchases",
		"credits.receipt": "Receipt",
		"credits.back": "Back to my occasions",
		"credits.manual_ref": "Purchase {0} created.",
		"credits.slow": "We're still waiting for the payment confirmation for {0}. Your credits will appear here once it arrives — you can leave this page.",
		"credits.done": "Payment received: {0} {1} credits added.",
		"credits.failed": "The payment didn't go through. Check your balance and PIN, then try again.",

		"err.name": "Enter your full name.",
		"err.email": "Enter a valid email address.",
		"err.terms": "Tick the box to accept the Terms & Conditions.",
		"err.password": "Password must be at least 8 characters.",
		"err.password_match": "The two passwords don't match.",
		"err.credit_terms": "Tick the box to accept the credit terms.",
		"err.phone": "Enter the mobile money number to pay with.",
		"err.network": "Couldn't reach the server. Check your connection and try again.",
	};

	// Swahili for strings that only exist in JavaScript (page text is already Swahili).
	const SW = {
		"credits.pick_sms": "Chagua kifurushi cha SMS",
		"calc.line": "Kadi {0}–{1}",
		"credits.pick_wa": "Chagua kifurushi cha WhatsApp",
		"credits.custom_ph": "Au weka idadi yako, mf. {0}",
		"credits.manual_ref": "Ombi la ununuzi {0} limeundwa.",
		"credits.slow": "Bado tunasubiri uthibitisho wa malipo ya {0}. Credits zitaonekana hapa zikifika — unaweza kuondoka kwenye ukurasa huu.",
		"credits.done": "Malipo yamepokelewa: credits {0} za {1} zimeongezwa.",
		"credits.failed": "Malipo hayakufanikiwa. Hakikisha salio na PIN yako, kisha jaribu tena.",
		"err.name": "Weka jina lako kamili.",
		"err.email": "Weka barua pepe sahihi.",
		"err.terms": "Weka alama kukubali Vigezo na Masharti.",
		"err.password": "Nenosiri liwe na herufi 8 au zaidi.",
		"err.password_match": "Manenosiri mawili hayafanani.",
		"err.credit_terms": "Weka alama kukubali masharti ya credits.",
		"err.phone": "Weka namba ya pesa ya simu utakayolipia.",
		"err.network": "Imeshindwa kufikia seva. Angalia mtandao wako na ujaribu tena.",
	};

	const STORE_KEY = "ec_lang";
	let lang = "sw";
	try { lang = localStorage.getItem(STORE_KEY) === "en" ? "en" : "sw"; } catch (e) { /* storage blocked */ }

	function format(text, args) {
		return (args || []).reduce((s, a, i) => s.split("{" + i + "}").join(a), text);
	}

	function t(key, args) {
		const text = (lang === "en" ? EN[key] : SW[key]) || EN[key] || key;
		return format(text, args);
	}

	function apply() {
		document.documentElement.lang = lang;
		document.querySelectorAll("[data-i18n], [data-i18n-html]").forEach((el) => {
			const key = el.dataset.i18n || el.dataset.i18nHtml;
			if (el.dataset.i18nSw === undefined) el.dataset.i18nSw = el.innerHTML;
			let args = [];
			try { args = JSON.parse(el.dataset.i18nArgs || "[]"); } catch (e) { /* ignore */ }
			if (lang === "en" && EN[key]) {
				el.innerHTML = format(EN[key], args);
			} else {
				el.innerHTML = el.dataset.i18nSw;
			}
		});
		document.querySelectorAll("[data-lang-block]").forEach((el) => {
			el.hidden = el.dataset.langBlock !== lang;
		});
		document.querySelectorAll(".ec-lang button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.lang === lang)));
		document.dispatchEvent(new CustomEvent("ec:lang", { detail: { lang } }));
	}

	function setLang(next) {
		lang = next === "en" ? "en" : "sw";
		try { localStorage.setItem(STORE_KEY, lang); } catch (e) { /* storage blocked */ }
		apply();
	}

	async function call(method, data, httpMethod) {
		const url = "/api/method/" + method + (httpMethod === "GET" && data ? "?" + new URLSearchParams(data) : "");
		let response;
		try {
			response = await fetch(url, {
				method: httpMethod,
				headers: {
					"Content-Type": "application/json",
					Accept: "application/json",
					"X-Frappe-CSRF-Token": window.EC_CSRF || "",
				},
				body: httpMethod === "POST" ? JSON.stringify(data || {}) : undefined,
				credentials: "same-origin",
			});
		} catch (e) {
			throw new Error(t("err.network"));
		}
		const body = await response.json().catch(() => ({}));
		if (!response.ok || body.exc_type) {
			throw new Error(serverMessage(body) || t("err.network"));
		}
		return body.message;
	}

	function serverMessage(body) {
		if (body._server_messages) {
			try {
				const first = JSON.parse(JSON.parse(body._server_messages)[0]);
				const div = document.createElement("div");
				div.innerHTML = first.message || "";
				return div.textContent;
			} catch (e) { /* fall through */ }
		}
		return body.message || body.exception || "";
	}

	window.EC = {
		t,
		post: (method, data) => call(method, data, "POST"),
		get: (method, params) => call(method, params, "GET"),
		get lang() { return lang; },
	};

	document.documentElement.classList.add("ec-js");

	function revealOnScroll() {
		const items = document.querySelectorAll(".ec-reveal");
		if (!("IntersectionObserver" in window)) {
			items.forEach((el) => el.classList.add("is-in"));
			return;
		}
		const io = new IntersectionObserver((entries) => {
			entries.forEach((entry) => {
				if (entry.isIntersecting) {
					entry.target.classList.add("is-in");
					io.unobserve(entry.target);
				}
			});
		}, { threshold: 0.15, rootMargin: "0px 0px -40px 0px" });
		items.forEach((el) => io.observe(el));
	}

	document.addEventListener("DOMContentLoaded", () => {
		revealOnScroll();
		document.querySelectorAll(".ec-lang button").forEach((b) => b.addEventListener("click", () => setLang(b.dataset.lang)));

		const nav = document.getElementById("ecNav");
		const menuBtn = document.getElementById("ecMenuBtn");
		if (nav && menuBtn) {
			menuBtn.addEventListener("click", () => {
				const open = nav.classList.toggle("is-open");
				menuBtn.setAttribute("aria-expanded", String(open));
			});
			nav.querySelectorAll(".ec-nav-links a").forEach((a) =>
				a.addEventListener("click", () => {
					nav.classList.remove("is-open");
					menuBtn.setAttribute("aria-expanded", "false");
				})
			);
		}
		apply();
	});
})();
