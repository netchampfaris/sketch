# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""/feed: the public Prototypes on this site, and the front door.

Server rendered, like /login and /help, because a Guest has to read it with no
session and no role. The listing itself is `sketch.api.public_prototypes`,
which explains the filter that keeps a private Prototype off this page, and
carries the card picture of each row (`sketch/thumbnails.py`).

`sketch/www/sketch.py` now sends a signed-out visitor here, so this page also
holds the job the marketing page used to hold: one line that says what Sketch
is, and the sign-in action (problem 8.1). The line is the one /login already
prints, word for word, so a visitor reads one sentence about Sketch and not
two versions of it.
"""

import frappe

from sketch.api import public_prototypes

no_cache = 1

#: How many Prototypes one page of the feed prints.
#:
#: A card is one PNG, requested lazily (`sketch/thumbnails.py`), so the page
#: pays one small image per card that scrolls into view. It used to print text
#: rows, because a preview was a live Viewer iframe and a page of those boots a
#: whole Runtime each.
#:
#: The cap is therefore about what a visitor reads, not what the server pays.
#: The order needs the tree stamp of every public Prototype
#: (`sketch.api.public_prototypes`), so the stat walk is the whole set at any
#: page size. Two dozen cards is a page somebody finishes; the rest of the list
#: is a directory, and the page says so instead of ending without a word.
PAGE_SIZE = 24


def get_context(context):
	# `prototypes`, never `items`. The context is a `frappe._dict`, which is a
	# dict, so `context.items` writes the key and then reads back as the bound
	# `dict.items` method, and every use of it here is a TypeError.
	listing = public_prototypes()
	context.title = "Public prototypes"
	context.description = "Prototypes their owners made public on Sketch."
	context.signed_in = frappe.session.user != "Guest"
	context.total = len(listing)
	context.prototypes = listing[:PAGE_SIZE]
	# The template prints the count line off this flag. It is computed here and
	# not as `total > PAGE_SIZE` in the markup, so the page and the list can
	# never disagree about whether anything was left out.
	context.capped = context.total > len(context.prototypes)
	return context
