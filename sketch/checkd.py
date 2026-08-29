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

#: checkd hard-timeouts a check at 30 s. Wait a little past that, then give up.
TIMEOUT = 45


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


def run(doc, screenshot: bool = False, thumbnails: bool = False) -> dict:
	"""POST to sketch-checkd and return the report. Contract 5.

	`screenshot` is the agent's option: one light PNG per static route.
	`thumbnails` is the card images: the home route, once per theme. They are
	independent, and a caller that wants neither pays for neither.
	"""
	import requests

	body = {
		"url": viewer_url(doc),
		"host": frappe.local.site,
		"screenshot": screenshot,
		"thumbnails": thumbnails,
	}

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
