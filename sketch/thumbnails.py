# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""The card image of a Prototype: one PNG per theme, on disk.

Why an image and not the Viewer. A card used to draw a live iframe, and every
frame booted a whole Runtime: about 4.5 MB of assets for the first one, then a
Vue app, a Tailwind compile and an SFC compile for each one after it. Twelve
cards meant twelve of those. An image is one request and one decode, so the
gallery and the feed can now draw the same card.

What it costs instead. The picture is as old as the last capture, not as old as
the last file write. `state()` names that gap and `request_refresh()` closes it
in the background, so a card is never blocked on a browser.

Where they live. `private/files/sketch-thumbs/<name>/`, beside the source tree
and never inside it: a file under `private/files/sketch/<name>/` would show up
in `list_files`, move `prototype_files.revision()`, and count as a file in the
line under the card's title.

Nothing here is reachable over HTTP. `sketch/thumbnail.py` is the one door, and
it runs the same access ladder the Viewer runs.
"""

import base64
import json
import os
import shutil
import time

import frappe

from sketch import prototype_files

#: `private/files/sketch-thumbs`, under the site path.
ROOT = ("private", "files", "sketch-thumbs")

#: The themes a card can ask for. The Viewer resolves to one of these two and
#: never to "system" (spec 12), so these are the only pictures worth taking.
THEMES = ("light", "dark")

#: The sidecar that says which tree the pictures are of.
META = "meta.json"


def thumb_dir(name: str) -> str:
	"""Absolute path to sites/<site>/private/files/sketch-thumbs/<name>.

	Does not create the directory. The guard is `prototype_files`', because a
	name that cannot address a tree must not address its pictures either.
	"""
	if not name or "/" in name or "\\" in name or name in (".", ".."):
		frappe.throw(frappe._("Invalid prototype id"), frappe.ValidationError)

	return os.path.abspath(frappe.get_site_path(*ROOT, name))


def png_path(name: str, theme: str) -> str:
	"""Absolute path to one theme's PNG. Raises on a theme that is not ours."""
	if theme not in THEMES:
		frappe.throw(frappe._("Unknown theme {0}").format(theme), frappe.ValidationError)

	return os.path.join(thumb_dir(name), f"{theme}.png")


def read(name: str, theme: str) -> bytes | None:
	"""The PNG bytes, or None when this Prototype has no picture in this theme.

	Falls back to nothing. A caller that wants light-for-missing-dark asks for
	light itself, so this function never answers with a different theme than
	the one it was asked for.
	"""
	try:
		with open(png_path(name, theme), "rb") as handle:
			return handle.read()
	except OSError:
		return None


def meta(name: str) -> dict:
	"""The sidecar: `rev`, `stamp`, and the themes on disk. `{}` when there is none."""
	try:
		with open(os.path.join(thumb_dir(name), META), encoding="utf-8") as handle:
			loaded = json.load(handle)
	except (OSError, ValueError):
		return {}

	return loaded if isinstance(loaded, dict) else {}


def state(name: str, rev: str | None = None) -> str:
	""""missing", "stale" or "fresh", for the tree as it is right now.

	`rev` is `prototype_files.revision()`. The caller usually has it already;
	when it does not, this reads it, which is one stat walk.

	"stale" and "missing" both mean "capture this", and they are two words
	rather than one because the card draws them differently: a stale card shows
	the old picture, a missing one shows a placeholder.
	"""
	stored = meta(name)
	if not stored.get("themes"):
		return "missing"

	current = prototype_files.revision(name) if rev is None else rev
	return "fresh" if stored.get("rev") == current else "stale"


