# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Make one slot of a `<Variants name="…">` set the default, by recording it on the tag.

A set's default is the slot its `default="…"` prop names, else its first slot
(runtime/variants/Variants.vue). The owner picks a new default in the Viewer,
and this module writes that prop, so the agent never has to be asked and no
option ever changes its place. Options show in the order they first appeared
(sketch/variant_order.py), never in the order of the source.

`record_slot` is pure text in, text out. It walks the template's tags with a
small tokenizer that skips quoted attribute values, comments and CDATA, so a
`>` inside `:class="a > b"` or a nested `<template v-if>` inside a slot cannot
end a slot early. Only the set's opening tag changes; the rest of the file stays
byte for byte.
"""

import json
import re

import frappe

from sketch import editor_variants, prototype_files, sharing, snapshots, versions

#: HTML elements with no closing tag, so they never open a depth.
VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())

TAG_NAME = re.compile(r"[A-Za-z][\w:.-]*")
SLOT_ATTR = re.compile(r"""(?:^|\s)(?:#|v-slot:)([^\s=/>"']+)""")
NAME_ATTR = re.compile(r"""(?:^|\s)name\s*=\s*(?:"([^"]*)"|'([^']*)')""")
DEFAULT_ATTR = re.compile(r"""(\s+)default\s*=\s*(?:"([^"]*)"|'([^']*)')""")


class Tag:
	__slots__ = ("start", "end", "name", "closing", "self_closing", "attrs")

	def __init__(self, start, end, name, closing, self_closing, attrs):
		self.start = start
		self.end = end
		self.name = name
		self.closing = closing
		self.self_closing = self_closing
		self.attrs = attrs


def tags(source: str):
	"""Every element tag in `source`, in order. Comments are skipped."""
	i = 0
	n = len(source)
	while i < n:
		i = source.find("<", i)
		if i < 0:
			return

		if source.startswith("<!--", i):
			stop = source.find("-->", i + 4)
			i = n if stop < 0 else stop + 3
			continue

		if source.startswith("<![CDATA[", i):
			stop = source.find("]]>", i + 9)
			i = n if stop < 0 else stop + 3
			continue

		closing = source.startswith("</", i)
		match = TAG_NAME.match(source, i + (2 if closing else 1))
		if not match:
			i += 1
			continue

		# Scan to the `>` that ends the tag, not one inside a quoted value.
		j = match.end()
		quote = ""
		while j < n:
			c = source[j]
			if quote:
				if c == quote:
					quote = ""
			elif c in "\"'":
				quote = c
			elif c == ">":
				break
			j += 1
		else:
			return

		inner = source[match.end() : j]
		self_closing = not closing and inner.rstrip().endswith("/")
		yield Tag(i, j + 1, match.group(0), closing, self_closing, inner)
		i = j + 1


def top_template(source: str) -> tuple[int, int]:
	"""The span inside the SFC's top-level `<template>`, or the whole text."""
	depth = 0
	start = None
	for tag in tags(source):
		if tag.name.lower() in VOID or tag.self_closing:
			continue

		if tag.closing:
			depth -= 1
			if depth == 0 and tag.name == "template" and start is not None:
				return start, tag.start
		else:
			if depth == 0 and tag.name == "template" and start is None:
				start = tag.end
			depth += 1

	return 0, len(source)


def find_sets(source: str, name: str | None) -> list[dict]:
	"""Each `<Variants name="{name}">` in the template, with its direct slots. Every set when `name` is None.

	A slot is {"key", "start", "end"}: `<template #key>` through its own
	`</template>`. `tag` is the opening `<Variants …>` tag's span.
	"""
	lo, hi = top_template(source)
	found = []
	stack = []  # open elements: (lower-case name, set, slot or None)
	for tag in tags(source[lo:hi]):
		tag.start += lo
		tag.end += lo
		lower = tag.name.lower()
		if lower in VOID:
			continue

		if not tag.closing:
			if tag.self_closing:
				continue

			if lower == "variants":
				attr = NAME_ATTR.search(tag.attrs)
				label = None
				if attr:
					label = attr.group(1) if attr.group(1) is not None else attr.group(2)

				entry = {"label": label, "slots": [], "tag": (tag.start, tag.end)}
				stack.append((lower, entry, None))
				if label == name or (name is None and label is not None):
					found.append(entry)
				continue

			slot = None
			parent = stack[-1] if stack else None
			if lower == "template" and parent and parent[0] == "variants":
				attr = SLOT_ATTR.search(tag.attrs)
				if attr and not attr.group(1).startswith("["):
					slot = {"key": attr.group(1), "start": tag.start, "end": None}
					parent[1]["slots"].append(slot)

			stack.append((lower, None, slot))
			continue

		# A closing tag pops back to its opener, so a stray unclosed tag
		# cannot swallow the rest of the file.
		for k in range(len(stack) - 1, -1, -1):
			if stack[k][0] == lower:
				if stack[k][2]:
					stack[k][2]["end"] = tag.end
				del stack[k:]
				break

	return found


def only_set(source: str, name: str) -> tuple[dict, list[dict]]:
	"""The one set `name` in `source` and its slots. Raises, with a message the owner can read, when it is missing or repeated."""
	sets = find_sets(source, name)
	if not sets:
		frappe.throw(
			frappe._('There is no <Variants name="{0}"> in this file.').format(name),
			frappe.ValidationError,
		)

	if len(sets) > 1:
		frappe.throw(
			frappe._('<Variants name="{0}"> appears {1} times in this file. Names must be unique.').format(
				name, len(sets)
			),
			frappe.ValidationError,
		)

	return sets[0], [s for s in sets[0]["slots"] if s["key"] != "default" and s["end"] is not None]


def recorded_default(source: str, entry: dict) -> str | None:
	"""The value of the set's `default="…"` prop, or None when it has none."""
	start, end = entry["tag"]
	attr = DEFAULT_ATTR.search(source, start, end)
	if not attr:
		return None

	return attr.group(2) if attr.group(2) is not None else attr.group(3)


def with_default(source: str, entry: dict, option: str | None) -> str:
	"""`source` with the set's `default` prop naming `option`, or with no `default` prop when `option` is None.

	Only the opening tag changes. A new prop goes right after `name="…"`.
	"""
	start, end = entry["tag"]
	attr = DEFAULT_ATTR.search(source, start, end)
	if attr:
		replacement = "" if option is None else f'{attr.group(1)}default="{option}"'
		return source[: attr.start()] + replacement + source[attr.end() :]

	if option is None:
		return source

	name = NAME_ATTR.search(source, start, end)
	at = name.end() if name else start + len("<Variants")
	return source[:at] + f' default="{option}"' + source[at:]


def record_slot(source: str, name: str, option: str, leading: bool = False) -> str:
	"""`source` with the `option` slot recorded as the default of the set `name`. No slot moves.

	Raises frappe.ValidationError when the set is missing or repeated, the option
	is not in it, or it is already the default. With `leading` (a teammate's option
	leads the set now) the owner's option is never already the default.
	"""
	entry, slots = only_set(source, name)
	count = [s["key"] for s in slots].count(option)
	if not count:
		frappe.throw(frappe._('"{0}" has no option "{1}".').format(name, option), frappe.ValidationError)

	if count > 1:
		frappe.throw(
			frappe._('"{0}" lists the option "{1}" more than once.').format(name, option),
			frappe.ValidationError,
		)

	current = recorded_default(source, entry)
	if current not in [s["key"] for s in slots]:
		current = slots[0]["key"]
	if current == option and not leading:
		frappe.throw(
			frappe._('"{0}" is already the default for {1}.').format(label_of(option), name),
			frappe.ValidationError,
		)

	return with_default(source, entry, option)


def label_of(option: str) -> str:
	"""The option's name as the pill prints it: `budgetBars` and `budget-bars` read "Budget bars"."""
	text = re.sub(r"([a-z])([A-Z])", r"\1 \2", option)
	text = re.sub(r"[-_]+", " ", text).lower()
	return text[:1].upper() + text[1:]


def set_default(doc, file: str, name: str, option: str) -> dict:
	"""Rewrite `file` of the Prototype and save a version. The caller has checked ownership."""
	if not isinstance(file, str) or not file.endswith(".vue"):
		frappe.throw(frappe._("The file must be a .vue page or component."), frappe.ValidationError)

	if editor_variants.is_extra(option):
		# An invited editor's option: Sketch copies it into the owner's files. One adopted before leads again.
		if option.startswith("adopted/"):
			return editor_variants.lead_adopted(doc, file, name, option)
		return editor_variants.adopt(doc, file, name, option)

	absolute = prototype_files.safe_join(doc.name, file)
	versions.lock(doc.name)
	try:
		with open(absolute, encoding="utf-8", newline="") as handle:
			source = handle.read()
	except FileNotFoundError:
		frappe.throw(frappe._("No such file: {0}").format(file), frappe.ValidationError)

	# An editor's option the owner made the default leads this set until one of
	# the owner's own options takes the lead back. The `default` prop on the tag
	# says which of the owner's own options that is.
	leading = editor_variants.leaders(doc.name, file, name)
	if leading and not find_sets(source, name):
		if option != "original":
			frappe.throw(frappe._('"{0}" has no option "{1}".').format(name, option), frappe.ValidationError)
		changed = source
	else:
		changed = record_slot(source, name, option, leading=bool(leading))

	# What the agent wrote and has not committed goes in its own version
	# first, so the next version holds the new default and nothing else.
	if versions.pending(doc.name):
		versions.commit(doc, "Changes before the default was changed", source="App")

	if changed != source:
		prototype_files.write_files(doc.name, [{"path": file, "content": changed}])
		versions.note(doc.name, file, versions.MODIFIED)

	if leading:
		editor_variants.clear_defaults(doc.name, file, name)
		versions.note(doc.name, "src/variants/adopted.json", versions.MODIFIED)

	version = versions.commit(doc, f"Made \u201c{label_of(option)}\u201d the default for {name}", source="App")
	return {"file": file, "name": name, "option": option, "sequence": version.sequence if version else None}


def undo_default(doc, file: str, sequence, name: str, option: str) -> dict:
	"""Put `file` back exactly as it was before version `sequence` made `option` the default.

	Only that one file is restored, from the version before. It is refused when
	the file is not as that version left it, so a later write is never
	clobbered. The caller has checked ownership.

	A default that touched the variants folder (an editor's option made the
	default, or the owner's option taking the lead back) restores every file it
	changed, under the same refusal (`editor_variants.restore_files`).
	"""
	if not isinstance(file, str) or not file.endswith(".vue"):
		frappe.throw(frappe._("The file must be a .vue page or component."), frappe.ValidationError)

	try:
		sequence = int(sequence)
	except (TypeError, ValueError):
		frappe.throw(frappe._("sequence must be a version number"), frappe.ValidationError)

	touched = versions._parse(
		frappe.db.get_value(versions.VERSION, {"prototype": doc.name, "sequence": sequence}, "changes")
	)
	if any(str(row.get("path", "")).startswith("src/variants/") for row in touched):
		prompt = frappe.db.get_value(versions.VERSION, {"prototype": doc.name, "sequence": sequence}, "prompt")
		if not (prompt or "").startswith("Made \u201c"):
			frappe.throw(frappe._("That version did not change a default."), frappe.ValidationError)

		# The version's own words name the option the way the owner saw it, "KPI strip" and not "@arohi/kpi-strip".
		said = re.match(r"Made [\u201c\"](.*)[\u201d\"] the default for ", prompt)
		result = editor_variants.restore_files(
			doc, sequence, f"Undid making \u201c{said.group(1) if said else label_of(option)}\u201d the default for {name}"
		)
		return {"file": file, "name": name, "option": option, **result}

	absolute = prototype_files.safe_join(doc.name, file)
	versions.lock(doc.name)
	changed_since = frappe._("the page changed since. Ask your agent instead.")
	prompt = frappe.db.get_value(versions.VERSION, {"prototype": doc.name, "sequence": sequence}, "prompt")
	# Straight quotes are what versions before the curly ones were saved with.
	if sequence < 2 or not (prompt or "").startswith(("Made \u201c", 'Made "')):
		frappe.throw(frappe._("That version did not change a default."), frappe.ValidationError)

	after = versions._manifest_of(doc.name, sequence)
	before = versions._manifest_of(doc.name, sequence - 1)
	if file not in before or file not in after:
		frappe.throw(changed_since, frappe.ValidationError)

	try:
		with open(absolute, "rb") as handle:
			current = handle.read()
	except FileNotFoundError:
		frappe.throw(changed_since, frappe.ValidationError)

	if snapshots._sha(current) != after[file]:
		frappe.throw(changed_since, frappe.ValidationError)

	original = snapshots.read_blob(doc.name, before[file]).decode("utf-8")
	if versions.pending(doc.name):
		versions.commit(doc, "Changes before the default was undone", source="App")

	prototype_files.write_files(doc.name, [{"path": file, "content": original}])
	versions.note(doc.name, file, versions.MODIFIED)
	version = versions.commit(doc, f"Undid making \u201c{label_of(option)}\u201d the default for {name}", source="App")
	return {"file": file, "name": name, "option": option, "sequence": version.sequence if version else None}


# ---------------------------------------------------------------- keep only this


def drop_slots(source: str, slots: list[dict]) -> str:
	"""`source` without these slots, and without the line break and indent that led each one."""
	for slot in sorted(slots, key=lambda s: s["start"], reverse=True):
		start = slot["start"]
		while start > 0 and source[start - 1] in " \t":
			start -= 1

		if start > 0 and source[start - 1] == "\n":
			start -= 1
			if start > 0 and source[start - 1] == "\r":
				start -= 1

		source = source[:start] + source[slot["end"] :]

	return source


def keep_only(doc, file: str, name: str, option: str) -> dict:
	"""Keep `option` as the only option of the set `name` in `file`. The caller has checked ownership.

	The set's other slots are cut from the source. Every variant an invited editor
	added to the set, and every one the owner adopted from them, is deleted with its
	registry row. One version records all of it, so `undo_keep` can put it back.

	`option` may be an invited editor's variant or an adopted one: an editor's is
	adopted first (moved into the owner's files, in the same version), then kept, and
	every slot of the owner's goes. The `<Variants>` wrapper stays, with the kept
	option as its only one, so an editor can add to it again.

	A wrapped component's only own option is `original`; its extras are all that goes.
	Keeping an extra of a wrapped component replaces `original`: the extra's source is
	written into the component's own file, its `<variant>` tag dropped, and every variant
	file of the component goes with its registry row. No set is left. `removed` counts the
	component's own version among the options that went.

	Returns `removed`, how many options went.
	"""
	if not isinstance(file, str) or not file.endswith(".vue"):
		frappe.throw(frappe._("The file must be a .vue page or component."), frappe.ValidationError)

	absolute = prototype_files.safe_join(doc.name, file)
	versions.lock(doc.name)
	try:
		with open(absolute, encoding="utf-8", newline="") as handle:
			source = handle.read()
	except FileNotFoundError:
		frappe.throw(frappe._("No such file: {0}").format(file), frappe.ValidationError)

	extra = editor_variants.is_extra(option)
	sets = find_sets(source, name)
	label = label_of(option)
	changed = source
	dropped = 0
	if sets:
		if len(sets) > 1:
			frappe.throw(
				frappe._('<Variants name="{0}"> appears {1} times in this file. Names must be unique.').format(
					name, len(sets)
				),
				frappe.ValidationError,
			)

		slots = [s for s in sets[0]["slots"] if s["key"] != "default" and s["end"] is not None]
		if extra:
			# The owner's own slots all go: the kept option is an extra.
			gone = slots
		else:
			if [s["key"] for s in slots].count(option) != 1:
				frappe.throw(frappe._('"{0}" has no option "{1}".').format(name, option), frappe.ValidationError)

			gone = [s for s in slots if s["key"] != option]

		changed = drop_slots(source, gone)
		# One option is left, or none of the owner's: a recorded default has nothing to name.
		changed = with_default(changed, find_sets(changed, name)[0], None)
		dropped = len(gone)
	elif not extra and option != "original":
		frappe.throw(frappe._('"{0}" has no option "{1}".').format(name, option), frappe.ValidationError)

	extras = editor_variants.targeting(doc.name, file, name)
	found = None
	kept_path = None
	# A person's option of a component with no `<Variants>` of its own replaces the component: it moves into the
	# component's file and no set is left around it.
	replaced = None
	if extra:
		kept_path = editor_variants.path_of(option)
		if kept_path not in extras:
			frappe.throw(frappe._('"{0}" has no option "{1}".').format(name, option), frappe.ValidationError)

		if not sets:
			replaced = editor_variants.replacement(doc, file, name, option)
			label = replaced["label"]
			changed = replaced["source"]
		elif sharing.is_editor_path(kept_path):
			found = editor_variants.adoptable(doc, file, name, option)
			label = found["meta"]["name"]
		else:
			label = _name_of(doc.name, kept_path, option)

	others = [path for path in extras if path != kept_path]
	leads = bool(extra and found is None and not replaced and not editor_variants.read_registry(doc.name).get(kept_path, {}).get("default"))
	if changed == source and not others and not found and not leads and not replaced:
		frappe.throw(frappe._("{0} is already the only option.").format(label), frappe.ValidationError)

	if versions.pending(doc.name):
		versions.commit(doc, "Changes before the other options were removed", source="App")

	if changed != source:
		prototype_files.write_files(doc.name, [{"path": file, "content": changed}])
		versions.note(doc.name, file, versions.MODIFIED)

	if found:
		kept_path = editor_variants.move_in(doc, file, name, found)

	registry = editor_variants.read_registry(doc.name)
	before = json.dumps(registry, sort_keys=True)
	# Replacing the component takes the kept variant's file away too: its source now lives in the component.
	for path in [*others, kept_path] if replaced else others:
		prototype_files.delete_file(doc.name, path)
		versions.note(doc.name, path, versions.DELETED)
		registry.pop(path, None)

	if kept_path and kept_path in registry and not replaced:
		registry[kept_path]["default"] = True

	if json.dumps(registry, sort_keys=True) != before:
		editor_variants.write_registry(doc.name, registry)
		versions.note(doc.name, sharing.ADOPTED_FILE, versions.MODIFIED)

	version = versions.commit(doc, f"Kept \u201c{label}\u201d as the only option of {name}", source="App")
	return {
		"file": file,
		"name": name,
		"option": "original" if replaced else editor_variants.option_of(kept_path) if kept_path else option,
		"label": label,
		# The component's own version goes too, when a person's replaced it.
		"removed": dropped + len(others) + (1 if replaced else 0),
		"replaced": bool(replaced),
		"sequence": version.sequence if version else None,
	}


def _name_of(name: str, path: str, option: str) -> str:
	"""The `<variant name>` of an adopted file, or the end of its option value."""
	try:
		meta = sharing.variant_meta(prototype_files.read_files(name, [path])[0]["content"])
	except frappe.ValidationError:
		meta = None

	return (meta or {}).get("name") or option.rsplit("/", 1)[-1]


def undo_keep(doc, file: str, sequence, name: str, option: str) -> dict:
	"""Bring back everything version `sequence` removed. Refused when any of it changed since."""
	try:
		sequence = int(sequence)
	except (TypeError, ValueError):
		frappe.throw(frappe._("sequence must be a version number"), frappe.ValidationError)

	prompt = frappe.db.get_value(versions.VERSION, {"prototype": doc.name, "sequence": sequence}, "prompt")
	if not (prompt or "").startswith("Kept \u201c"):
		frappe.throw(frappe._("That version did not keep one option."), frappe.ValidationError)

	# The version's own words name the option the way the owner saw it: "KPI strip", not "adopted/kpi-strip".
	said = re.match(r"Kept \u201c(.*)\u201d as the only option of ", prompt)
	label = said.group(1) if said else label_of(option)
	return {
		"file": file,
		"name": name,
		"option": option,
		**editor_variants.restore_files(doc, sequence, f"Undid keeping only \u201c{label}\u201d in {name}"),
	}
