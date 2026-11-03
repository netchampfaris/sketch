# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The methods the Viewer's shell calls, checked against the real session.

The shell is Sketch's own page around the prototype's frame. It sends the
session cookie and Frappe's CSRF token, so who is asking comes from
`frappe.session.user` and never from anything the page names. The prototype's
frame sits in an opaque origin and carries neither, so code running there can
call none of these.

Every method is POST only and never `allow_guest`. One door, `_actor`: a Guest
is refused (403), a Prototype this person may not see answers 404, and their
role is read again on every call, so a removed editor loses their rights at once.

Make default and Keep only this are the owner's and stay in `sketch.api`
(`set_variant_default` and the rest), behind `resolve_owned`.
"""

import json
from dataclasses import dataclass

import frappe

from sketch import annotations, badges, comments, editor_variants, sharing


@dataclass(frozen=True)
class Who:
	"""The signed-in person behind a call, and their standing on one Prototype."""

	user: str
	username: str
	role: str

	@property
	def is_owner(self) -> bool:
		return self.role == "owner"


def _actor(name: str) -> Who:
	"""The session's person on Prototype `name`. A Guest gets 403; someone who may not see it, 404."""
	user = frappe.session.user
	if not user or user == "Guest":
		raise frappe.PermissionError

	if not sharing.can_view(name, user):
		raise frappe.DoesNotExistError

	return Who(user, sharing.username_of(user), sharing.role_of(name, user))


def _commenter(name: str) -> comments.Actor:
	"""The session's person as a commenter. Nobody without a username can sign a comment, so that is a 404 too."""
	who = _actor(name)
	if not who.username:
		raise frappe.DoesNotExistError

	return comments.commenter(name, who.username, who.user)


# ------------------------------------------------------------------- variants


def _variant_editor(name: str) -> tuple:
	"""The Prototype and the person, for a delete: the owner or an invited editor, else 403."""
	who = _actor(name)
	if who.role not in ("owner", "editor"):
		raise frappe.PermissionError

	return frappe.get_doc("Sketch Prototype", name), who


@frappe.whitelist(methods=["POST"])
def delete_variant(name: str, option: str) -> dict:
	"""Delete a variant a person added. The owner may delete any; an editor, their own (`editor_variants.delete`)."""
	doc, who = _variant_editor(name)
	return editor_variants.delete(doc, who.username, who.is_owner, option)


@frappe.whitelist(methods=["POST"])
def undo_delete_variant(name: str, option: str, sequence: str) -> dict:
	"""Bring back the variant version `sequence` deleted. An editor may undo their own deletions only."""
	doc, who = _variant_editor(name)
	return editor_variants.undo_delete(doc, who.username, who.is_owner, sequence, option)


# ---------------------------------------------------------------------- notes


@frappe.whitelist(methods=["POST"])
def save_annotations(name: str, data: str = "", epoch: str = "") -> dict:
	"""Save the toolbar's notes and tweaks: the owner's for the owner, an invited editor's own for them.

	Anyone else gets 404, as if there were no notes to write. The owner's notes
	and an editor's never mix (decision 29). Capped at 256 KB (413),
	shape-checked, and 409 for a page from before the agent's last clear
	(`annotations.save`).
	"""
	who = _actor(name)
	if who.role not in ("owner", "editor"):
		raise frappe.DoesNotExistError

	editor = who.user if who.role == "editor" else None
	saved = annotations.save(name, data, frappe.utils.cint(epoch), editor=editor)
	return {"updated": saved["updated"]}


# ------------------------------------------------------------------- comments


@frappe.whitelist(methods=["POST"])
def comments_list(name: str) -> dict:
	"""Every thread on a Prototype, for someone who may comment on it."""
	actor = _commenter(name)
	threads = badges.decorate(name, actor.user, comments.list_threads(name))
	return {
		"threads": threads,
		"people": comments.people_in(threads),
		"mentionable": [p for p in comments.mentionable(name) if p["username"] != actor.username],
		"me": actor.username,
		"is_owner": actor.is_owner,
	}


@frappe.whitelist(methods=["POST"])
def comment_add(name: str, anchor: str = "", text: str = ""):
	"""Start a thread on an element. Returns the thread."""
	actor = _commenter(name)
	thread = comments.add_thread(name, actor, anchor, text)
	return comments.one_thread(name, thread, actor.user)


@frappe.whitelist(methods=["POST"])
def comment_reply(name: str, thread: str = "", text: str = ""):
	"""Reply in a thread. Returns the thread."""
	actor = _commenter(name)
	comments.add_reply(name, actor, thread, text)
	return comments.one_thread(name, thread, actor.user)


@frappe.whitelist(methods=["POST"])
def comment_edit(name: str, comment: str = "", text: str = ""):
	"""Edit your own comment. Returns its thread."""
	actor = _commenter(name)
	return comments.one_thread(name, comments.edit(name, actor, comment, text), actor.user)


@frappe.whitelist(methods=["POST"])
def comment_delete(name: str, comment: str = ""):
	"""Delete a comment for good. Returns its thread, or null when the thread went with it."""
	actor = _commenter(name)
	return comments.one_thread(name, comments.delete(name, actor, comment), actor.user)


@frappe.whitelist(methods=["POST"])
def comment_restore(name: str, comment: str = ""):
	"""Undo a delete, for the person who made it, within minutes. Returns the thread."""
	actor = _commenter(name)
	return comments.one_thread(name, comments.restore(name, actor, comment), actor.user)


@frappe.whitelist(methods=["POST"])
def comment_resolve(name: str, thread: str = "", resolved: str = "1"):
	"""Resolve (or reopen, with resolved=0) a thread. Returns the thread."""
	actor = _commenter(name)
	comments.set_resolved(name, actor, thread, bool(frappe.utils.cint(resolved)))
	return comments.one_thread(name, thread, actor.user)


@frappe.whitelist(methods=["POST"])
def comments_delete_resolved(name: str, also: str = "") -> dict:
	"""The owner deletes every resolved thread, and the ones named in `also` (a JSON list of ids: the ones on
	canvas tiles that have gone, which the page counts as resolved). Anyone else gets 403."""
	return {"deleted": comments.delete_resolved(name, _commenter(name), json_list(also))}


@frappe.whitelist(methods=["POST"])
def comment_note_draft(name: str, comment: str = "") -> dict:
	"""The note a thread would make, for the owner to edit and save. Saves nothing."""
	return comments.note_draft(name, _commenter(name), comment)


@frappe.whitelist(methods=["POST"])
def seen_mark(name: str, variants: str = "", threads: str = "") -> dict:
	"""Record that this person has looked at some variants (option values) and threads (ids), two JSON lists.

	A person with no badges here is a 404 (`badges.mark`).
	"""
	user = _commenter(name).user
	return {"marked": badges.mark(name, user, json_list(variants), json_list(threads))}


def json_list(raw) -> list:
	"""A JSON array from a form field, or [] for anything else."""
	try:
		data = json.loads(raw) if isinstance(raw, str) else raw
	except ValueError:
		return []

	return data if isinstance(data, list) else []
