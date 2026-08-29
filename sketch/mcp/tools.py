# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The MCP tool surface: twelve tools, and no more.

There is **no `delete_prototype`**. Deleting is a human act in the Sketch UI.
MCP refuses delete by exposing no tool, not by permission.

Every tool addresses a Prototype by its **slug**, scoped to the authenticated
user through `prototype.resolve_owned`. Every agent-supplied file path goes
through `prototype_files.safe_join`, which is the one path guard. This module
writes no second guard.

Seven tools return structured output: `create_prototype`, `list_prototypes`,
`list_files`, `read_files`, `check`, `commit` and `set_public`. They declare an
`outputSchema` and answer with `structuredContent`. `isError` is set
explicitly, never guessed from the text.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Callable

import frappe
from frappe.utils import strip_html

from sketch import checkd, prototype, prototype_files, thumbnails, versions

logger = frappe.logger("sketch.mcp")

# get_app_path() scrubs a hyphen to an underscore, so join by hand.
SKILL_FILE = ("skill", "frappe-ui.md")


@dataclass
class Tool:
	"""One MCP tool. `handler(args)` returns a ToolResult."""

	name: str
	description: str
	parameters: dict
	handler: Callable
	output_schema: dict | None = None


@dataclass
class ToolResult:
	"""What a handler returns: text, and optionally structure and images."""

	text: str
	structured: dict | None = None
	images: list[dict] = field(default_factory=list)


READ_ONLY = {"list_prototypes", "list_files", "read_files", "check", "get_skill"}

DESTRUCTIVE = {"delete_file", "set_public"}


def annotations(name: str) -> dict:
	return {"readOnlyHint": name in READ_ONLY, "destructiveHint": name in DESTRUCTIVE}


# --- dispatch ---------------------------------------------------------------


def call_tool(name: str, arguments: dict) -> dict:
	"""Run one tool and shape the `tools/call` result.

	A crashed handler must not ride the end-of-request commit half-applied, so
	each call runs inside a savepoint and rolls back to it on any exception.
	"""
	tool = TOOLS[name]
	frappe.db.savepoint("mcp_tool")
	try:
		out = tool.handler(dict(arguments or {}))
	except Exception as e:
		frappe.db.rollback(save_point="mcp_tool")
		logger.warning(f"mcp tool {name} raised: {e}", exc_info=True)
		return {"content": [{"type": "text", "text": failure_text(name, e)}], "isError": True}

	reply = {"content": [{"type": "text", "text": out.text}] + out.images, "isError": False}
	if out.structured is not None:
		reply["structuredContent"] = out.structured

	return reply


def failure_text(name: str, e: Exception) -> str:
	"""One readable line for the agent. No traceback, no HTML."""
	message = strip_html(str(e)).strip() or type(e).__name__
	if isinstance(e, frappe.DoesNotExistError):
		return f"{name} failed: {message}. Call list_prototypes for the slugs you own."

	return f"{name} failed: {message}"


# --- shared helpers ---------------------------------------------------------


def owned(args: dict):
	"""The Prototype named by the `prototype` argument, for this user."""
	slug = str(args.get("prototype") or "").strip()
	if not slug:
		frappe.throw(frappe._("prototype is required. It is the slug, not the title."))

	return prototype.resolve_owned(slug)


def user_prompt(args: dict) -> str:
	"""The `prompt` argument, word for word. Nothing here reshapes it."""
	prompt = args.get("prompt")
	prompt = prompt if isinstance(prompt, str) else ""
	if not prompt.strip():
		frappe.throw(
			frappe._(
				"prompt is required. Send the user's message for this request, word for word."
			)
		)

	return prompt


def record(doc) -> dict:
	"""The Prototype as structured fields. Never prose."""
	return {
		"id": doc.name,
		"title": doc.title,
		"slug": doc.slug,
		"pin": doc.pin,
		"is_public": bool(doc.is_public),
		"url": prototype.public_url(doc),
	}


def as_json(payload) -> str:
	return json.dumps(payload, indent=2, sort_keys=False)


