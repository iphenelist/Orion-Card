"""Terms & Conditions / Privacy Policy: default text, rendering and acceptance.

The text is stored on OrionCard Settings (editable by a System Manager) and may use
Jinja placeholders such as {{ business_name }} or {{ sms_price }}, filled from
the same settings when rendered, so prices and contacts never drift out of date.

NOTE: the default text is a starting draft, not legal advice — have it reviewed
by a Tanzanian lawyer before launch.
"""

import hashlib

import frappe
from frappe import _
from frappe.utils import cint, fmt_money, formatdate, now_datetime

# ---------------------------------------------------------------- default text

TERMS_SW = """
<h2>1. Sisi ni nani na huduma hii ni nini</h2>
<p>Huduma hii ya OrionCard inaendeshwa na <b>{{ business_name }}</b>. Ni zana ya kusaidia kuandaa matukio: kutengeneza kadi za mwaliko za kidijitali zenye QR code, kutuma mialiko kwa SMS na WhatsApp, kurekodi michango na bajeti, na kuthibitisha wageni getini.</p>

<h2>2. Akaunti yako</h2>
<ul>
<li>Toa taarifa sahihi wakati wa kujisajili.</li>
<li>Linda nenosiri lako; vitendo vyote vinavyofanyika kupitia akaunti yako ni jukumu lako.</li>
<li>Tunaweza kusimamisha au kufunga akaunti inayokiuka masharti haya.</li>
</ul>

<h2>3. Taarifa unazoingiza na idhini ya wahusika</h2>
<p>Wewe (Msimamizi wa Tukio) ndiye <b>mdhibiti wa taarifa</b> (data controller) za wageni na wachangiaji unaowaingiza kwenye mfumo. Unathibitisha kuwa umepata <b>idhini</b> yao kuhifadhi majina na namba zao za simu na kuwatumia ujumbe, kwa mujibu wa <b>Sheria ya Ulinzi wa Taarifa Binafsi, 2022 (Tanzania)</b>. Sisi tunachakata taarifa hizo kwa niaba yako ili kukupa huduma.</p>

<h2>4. Maudhui ya ujumbe na matumizi mabaya</h2>
<p>Unawajibika kwa maudhui ya kila ujumbe unaotumwa kupitia akaunti yako. Ni marufuku kutuma ujumbe wa unyanyasaji, utapeli, maombi ya fedha ya kupotosha, kampeni za kisiasa, au ujumbe kwa watu wasiokubali kupokea. Tunaweza kusimamisha utumaji na kufunga akaunti inayotumika vibaya; credits za akaunti iliyofungwa kwa matumizi mabaya hazirudishwi.</p>

<h2>5. Michango ni kumbukumbu tu</h2>
<p>Mfumo <b>haupokei, haushikilii wala hauhamishi fedha za michango</b>. Unarekodi tu kile unachoingiza. Fedha zote za michango hupokelewa moja kwa moja na mwandaaji wa tukio. {{ business_name }} <b>si sehemu</b> ya mgogoro wowote kuhusu michango, ahadi, malipo yasiyokamilika au matumizi ya fedha.</p>

<h2>6. Malipo, credits na kifurushi cha kadi</h2>
<ul>
<li>Bei zote ni kwa {{ currency }} kama zinavyoonyeshwa wakati wa ununuzi. Kwa sasa: credit 1 ya SMS = {{ sms_price }}, credit 1 ya WhatsApp = {{ whatsapp_price }}.</li>
<li>SMS hukatwa credit 1 kwa kila kipande cha herufi 160 (herufi 70 ikiwa ujumbe una emoji au herufi maalum). WhatsApp hukatwa credit 1 kwa kila ujumbe.</li>
<li>Credits huongezwa baada ya mtoa huduma wa malipo kuthibitisha malipo.</li>
<li><b>Credits hazirudishwi wala kubadilishwa kuwa fedha taslimu</b>, na haziwezi kuhamishiwa akaunti nyingine.</li>
<li>Ujumbe uliokataliwa na mtoa huduma wa ujumbe haukatwi credits.</li>
<li>{{ credit_expiry_sw }}</li>
<li>Kifurushi cha kadi (subscription) hulipwa kwa idadi ya wageni wa tukio husika.</li>
<li>Bei zinaweza kubadilika; credits ulizokwisha nunua haziathiriki.</li>
</ul>

<h2>7. Ufikaji wa ujumbe haudhaminiwi</h2>
<p>Tunatuma ujumbe kwenye mitandao ya SMS na WhatsApp lakini <b>hatudhamini</b> kuwa utafika, utafika lini, au utasomwa. Kuchelewa au kutofika kwa ujumbe si sababu ya kurejeshewa fedha isipokuwa kama kosa ni letu.</p>

<h2>8. Kadi za kidijitali na QR code</h2>
<p>Hakikisha majina na taarifa ni sahihi kabla ya kutuma. Kadi yenye QR code inaweza kunakiliwa au kutumwa kwa mtu mwingine; kwa hiyo mfumo huruhusu kila kadi kuingia mara moja tu (isipokuwa ukiruhusu kuingia tena). Walinzi wa getini wanapaswa kulinda PIN ya geti.</p>

<h2>9. Upatikanaji wa huduma</h2>
<p>Huduma inatolewa "kama ilivyo" na "inapopatikana". Kunaweza kuwa na matengenezo au kukatika kwa huduma. Hatudhamini kuwa huduma haitakatika, hasa siku ya tukio; tunashauri uwe na orodha ya wageni iliyochapishwa kama akiba.</p>

<h2>10. Ukomo wa dhima</h2>
<p>Kwa kiwango kinachoruhusiwa na sheria, dhima yetu yote kwa madai yoyote <b>haitazidi kiasi ulichotulipa katika miezi {{ liability_cap_months }} kabla ya madai</b>. Hatuwajibiki kwa hasara zisizo za moja kwa moja kama hasara za tukio, wageni waliokosa mwaliko, michango isiyolipwa au madhara ya sifa.</p>

<h2>11. Fidia</h2>
<p>Unakubali kutulinda dhidi ya madai yanayotokana na taarifa ulizoingiza bila idhini au maudhui uliyotuma.</p>

<h2>12. Haki miliki</h2>
<p>Miundo ya kadi na taarifa zako ni mali yako; unatupa ruhusa ya kuzichakata ili kukupa huduma tu. Mfumo, msimbo na chapa ni mali ya {{ business_name }}.</p>

<h2>13. Kusitisha huduma</h2>
<p>Unaweza kufunga akaunti yako wakati wowote. Tunaweza kuifunga ukikiuka masharti haya. Taarifa zako zitahifadhiwa na kufutwa kwa mujibu wa Sera ya Faragha.</p>

<h2>14. Mabadiliko ya masharti</h2>
<p>Toleo jipya likitolewa litatangazwa kwenye mfumo, na utahitajika kulikubali kabla ya kuendelea kutumia huduma.</p>

<h2>15. Sheria inayotumika na migogoro</h2>
<p>Masharti haya yanaongozwa na sheria za Jamhuri ya Muungano wa Tanzania. Pande zote zitajaribu kutatua mgogoro kwa mazungumzo kwa siku 30 kwanza, kisha mahakama za Tanzania.</p>

<h2>16. Mawasiliano</h2>
<p>{{ business_name }} &middot; {{ support_email }} &middot; {{ support_phone }}<br>{{ business_address }}</p>
"""

