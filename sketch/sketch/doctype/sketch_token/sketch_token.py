# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

import hashlib
import hmac
import json
import secrets

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, now_datetime, pretty_date, time_diff_in_seconds
from frappe.utils.password import get_decrypted_password

TOKEN_PREFIX = "sk_"

#: What an MCP client calls itself in `initialize`'s `clientInfo.name`, folded
#: to lower case, and the name a person knows the app by. The one place the
#: mapping lives: the gallery and Settings print these names as they come.
CLIENT_NAMES = {
	"claude-code": "Claude Code",
	"cursor": "Cursor",
	"codex-mcp-client": "Codex",
	"codex": "Codex",
	"visual studio code": "VS Code",
	"windsurf": "Windsurf",
	"opencode": "OpenCode",
}

#: An unknown client keeps its own name, cut to this many characters.
CLIENT_NAME_LIMIT = 40

#: Record one app at most once a minute. A client may send `initialize` on
#: every reconnect, and a row write each time buys nothing the screen shows.
CLIENT_INTERVAL_SECONDS = 60

#: The most apps one row keeps. The name comes from the client, so the map is
#: capped rather than grown by whatever a client chooses to call itself.
CLIENT_LIMIT = 10


class SketchToken(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		clients: DF.JSON | None
		last_used: DF.Datetime | None
		token: DF.Password
		token_hash: DF.Data | None
		user: DF.Link
	# end: auto-generated types

	def before_insert(self):
		"""Put `owner` back on the named user.

		`set_user_and_timestamp` forces `owner` to the session user
		(`frappe/model/document.py:1059-1063`), and `Document.insert` calls it
		at line 728, five lines before `run_method("before_insert")` at line
		733. So a row minted for another user, which every test fixture and
		every admin call does, would land on the caller. Both the `if_owner`
		read rule and the `validate` check below read `owner`, so it has to
		name the user the token belongs to.
		"""
		if self.flags.minted_by_sketch:
			self.owner = self.user

	def validate(self):
		"""A Sketch Token is minted by this module and by nobody else.

		The doctype is named `field:user` and `sketch.auth.resolve` trusts that
		field as the identity, so a row that names another user is an account
		takeover. The permission rows no longer grant `create` or `write` to a
		Sketch User, and this guard holds even if a later permission change
		gives them back: a REST insert carries no `minted_by_sketch` flag.
		"""
		if not self.flags.minted_by_sketch:
			frappe.throw(_("A Sketch Token is minted by the server only."), frappe.PermissionError)
		if self.user != self.owner:
			frappe.throw(_("A Sketch Token belongs to its owner."), frappe.PermissionError)


def new_token() -> str:
	"""A fresh token. `sk_` plus 32 random bytes, URL-safe."""
	return TOKEN_PREFIX + secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
	"""The index value for one token. Never a credential on its own.

	`resolve` needs an equality lookup, and the `token` field is encrypted with
	a random IV, so the same secret stores as different bytes every time. A
	plain SHA-256 is enough here: the token is 32 random bytes, so it cannot be
	guessed from the digest.
	"""
	return hashlib.sha256(token.encode()).hexdigest()


def get_or_create(user: str | None = None) -> str:
	"""Return the user's token. Create the row on first call.

	The row is owned by the user, so the `if_owner` rules let the user read it.
	"""
	user = user or frappe.session.user
	name = frappe.db.get_value("Sketch Token", {"user": user}, "name")
	if name:
		return get_token(user)

	token = new_token()
	doc = frappe.new_doc("Sketch Token")
	doc.user = user
	doc.token = token
	doc.token_hash = token_hash(token)
	# `owner` is not set here. `insert` overwrites it with the session user,
	# and `before_insert` then puts it back on `doc.user`.
	# The one flag `validate` accepts. Without it no row is ever written.
	doc.flags.minted_by_sketch = True
	doc.insert(ignore_permissions=True)
	# The commit is not optional. Core rolls a request back at
	# `frappe/app.py:404-407` unless the HTTP method is unsafe or
	# `flags.commit` is set, and this mint also runs from read paths that
	# never set either. Without this the screen shows a token, the row never
	# lands, the next read mints a different one, and no token the user pastes
	# can ever authenticate. So it commits itself.
	frappe.db.commit()
	# Frappe masks a Password field on the document after save. Return the
	# plain value we generated, never doc.token.
	return token


def get_token(user: str | None = None) -> str:
	"""The stored token in the clear. Raises when the user has no row."""
	user = user or frappe.session.user
	return get_decrypted_password("Sketch Token", user, "token")


def regenerate(user: str | None = None) -> str:
	"""Write a new token over the old one. A write, never a delete."""
	user = user or frappe.session.user
	if not frappe.db.exists("Sketch Token", {"user": user}):
		return get_or_create(user)

	token = new_token()
	doc = frappe.get_doc("Sketch Token", user)
	doc.token = token
	doc.token_hash = token_hash(token)
	doc.flags.minted_by_sketch = True
	# The connection state goes with the token. Settings reads `last_used` and
	# prints "Last agent request: N ago" from it. Every agent still holding the
	# old token now gets a 401 from `sketch.auth`, so leaving the old stamp
	# there claims a live connection that is dead, on the one screen the user
	# opens to fix it. The next good /mcp request stamps it again.
	doc.last_used = None
	# The apps go with it, for the same reason: each one holds the dead token.
	doc.clients = None
	doc.save(ignore_permissions=True)
	return token


def record_client(user: str, client_info) -> None:
	"""Remember which app just connected, from `initialize`'s `clientInfo`.

	Cheap on purpose, like `sketch.auth._stamp_last_used`: one row read, and a
	direct write only when this app is new or was last seen over a minute ago.
	`update_modified=False` keeps `modified` for real token changes.

	A name is a nicety, so no failure of it reaches the agent.
	"""
	info = client_info if isinstance(client_info, dict) else {}
	name = client_display_name(info.get("name"))
	if not name:
		return

	try:
		row = frappe.db.get_value("Sketch Token", {"user": user}, ["name", "clients"], as_dict=True)
		if not row:
			return

		clients = _load_clients(row.clients)
		seen = clients.get(name)
		now = now_datetime()
		if seen and time_diff_in_seconds(now, seen) < CLIENT_INTERVAL_SECONDS:
			return

		clients[name] = str(now)
		newest = sorted(clients.items(), key=lambda item: item[1], reverse=True)[:CLIENT_LIMIT]
		frappe.db.set_value("Sketch Token", row.name, "clients", json.dumps(dict(newest)), update_modified=False)
	except Exception:
		frappe.logger("sketch.auth").warning("could not record the MCP client", exc_info=True)


def clients(user: str) -> list[dict]:
	"""The apps that used this user's token, newest first, as the screens print them."""
	stored = frappe.db.get_value("Sketch Token", {"user": user}, "clients")
	rows = sorted(_load_clients(stored).items(), key=lambda item: item[1], reverse=True)
	return [{"name": name, "last_used": seen, "last_used_pretty": pretty_date(seen)} for name, seen in rows]


def client_display_name(raw) -> str | None:
	"""The name a person knows the app by, or None for a client with no name."""
	if not isinstance(raw, str) or not raw.strip():
		return None
	raw = raw.strip()
	return CLIENT_NAMES.get(raw.lower(), raw[:CLIENT_NAME_LIMIT])


def resolve(token: str) -> str | None:
	"""The User that owns this token, or None.

	One indexed `token_hash` lookup, then one constant-time compare against the
	decrypted value. The hash is only the index; the encrypted `token` field
	stays the authority, so a row with a planted hash still fails.

	This runs before authentication on every `/mcp` request, so it must not
	grow with the number of accounts. It used to read every row and decrypt it,
	which let an unauthenticated caller pay one Fernet decrypt per registered
	token per request.

	`name` is the user, because `autoname` is `field:user`.
	"""
	if not token or not token.startswith(TOKEN_PREFIX):
		return None

	name = frappe.db.get_value("Sketch Token", {"token_hash": token_hash(token)}, "name")
	if not name:
		return None

	stored = get_decrypted_password("Sketch Token", name, "token", raise_exception=False)
	if not stored or not hmac.compare_digest(stored, token):
		return None

	# Disable is the site's only ban, and `frappe.set_user` checks nothing. A
	# token left over from before the ban must not open /mcp. Frappe's own
	# `validate_api_key_secret` filters on `enabled` the same way.
	if not frappe.db.get_value("User", name, "enabled"):
		return None

	return name


def _load_clients(stored) -> dict[str, str]:
	"""The stored map, or an empty one. Frappe hands a JSON field back as text."""
	if not stored:
		return {}
	try:
		value = json.loads(stored) if isinstance(stored, str) else stored
	except ValueError:
		return {}
	if not isinstance(value, dict):
		return {}
	return {str(name): str(get_datetime(seen)) for name, seen in value.items() if seen}