RECORD_SCHEMA = {
	"type": "object",
	"properties": {
		"id": {"type": "string", "description": "The Prototype's stable id."},
		"title": {"type": "string"},
		"slug": {"type": "string", "description": "Pass this as `prototype` to every other tool."},
		"pin": {"type": "string", "description": "The frappe-ui version this Prototype renders with."},
		"is_public": {"type": "boolean"},
		"url": {"type": "string"},
	},
	"required": ["id", "title", "slug", "pin", "is_public", "url"],
}

PROTOTYPE_PARAM = {
	"type": "string",
	"description": "The Prototype slug, as returned by create_prototype or list_prototypes.",
}


# --- handlers ---------------------------------------------------------------


def do_list_prototypes(args: dict) -> ToolResult:
	# The owner filter is explicit. `if_owner` is per role, so a token held by a
	# System Manager would otherwise list every user's Prototypes. get_list, and
	# never get_all, because get_all drops the permission check as well.
	rows = frappe.get_list(
		"Sketch Prototype",
		filters={"owner": frappe.session.user},
		fields=["name", "title", "slug", "pin", "is_public", "owner"],
		order_by="modified desc",
		limit_page_length=0,
	)
	items = [record(frappe._dict(row)) for row in rows]
	payload = {"prototypes": items}
	return ToolResult(text=as_json(payload), structured=payload)


def do_create_prototype(args: dict) -> ToolResult:
	title = str(args.get("name") or "").strip()
	if not title:
		frappe.throw(frappe._("name is required"))

	doc = prototype.create(title)
	payload = record(doc)
	return ToolResult(text=as_json(payload), structured=payload)


def do_list_files(args: dict) -> ToolResult:
	doc = owned(args)
	payload = {"files": prototype_files.list_files(doc.name)}
	return ToolResult(text=as_json(payload), structured=payload)


def do_read_files(args: dict) -> ToolResult:
	doc = owned(args)
	paths = args.get("paths")
	if not isinstance(paths, list) or not paths:
		frappe.throw(frappe._("paths must be a list of one or more relative paths"))

	payload = {"files": prototype_files.read_files(doc.name, paths)}
	return ToolResult(text=as_json(payload), structured=payload)


def do_write_files(args: dict) -> ToolResult:
	doc = owned(args)
	files = args.get("files")
	if not isinstance(files, list) or not files:
		frappe.throw(frappe._("files must be a list of {path, content} objects"))

	# Which paths are already on disk decides added against modified, so read
	# it before the write overwrites the answer.
	existed = {
		entry.get("path")
		for entry in files
		if entry.get("path") and os.path.isfile(prototype_files.safe_join(doc.name, entry["path"]))
	}

	written = prototype_files.write_files(doc.name, files)
	versions.note_write(doc.name, written, existed)
	return ToolResult(text="Wrote {0} file(s): {1}".format(len(written), ", ".join(written)))


def do_edit_file(args: dict) -> ToolResult:
	doc = owned(args)
	path = args.get("path")
	old_string = args.get("old_string")
	new_string = args.get("new_string")
	if not path or old_string is None or new_string is None:
		frappe.throw(frappe._("path, old_string and new_string are all required"))

	prototype_files.edit_file(doc.name, path, old_string, new_string)
	versions.note(doc.name, path, versions.MODIFIED)
	return ToolResult(text=f"Edited {path}.")


def do_delete_file(args: dict) -> ToolResult:
	doc = owned(args)
	path = args.get("path")
	if not path:
		frappe.throw(frappe._("path is required"))

	prototype_files.delete_file(doc.name, path)
	versions.note(doc.name, path, versions.DELETED)
	return ToolResult(text=f"Deleted {path}.")


