"""Site setup for Sketch.

`after_install` runs once when the app is installed. `setup_site_settings` is
also safe to call by hand on a live site:

    bench --site sketch.localhost execute sketch.install.setup_site_settings
"""

import frappe

SKETCH_ROLE = "Sketch User"
GITHUB_LOGIN_KEY = "github"


def after_install() -> None:
	setup_site_settings()
	setup_github_login()


def setup_site_settings() -> None:
	"""Point Portal Settings at the Sketch User role and shut the email login.

	`frappe/utils/oauth.py:347` reads `Portal Settings.default_role` and gives
	the new GitHub user that one role. The field has no default, so a sign-up
	gets no role until this runs.

	Website Settings `disable_signup` is left alone on purpose. It stays 1.
	"""
	if not frappe.db.exists("Role", SKETCH_ROLE):
		frappe.log_error(
			title="Sketch setup",
			message=f"Role {SKETCH_ROLE} is missing. Portal Settings default_role not set.",
		)
		return

	settings = frappe.get_single("Portal Settings")
	if settings.default_role != SKETCH_ROLE:
		settings.default_role = SKETCH_ROLE
		settings.flags.ignore_permissions = True
		settings.save()
		frappe.db.commit()

	disable_email_login()


def disable_email_login() -> None:
	"""Hide the email and password form on `/login`.

	Sketch signs people in with GitHub only. System Settings
	`disable_user_pass_login` hides the form (`frappe/www/login.html:9`) and
	also refuses `/api/method/login` (`frappe/auth.py:151`).
	`login_with_email_link` goes off with it, because that button carries its
	own email field.

	Escape hatch, and the only way into Desk before the GitHub credentials are
	in place:

	    bench --site sketch.localhost browse --user Administrator --sid

	It prints a one-time session id. Send it as the `sid` cookie, or open
	`/app` with `?sid=<value>`.

	The writes go through `frappe.db.set_single_value`, not `Document.save`.
	`SystemSettings.validate_user_pass_login` wants an enabled Social Login Key
	first, and the GitHub key is created disabled.
	"""
	frappe.db.set_single_value("System Settings", "disable_user_pass_login", 1)
	frappe.db.set_single_value("System Settings", "login_with_email_link", 0)
	frappe.db.commit()


def setup_github_login() -> None:
	"""Create the GitHub `Social Login Key` if the site has none.

	The record holds the preset GitHub URLs and `sign_ups = "Allow"`. That one
	field opens sign-up for GitHub only, because `provider_allows_signup` reads
	the key before it reads Website Settings. Website Settings `disable_signup`
	stays 1.

	The record is created disabled. A person sets `client_id` and
	`client_secret` by hand, one time, from the GitHub OAuth App. This code
	never writes a credential. `validate` refuses to save an enabled key with a
	blank client id, so the login stays off until the credentials are in place.
	"""
	if frappe.db.exists("Social Login Key", GITHUB_LOGIN_KEY):
		return

	key = frappe.new_doc("Social Login Key")
	key.get_social_login_provider("GitHub", initialize=True)
	key.social_login_provider = "GitHub"
	key.enable_social_login = 0
	key.sign_ups = "Allow"
	key.flags.ignore_permissions = True
	key.insert()
	frappe.db.commit()
