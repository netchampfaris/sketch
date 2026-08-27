# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Trap 1: the Viewer serialiser must escape `<` as `\\u003c`.

Every Vue SFC with a script block ends with `</script>`. Inside an inline
`<script type="application/json">` block a browser ends the block at the first
`</script`, wherever it sits, so an unescaped one truncates the JSON and the
page dies on the most ordinary file a Prototype can hold. `frappe.as_json` does
not escape it.

The HTTP test reads the slot the way a browser reads it: up to the first
`</script`. That is the only reading that catches the bug.
"""

import json

from frappe.tests import IntegrationTestCase

from sketch import viewer
from sketch.tests import utils

#: A file that holds every character the serialiser has to defend against.
APP_VUE = """<script setup lang="ts">
const closing = '</script>'
const upper = '</SCRIPT >'
const cdata = ']]>'
const comment = '<!-- <script> -->'
const amp = '&amp; & <b>bold</b>'
const backref = '$& $1 \\\\ ${x}'
</script>

<template>
  <div>{{ closing }} &lt; &gt; &amp;</div>
</template>
"""

NOTES_MD = "# Notes\n\n`</script>` and `<script>` and & and < and >.\n"


class TestViewerEscaping(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("escape", "d2tescape")
		cls.addClassCleanup(utils.drop_user, cls.user)
		cls.doc = utils.make_prototype(
			cls.user,
			"d2t-escape",
			files={"src/App.vue": APP_VUE, "src/notes.md": NOTES_MD},
		)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)

	# ------------------------------------------------------- the serialiser

	def test_to_json_escapes_the_three_characters(self):
		text = viewer.to_json({"files": {"src/App.vue": APP_VUE}})
		self.assertNotIn("<", text)
		self.assertNotIn(">", text)
		self.assertNotIn("&", text)
		self.assertIn("\\u003c", text)
		self.assertIn("\\u003e", text)
		self.assertIn("\\u0026", text)

	def test_to_json_round_trips(self):
		"""Escaping must not change the value a browser parses back out."""
		payload = {"files": {"src/App.vue": APP_VUE, "src/notes.md": NOTES_MD}}
		self.assertEqual(json.loads(viewer.to_json(payload)), payload)

	def test_to_json_holds_no_closing_tag(self):
		self.assertNotIn("</script", viewer.to_json({"files": {"a": "</script>"}}))

	# ------------------------------------------------------------ the server

	def test_the_served_page_carries_the_tree_intact(self):
		utils.require_webserver()
		response = utils.request("GET", self.viewer_path())
		self.assertEqual(response.status_code, 200, response.text[:500])

		html = response.text
		self.assertIn("</script", html, "the served document has no closing script tag")
		self.assertIn("\\u003c", html, "the data slot was not escaped")

		payload = utils.data_slot(html)
		self.assertEqual(payload["files"]["src/App.vue"], APP_VUE)
		self.assertEqual(payload["files"]["src/notes.md"], NOTES_MD)
		self.assertEqual(payload["name"], self.doc.name)
		self.assertEqual(payload["slug"], self.doc.slug)
		self.assertEqual(payload["pin"], self.doc.pin)
		self.assertEqual(payload["theme"], "light")
		self.assertFalse(payload["is_public"])
		self.assertFalse(payload["is_owner"])

	def test_the_raw_closing_tag_never_reaches_the_slot(self):
		"""The direct read of the trap: the file's `</script>` must be escaped."""
		utils.require_webserver()
		html = utils.request("GET", self.viewer_path()).text
		opening = '<script id="sketch-data" type="application/json">'
		start = html.find(opening) + len(opening)
		block = html[start : html.find("</script", start)]
		self.assertIn("\\u003c/script\\u003e", block)

	def test_the_slot_is_substituted_once(self):
		utils.require_webserver()
		html = utils.request("GET", self.viewer_path()).text
		self.assertNotIn(viewer.SLOT, html, "the data slot literal survived the substitution")

	def test_the_viewer_headers(self):
		"""Spec 6.4. Frappe sets neither header on its own.

		Frappe appends `no-cache,must-revalidate,max-age=0` to the value the
		renderer sets, so the test reads the directive, not the whole string.
		"""
		utils.require_webserver()
		response = utils.request("GET", self.viewer_path())
		directives = [
			part.strip() for part in (response.headers.get("Cache-Control") or "").split(",")
		]
		self.assertIn("no-store", directives)
		self.assertEqual(response.headers.get("Content-Security-Policy"), "frame-ancestors 'self'")
		self.assertIn("text/html", response.headers.get("Content-Type", ""))

	def viewer_path(self) -> str:
		url = utils.signed_viewer_url(self.doc)
		return url[len(utils.base_url()) :]