def do_commit(args: dict) -> ToolResult:
	"""File every change since the last version under the user's prompt."""
	doc = owned(args)
	prompt = user_prompt(args)
	summary = args.get("summary")
	summary = summary.strip() if isinstance(summary, str) else None

	version = versions.commit(doc, prompt, summary or None)
	if version is None:
		return ToolResult(
			text="No file changed since the last version. Nothing recorded.",
			structured={"recorded": False},
		)

	payload = {
		"recorded": True,
		"sequence": version.sequence,
		"files_added": version.files_added,
		"files_modified": version.files_modified,
		"files_deleted": version.files_deleted,
		"changes": json.loads(version.changes or "[]"),
	}
	text = "Recorded version {0}. {1} added, {2} changed, {3} deleted.".format(
		version.sequence, version.files_added, version.files_modified, version.files_deleted
	)
	return ToolResult(text=text, structured=payload)


def do_get_skill(args: dict) -> ToolResult:
	path = os.path.join(frappe.get_app_path("sketch"), *SKILL_FILE)
	with open(path, encoding="utf-8") as handle:
		return ToolResult(text=handle.read())


def do_set_public(args: dict) -> ToolResult:
	doc = owned(args)
	is_public = args.get("is_public")
	if not isinstance(is_public, bool):
		frappe.throw(frappe._("is_public must be true or false"))

	doc.is_public = 1 if is_public else 0
	doc.save()
	payload = record(doc)
	return ToolResult(text=as_json(payload), structured=payload)


def do_set_name(args: dict) -> ToolResult:
	doc = owned(args)
	title = str(args.get("name") or "").strip()
	if not title:
		frappe.throw(frappe._("name is required"))

	# The slug is frozen at creation, so the URL never moves.
	doc.title = title
	doc.save()
	return ToolResult(text=as_json(record(doc)))


def do_check(args: dict) -> ToolResult:
	"""Open the Prototype in sketch-checkd and report what the browser saw.

	`screenshot` also takes the card images, in both themes. They are the same
	browser run and the agent never sees them: the gallery and the feed do
	(`sketch/thumbnails.py`). The skill tells the agent to call check with
	`screenshot: true` once at the end of every request, so that is the moment
	the card is already worth re-taking, and it costs one extra page load
	rather than a second check.

	The stamp is read before the run and not after. A file written while the
	browser was open must leave the pictures stale, so the next card view asks
	for another capture.
	"""
	doc = owned(args)
	screenshot = bool(args.get("screenshot"))
	rev = prototype_files.revision(doc.name) if screenshot else ""
	report = checkd.run(doc, screenshot=screenshot, thumbnails=screenshot)

	shots = report.pop("screenshots", None) or []
	cards = report.pop("thumbnails", None) or []
	if rev and cards:
		thumbnails.store(doc.name, cards, rev)

	images = [
		{"type": "image", "data": shot.get("png_base64"), "mimeType": "image/png"}
		for shot in shots
		if shot.get("png_base64")
	]
	uncommitted = versions.pending_count(doc.name)
	report["uncommitted"] = uncommitted
	return ToolResult(text=check_text(report, uncommitted), structured=report, images=images)


def check_text(report: dict, uncommitted: int = 0) -> str:
	"""The report as lines an agent reads. Errors as file:line:col message.

	`uncommitted` is the number of files changed since the last version. The
	caller counts them; this function reads nothing of its own.
	"""
	lines = [f"status: {report.get('status')}"]
	for entry in report.get("errors") or []:
		lines.append(f"error {entry.get('kind')}: {error_line(entry)}")
	for entry in report.get("warnings") or []:
		lines.append(f"warning {entry.get('kind')}: {entry.get('file')} {entry.get('message')}")
	for entry in report.get("consoleErrors") or []:
		lines.append(f"console: {entry}")
	if report.get("routes"):
		lines.append("routes: " + ", ".join(report["routes"]))
	for entry in report.get("skipped") or []:
		lines.append(f"skipped {entry.get('route')}: {entry.get('reason')}")
	if uncommitted > 0:
		lines.append(
			f"uncommitted: {uncommitted} file(s) changed since the last version. "
			"Call commit with the user's prompt."
		)

	return "\n".join(lines)


