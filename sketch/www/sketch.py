"""The one page that boots the Sketch SPA.

`home_page = "sketch"` in hooks.py points the site root here, and
`website_route_rules` sends `/settings` here as well.
"""

from urllib.parse import quote

import frappe

no_cache = 1


def get_context():
	_require_login()
	csrf_token = frappe.sessions.get_csrf_token()
	frappe.db.commit()
	context = frappe._dict()
	context.boot = get_boot()
	context.boot.csrf_token = csrf_token
	return context


def _require_login() -> None:
	"""Bounce a signed-out visitor before the SPA bundle is served.

	Without this a Guest downloads the whole bundle, the SPA calls
	`get_session`, that throws `PermissionError`, and only then does the
	browser move to /login. The visitor pays for a bundle they cannot use.

	`frappe.Redirect` is the website way to leave a `get_context`. Core reads
	`flags.redirect_location` in its exception handler and answers 301.
	"""
	if frappe.session.user != "Guest":
		return

	request = getattr(frappe.local, "request", None)
	back = getattr(request, "full_path", "/") if request else "/"
	# full_path keeps a bare "?" on a query-less URL. It is harmless, but the
	# login page echoes this value, so send the clean form.
	back = back.rstrip("?") or "/"

	frappe.local.flags.redirect_location = f"/login?redirect-to={quote(back, safe='')}"
	raise frappe.Redirect


def get_boot():
	return frappe._dict(
		{
			"frappe_version": frappe.__version__,
			"site_name": frappe.local.site,
		}
	)
