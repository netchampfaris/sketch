"""Sketch's own /login.

`TemplatePage.set_template_path` walks `reversed(frappe.get_active_apps())`
(`frappe/website/page_renderers/template_page.py:51`), so `sketch/www/login.html`
is found before `frappe/www/login.html`, and `set_pymodule` then picks up this
module beside it (`template_page.py:129-145`).

The login decision stays in core. This module borrows core's context, so the
OAuth URLs, the `redirect-to` handling and the redirect for a visitor who is
already signed in are all core's, unchanged.
"""

from frappe.www.login import get_context as get_core_context

no_cache = True


def get_context(context):
	"""Core's login context, with the two dead surfaces removed.

	`signup_form_template` is a rendered email and password form
	(`frappe/templates/signup.html`). Sketch signs people in with GitHub only,
	so `disable_user_pass_login` is 1 (`sketch/install.py`, `disable_email_login`)
	and that form can never be submitted. Dropping it here means no template can
	print it by accident.

	The other one is `disable_signup`. It is 1, and core's template answers the
	flag with a "Signups have been disabled for this website." block
	(`frappe/www/login.html:144-146`). The sentence is false on this site: the
	GitHub Social Login Key carries `sign_ups = "Allow"`, and
	`provider_allows_signup` reads the key before it reads Website Settings
	(`frappe/utils/oauth.py`), so the GitHub button does create accounts. The
	Sketch template renders no signup section at all, which is why the flag is
	left exactly as core computed it: nothing reads it (problem 8.2).

	`title` is sentence case, like every other header in Sketch (problem 8.3).
	`Website Settings.title_prefix` turns it into "Sketch - Sign in"
	(`frappe/website/page_renderers/base_template_page.py:43`).
	"""
	get_core_context(context)

	context.title = "Sign in"
	context.signup_form_template = None

	return context
