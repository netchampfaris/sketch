"""/help: the page between "I have a token" and "my agent is connected".

Nothing in the app linked out to anything before this: a `grep` over
`frontend/src` found one external URL, and it was inside a config snippet
(problem 3.12). The account menu now points here, so this route has to exist.

Guests reach it too. Half of the reason a person is stuck is that they have not
signed in yet, and a page that asks for a login before it explains the login is
the problem this sweep is fixing (problem 8.1).
"""

import frappe
from frappe.utils import get_url

no_cache = 1


def get_context(context):
	context.title = "Help"
	# The live endpoint, so the beta site and a local site each name
	# themselves. `sketch/mcp/http.py` builds its error bodies the same way.
	context.mcp_url = get_url("/mcp")
	context.signed_in = frappe.session.user != "Guest"
	return context
