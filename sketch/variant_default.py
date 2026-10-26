# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Make one slot of a `<Variants name="…">` set the default, by moving it first.

The first slot of a Variants set is the default (runtime/variants/Variants.vue).
The owner picks a new default in the Viewer, and this module rewrites the
source so the agent never has to be asked.

`move_slot` is pure text in, text out. It walks the template's tags with a
small tokenizer that skips quoted attribute values, comments and CDATA, so a
`>` inside `:class="a > b"` or a nested `<template v-if>` inside a slot cannot
end a slot early. Everything outside the moved slot stays byte for byte: the
slot is swapped with the text from the first slot up to it, so the whitespace
that separated slots keeps its place.
"""

import re

import frappe

from sketch import prototype_files, snapshots, versions

#: HTML elements with no closing tag, so they never open a depth.
VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())

TAG_NAME = re.compile(r"[A-Za-z][\w:.-]*")
SLOT_ATTR = re.compile(r"""(?:^|\s)(?:#|v-slot:)([^\s=/>"']+)""")
NAME_ATTR = re.compile(r"""(?:^|\s)name\s*=\s*(?:"([^"]*)"|'([^']*)')""")


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


def find_sets(source: str, name: str) -> list[dict]:
	"""Each `<Variants name="{name}">` in the template, with its direct slots.

	A slot is {"key", "start", "end"}: `<template #key>` through its own
	`</template>`.
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

				entry = {"label": label, "slots": []}
				stack.append((lower, entry, None))
				if label == name:
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


def move_slot(source: str, name: str, option: str) -> str:
	"""`source` with the `option` slot of the set `name` moved to the front.

	Raises frappe.ValidationError, with a message the owner can read, when the
	set is missing or repeated, the option is not in it, or it is already first.
	"""
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

	slots = [s for s in sets[0]["slots"] if s["key"] != "default" and s["end"] is not None]
	matches = [s for s in slots if s["key"] == option]
	if not matches:
		frappe.throw(frappe._('"{0}" has no option "{1}".').format(name, option), frappe.ValidationError)

	if len(matches) > 1:
		frappe.throw(
			frappe._('"{0}" lists the option "{1}" more than once.').format(name, option),
			frappe.ValidationError,
		)

	target = matches[0]
	first = slots[0]
	if target is first:
		frappe.throw(
			frappe._('"{0}" is already the default for {1}.').format(label_of(option), name),
			frappe.ValidationError,
		)

	# [first … previous slot] [gap] [target]  ->  [target] [gap] [first … previous slot]
	previous = max((s for s in slots if s["end"] <= target["start"]), key=lambda s: s["end"])
	gap = source[previous["end"] : target["start"]]
	return (
		source[: first["start"]]
		+ source[target["start"] : target["end"]]
		+ gap
		+ source[first["start"] : previous["end"]]
		+ source[target["end"] :]
	)


def label_of(option: str) -> str:
	"""The option's name as the pill prints it: `budgetBars` and `budget-bars` read "Budget bars"."""
	text = re.sub(r"([a-z])([A-Z])", r"\1 \2", option)
	text = re.sub(r"[-_]+", " ", text).lower()
	return text[:1].upper() + text[1:]


def set_default(doc, file: str, name: str, option: str) -> dict:
	"""Rewrite `file` of the Prototype and save a version. The caller has checked ownership."""
	if not isinstance(file, str) or not file.endswith(".vue"):
		frappe.throw(frappe._("The file must be a .vue page or component."), frappe.ValidationError)

	absolute = prototype_files.safe_join(doc.name, file)
	versions.lock(doc.name)
	try:
		with open(absolute, encoding="utf-8", newline="") as handle:
			source = handle.read()
	except FileNotFoundError:
		frappe.throw(frappe._("No such file: {0}").format(file), frappe.ValidationError)

	changed = move_slot(source, name, option)

	# What the agent wrote and has not committed goes in its own version
	# first, so the next version holds the reorder and nothing else.
	if versions.pending(doc.name):
		versions.commit(doc, "Changes before the default was changed", source="App")

	prototype_files.write_files(doc.name, [{"path": file, "content": changed}])
	versions.note(doc.name, file, versions.MODIFIED)
	version = versions.commit(doc, f"Made \u201c{label_of(option)}\u201d the default for {name}", source="App")
	return {"file": file, "name": name, "option": option, "sequence": version.sequence if version else None}


def undo_default(doc, file: str, sequence, name: str, option: str) -> dict:
	"""Put `file` back exactly as it was before version `sequence` made `option` the default.

	Only that one file is restored, from the version before. It is refused when
	the file is not as that version left it, so a later write is never
	clobbered. The caller has checked ownership.
	"""
	if not isinstance(file, str) or not file.endswith(".vue"):
		frappe.throw(frappe._("The file must be a .vue page or component."), frappe.ValidationError)

	try:
		sequence = int(sequence)
	except (TypeError, ValueError):
		frappe.throw(frappe._("sequence must be a version number"), frappe.ValidationError)

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