TERMS_EN = """
<h2>1. Who we are and what the service is</h2>
<p>The OrionCard service is operated by <b>{{ business_name }}</b>. It is a tool for organising events: creating digital invitation cards with QR codes, sending invitations by SMS and WhatsApp, recording contributions and budgets, and checking guests in at the gate.</p>

<h2>2. Your account</h2>
<ul>
<li>Provide accurate information when you sign up.</li>
<li>Keep your password secret; everything done through your account is your responsibility.</li>
<li>We may suspend or close an account that breaches these Terms.</li>
</ul>

<h2>3. Data you enter and consent</h2>
<p>You (the Occasion Manager) are the <b>data controller</b> for the guest and contributor data you enter. You confirm you have their <b>consent</b> to store their names and phone numbers and to send them messages, as required by the <b>Personal Data Protection Act, 2022 (Tanzania)</b>. We process that data on your behalf to provide the service.</p>

<h2>4. Message content and misuse</h2>
<p>You are responsible for the content of every message sent from your account. Harassment, fraud, misleading requests for money, political campaigning, and messages to people who have not agreed to receive them are prohibited. We may stop sending and close an account that is misused; credits on an account closed for misuse are not refunded.</p>

<h2>5. Contributions are a record only</h2>
<p>The system <b>does not collect, hold or transfer contribution money</b>. It only records what you enter. All contribution money is received directly by the event organiser. {{ business_name }} is <b>not a party</b> to any dispute about contributions, pledges, unpaid amounts, or how money was used.</p>

<h2>6. Payments, credits and card subscriptions</h2>
<ul>
<li>All prices are in {{ currency }} as shown at the time of purchase. Currently: 1 SMS credit = {{ sms_price }}, 1 WhatsApp credit = {{ whatsapp_price }}.</li>
<li>SMS uses 1 credit per 160-character part (70 characters if the message contains emoji or special characters). WhatsApp uses 1 credit per message.</li>
<li>Credits are added once the payment provider confirms the payment.</li>
<li><b>Credits are non-refundable and cannot be exchanged for cash</b> or transferred to another account.</li>
<li>A message rejected by the messaging provider is not charged.</li>
<li>{{ credit_expiry_en }}</li>
<li>A card subscription is paid per guest for the specific occasion.</li>
<li>Prices may change; credits you have already bought are not affected.</li>
</ul>

<h2>7. Message delivery is not guaranteed</h2>
<p>We hand messages to the SMS and WhatsApp networks but <b>do not guarantee</b> they will be delivered, when, or that they will be read. Late or failed delivery is not grounds for a refund unless we caused it.</p>

<h2>8. Digital cards and QR codes</h2>
<p>Check names and details before sending. A QR card can be copied or forwarded, so the system admits each card only once (unless you allow re-entry). Gate staff must protect the gate PIN.</p>

<h2>9. Service availability</h2>
<p>The service is provided "as is" and "as available". There may be maintenance or interruptions. We do not guarantee uninterrupted service, especially on the day of your event; keep a printed guest list as a backup.</p>

<h2>10. Limitation of liability</h2>
<p>To the extent permitted by law, our total liability for any claim is <b>limited to the amount you paid us in the {{ liability_cap_months }} months before the claim</b>. We are not liable for indirect losses such as event losses, guests who missed an invitation, unpaid contributions, or reputational harm.</p>

<h2>11. Indemnity</h2>
<p>You agree to protect us against claims arising from data you entered without consent or content you sent.</p>

<h2>12. Intellectual property</h2>
<p>Your card designs and data remain yours; you license us to process them only to provide the service. The system, its code and brand belong to {{ business_name }}.</p>

<h2>13. Ending the service</h2>
<p>You can close your account at any time. We may close it if you breach these Terms. Your data is kept and deleted as described in the Privacy Policy.</p>

<h2>14. Changes to these Terms</h2>
<p>A new version will be announced in the system, and you will need to accept it before continuing to use the service.</p>

<h2>15. Governing law and disputes</h2>
<p>These Terms are governed by the laws of the United Republic of Tanzania. The parties will first try to resolve a dispute by negotiation for 30 days, then before the courts of Tanzania.</p>

<h2>16. Contact</h2>
<p>{{ business_name }} &middot; {{ support_email }} &middot; {{ support_phone }}<br>{{ business_address }}</p>
"""

