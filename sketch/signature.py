# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Short-lived signatures that open one private Prototype.

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
"""

import hashlib
import hmac
import time

from frappe.utils.verified_command import get_secret

DEFAULT_TTL = 60


def _digest(prototype_name: str, exp: int) -> str:
	"""The hex HMAC-SHA256 over "<name>:<exp>" with the site secret."""
	secret = get_secret()
	message = f"{prototype_name}:{exp}"
	return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def _now() -> int:
	"""The current time in unix seconds. mint and verify share this clock."""
	return int(time.time())


def mint(prototype_name: str, ttl_seconds: int = DEFAULT_TTL) -> dict:
	"""Sign this Prototype for the next ttl_seconds.

	Returns {"exp": <int unix seconds>, "sig": <hex str>}.
	"""
	exp = _now() + int(ttl_seconds)
	return {"exp": exp, "sig": _digest(prototype_name, exp)}


def verify(prototype_name: str, exp, sig) -> bool:
	"""True only for an unexpired signature over this exact hash id.

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
		return hmac.compare_digest(given, _digest(prototype_name, expiry))
	except TypeError, ValueError:
		return False
