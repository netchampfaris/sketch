# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""When each option of a Variants set first appeared, so the Runtime can show them oldest first.

A set's options keep their place: making one the default never moves it
(sketch/variant_default.py). The place is the version that first held the
option: an owner's slot, the first version whose `<Variants name="…">` had that
`<template #key>`; a teammate's variant, the first version that held its file.
Adopting a teammate's variant moves its file byte for byte, so a new variant
file whose content left another variant file in the same version keeps that
file's place.

It is all read from version history, so a Prototype made before this existed
gets its places from the versions it already has. The result is kept in the
snapshot store (`first-seen.json`), beside the blobs it was read from, and only
versions newer than the last one read are read again. A place, once known, is
never forgotten: a prune or a restore cannot move an option.

What no version holds yet (the agent wrote it and has not committed) has no
place, and the Runtime puts it last.
"""

import json
import os

import frappe

from sketch import sharing, snapshots, versions, variant_default

FILE = "first-seen.json"
SHAPE = 1


def first_seen(name: str) -> dict:
	"""{"slots": {file: {set: {key: sequence}}}, "extras": {option: sequence}, "files": {file: sequence}}."""
	state = _read(name)
	rows = frappe.get_all(
		versions.VERSION,
		filters={"prototype": name, "sequence": [">", state["upto"]]},
		fields=["sequence", "manifest", "changes"],
		order_by="sequence asc",
	)
	if rows:
		for row in rows:
			filed = {r.get("path") for r in versions._parse(row.changes) if r.get("action") != versions.DELETED}
			_read_version(name, state, row.sequence, versions._parse_manifest(row.manifest), filed)
		_write(name, state)

	return {"slots": state["slots"], "extras": state["extras"], "files": state["files"]}


def _read_version(name: str, state: dict, sequence: int, manifest: dict, filed: set) -> None:
	"""Fold one version into `state`. A version stored before manifests existed only moves `upto`.

	Only the files the version filed count: its manifest is the whole tree on disk, which holds what a
	teammate's agent wrote and has not committed yet.
	"""
	state["upto"] = max(state["upto"], int(sequence))
	if not manifest:
		return

	now = {path: sha for path, sha in manifest.items() if path.endswith(".vue")}
	was = state["manifest"]
	gone = {sha: path for path, sha in was.items() if path not in now and _is_variant(path)}
	for path, sha in now.items():
		if path not in filed:
			continue

		state["files"].setdefault(path, sequence)
		if _is_variant(path):
			option = path[len(sharing.VARIANTS_ROOT) + 1 : -len(".vue")]
			moved = gone.get(sha)
			origin = state["extras"].get(moved[len(sharing.VARIANTS_ROOT) + 1 : -len(".vue")]) if moved else None
			state["extras"].setdefault(option, origin or sequence)
			continue

		try:
			source = snapshots.read_blob(name, sha).decode("utf-8", errors="replace")
		except frappe.ValidationError:
			continue

		if "<Variants" not in source:
			continue

		for entry in variant_default.find_sets(source, None):
			known = state["slots"].setdefault(path, {}).setdefault(entry["label"], {})
			for slot in entry["slots"]:
				if slot["key"] != "default":
					known.setdefault(slot["key"], sequence)

	state["manifest"] = {**{p: sha for p, sha in was.items() if p in now}, **{p: now[p] for p in filed if p in now}}


def _is_variant(path: str) -> bool:
	return sharing.is_editor_path(path) or path.startswith(sharing.ADOPTED_DIR)


def _path(name: str) -> str:
	return os.path.join(snapshots.store_dir(name), FILE)


def _read(name: str) -> dict:
	try:
		with open(_path(name), encoding="utf-8") as handle:
			state = json.load(handle)
		if isinstance(state, dict) and state.get("shape") == SHAPE:
			return state
	except (OSError, ValueError):
		pass

	return {"shape": SHAPE, "upto": 0, "manifest": {}, "slots": {}, "extras": {}, "files": {}}


def _write(name: str, state: dict) -> None:
	snapshots._write_atomic(_path(name), json.dumps(state, sort_keys=True).encode("utf-8"))