LIMITATIONS_SW = """
<h2>Mapungufu ya mfumo unayopaswa kujua</h2>
<ul>
<li><b>SMS na WhatsApp:</b> ufikaji unategemea watoa huduma wengine (RodSMS, WaSenderAPI) na mitandao ya simu. Simu inaweza kuwa imezimwa, namba si sahihi, au mpokeaji amezuia ujumbe.</li>
<li><b>WhatsApp:</b> WaSenderAPI si huduma rasmi ya WhatsApp Business. Namba inayotuma <b>inaweza kuzuiwa na WhatsApp</b> ikituma ujumbe mwingi; ufikaji haudhaminiwi.</li>
<li><b>SMS ndefu:</b> hugawanywa vipande kadhaa (na credits kadhaa). Emoji au herufi maalum hupunguza kipande kuwa herufi 70.</li>
<li><b>Malipo ya simu:</b> credits huonekana baada ya Abliner kuthibitisha malipo, inaweza kuchukua dakika chache. Ukikatwa fedha bila kupata credits ndani ya dakika 60, wasiliana nasi ukiwa na namba ya kumbukumbu.</li>
<li><b>Getini:</b> simu ya kuskani inahitaji intaneti. Picha au nakala ya QR inaweza kuingia mara moja badala ya kadi halisi; anayefika kwanza ndiye anaingia. Weka orodha ya wageni iliyochapishwa kama akiba.</li>
<li><b>Code ya mgeni:</b> namba 6 si nenosiri; usisambaze kiungo cha mwaliko hadharani.</li>
<li><b>Michango na bajeti:</b> takwimu ni sahihi kwa kadri ya taarifa unazoingiza. Huu si mfumo wa uhasibu wala risiti rasmi.</li>
<li><b>Kuingiza Excel:</b> faili lazima lifuate kiolezo; mistari yenye makosa huonyeshwa na kurukwa.</li>
<li><b>Muundo wa kadi:</b> majina marefu sana hugawanywa hadi mistari 3 au kufupishwa; kagua mfano kabla ya kutuma.</li>
<li><b>Kompyuta ya pamoja:</b> toka (logout) baada ya kutumia.</li>
</ul>
"""

