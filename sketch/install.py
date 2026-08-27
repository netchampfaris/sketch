"""Site setup for Sketch.

`after_install` runs once when the app is installed. `setup_site_settings` is
also safe to call by hand on a live site:

    bench --site sketch.localhost execute sketch.install.setup_site_settings
"""

import frappe

SKETCH_ROLE = "Sketch User"


def after_install() -> None:
	setup_site_settings()


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
