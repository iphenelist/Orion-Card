app_name = "orion_card"
app_title = "OrionCard"
app_publisher = "Innocent P M"
app_description = "electronic card management app"
app_email = "innocentphenelist@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "orion_card",
# 		"logo": "/assets/orion_card/logo.png",
# 		"title": "OrionCard",
# 		"route": "/orion_card",
# 		"has_permission": "orion_card.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/orion_card/css/orion_card.css"
app_include_js = "/assets/orion_card/js/orioncard_desk.js"

# include js, css files in header of web template
# web_include_css = "/assets/orion_card/css/orion_card.css"
# web_include_js = "/assets/orion_card/js/orion_card.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "orion_card/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "orion_card/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
home_page = "orioncard"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "orion_card.utils.jinja_methods",
# 	"filters": "orion_card.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "orion_card.install.before_install"
after_install = "orion_card.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "orion_card.uninstall.before_uninstall"
# after_uninstall = "orion_card.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "orion_card.utils.before_app_install"
# after_app_install = "orion_card.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "orion_card.utils.before_app_uninstall"
# after_app_uninstall = "orion_card.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "orion_card.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "orion_card.notifications.get_notification_config"

# Permissions
# -----------
# Administrator and System Manager have full access to every OrionCard doctype.
# Occasion Managers only have the Occasion doctype (and its child tables),
# and only see the Occasions they created or that a System Manager assigned
# to them (assigned_user, permlevel 1).

permission_query_conditions = {
    "Occasion": "orion_card.orioncard.doctype.occasion.occasion.get_permission_query_conditions",
    "Message Credit Account": "orion_card.permissions.credit_account_query",
    "Credit Transaction": "orion_card.permissions.credit_transaction_query",
    "Credit Purchase": "orion_card.permissions.credit_purchase_query",
    "Occasion Subscription": "orion_card.orioncard.doctype.occasion_subscription.occasion_subscription.get_permission_query_conditions",
    "Occasion Guest Invite Log": "orion_card.orioncard.doctype.occasion_guest_invite_log.occasion_guest_invite_log.get_permission_query_conditions",
}

has_permission = {
    "Occasion": "orion_card.orioncard.doctype.occasion.occasion.has_permission",
    "Message Credit Account": "orion_card.permissions.credit_account_has_permission",
    "Credit Transaction": "orion_card.permissions.credit_transaction_has_permission",
    "Credit Purchase": "orion_card.permissions.credit_purchase_has_permission",
    "Occasion Subscription": "orion_card.orioncard.doctype.occasion_subscription.occasion_subscription.has_permission",
    "Occasion Guest Invite Log": "orion_card.orioncard.doctype.occasion_guest_invite_log.occasion_guest_invite_log.has_permission",
}

website_route_rules = [
    {"from_route": "/invitee/download/occasion-card/<guest_code>", "to_route": "invitee/download/occasion-card"},
    # Short card link used in the SMS invitation, to keep it to 2 SMS parts.
    {"from_route": "/k/<guest_code>", "to_route": "invitee/download/occasion-card"},
    {"from_route": "/gate-checkin", "to_route": "gate-checkin"},
]

# The app used to be called e_card_ms with its landing page at /e-card.
website_redirects = [
    {"source": "/e-card", "target": "/orioncard"},
]

# Old method paths that outside callers still use: Abliner's webhook URL (set
# in its dashboard and on payments started before the rename) and pages
# already open in browsers. They keep working under the new app name.
override_whitelisted_methods = {
    "e_card_ms.api.payments.payment_callback": "orion_card.api.payments.payment_callback",
    "e_card_ms.www.gate-checkin.index.validate_guest": "orion_card.www.gate-checkin.index.validate_guest",
    "e_card_ms.www.invitee.download.occasion-card.index.confirm_rsvp":
        "orion_card.www.invitee.download.occasion-card.index.confirm_rsvp",
}

boot_session = "orion_card.api.auth.boot_session"

jinja = {"methods": ["orion_card.utils.assets.asset_version"]}

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		"*/5 * * * *": [
			"orion_card.api.payments.sync_pending_purchases",
			"orion_card.api.auth.send_pending_welcome_emails",
		],
	}
}

# Testing
# -------

# before_tests = "orion_card.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "orion_card.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "orion_card.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "orion_card.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["orion_card.utils.before_request"]
# after_request = ["orion_card.utils.after_request"]

# Job Events
# ----------
# before_job = ["orion_card.utils.before_job"]
# after_job = ["orion_card.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"orion_card.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

