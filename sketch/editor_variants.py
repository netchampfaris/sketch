# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""What the owner does with an invited editor's variants, and what an editor does with their own.

An editor's agent writes `src/variants/@<username>/<name>.vue`, a component with a
`<variant>` tag (`sketch.sharing.variant_meta`). The Runtime shows it as one more option
of the set it targets, labelled with its author. Three things can happen to it after that,
all of them here, all of them recorded as a version so they can be undone:

- **Make default** (the owner). Sketch moves the file into the owner's own tree,
  `src/variants/adopted/`, and writes the author into `src/variants/adopted.json`. The
  option is then the owner's to edit and keeps "Made by <author>". Nothing in the owner's
  page source is rewritten: the registry says which option leads, and the Runtime reads it.
- **Delete** (the owner, any variant; an editor, their own).
- **Undo** of either.

An option value is the file's path under `src/variants/`, without `.vue`: `@arohi/compact`
or `adopted/compact`. It is a name in a URL and a toast, never a place to write: every
path built from it is checked against the folder it must be in.
"""

import json
import re

import frappe

from sketch import prototype_files, sharing, snapshots, versions

OPTION = re.compile(r"(?:@[a-z0-9-]+|adopted)/[A-Za-z0-9][A-Za-z0-9._/-]*")


def slug_of(text: str) -> str:
	return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")


def is_extra(option: str) -> bool:
	"""True when an option value names a file under src/variants/ rather than a slot."""
	return isinstance(option, str) and bool(OPTION.fullmatch(option)) and ".." not in option.split("/")


def path_of(option: str) -> str:
	if not is_extra(option):
		frappe.throw(frappe._("That is not a variant a person added."), frappe.ValidationError)

	return f"{sharing.VARIANTS_ROOT}/{option}.vue"


def option_of(path: str) -> str:
	return path[len(sharing.VARIANTS_ROOT) + 1 : -len(".vue")]


# ------------------------------------------------------------------- registry


def read_registry(name: str) -> dict:
	try:
		raw = prototype_files.read_files(name, [sharing.ADOPTED_FILE])[0]["content"]
	except frappe.ValidationError:
		return {}

	return sharing.read_adopted({sharing.ADOPTED_FILE: raw})


def write_registry(name: str, registry: dict) -> None:
	"""The registry as the server writes it. An empty registry is no file at all."""
	if not registry:
		try:
			prototype_files.delete_file(name, sharing.ADOPTED_FILE)
		except frappe.ValidationError:
			pass
		return

	text = json.dumps(registry, indent=1, sort_keys=True) + "\n"
	prototype_files.write_files(name, [{"path": sharing.ADOPTED_FILE, "content": text}])


def targets_same(meta: dict, other: dict) -> bool:
	"""Two variants lead the same set when they name the same set or the same component."""
	if meta["component"] or other["component"]:
		return meta["component"] == other["component"]

	return slug_of(meta["set"]) == slug_of(other["set"])


def leaders(name: str, host_file: str, set_name: str, keep: str | None = None) -> list[str]:
	"""The adopted variants that lead this set now."""
	registry = read_registry(name)
	probe = {
		"set": set_name,
		"component": host_file if _is_component_host(name, host_file, set_name) else "",
		"name": "",
	}
	found = []
	for path, row in registry.items():
		if path == keep or not isinstance(row, dict) or not row.get("default"):
			continue

		try:
			meta = sharing.variant_meta(prototype_files.read_files(name, [path])[0]["content"])
		except frappe.ValidationError:
			continue

		if meta and targets_same(meta, probe):
			found.append(path)

	return found


def targeting(name: str, host_file: str, set_name: str) -> list[str]:
	"""Every variant file, an editor's or an adopted one, that is an option of this set.

	A file whose `<variant>` tag cannot be read is left out: nothing says which set it is for.
	"""
	probe = {
		"set": set_name,
		"component": host_file if _is_component_host(name, host_file, set_name) else "",
		"name": "",
	}
	found = []
	for row in prototype_files.list_files(name):
		path = row["path"]
		if not path.endswith(".vue") or not (sharing.is_editor_path(path) or path.startswith(sharing.ADOPTED_DIR)):
			continue

		try:
			meta = sharing.variant_meta(prototype_files.read_files(name, [path])[0]["content"])
		except frappe.ValidationError:
			continue

		if meta and targets_same(meta, probe):
			found.append(path)

	return found


def clear_defaults(name: str, host_file: str, set_name: str, keep: str | None = None) -> bool:
	"""Stop every adopted variant of this set from leading it. True when one did."""
	found = leaders(name, host_file, set_name, keep)
	if not found:
		return False

	registry = read_registry(name)
	for path in found:
		registry[path]["default"] = False

	write_registry(name, registry)
	return True


def _is_component_host(name: str, file: str, set_name: str) -> bool:
	"""True when `file` holds no `<Variants name="{set_name}">`, so its set is the component wrapped around it."""
	from sketch import variant_default

	try:
		source = prototype_files.read_files(name, [file])[0]["content"]
	except frappe.ValidationError:
		return False

	return not variant_default.find_sets(source, set_name)


# --------------------------------------------------------------------- adopt


def adopt(doc, host_file: str, set_name: str, option: str) -> dict:
	"""Make an editor's variant the default of its set, as the owner's own file."""
	source_path = path_of(option)
	if not sharing.is_editor_path(source_path):
		frappe.throw(frappe._("“{0}” is already the owner's.").format(option), frappe.ValidationError)

	versions.lock(doc.name)
	try:
		source = prototype_files.read_files(doc.name, [source_path])[0]["content"]
	except frappe.ValidationError:
		frappe.throw(frappe._("That variant is gone. Reload the page."), frappe.ValidationError)

	meta = sharing.variant_meta(source)
	if not meta:
		frappe.throw(frappe._("That file does not declare a <variant>."), frappe.ValidationError)

	_check_target(doc.name, meta, host_file, set_name)
	author = sharing.author_of_path(source_path)
	if author not in sharing.authors([source_path]):
		frappe.throw(frappe._("The author of that variant is not a Sketch user."), frappe.ValidationError)

	if versions.pending(doc.name):
		versions.commit(doc, "Changes before the default was changed", source="App")

	stem = source_path.rsplit("/", 1)[1][: -len(".vue")]
	destination = _free_path(doc.name, f"{sharing.ADOPTED_DIR}{stem}.vue")
	clear_defaults(doc.name, host_file, set_name)
	registry = read_registry(doc.name)
	registry[destination] = {"author": author, "default": True}

	prototype_files.write_files(doc.name, [{"path": destination, "content": source}])
	prototype_files.delete_file(doc.name, source_path)
	write_registry(doc.name, registry)
	versions.note(doc.name, destination, versions.ADDED)
	versions.note(doc.name, source_path, versions.DELETED)
	versions.note(doc.name, sharing.ADOPTED_FILE, versions.MODIFIED)
	version = versions.commit(
		doc,
		f"Made “{meta['name']}” the default for {set_name}",
		source="App",
	)
	return {
		"file": host_file,
		"name": set_name,
		"option": option_of(destination),
		"sequence": version.sequence if version else None,
	}


def _check_target(name: str, meta: dict, host_file: str, set_name: str) -> None:
	"""The variant must belong to the set it is being made the default of."""
	if meta["component"]:
		if meta["component"] != host_file:
			frappe.throw(frappe._("That variant belongs to another component."), frappe.ValidationError)
		return

	if slug_of(meta["set"]) != slug_of(set_name):
		frappe.throw(frappe._("That variant belongs to another set."), frappe.ValidationError)


def _free_path(name: str, path: str) -> str:
	"""`path`, or the same name with -2, -3 … when a file is already there."""
	existing = {row["path"] for row in prototype_files.list_files(name)}
	if path not in existing:
		return path

	stem = path[: -len(".vue")]
	n = 2
	while f"{stem}-{n}.vue" in existing:
		n += 1

	return f"{stem}-{n}.vue"


# -------------------------------------------------------------------- delete


def delete(doc, username: str, is_owner: bool, option: str) -> dict:
	"""Delete one variant file. The owner may delete any; an editor, their own."""
	path = path_of(option)
	owner_of_file = sharing.author_of_path(path)
	if not is_owner and owner_of_file != username:
		frappe.throw(frappe._("You can delete your own variants only."), frappe.PermissionError)

	versions.lock(doc.name)
	by = None if is_owner else username
	try:
		source = prototype_files.read_files(doc.name, [path])[0]["content"]
	except frappe.ValidationError:
		frappe.throw(frappe._("That variant is already gone."), frappe.ValidationError)

	meta = sharing.variant_meta(source) if _quiet(source) else None
	label = (meta or {}).get("name") or option.rsplit("/", 1)[-1]
	if versions.pending(doc.name, by):
		versions.commit(doc, "Changes before a variant was deleted", source="App", by=by)

	prototype_files.delete_file(doc.name, path)
	versions.note(doc.name, path, versions.DELETED, by)
	registry = read_registry(doc.name)
	if path in registry:
		registry.pop(path)
		write_registry(doc.name, registry)
		versions.note(doc.name, sharing.ADOPTED_FILE, versions.MODIFIED, by)

	version = versions.commit(doc, f"Deleted the variant “{label}”", source="App", by=by)
	return {"option": option, "label": label, "sequence": version.sequence if version else None}


def _quiet(source: str) -> bool:
	"""True when the tag parses. A broken file still deletes; it just has no label."""
	try:
		sharing.variant_meta(source)
		return True
	except frappe.ValidationError:
		return False


def undo_delete(doc, username: str, is_owner: bool, sequence, option: str) -> dict:
	"""Bring a deleted variant back. An editor may undo their own deletions only."""
	sequence = _int(sequence)
	row = frappe.db.get_value(
		versions.VERSION, {"prototype": doc.name, "sequence": sequence}, ["prompt", "author"], as_dict=True
	)
	if not row or not (row.prompt or "").startswith("Deleted the variant"):
		frappe.throw(frappe._("That version did not delete a variant."), frappe.ValidationError)

	if not is_owner and (row.author or "") != username:
		frappe.throw(frappe._("You can undo your own deletions only."), frappe.PermissionError)

	by = None if is_owner else username
	label = re.sub(r"^Deleted the variant “(.*)”$", r"\1", row.prompt)
	return restore_files(doc, sequence, f"Undid deleting the variant “{label}”", by)


# ------------------------------------------------------------------ undo (any)


def restore_files(doc, sequence: int, prompt: str, by: str | None = None) -> dict:
	"""Put every file version `sequence` changed back as the version before left it.

	Refused when any of them is not as that version left it, so a later write is
	never clobbered. A file the version added is deleted; one it deleted comes back.
	"""
	changed_since = frappe._("the page changed since. Ask your agent instead.")
	if sequence < 2:
		frappe.throw(changed_since, frappe.ValidationError)

	versions.lock(doc.name)
	raw = frappe.db.get_value(versions.VERSION, {"prototype": doc.name, "sequence": sequence}, "changes")
	paths = [row["path"] for row in versions._parse(raw) if row.get("path")]
	after = versions._manifest_of(doc.name, sequence)
	before = versions._manifest_of(doc.name, sequence - 1)
	if not paths:
		frappe.throw(changed_since, frappe.ValidationError)

	current = snapshots.capture(doc.name)
	for path in paths:
		if current.get(path) != after.get(path):
			frappe.throw(changed_since, frappe.ValidationError)

	if versions.pending(doc.name, by):
		versions.commit(doc, "Changes before an undo", source="App", by=by)

	for path in paths:
		if path in before:
			content = snapshots.read_blob(doc.name, before[path]).decode("utf-8")
			prototype_files.write_files(doc.name, [{"path": path, "content": content}])
			versions.note(doc.name, path, versions.MODIFIED if path in current else versions.ADDED, by)
		elif path in current:
			prototype_files.delete_file(doc.name, path)
			versions.note(doc.name, path, versions.DELETED, by)

	version = versions.commit(doc, prompt, source="App", by=by)
	return {"sequence": version.sequence if version else None}


def _int(value) -> int:
	try:
		return int(value)
	except (TypeError, ValueError):
		frappe.throw(frappe._("sequence must be a version number"), frappe.ValidationError)