LIMITATIONS_EN = """
<h2>Known limitations you should be aware of</h2>
<ul>
<li><b>SMS and WhatsApp:</b> delivery depends on third-party providers (RodSMS, WaSenderAPI) and mobile networks. A phone may be off, a number wrong, or the recipient may block messages.</li>
<li><b>WhatsApp:</b> WaSenderAPI is not WhatsApp's official Business API. The sending number <b>can be restricted or blocked by WhatsApp</b> when sending in volume; delivery is not guaranteed.</li>
<li><b>Long SMS:</b> split into several parts (and several credits). Emoji or special characters shorten each part to 70 characters.</li>
<li><b>Mobile payments:</b> credits appear once Abliner confirms the payment, which can take a few minutes. If you were charged but have no credits after 60 minutes, contact us with the reference number.</li>
<li><b>Gate check-in:</b> the scanning phone needs internet. A photo or copy of a QR code can get in once instead of the original card; whoever arrives first is admitted. Keep a printed guest list as a backup.</li>
<li><b>Guest codes:</b> a 6-digit code is not a password; don't share invitation links publicly.</li>
<li><b>Contributions and budget:</b> figures are only as accurate as what you enter. This is not an accounting system or an official receipt.</li>
<li><b>Excel import:</b> files must follow the template; rows with problems are reported and skipped.</li>
<li><b>Card design:</b> very long names wrap onto up to 3 lines or are shortened; check the preview before sending.</li>
<li><b>Shared computers:</b> log out after use.</li>
</ul>
"""

PRIVACY_SW = """
<h2>Taarifa tunazokusanya</h2>
<ul>
<li>Akaunti yako: jina, barua pepe, namba ya simu.</li>
<li>Taarifa za wageni na wachangiaji unazoingiza: majina, namba za simu, kiasi cha michango.</li>
<li>Kumbukumbu za kuingia getini na majibu ya mwaliko (RSVP).</li>
<li>Kumbukumbu za malipo. <b>Hatupokei wala kuhifadhi PIN za pesa za simu au namba za kadi</b>; hayo yanashughulikiwa na mtoa huduma wa malipo.</li>
<li>Kumbukumbu za kiufundi: anwani ya IP na aina ya kivinjari.</li>
</ul>
<h2>Kwa nini</h2>
<p>Kutoa huduma, kutuma ujumbe, kushughulikia malipo, kuzuia matumizi mabaya na kutimiza wajibu wa kisheria.</p>
<h2>Tunashirikiana na nani</h2>
<p>Ni watoa huduma wanaohitajika tu kutoa huduma (SMS, WhatsApp, malipo, seva na barua pepe). <b>Hatuuzi taarifa zako.</b></p>
<h2>Muda wa kuhifadhi</h2>
<p>Taarifa za wageni na wachangiaji huhifadhiwa wakati akaunti iko hai, kisha hufutwa au kufichwa utambulisho miezi 12 baada ya tukio au ukiomba. Kumbukumbu za malipo na makubaliano ya masharti huhifadhiwa kwa muda unaotakiwa na sheria.</p>
<h2>Haki zako</h2>
<p>Unaweza kuomba kuona, kusahihisha au kufuta taarifa zako. Wageni na wachangiaji wanaweza kuwasiliana na mwandaaji wa tukio au nasi: {{ support_email }} &middot; {{ support_phone }}.</p>
<h2>Usalama</h2>
<p>Ufikiaji unalindwa kwa nenosiri na majukumu (roles), na funguo za API huhifadhiwa kwa usimbaji fiche. Uvujaji wa taarifa utaripotiwa kama sheria inavyotaka.</p>
"""