def error_line(entry: dict) -> str:
	place = entry.get("file") or ""
	if entry.get("line") is not None:
		place = f"{place}:{entry.get('line')}:{entry.get('column')}"

	return f"{place} {entry.get('message')}".strip()


# --- the surface ------------------------------------------------------------

CHECK_SCHEMA = {
	"type": "object",
	"properties": {
		"status": {
			"type": "string",
			"enum": ["ok", "errors", "compile-failed", "link-failed", "boot-failed", "empty"],
		},
		"errors": {"type": "array", "items": {"type": "object"}},
		"warnings": {"type": "array", "items": {"type": "object"}},
		"consoleErrors": {"type": "array"},
		"routes": {"type": "array", "items": {"type": "string"}},
		"skipped": {"type": "array", "items": {"type": "object"}},
		"timings": {"type": "object"},
		"uncommitted": {
			"type": "integer",
			"description": "Files changed since the last version. Call commit when it is above zero.",
		},
	},
	"required": ["status"],
}

CHANGE_SCHEMA = {
	"type": "object",
	"properties": {
		"path": {"type": "string"},
		"action": {"type": "string", "enum": [versions.ADDED, versions.MODIFIED, versions.DELETED]},
	},
	"required": ["path", "action"],
}

COMMIT_SCHEMA = {
	"type": "object",
	"properties": {
		"recorded": {
			"type": "boolean",
			"description": "False when no file changed since the last version.",
		},
		"sequence": {"type": "integer", "description": "The version number, 1 for the first."},
		"files_added": {"type": "integer"},
		"files_modified": {"type": "integer"},
		"files_deleted": {"type": "integer"},
		"changes": {"type": "array", "items": CHANGE_SCHEMA},
	},
	"required": ["recorded"],
}


