# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Short-lived signatures that open one thing about one Prototype.

`check` opens the Viewer in a browser, so the browser needs a way in. This
module mints a signature over the Prototype hash id and an expiry, and checks
it again on the way back.

Sketch owns this instead of `frappe.utils.verified_command` for two reasons
(spec 7.2):

- `verify_request` calls `respond_as_web_page` on a bad signature. That is a
  rendered error page, not the 404 the Viewer must return.
- `get_signed_params` carries no expiry.

The signature covers the hash id, not the URL. Rename a slug or a username and
an old signature signs nothing.

It also covers a scope, so one signature opens one thing.
"""

import hashlib
import hmac
import time

from frappe.utils.verified_command import get_secret

DEFAULT_TTL = 60

#: What a signature opens. The scope is inside the HMAC message, so a
#: signature minted for one scope verifies under no other one.
#:
#: - VIEW opens the whole Viewer document, which carries the source tree. Only
#:   `check` mints it, and it lives for `DEFAULT_TTL` seconds.
#: - REVISION opens one number, `sketch.api.signed_revision`, and nothing
#:   else. The Viewer mints it into the page, where the Prototype's own
#:   JavaScript reads it, so it must never open the document as well: a
#:   forked tree runs a stranger's code, and that code would hold a link to
#:   the reader's own Prototype for as long as the signature lasts.
VIEW = "view"
REVISION = "revision"


def _digest(prototype_name: str, exp: int, scope: str = VIEW) -> str:
	"""The hex HMAC-SHA256 over "<scope>:<name>:<exp>" with the site secret."""
	secret = get_secret()
	message = f"{scope}:{prototype_name}:{exp}"
	return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def _now() -> int:
	"""The current time in unix seconds. mint and verify share this clock."""
	return int(time.time())


def mint(prototype_name: str, ttl_seconds: int = DEFAULT_TTL, scope: str = VIEW) -> dict:
	"""Sign this Prototype, for this scope, for the next ttl_seconds.

	Returns {"exp": <int unix seconds>, "sig": <hex str>}.
	"""
	exp = _now() + int(ttl_seconds)
	return {"exp": exp, "sig": _digest(prototype_name, exp, scope)}


def verify(prototype_name: str, exp, sig, scope: str = VIEW) -> bool:
	"""True only for an unexpired signature over this hash id and this scope.

	Never raises. A malformed exp or sig is False, not an error.
	"""
	if not prototype_name or not exp or not sig:
		return False

	try:
		expiry = int(str(exp).strip())
		given = str(sig).strip()
	except TypeError, ValueError:
		return False

	if expiry < _now():
		return False

	try:
		return hmac.compare_digest(given, _digest(prototype_name, expiry, scope))
	except TypeError, ValueError:
		return False
