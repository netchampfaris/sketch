app_name = "sketch"
app_title = "Sketch"
app_publisher = "Faris Ansari"
app_description = "High-fidelity frappe-ui prototypes, written by your own agent over MCP"
app_email = "netchamp.faris@gmail.com"
app_license = "mit"

# Send non-GET requests for this app's endpoints as native `application/json`
# bodies instead of form-encoded, per-key JSON-stringified values.
use_json_request_body = True

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "sketch",
# 		"logo": "/assets/sketch/logo.png",
# 		"title": "Sketch",
# 		"route": "/sketch",
# 		"has_permission": "sketch.api.permission.has_app_permission",
# 	}
# ]

# Companion apps that extend a host app (instead of taking their own apps-screen icon) can pin
# their workspaces into the host app's workspace dock (rail) with this hook. Declaring it keeps
# the app off the apps screen, so it takes precedence over any add_to_apps_screen above. Who can
# see a pinned workspace is controlled by that workspace's own Roles table.
# add_to_workspace_dock = [
# 	{
# 		"app": "erpnext",
# 		"workspace": "My Workspace",
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/sketch/css/sketch.css"
# app_include_js = "/assets/sketch/js/sketch.js"

# include js, css files in header of web template
# web_include_css = "/assets/sketch/css/sketch.css"
# web_include_js = "/assets/sketch/js/sketch.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "sketch/public/scss/website"

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
# app_include_icons = "sketch/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Setup Wizard
# ------------

# open a fresh site's setup in this app's own UI instead of the desk wizard.
# must be a non-desk route (not under /desk or /app); to customize setup within
# desk, use setup_wizard_stages / setup_wizard_complete instead.
# setup_wizard_url = "/sketch/setup"

# `/` comes from `home_page` below. Every other SPA route needs a rule of its
# own, or a direct load of it is a 404. `/sketch` stays because core's login
# redirect reads `get_home_page()`, which answers "sketch"; the router rewrites
# that to `/` before the location is read.
#
# `/feed` and `/about` are the two routes a Guest may read. The page itself
# decides that, in `sketch/www/sketch.py` PUBLIC_PATHS, which has to name the
# same paths.
website_route_rules = [
	{"from_route": "/sketch/<path:app_path>", "to_route": "sketch"},
	{"from_route": "/settings", "to_route": "sketch"},
	{"from_route": "/feed", "to_route": "sketch"},
	{"from_route": "/about", "to_route": "sketch"},
]

# The SPA answers the site root. `website_route_rules` cannot claim "/", because
# the resolver skips the map while the path is "index" (spec 3).
home_page = "sketch"

# The Viewer serves /u/<username>/<slug>, and the card image serves
# /t/<username>/<slug>/<theme>.png. Custom renderers run first inside
# PathResolver.resolve(), ahead of every built-in page type.
page_renderer = [
	"sketch.viewer.SketchViewerRenderer",
	"sketch.thumbnail.SketchThumbnailRenderer",
	"sketch.mcp.http.McpPageRenderer",
]

# The Sketch Token resolver. It refuses every path except /mcp, which is the
# whole reason Sketch owns a third auth scheme instead of using Frappe's
# api_key: api_key authenticates every Frappe endpoint, and anyone with a
# GitHub account can sign up.
auth_hooks = ["sketch.auth.validate_sketch_token"]

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
# 	"methods": "sketch.utils.jinja_methods",
# 	"filters": "sketch.utils.jinja_filters"
# }

# Fixtures
# --------
# Filtered on purpose. Plain `fixtures = ["Role"]` makes `bench export-fixtures`
# overwrite sketch/fixtures/role.json with every Role on the site.

fixtures = [{"dt": "Role", "filters": [["name", "in", ["Sketch User"]]]}]

# Installation
# ------------

# before_install = "sketch.install.before_install"
# after_install = "sketch.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "sketch.uninstall.before_uninstall"
# after_uninstall = "sketch.uninstall.after_uninstall"

# Disable / Enable
# ----------------
# Called when this app is logically disabled or re-enabled on a site,
# without uninstalling it. Use this to hide/restore fields this app adds
# to other apps' doctypes.

# before_disable = "sketch.uninstall.before_disable"
# after_disable = "sketch.uninstall.after_disable"
# before_enable = "sketch.install.before_enable"
# after_enable = "sketch.install.after_enable"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "sketch.utils.before_app_install"
# after_app_install = "sketch.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "sketch.utils.before_app_uninstall"
# after_app_uninstall = "sketch.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "sketch.build.after_build"

# To hook into the build process of other apps
# The list of apps being built is passed as an argument

# after_app_build = "sketch.build.after_app_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "sketch.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["sketch.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

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

# Document Events
# ---------------

doc_events = {
	"User": {
		"before_insert": "sketch.oauth_hooks.set_username_for_social_signup",
		"validate": "sketch.user_hooks.validate_username",
	},
}

after_install = "sketch.install.after_install"

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"sketch.tasks.all"
# 	],
# 	"daily": [
# 		"sketch.tasks.daily"
# 	],
# 	"hourly": [
# 		"sketch.tasks.hourly"
# 	],
# 	"weekly": [
# 		"sketch.tasks.weekly"
# 	],
# 	"monthly": [
# 		"sketch.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "sketch.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "sketch.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "sketch.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "sketch.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------

# The three /mcp cases that are decided before any renderer or auth hook runs.
# Core raises NotFound for DELETE (frappe/app.py:117-118), returns a bare 200
# for OPTIONS (frappe/app.py:82-83), and throws its own HTML page for a Basic
# or token Authorization scheme (frappe/auth.py:649-651, 734-738). This hook
# runs inside init_request (frappe/app.py:183-184), ahead of all three. It
# returns at once on every path but /mcp.
before_request = ["sketch.mcp.http.before_request"]

# The one /mcp case that is decided before before_request itself. Core parses
# the request body in make_form_dict (frappe/app.py:302-308) and throws its own
# 417 HTML page on JSON it cannot read, from inside init_request
# (frappe/app.py:178) and ahead of every app hook. This hook runs in the finally
# of application (frappe/app.py:132-134), holds the response object core is
# about to return, and rewrites that page as the JSON-RPC parse error. It
# returns at once on every path but /mcp.
after_request = ["sketch.mcp.http.after_request"]

# Job Events
# ----------
# before_job = ["sketch.utils.before_job"]
# after_job = ["sketch.utils.after_job"]

# after_file_upload = ["sketch.utils.after_file_upload"]

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
# 	"sketch.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
export_python_type_annotations = True

# Require all whitelisted methods to have type annotations
require_type_annotated_api_methods = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

