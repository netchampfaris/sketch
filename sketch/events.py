# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Product analytics: what a Sketch user and their agent actually did.

Sketch already answers half the funnel from rows it keeps anyway. `User.creation`
is a signup. A `Sketch Token` row is a token handed out. A `Sketch Prototype` row
is a tree that exists, and `sketch.versions` holds every commit and its prompt.
None of that needed a new table, and none of it is written here.

This module covers the half those tables cannot answer, because the moments are
not states:

- **agent_connected**, the first time a token ever authenticated. `last_used`
  holds the newest request and overwrites the first one, so the moment a user
  crossed from "has a token" to "the agent works" is lost the next minute.
- **auth_failed**, and which of the four ways it failed. The onboarding audit
  called a wrong token the most likely failure a real user meets, and until now
  the endpoint answered it and forgot it.
- **tool_call**, per tool, with the error rate. A tool that fails is an agent
  going in circles, and nothing recorded it.
- **check**, per outcome. `compile-failed` is the agent writing Vue that does
  not build, which is the quality signal for the whole product.
- **viewer_open**, owner against public. A public link that nobody opens is a
  share feature nobody uses.

## What is not stored

No prompt text, no file content, no token, no request body, no IP, no user
agent. A row is a name, a user, a Prototype id, a boolean, one short
discriminator and a duration. The prompt a user typed is already in
`sketch.versions`, per Prototype, where it is readable in context and where the
owner can delete it by deleting the Prototype.

## Why a write is buffered, not immediate

Two of the five events fire inside work that is about to be thrown away.
`sketch.mcp.tools.call_tool` rolls back to a savepoint when a tool raises
(`sketch/mcp/tools.py`), and core rolls the whole request back for every safe
HTTP method (`frappe/app.py:404-407`). An event written inline would vanish
exactly when it is most worth having: on the failures.

So `record` appends to a per-request buffer and `flush_after_request` writes it.
That hook runs in the `finally` of `application` (`frappe/app.py:132-134`),
which is after `sync_database` has already committed or rolled the request back.
The transaction is clean by then, so the insert commits on its own and carries
nothing of the caller's with it.

A caller outside a request, a background job or a test, calls `flush` directly.

## Nothing here may break a caller

Every entry point swallows its own exceptions and logs. Analytics that can fail
a tool call is worse than no analytics.
"""

import frappe

#: An agent's token authenticated for the first time. `detail` is empty.
#: Recorded once per account, ever: `sketch.auth` fires it only on the write
#: that moves `last_used` off NULL.
AGENT_CONNECTED = "agent_connected"

#: A request to `/mcp` was refused. `detail` is the `sketch.mcp.http.ERRORS`
#: key: `no_credentials`, `wrong_auth_scheme`, `invalid_token` or `no_access`.
#: `user` is empty, because the request never resolved one.
AUTH_FAILED = "auth_failed"

#: One `tools/call`. `detail` is the tool name, `ok` is false when the tool
#: raised, `ms` is the handler's own time.
TOOL_CALL = "tool_call"

#: One `check` that reached the browser. `detail` is the report status: `ok`,
#: `empty`, `compile-failed`, `link-failed` or `boot-failed`. A check that never
#: reached the browser is a failed `tool_call` instead, and has no row here.
CHECK = "check"

#: A Viewer document was served. `detail` is `owner`, `public` or `check`, so a
#: real reader is told apart from the browser Sketch drives itself.
VIEWER_OPEN = "viewer_open"

#: Where `record` puts a row until the request ends.
BUFFER = "sketch_events"

#: The most rows one request may buffer. A request that records more than this
#: is a loop, and a log must not be the thing that runs the site out of memory.
MAX_PER_REQUEST = 200

#: How long a row lives. `trim` deletes past it, daily. The funnel is read in
#: days and weeks, so a quarter is far more than any question asked of it, and
#: it keeps one row per tool call from growing without end.
RETENTION_DAYS = 90


def record(
	event: str,
	*,
	user: str | None = None,
	prototype: str | None = None,
	ok: bool = True,
	detail: str | None = None,
	ms: int = 0,
) -> None:
	"""Buffer one event. Written when the request ends, never before.

	`user` defaults to the session user. Pass it explicitly only when the
	session is not the subject, which is every `auth_failed` row: those pass
	`user=""` because no user was resolved.
	"""
	try:
		if user is None:
			user = frappe.session.user if frappe.session else None
		if user in ("", "Guest"):
			# Guest is a real User row, so it would link fine. It is stored as
			# empty all the same: "the account that did this" and "nobody was
			# signed in" are different facts, and a Guest link reads as the
			# first one.
			user = None

		buffer = _buffer()
		if len(buffer) >= MAX_PER_REQUEST:
			return

		buffer.append(
			{
				"doctype": "Sketch Event",
				"event": event,
				"user": user,
				"prototype": prototype,
				"ok": 1 if ok else 0,
				"detail": (detail or "")[:140] or None,
				"ms": int(ms or 0),
			}
		)
	except Exception:
		frappe.logger("sketch.events").warning("could not record an event", exc_info=True)


def flush() -> None:
	"""Write every buffered row and commit. Safe to call with nothing buffered.

	The commit is the point. This runs after core has already closed the
	caller's transaction, so without it the rows sit in a transaction nobody
	commits and the next request rolls them back.

	The buffer is emptied before the write, not after. A row that cannot be
	written is dropped, so a second flush in the same request never retries it
	and a failing row cannot be written twice.
	"""
	rows = _buffer()
	if not rows:
		return

	pending, rows[:] = list(rows), []
	try:
		for row in pending:
			frappe.get_doc(row).insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		frappe.logger("sketch.events").warning("could not write %s events" % len(pending), exc_info=True)
		try:
			frappe.db.rollback()
		except Exception:
			pass


def flush_after_request(response=None, request=None) -> None:
	"""The `after_request` hook. Registered site-wide, so it must be cheap.

	It runs on every request this site serves, and all but a handful buffer
	nothing, so the common path is one `getattr` and a return.

	The seat matters. `run_after_request_hooks` sits in the `finally` of
	`application` (`frappe/app.py:132-134`), below both the rollback on the
	exception path (`frappe/app.py:121-123`) and `sync_database` on the good
	one (`frappe/app.py:127`). So a tool call that raised, rolled back to its
	savepoint and answered `isError` still leaves its row here.
	"""
	try:
		flush()
	except Exception:
		frappe.logger("sketch.events").warning("could not flush events", exc_info=True)


def trim() -> None:
	"""Delete rows past `RETENTION_DAYS`. The daily scheduler calls this.

	A direct delete, not `frappe.delete_doc` per row: there is no lifecycle to
	run, no child table to cascade and no link to check, and the table holds one
	row per tool call.
	"""
	from frappe.utils import add_days, now_datetime

	cutoff = add_days(now_datetime(), -RETENTION_DAYS)
	frappe.db.delete("Sketch Event", {"creation": ("<", cutoff)})
	frappe.db.commit()


def _buffer() -> list:
	"""This request's row list, created on first use."""
	rows = getattr(frappe.local, BUFFER, None)
	if rows is None:
		rows = []
		setattr(frappe.local, BUFFER, rows)

	return rows
