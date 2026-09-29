# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The MCP tool surface for prototype files, checks, and versions.

There is **no `delete_prototype`**. Deleting is a human act in the Sketch UI.
MCP refuses delete by exposing no tool, not by permission.

Every tool addresses a Prototype by its **slug**, scoped to the authenticated
user through `prototype.resolve_owned`. Every agent-supplied file path goes
through `prototype_files.safe_join`, which is the one path guard. This module
writes no second guard.

Tools with structured output declare an `outputSchema` and answer with
`structuredContent`. `isError` is explicit, never guessed from the text.
"""

import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field

import frappe
from frappe.utils import strip_html
from jsonschema import Draft202012Validator

from sketch import assets, checkd, events, prototype, prototype_files, thumbnails, versions

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
	"""A summary, structured output, and optional labeled MCP content blocks."""

	text: str
	structured: dict | None = None
	content: list[dict] = field(default_factory=list)


READ_ONLY = {"list_prototypes", "list_files", "read_files", "check", "get_skill", "list_runtimes"}

DESTRUCTIVE = {"delete_file", "set_public"}


def annotations(name: str) -> dict:
	return {"readOnlyHint": name in READ_ONLY, "destructiveHint": name in DESTRUCTIVE}


# --- dispatch ---------------------------------------------------------------


def call_tool(name: str, arguments: dict) -> dict:
	"""Run one tool and shape the `tools/call` result.

	A crashed handler must not ride the end-of-request commit half-applied, so
	each call runs inside a savepoint and rolls back to it on any exception.

	This is the one seat that sees every tool, so it is where the `tool_call`
	event is recorded. It counts the handler alone, not the transport.
	"""
	tool = TOOLS[name]
	started = time.monotonic()
	frappe.db.savepoint("mcp_tool")
	try:
		validate_arguments(tool.parameters, arguments)
		out = tool.handler(dict(arguments))
	except Exception as e:
		frappe.db.rollback(save_point="mcp_tool")
		logger.warning(f"mcp tool {name} raised: {e}", exc_info=True)
		# The rollback above does not reach this: `events.record` only buffers,
		# and the write happens after the request ends (`sketch/events.py`).
		# A failed tool call is the row most worth keeping.
		events.record(events.TOOL_CALL, ok=False, detail=name, ms=_elapsed_ms(started))
		return {"content": [{"type": "text", "text": failure_text(name, e)}], "isError": True}

	events.record(events.TOOL_CALL, ok=True, detail=name, ms=_elapsed_ms(started))
	reply = {"content": [{"type": "text", "text": out.text}, *out.content], "isError": False}
	if out.structured is not None:
		reply["structuredContent"] = out.structured

	return reply


def validate_arguments(schema: dict, arguments: dict) -> None:
	"""Reject invalid inputs without echoing source content or asset data."""
	for error in Draft202012Validator(schema).iter_errors(arguments):
		path = "arguments"
		for part in error.absolute_path:
			path += f"[{part}]" if isinstance(part, int) else f".{part}"
		if error.validator == "required":
			missing = [key for key in error.validator_value if key not in error.instance]
			message = f"{path}: required field(s): {', '.join(missing)}"
		elif error.validator == "additionalProperties":
			message = f"{path}: use only these fields: {', '.join(error.schema.get('properties', {}))}"
		elif error.validator == "type":
			message = f"{path} must be {error.validator_value}"
		elif error.validator in ("minLength", "maxLength", "minItems", "maxItems", "minimum", "maximum"):
			message = f"{path}: {error.validator} is {error.validator_value}"
		elif error.validator == "enum":
			message = f"{path}: choose one of {', '.join(map(str, error.validator_value))}"
		else:
			message = f"{path}: invalid value ({error.validator})"
		frappe.throw(message, frappe.ValidationError)


def _elapsed_ms(started: float) -> int:
	"""Milliseconds since a `time.monotonic()` reading. Never a wall clock."""
	return int((time.monotonic() - started) * 1000)


def failure_text(name: str, e: Exception) -> str:
	"""One readable line for the agent. No traceback, no HTML, no host path.

	A filesystem OSError prints the absolute path it failed on, which names
	the bench root, the OS user and the private files layout. `filename` is
	what carries that path, and it is set by `open`, `os.mkdir` and every
	other call that takes a name. So a file error answers with one fixed line
	and the whole exception stays in the log.

	The test is `filename` and not the class, because OSError is a much wider
	family than the filesystem: `requests.exceptions.RequestException` is an
	OSError too, and one escapes `sketch/checkd.py` when the network drops
	mid-answer. Calling that a failed write would send the agent to debug the
	wrong thing. It names no path, so it answers with its own message.
	"""
	if isinstance(e, OSError) and (e.filename or e.filename2):
		return f"{name} failed: the file could not be written."

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
		frappe.throw(frappe._("prompt is required. Send the user's message for this request, word for word."))

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


def do_list_runtimes(args: dict) -> ToolResult:
	pins = prototype.available_pins()
	payload = {"versions": pins, "latest": pins[0] if pins else None}
	return ToolResult(text=as_json(payload), structured=payload)


def do_set_runtime(args: dict) -> ToolResult:
	doc = owned(args)
	pin = args["version"]
	if pin not in prototype.available_pins():
		frappe.throw("version must name an installed runtime. Call list_runtimes for available versions.")
	previous = doc.pin
	if previous != pin:
		doc.pin = pin
		doc.save()
	payload = {**record(doc), "previous_pin": previous}
	return ToolResult(
		text=f"Runtime: {previous} -> {pin}. Source files are unchanged. Run check with screenshot: true to verify compatibility and refresh previews.",
		structured=payload,
	)


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


def do_upload_asset(args: dict) -> ToolResult:
	"""Keep images inside the existing source tree and permission boundary."""
	doc = owned(args)
	path = args["path"]
	if not path.startswith("src/assets/") or not path.endswith(".js"):
		frappe.throw("path must be a JavaScript module under src/assets/, such as src/assets/logo.js")
	content = assets.image_module(args["data_base64"], args["mime_type"])
	existed = {path} if os.path.isfile(prototype_files.safe_join(doc.name, path)) else set()
	prototype_files.write_files(doc.name, [{"path": path, "content": content}])
	versions.note_write(doc.name, [path], existed)
	return ToolResult(
		text=f"Uploaded {path}. Import its default export and bind it to an image's src. The image works in checks without external requests."
	)


def do_edit_files(args: dict) -> ToolResult:
	doc = owned(args)
	paths = prototype_files.edit_files(doc.name, args["edits"])
	versions.note_write(doc.name, paths, set(paths))
	return ToolResult(text=f"Edited {len(paths)} file(s): {', '.join(paths)}")


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

	The browser runs inline on a web worker, so one account with many agents
	must not hold them all. `claim_slot` is what stops that, and it sits
	against the run it guards: `run` gives the claim back on every way out, so
	nothing between here and there can leave a slot held (`sketch/checkd.py`).
	"""
	doc = owned(args)
	screenshot = args.get("screenshot", False)
	rev = prototype_files.revision(doc.name) if screenshot else ""
	checkd.claim_slot()
	options = {key: args[key] for key in ("routes", "viewport", "full_page") if key in args}
	report = checkd.run(doc, screenshot=screenshot, thumbnails=screenshot, **options)

	shots = report.pop("screenshots", None) or []
	cards = report.pop("thumbnails", None) or []
	if rev and cards:
		thumbnails.store(doc.name, cards, rev)

	content = []
	for shot in shots:
		if not shot.get("png_base64"):
			continue
		viewport = shot.get("viewport", report.get("viewport", {"width": 1280, "height": 800}))
		label = f"Screenshot: {shot.get('route', '/')} ({viewport['width']}x{viewport['height']}, {'full page' if shot.get('fullPage') else 'viewport'})"
		content.extend(
			[
				{"type": "text", "text": label},
				{"type": "image", "data": shot["png_base64"], "mimeType": "image/png"},
			]
		)
	uncommitted = versions.pending_count(doc.name)
	report["uncommitted"] = uncommitted
	status = str(report.get("status") or "unknown")
	# The quality signal for the whole product: how often an agent writes Vue
	# that does not build. A check that never reached the browser raises out of
	# `checkd.run` above and is a failed `tool_call` instead, with no row here.
	events.record(events.CHECK, prototype=doc.name, ok=status == "ok", detail=status)
	return ToolResult(text=check_text(report, uncommitted), structured=report, content=content)


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
	if "visited" in report:
		lines.append("visited: " + (", ".join(report["visited"]) or "none"))
	if report.get("viewport"):
		v = report["viewport"]
		lines.append(f"viewport: {v['width']}x{v['height']}")
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
		"visited": {"type": "array", "items": {"type": "string"}},
		"viewport": {"type": "object"},
		"fullPage": {"type": "boolean"},
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
				name="list_runtimes",
				description="List installed frappe-ui runtime versions, newest first. Use an exact version with set_runtime.",
				parameters={"type": "object", "properties": {}},
				handler=do_list_runtimes,
				output_schema={
					"type": "object",
					"properties": {
						"versions": {"type": "array", "items": {"type": "string"}},
						"latest": {"type": ["string", "null"]},
					},
					"required": ["versions", "latest"],
				},
			),
			Tool(
				name="set_runtime",
				description="Change a Prototype's frappe-ui runtime to an installed version. Source files and its URL stay unchanged. Run check with screenshot: true afterward; component APIs can differ between versions. Use previous_pin from the result to switch back.",
				parameters={
					"type": "object",
					"properties": {
						"prototype": PROTOTYPE_PARAM,
						"version": {"type": "string", "minLength": 1},
					},
					"required": ["prototype", "version"],
				},
				handler=do_set_runtime,
				output_schema={
					**RECORD_SCHEMA,
					"properties": {**RECORD_SCHEMA["properties"], "previous_pin": {"type": "string"}},
					"required": [*RECORD_SCHEMA["required"], "previous_pin"],
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
						"paths": {
							"type": "array",
							"minItems": 1,
							"maxItems": 500,
							"items": {"type": "string", "minLength": 1},
						},
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
				name="edit_files",
				description="Apply exact replacements across files in order. Repeated paths use the preceding edit's result. Every match and quota is checked before files change. An absent or ambiguous match leaves all files unchanged.",
				parameters={
					"type": "object",
					"properties": {
						"prototype": PROTOTYPE_PARAM,
						"edits": {
							"type": "array",
							"minItems": 1,
							"maxItems": prototype_files.MAX_BATCH_FILES,
							"items": {
								"type": "object",
								"properties": {
									"path": {"type": "string", "minLength": 1},
									"old_string": {"type": "string", "minLength": 1},
									"new_string": {"type": "string"},
								},
								"required": ["path", "old_string", "new_string"],
							},
						},
					},
					"required": ["prototype", "edits"],
				},
				handler=do_edit_files,
			),
			Tool(
				name="upload_asset",
				description="Upload an image as a JavaScript module exporting a data URL. Import that module and bind the export to an image's src. Images work in checks without external network access. At most 512000 decoded bytes. Replaces an existing module at the same path; normal file and tree quotas apply.",
				parameters={
					"type": "object",
					"properties": {
						"prototype": PROTOTYPE_PARAM,
						"path": {
							"type": "string",
							"pattern": r"^src/assets/.+\.js$",
							"description": "Module path, such as src/assets/logo.js.",
						},
						"mime_type": {"type": "string", "enum": list(assets.MIME_FORMATS)},
						"data_base64": {
							"type": "string",
							"minLength": 4,
							"maxLength": ((assets.MAX_ASSET_BYTES + 2) // 3) * 4,
							"description": "Base64 image bytes, without a data URL prefix.",
						},
					},
					"required": ["prototype", "path", "mime_type", "data_base64"],
				},
				handler=do_upload_asset,
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
						"routes": {
							"type": "array",
							"minItems": 1,
							"maxItems": 20,
							"uniqueItems": True,
							"items": {
								"type": "string",
								"minLength": 1,
								"maxLength": 2048,
								"pattern": r"^/(?!/)[^\\\s]*$",
							},
							"description": "Concrete router paths to check instead of automatic discovery, such as /proposals/123 or /schedule?day=2.",
						},
						"viewport": {
							"type": "object",
							"properties": {
								"width": {"type": "integer", "minimum": 320, "maximum": 2560},
								"height": {"type": "integer", "minimum": 240, "maximum": 2160},
							},
							"required": ["width", "height"],
							"description": "Capture viewport in pixels. Defaults to 1280x800. Use 390x844 for a mobile layout.",
						},
						"full_page": {
							"type": "boolean",
							"default": False,
							"description": "Capture the full scrollable page. Gallery thumbnails keep their default viewport.",
						},
						"screenshot": {
							"type": "boolean",
							"description": "Return one labeled PNG per visited route, and refresh the picture on this Prototype's gallery card. Set it true at the end of each user request.",
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
							"maxLength": 140,
							"description": "One short line naming what you changed. At most 140 characters. Optional.",
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


def close_input_objects(schema: dict) -> None:
	if schema.get("type") == "object":
		schema["additionalProperties"] = False
		for value in schema.get("properties", {}).values():
			close_input_objects(value)
	if "items" in schema:
		close_input_objects(schema["items"])


TOOLS = build_tools()
for tool in TOOLS.values():
	close_input_objects(tool.parameters)
