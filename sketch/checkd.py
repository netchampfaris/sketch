# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The client for sketch-checkd, the Node service that opens the Viewer.

Two callers, one wire format. `sketch/mcp/tools.py` asks for a report the agent
reads. `sketch/thumbnails.py` asks for the card images. Both need the same
signed Viewer URL and the same error handling, so both come through here rather
than each holding its own copy of Contract 5.

This module knows nothing about what the answer means. It posts, it validates
that the answer is JSON, and it turns every transport failure into a readable
`frappe.throw`. The report is the caller's to read.
"""

import frappe

from sketch import signature

#: sketch-checkd, the Node service that opens the Viewer in one Chromium.
URL = "http://127.0.0.1:8010/check"

#: checkd hard-timeouts a check at 30 s. Wait just past that, then give up. The
#: caller is a web worker, so every extra second is a worker another request
#: cannot have.
TIMEOUT = 35

#: How long one user's claim on the inline browser path lives. A little under
#: TIMEOUT: the key expires by itself, so a killed worker cannot lock an
#: account out, and a caller who waits out the cooldown gets the slot back.
COOLDOWN_SECONDS = 20


def viewer_url(doc, theme: str = "light") -> str:
	"""The signed, loopback Viewer URL for one Prototype.

	Loopback and not the public hostname: the public name routes every request
	out to Cloudflare and back (trap 14). checkd rewrites the Host header from
	the `host` field of the request body.

	The signature is what lets checkd read a private Prototype as a Guest.
	`theme` sits outside it, because it picks a stylesheet and not a permission
	(spec 7.3).
	"""
	signed = signature.mint(doc.name)
	username = frappe.db.get_value("User", doc.owner, "username")
	port = frappe.conf.webserver_port or 8000
	return (
		f"http://127.0.0.1:{port}/u/{username}/{doc.slug}"
		f"?theme={theme}&exp={signed['exp']}&sig={signed['sig']}"
	)


def slot_key(user: str) -> bytes:
	"""The cache key that names one user's claim on the browser path."""
	return frappe.cache().make_key(f"sketch:check:{user}")


def claim_slot() -> None:
	"""One inline browser run per user at a time. Raises when a run is live.

	`run` blocks a web worker for up to TIMEOUT seconds, and two doors reach it
	with a session: `mcp.tools.do_check` and `api.refresh_preview`. Without
	this, one account holds every worker on the site.

	`cache().set_value` has no `if_not_exists` on this Frappe version, so this
	uses the Redis SET NX EX under it. A cache that is down allows the run: the
	throttle must not be the reason a check fails.

	The claim is given back in `run`, on the way out of the browser call.
	"""
	import redis.exceptions

	key = slot_key(frappe.session.user)
	try:
		claimed = frappe.cache().set(key, b"1", ex=COOLDOWN_SECONDS, nx=True)
	except redis.exceptions.ConnectionError:
		return

	if not claimed:
		frappe.throw(
			frappe._("A check is already running for your account. Try again in a few seconds.")
		)

	# Only the request that took the claim may give it back. A background
	# thumbnail job for the same user calls `run` without claiming, and must
	# not free a slot an inline check is holding.
	frappe.local.sketch_check_slot = key


def release_slot() -> None:
	"""Give the claim back. Does nothing when this request holds none."""
	import redis.exceptions

	key = getattr(frappe.local, "sketch_check_slot", None)
	if not key:
		return

	frappe.local.sketch_check_slot = None
	try:
		frappe.cache().delete(key)
	except redis.exceptions.ConnectionError:
		pass


def run(doc, screenshot: bool = False, thumbnails: bool = False) -> dict:
	"""POST to sketch-checkd and return the report. Contract 5.

	`screenshot` is the agent's option: one light PNG per static route.
	`thumbnails` is the card images: the home route, once per theme. They are
	independent, and a caller that wants neither pays for neither.

	The claim `claim_slot` took is released here, on every way out. A run that
	throws must free the slot too, or one crashed check locks the account out
	for the whole cooldown.
	"""
	import requests

	body = {
		"url": viewer_url(doc),
		"host": frappe.local.site,
		"screenshot": screenshot,
		"thumbnails": thumbnails,
	}

	try:
		try:
			response = requests.post(URL, json=body, timeout=TIMEOUT)
		except requests.exceptions.ConnectionError:
			frappe.throw(
				frappe._("the check service is not running at {0}. Ask the site owner to start it.").format(URL)
			)
		except requests.exceptions.Timeout:
			frappe.throw(frappe._("the check service did not answer in {0}s").format(TIMEOUT))

		if response.status_code >= 400:
			frappe.throw(
				frappe._("the check service refused the request: HTTP {0} {1}").format(
					response.status_code, response.text[:400]
				)
			)

		try:
			return response.json()
		except ValueError:
			frappe.throw(frappe._("the check service answered with something that is not JSON"))
	finally:
		release_slot()