PRIVACY_EN = """
<h2>What we collect</h2>
<ul>
<li>Your account: name, email, phone number.</li>
<li>Guest and contributor data you enter: names, phone numbers, contribution amounts.</li>
<li>Gate check-in and RSVP records.</li>
<li>Payment records. <b>We never receive or store mobile-money PINs or card numbers</b>; the payment provider handles those.</li>
<li>Technical logs: IP address and browser type.</li>
</ul>
<h2>Why</h2>
<p>To provide the service, send messages, process payments, prevent misuse, and meet legal obligations.</p>
<h2>Who we share with</h2>
<p>Only the providers needed to deliver the service (SMS, WhatsApp, payments, hosting and email). <b>We do not sell your data.</b></p>
<h2>Retention</h2>
<p>Guest and contributor data is kept while your account is active, then deleted or anonymised 12 months after the event or on request. Payment and terms-acceptance records are kept as long as the law requires.</p>
<h2>Your rights</h2>
<p>You can ask to see, correct or delete your data. Guests and contributors can contact the event organiser or us: {{ support_email }} &middot; {{ support_phone }}.</p>
<h2>Security</h2>
<p>Access is protected by passwords and roles, and API keys are stored encrypted. Data breaches will be reported as the law requires.</p>
"""


def set_default_legal_text(settings):
	settings.terms_content_sw = (TERMS_SW + LIMITATIONS_SW).strip()
	settings.terms_content_en = (TERMS_EN + LIMITATIONS_EN).strip()
	settings.privacy_content_sw = PRIVACY_SW.strip()
	settings.privacy_content_en = PRIVACY_EN.strip()
	if not settings.terms_version:
		settings.terms_version = "1.0"
	if not settings.terms_effective_date:
		settings.terms_effective_date = frappe.utils.today()


# ---------------------------------------------------------------- rendering


def _context(settings) -> dict:
	currency = settings.currency or "TZS"
	months = cint(settings.credit_expiry_months)
	return {
		"business_name": settings.business_legal_name or "OrionCard",
		"support_email": settings.support_email or "",
		"support_phone": settings.support_phone or "",
		"business_address": settings.business_address or "",
		"currency": currency,
		"sms_price": fmt_money(settings.sms_credit_price or 0, currency=currency, precision=0),
		"whatsapp_price": fmt_money(settings.whatsapp_credit_price or 0, currency=currency, precision=0),
		"liability_cap_months": cint(settings.liability_cap_months) or 3,
		"credit_expiry_sw": (
			f"Credits ambazo hazijatumika zinaisha muda baada ya miezi {months} tangu kununuliwa."
			if months
			else "Credits hazina muda wa kuisha."
		),
		"credit_expiry_en": (
			f"Unused credits expire {months} months after purchase." if months else "Credits do not expire."
		),
	}


def get_legal_documents() -> dict:
	"""Rendered Terms + Privacy in both languages, with version info and hash."""
	settings = frappe.get_cached_doc("OrionCard Settings")
	ctx = _context(settings)
	docs = {}
	for key in ("terms_content_sw", "terms_content_en", "privacy_content_sw", "privacy_content_en"):
		docs[key] = frappe.render_template(settings.get(key) or "", ctx)
	docs["terms_version"] = settings.terms_version or "1.0"
	docs["effective_date"] = formatdate(settings.terms_effective_date) if settings.terms_effective_date else ""
	docs["content_hash"] = hashlib.sha256(
		"\n".join(docs[k] for k in ("terms_content_sw", "terms_content_en", "privacy_content_sw", "privacy_content_en")).encode()
	).hexdigest()
	return docs


# ---------------------------------------------------------------- acceptance


def current_terms_version() -> str:
	return frappe.db.get_single_value("OrionCard Settings", "terms_version") or "1.0"


def record_acceptance(user: str, context: str):
	docs = get_legal_documents()
	request = getattr(frappe.local, "request", None)
	frappe.get_doc({
		"doctype": "Terms Acceptance",
		"user": user,
		"terms_version": docs["terms_version"],
		"context": context,
		"accepted_at": now_datetime(),
		"ip_address": getattr(frappe.local, "request_ip", None),
		"user_agent": (request.headers.get("User-Agent") if request else None),
		"content_hash": docs["content_hash"],
	}).insert(ignore_permissions=True)


def terms_pending(user: str | None = None) -> bool:
	"""True when this Occasion Manager hasn't accepted the current Terms version."""
	user = user or frappe.session.user
	if user in ("Guest", "Administrator"):
		return False
	roles = frappe.get_roles(user)
	if "System Manager" in roles or "Occasion Manager" not in roles:
		return False
	if not cint(frappe.db.get_single_value("OrionCard Settings", "require_reacceptance")):
		return not frappe.db.exists("Terms Acceptance", {"user": user})
	return not frappe.db.exists("Terms Acceptance", {"user": user, "terms_version": current_terms_version()})


def assert_terms_accepted(user: str | None = None):
	if terms_pending(user):
		frappe.throw(
			_("Tafadhali kubali Vigezo na Masharti mapya kwanza. / Please accept the updated Terms & Conditions first."),
			title=_("Terms not accepted"),
		)
