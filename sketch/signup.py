"""The Sketch `sign_up` override.

Core's `frappe.core.doctype.user.user.sign_up(email, full_name, redirect_to)`
has a fixed signature and no hook adds a field to it. `override_whitelisted_methods`
points that dotted path here, and this copy takes `username` as a fourth
argument.

Type annotations are required: `require_type_annotated_api_methods = True`.

Every guard core runs is repeated below. Read
`frappe/core/doctype/user/user.py:1123` next to this file before you change it.
"""

import frappe
from frappe import _
from frappe.utils import cint, escape_html, random_string
from frappe.website.utils import is_signup_disabled
from frappe.www.login import sanitize_redirect

from sketch.user_hooks import REQUESTED_FLAG, check_format, is_taken, normalise


@frappe.whitelist(allow_guest=True)
def sign_up(email: str, full_name: str, redirect_to: str, username: str = "") -> tuple[int, str]:
	"""Create a Website User with a Sketch username.

	Returns core's `(code, message)` pair:
	0 = refused, 1 = mail sent, 2 = mail not sent.
	"""
	if is_signup_disabled():
		frappe.throw(_("Sign Up is disabled"), title=_("Not Allowed"))

	user = frappe.db.get("User", {"email": email})
	if user:
		if user.enabled:
			return 0, _("Already Registered")
		else:
			return 0, _("Registered but disabled")

	username = normalise(username)
	check_format(username)

	max_signups_allowed_per_hour = cint(frappe.get_system_settings("max_signups_allowed_per_hour") or 300)
	users_created_past_hour = frappe.db.get_creation_count("User", 60)
	if users_created_past_hour >= max_signups_allowed_per_hour:
		frappe.respond_as_web_page(
			_("Temporarily Disabled"),
			_("Too many users signed up recently, so the registration is disabled. Please try back in an hour"),
			http_status_code=429,
		)
		# Core does not return here, so it creates the user anyway. Sketch stops.
		return 0, _("Temporarily Disabled")

	if is_taken(username):
		frappe.throw(
			_("The username {0} is already taken. Choose another.").format(username),
			title=_("Username Taken"),
		)

	new_user = frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": escape_html(full_name),
			"username": username,
			"enabled": 1,
			"new_password": random_string(10),
			"user_type": "Website User",
		}
	)
	new_user.flags.ignore_permissions = True
	new_user.flags.ignore_password_policy = True
	# Lets sketch.user_hooks name the username core blanks on a race.
	new_user.flags[REQUESTED_FLAG] = username
	new_user.insert()

	# The role comes from Portal Settings. sketch.install sets it to Sketch User.
	default_role = frappe.get_single_value("Portal Settings", "default_role")
	if default_role:
		new_user.add_roles(default_role)

	if redirect_to:
		frappe.cache.hset("redirect_after_login", new_user.name, sanitize_redirect(redirect_to))

	if new_user.flags.email_sent:
		return 1, _("Please check your email for verification")
	else:
		return 2, _("Please ask your administrator to verify your sign-up")