def build_tools() -> dict[str, Tool]:
	return {
		tool.name: tool
		for tool in [
			Tool(
				name="list_prototypes",
				description="List your Prototypes. Returns id, title, slug, pin, is_public and url for each one. The slug is what every other tool takes as `prototype`.",
				parameters={"type": "object", "properties": {}},
				handler=do_list_prototypes,
				output_schema={
					"type": "object",
					"properties": {"prototypes": {"type": "array", "items": RECORD_SCHEMA}},
					"required": ["prototypes"],
				},
			),
			Tool(
				name="create_prototype",
				description="Create an empty Prototype and return its record. `name` is required and there is no default: the slug and the public URL are derived from it and then frozen, so pick a good name. The new Prototype holds no files until you write them.",
				parameters={
					"type": "object",
					"properties": {"name": {"type": "string", "description": "The display name."}},
					"required": ["name"],
				},
				handler=do_create_prototype,
				output_schema=RECORD_SCHEMA,
			),
			Tool(
				name="list_files",
				description="List every file in a Prototype with its size. Content is not returned; call read_files for that.",
				parameters={
					"type": "object",
					"properties": {"prototype": PROTOTYPE_PARAM},
					"required": ["prototype"],
				},
				handler=do_list_files,
				output_schema={
					"type": "object",
					"properties": {
						"files": {
							"type": "array",
							"items": {
								"type": "object",
								"properties": {"path": {"type": "string"}, "size": {"type": "integer"}},
								"required": ["path", "size"],
							},
						}
					},
					"required": ["files"],
				},
			),
			Tool(
				name="read_files",
				description="Read the named files. Each path is a full relative path such as src/pages/Home.vue. Read a file before you edit it.",
				parameters={
					"type": "object",
					"properties": {
						"prototype": PROTOTYPE_PARAM,
						"paths": {"type": "array", "items": {"type": "string"}},
					},
					"required": ["prototype", "paths"],
				},
				handler=do_read_files,
				output_schema={
					"type": "object",
					"properties": {
						"files": {
							"type": "array",
							"items": {
								"type": "object",
								"properties": {
									"path": {"type": "string"},
									"content": {"type": "string"},
								},
								"required": ["path", "content"],
							},
						}
					},
					"required": ["files"],
				},
			),
			Tool(
				name="write_files",
				description="Write whole files. Creates a file, or replaces one end to end. Parent folders are made for you. Use edit_file for a small change to a file that already exists.",
				parameters={
					"type": "object",
					"properties": {
						"prototype": PROTOTYPE_PARAM,
						"files": {
							"type": "array",
							"items": {
								"type": "object",
								"properties": {
									"path": {"type": "string"},
									"content": {"type": "string"},
								},
								"required": ["path", "content"],
							},
						},
					},
					"required": ["prototype", "files"],
				},
				handler=do_write_files,
			),
			Tool(
				name="edit_file",
				description="Replace one exact string in one file. `old_string` must occur exactly once; the call fails when it occurs zero times or more than once. Recover from a failure by reading the file again and giving more surrounding lines.",
				parameters={
					"type": "object",
					"properties": {
						"prototype": PROTOTYPE_PARAM,
						"path": {"type": "string"},
						"old_string": {"type": "string", "description": "The exact text to replace."},
						"new_string": {"type": "string", "description": "The text to put there."},
					},
					"required": ["prototype", "path", "old_string", "new_string"],
				},
				handler=do_edit_file,
			),
			Tool(
				name="delete_file",
				description="Delete one file from a Prototype. This cannot be undone.",
				parameters={
					"type": "object",
					"properties": {"prototype": PROTOTYPE_PARAM, "path": {"type": "string"}},
					"required": ["prototype", "path"],
				},
				handler=do_delete_file,
			),
			Tool(
				name="check",
				description="Compile and mount the Prototype in a real browser, walk its routes, and report compile errors, console errors and timings. Call it with screenshot: true once at the end of every user request: that is a workflow step, not an option. Fix every error it reports before you report done, then call commit.",
				parameters={
					"type": "object",
					"properties": {
						"prototype": PROTOTYPE_PARAM,
						"screenshot": {
							"type": "boolean",
							"description": "Return one PNG per static route, and refresh the picture on this Prototype's gallery card. Set it true at the end of each user request.",
							"default": False,
						},
					},
					"required": ["prototype"],
				},
				handler=do_check,
				output_schema=CHECK_SCHEMA,
			),
			Tool(
				name="commit",
				description="Record a version of the Prototype. Call it once at the end of every user request, after check, with `prompt` set to the user's message word for word. It files every change you made since the last version under that prompt, so the person can read back what they asked for and what it changed.",
				parameters={
					"type": "object",
					"properties": {
						"prototype": PROTOTYPE_PARAM,
						"prompt": {
							"type": "string",
							"description": "The user's request, word for word. Copy their message exactly. Do not paraphrase it, do not shorten it, and do not write your own summary here.",
						},
						"summary": {
							"type": "string",
							"description": "One short line naming what you changed. Optional.",
						},
					},
					"required": ["prototype", "prompt"],
				},
				handler=do_commit,
				output_schema=COMMIT_SCHEMA,
			),
			Tool(
				name="get_skill",
				description="The frappe-ui skill for this server: the components, tokens, icons and import specifiers that resolve, and the patterns that do not. Read it first, before you write any file.",
				parameters={"type": "object", "properties": {}},
				handler=do_get_skill,
			),
			Tool(
				name="set_public",
				description="Turn the public link on or off. Public means anyone with the URL can open the Prototype.",
				parameters={
					"type": "object",
					"properties": {"prototype": PROTOTYPE_PARAM, "is_public": {"type": "boolean"}},
					"required": ["prototype", "is_public"],
				},
				handler=do_set_public,
				output_schema=RECORD_SCHEMA,
			),
			Tool(
				name="set_name",
				description="Rename a Prototype. This changes the display name only. The slug and the public URL never move.",
				parameters={
					"type": "object",
					"properties": {"prototype": PROTOTYPE_PARAM, "name": {"type": "string"}},
					"required": ["prototype", "name"],
				},
				handler=do_set_name,
			),
		]
	}


TOOLS = build_tools()
