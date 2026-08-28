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
	"""Point Portal Settings at the Sketch User role.

	Core's `sign_up` reads `Portal Settings.default_role` and gives the new user
	that one role. The field has no default, so a signup gets no role until this
	runs.

	Website Settings `disable_signup` is left alone on purpose. Signup stays shut
	until the MVP is done.
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


def setup_github_login() -> None:
	"""Create the GitHub `Social Login Key` if the site has none.

	The record holds the preset GitHub URLs and `sign_ups = "Allow"`. That one
	field opens signup for GitHub only, because `provider_allows_signup` reads
	the key before it reads Website Settings. Website Settings `disable_signup`
	stays 1, so the email signup form stays shut.

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