def store(name: str, shots: list[dict], rev: str) -> list[str]:
	"""Write the PNGs checkd took, and the sidecar that dates them.

	`shots` is checkd's `thumbnails` list: `theme` and `png_base64` per entry.
	An entry checkd could not take is simply absent, so a dark capture that
	failed leaves the last dark picture in place rather than deleting it.

	`rev` is the tree stamp the pictures were taken at. It is passed in, not
	read here: the caller reads it *before* the capture, so a file written
	while the browser was open leaves the sidecar stale and the next card view
	asks for another capture. Reading it after would record a tree the picture
	does not show.

	The sidecar also carries `stamp`, which is new on every call. That is what
	the URL is keyed on, and it cannot be `rev`: a capture leaves the tree
	untouched, so two captures of one tree share a `rev`, and the second one
	would land at a URL the browser already holds under a year-long cache. The
	Refresh preview action is exactly that case.

	Returns the themes written.
	"""
	written = []
	folder = thumb_dir(name)
	os.makedirs(folder, exist_ok=True)

	for shot in shots:
		theme = shot.get("theme")
		data = shot.get("png_base64")
		if theme not in THEMES or not data:
			continue

		try:
			raw = base64.b64decode(data)
		except (ValueError, TypeError):
			continue

		# Written whole, then moved into place. A card reading the file while
		# the job writes it would otherwise decode half a PNG.
		final = png_path(name, theme)
		partial = f"{final}.part"
		with open(partial, "wb") as handle:
			handle.write(raw)
		os.replace(partial, final)
		written.append(theme)

	if not written:
		return []

	# The themes on disk, not the themes this call wrote: a run that captured
	# light only must not drop a dark picture an earlier run took.
	on_disk = sorted({*meta(name).get("themes", []), *written})
	with open(os.path.join(folder, META), "w", encoding="utf-8") as handle:
		json.dump({"rev": rev, "stamp": str(time.time_ns()), "themes": on_disk}, handle)

	return written


def stamp(name: str) -> str:
	"""The cache key of this Prototype's pictures. "" when there are none.

	Falls back to `rev` for a sidecar written before `stamp` existed, so an
	early capture keeps a URL that a browser can cache rather than losing one.
	"""
	stored = meta(name)
	return stored.get("stamp") or stored.get("rev") or ""


def capture(name: str) -> list[str]:
	"""Take this Prototype's pictures now. The body of the background job.

	Runs as the owner. The Viewer answers a signed URL for a private Prototype
	(`sketch/checkd.py`), so the browser needs no session, but reading the doc
	does.

	A Prototype whose tree does not compile is left with the pictures it has.
	checkd returns no thumbnails for a tree that never mounted, and an empty
	`shots` list writes nothing, so a broken tree keeps the last good card
	instead of blanking it.
	"""
	from sketch import checkd

	if not frappe.db.exists("Sketch Prototype", name):
		return []

	doc = frappe.get_doc("Sketch Prototype", name)
	# Read before the capture, never after. See `store`.
	rev = prototype_files.revision(name)
	if not rev:
		return []

	report = checkd.run(doc, screenshot=False, thumbnails=True)
	return store(name, report.get("thumbnails") or [], rev)


def request_refresh(name: str) -> None:
	"""Ask for a capture in the background, at most one per Prototype at a time.

	The gallery polls, so this is called on every poll of every stale card. The
	`job_id` plus `deduplicate` is what keeps that from queueing a browser run
	every few seconds: a second request while the first is queued or running is
	dropped.

	It never raises. A site with no worker, or a checkd that is down, must not
	turn a gallery read into an error: the card falls back to the picture it
	has, or to its placeholder.
	"""
	try:
		frappe.enqueue(
			"sketch.thumbnails.capture",
			queue="long",
			name=name,
			job_id=f"sketch-thumbnail-{name}",
			deduplicate=True,
			enqueue_after_commit=True,
		)
	except Exception:
		frappe.logger("sketch").debug(f"thumbnail refresh not queued for {name}", exc_info=True)


def forget(name: str) -> None:
	"""Delete the pictures of a Prototype. Called from `on_trash`."""
	shutil.rmtree(thumb_dir(name), ignore_errors=True)
