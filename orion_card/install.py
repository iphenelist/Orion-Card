import frappe

# (from card, to card [0 = no limit], price, internal profit, SMS credits, WhatsApp credits)
DEFAULT_CARD_TIERS = [
    (1, 100, 900, 400, 10, 3),
    (101, 0, 1200, 400, 14, 6),
]

DEFAULT_PACKAGES = [
    ("Starter", 100),
    ("Popular", 500),
    ("Pro", 900),
    ("Enterprise", 1000),
]


# Check fields that should start switched on. A Single doctype loads a never-saved
# Check as 0, so "missing" has to be detected in tabSingles itself.
ON_BY_DEFAULT = (
    "enable_credit_billing",
    "sms_enabled",
    "whatsapp_enabled",
    "poll_pending_payments",
    "require_reacceptance",
)


def _saved_before(field: str) -> bool:
    return bool(frappe.db.sql(
        "select 1 from `tabSingles` where doctype='OrionCard Settings' and field=%s", field
    ))


def after_install():
    setup_roles()
    setup_settings_defaults()
    frappe.db.commit()
    print("✅ OrionCard roles and settings installed successfully!")


def setup_roles():
    # "Occasion Manager": a self-registered (or approved) customer — sees and
    # manages only the Occasions they created (or were assigned), with their
    # child tables. Every other OrionCard doctype is System Manager only.
    for role_name in ("Occasion Manager",):
        if not frappe.db.exists("Role", role_name):
            r = frappe.new_doc("Role")
            r.role_name = role_name
            r.desk_access = 1
            r.insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Role", role_name, "desk_access", 1)
    # Occasion Managers land on their Occasion list in the Desk after login.
    frappe.db.set_value("Role", "Occasion Manager", "home_page", "/app/occasion")


def setup_settings_defaults():
    """Seed prices, the 8 credit packages from the pricing screen, and the
    default Terms & Privacy text — only where nothing is set yet."""
    from orion_card.legal import set_default_legal_text

    settings = frappe.get_single("OrionCard Settings")
    defaults = {
        "currency": "TZS",
        "sms_credit_price": 25,
        "whatsapp_credit_price": 75,
        "min_custom_credits": 10,
        "base_url": "https://abliner.net/api/v1",
        "gateway_provider": "Abliner",
        "request_timeout": 30,
        "liability_cap_months": 3,
    }
    for field, value in defaults.items():
        if not settings.get(field):
            settings.set(field, value)
    if not _saved_before("top_up_locked_percent"):
        settings.top_up_locked_percent = 20
    for field in ON_BY_DEFAULT:
        if not _saved_before(field):
            settings.set(field, 1)

    if not settings.credit_packages:
        for channel in ("SMS", "WhatsApp"):
            for label, credit_count in DEFAULT_PACKAGES:
                settings.append("credit_packages", {
                    "channel": channel, "label": label, "credits": credit_count, "enabled": 1,
                })

    seed_card_price_tiers(settings)

    if not settings.terms_content_sw:
        set_default_legal_text(settings)

    settings.flags.ignore_permissions = True
    settings.save()


def seed_card_price_tiers(settings):
    if settings.card_price_tiers:
        return
    for start, end, price, profit, sms, whatsapp in DEFAULT_CARD_TIERS:
        settings.append("card_price_tiers", {
            "from_card": start,
            "to_card": end,
            "price_per_card": price,
            "profit_per_card": profit,
            "sms_credits_per_card": sms,
            "whatsapp_credits_per_card": whatsapp,
        })
