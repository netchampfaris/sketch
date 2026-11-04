# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Make default records one slot of a `<Variants>` set as its default, on the tag.

No slot moves: the owner's pick is written as `default="…"` and the rest of the
file stays byte for byte. The traps:

- A slot holds nested `<template>` elements and a `>` inside an attribute, so
  the end of a slot is found by tag depth, not by the first `</template>`.
- Indentation and the whitespace between slots keep their place.
- It refuses, with a message the owner can read, a set that is missing or
  repeated, an option that is not there, and an option already first.
- Only the owner may do it, with their session: the Viewer's shell calls the same method.
- The move is one version, with no agent prompt, and the version before it
  restores the old order.
"""

from unittest.mock import patch
from urllib.parse import urlencode

import frappe
from frappe.tests import IntegrationTestCase, set_user
from frappe.utils import set_request
from frappe.website.serve import get_response

from sketch import api, prototype_files, signature, variant_default, versions, viewer_api
from sketch.tests import utils

SLUG = "d2t-vardef-work"

SIMPLE = """<script setup>
import { Variants } from 'sketch:variants'
</script>

<template>
  <Variants name="Spend summary">
    <template #totals>
      <p>Totals</p>
    </template>
    <template #budget-bars>
      <p>Budget bars</p>
    </template>
  </Variants>
</template>
"""

NESTED = """<template>
  <div>
    <Variants name="Spend summary">
      <template #totals>
        <ul>
          <template v-for="row in rows" :key="row.id">
            <li :class="row.n > 1 ? 'a' : 'b'">{{ row.n }}</li>
          </template>
        </ul>
        <!-- </template> inside a comment -->
      </template>
      <template v-slot:timeline>
        <template v-if="open">
          <Chart />
        </template>
        <img src="x.png">
      </template>
      <template #bars>
        <p>Bars</p>
      </template>
    </Variants>
  </div>
</template>
"""


class TestMoveSlot(IntegrationTestCase):
	"""The text rewrite, with no Prototype."""

	def test_nested_templates_do_not_end_a_slot_early(self):
		"""A slot with nested templates, an attribute holding `>` and a comment holding a closing tag ends at its own tag."""
		(found,) = variant_default.find_sets(NESTED, "Spend summary")
		slots = {slot["key"]: NESTED[slot["start"] : slot["end"]] for slot in found["slots"]}
		self.assertEqual(list(slots), ["totals", "timeline", "bars"])
		self.assertTrue(slots["totals"].endswith("<!-- </template> inside a comment -->\n      </template>"))
		self.assertTrue(slots["timeline"].endswith('<img src="x.png">\n      </template>'))

	def test_a_set_that_is_not_there_is_refused(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			variant_default.record_slot(SIMPLE, "Nope", "totals")
		self.assertIn('There is no <Variants name="Nope">', str(caught.exception))

	def test_the_same_name_twice_is_refused(self):
		block = SIMPLE[SIMPLE.index("  <Variants") : SIMPLE.index("</template>\n", SIMPLE.index("</Variants>"))]
		twice = SIMPLE.replace(block, block + block)
		with self.assertRaises(frappe.ValidationError) as caught:
			variant_default.record_slot(twice, "Spend summary", "budget-bars")
		self.assertIn("2 times", str(caught.exception))

	def test_an_option_that_is_not_in_the_set_is_refused(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			variant_default.record_slot(SIMPLE, "Spend summary", "missing")
		self.assertIn('has no option "missing"', str(caught.exception))

	def test_recording_a_default_moves_no_slot(self):
		out = variant_default.record_slot(SIMPLE, "Spend summary", "budget-bars")

		self.assertIn('<Variants name="Spend summary" default="budget-bars">', out)
		self.assertEqual(out.replace(' default="budget-bars"', ""), SIMPLE)

	def test_a_recorded_default_is_replaced_not_repeated(self):
		once = variant_default.record_slot(SIMPLE, "Spend summary", "budget-bars")
		twice = variant_default.record_slot(once, "Spend summary", "totals")

		self.assertEqual(twice.count("default="), 1)
		self.assertIn('default="totals"', twice)
		with self.assertRaises(frappe.ValidationError):
			variant_default.record_slot(twice, "Spend summary", "totals")

	def test_the_first_slot_is_the_default_when_none_is_recorded(self):
		with self.assertRaises(frappe.ValidationError):
			variant_default.record_slot(SIMPLE, "Spend summary", "totals")

	def test_a_leading_teammate_option_lets_the_first_slot_take_it_back(self):
		out = variant_default.record_slot(SIMPLE, "Spend summary", "totals", leading=True)

		self.assertIn('default="totals"', out)

	def test_the_default_prop_can_be_dropped(self):
		once = variant_default.record_slot(SIMPLE, "Spend summary", "budget-bars")
		entry = variant_default.find_sets(once, "Spend summary")[0]

		self.assertEqual(variant_default.with_default(once, entry, None), SIMPLE)


class TestSetVariantDefault(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.owner = utils.make_user("vdown", "d2tvdown")
		cls.other = utils.make_user("vdoth", "d2tvdoth")

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for email in (cls.owner, cls.other):
			utils.drop_user(email)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.doc = utils.make_prototype(self.owner, SLUG, files={"src/App.vue": SIMPLE})
		self.addCleanup(utils.drop_prototype, self.doc.name)
		versions.record_created(self.doc, "Created")
		frappe.db.commit()
		refresh = patch("sketch.thumbnails.request_refresh")
		refresh.start()
		self.addCleanup(refresh.stop)
		frappe.set_user(self.owner)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def source(self) -> str:
		return prototype_files.read_text(self.doc.name, "src/App.vue")["content"]

	def test_the_owner_records_it_and_a_version_is_saved(self):
		out = api.set_variant_default(SLUG, "src/App.vue", "Spend summary", "budget-bars")

		self.assertEqual(self.source(), SIMPLE.replace('name="Spend summary"', 'name="Spend summary" default="budget-bars"'))
		rows = api.list_versions(SLUG)
		self.assertEqual(rows[0]["sequence"], out["sequence"])
		self.assertEqual(rows[0]["source"], "App")
		self.assertEqual(rows[0]["prompt"], "Made \u201cBudget bars\u201d the default for Spend summary")
		self.assertEqual(versions.pending(self.doc.name), [])

	def test_undo_is_one_more_version(self):
		api.set_variant_default(SLUG, "src/App.vue", "Spend summary", "budget-bars")
		api.set_variant_default(SLUG, "src/App.vue", "Spend summary", "totals")

		# Back to the first slot: the default is recorded, and no slot ever moved.
		self.assertEqual(self.source(), SIMPLE.replace('name="Spend summary"', 'name="Spend summary" default="totals"'))
		self.assertEqual(len(api.list_versions(SLUG)), 3)

	def test_a_refusal_writes_nothing_and_saves_no_version(self):
		for name, option in (("Nope", "totals"), ("Spend summary", "missing"), ("Spend summary", "totals")):
			with self.assertRaises(frappe.ValidationError):
				api.set_variant_default(SLUG, "src/App.vue", name, option)

		self.assertEqual(self.source(), SIMPLE)
		self.assertEqual(len(api.list_versions(SLUG)), 1)

	def test_work_the_agent_had_not_committed_is_its_own_version(self):
		prototype_files.write_files(self.doc.name, [{"path": "src/extra.txt", "content": "x\n"}])
		versions.note_write(self.doc.name, ["src/extra.txt"], set())

		api.set_variant_default(SLUG, "src/App.vue", "Spend summary", "budget-bars")

		rows = api.list_versions(SLUG)
		self.assertEqual(len(rows), 3)
		self.assertEqual(rows[0]["files_modified"], 1)
		self.assertEqual(rows[0]["files_added"], 0)

	def test_only_a_vue_file_inside_the_prototype(self):
		for path in ("src/nope.vue", "src/App.ts", "../x.vue"):
			with self.assertRaises(frappe.ValidationError):
				api.set_variant_default(SLUG, path, "Spend summary", "budget-bars")

	def test_a_non_owner_cannot_do_it(self):
		with set_user(self.other):
			with self.assertRaises(frappe.DoesNotExistError):
				api.set_variant_default(SLUG, "src/App.vue", "Spend summary", "budget-bars")

		self.assertEqual(self.source(), SIMPLE)

class TestUndoVariantDefault(IntegrationTestCase):
	"""Undo puts the one file back exactly, and never over a later write."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.owner = utils.make_user("vduown", "d2tvduown")
		cls.other = utils.make_user("vduoth", "d2tvduoth")

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		for email in (cls.owner, cls.other):
			utils.drop_user(email)
		frappe.db.commit()
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.doc = utils.make_prototype(
			self.owner, "d2t-vdundo-work", files={"src/App.vue": NESTED, "src/other.txt": "o\n"}
		)
		self.addCleanup(utils.drop_prototype, self.doc.name)
		versions.record_created(self.doc, "Created")
		frappe.db.commit()
		refresh = patch("sketch.thumbnails.request_refresh")
		refresh.start()
		self.addCleanup(refresh.stop)
		frappe.set_user(self.owner)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def source(self) -> str:
		return prototype_files.read_text(self.doc.name, "src/App.vue")["content"]

	def make(self, option="bars") -> int:
		return api.set_variant_default("d2t-vdundo-work", "src/App.vue", "Spend summary", option)["sequence"]

	def test_undo_restores_the_file_exactly_with_three_options(self):
		sequence = self.make("bars")
		# Moving the old default back would give [totals, bars, timeline].
		self.assertNotEqual(self.source(), NESTED)

		api.undo_variant_default("d2t-vdundo-work", "src/App.vue", sequence, "Spend summary", "bars")

		self.assertEqual(self.source(), NESTED)
		top = api.list_versions("d2t-vdundo-work")[0]
		self.assertEqual(top["prompt"], "Undid making \u201cBars\u201d the default for Spend summary")
		self.assertEqual(len(api.list_versions("d2t-vdundo-work")), 3)

	def test_undo_leaves_other_files_alone(self):
		sequence = self.make("bars")
		prototype_files.write_files(self.doc.name, [{"path": "src/other.txt", "content": "changed\n"}])
		versions.note_write(self.doc.name, ["src/other.txt"], {"src/other.txt"})

		api.undo_variant_default("d2t-vdundo-work", "src/App.vue", sequence, "Spend summary", "bars")

		self.assertEqual(self.source(), NESTED)
		self.assertEqual(prototype_files.read_text(self.doc.name, "src/other.txt")["content"], "changed\n")

	def test_undo_is_refused_after_a_later_write(self):
		sequence = self.make("bars")
		later = self.source().replace("<Chart />", "<Chart size='lg' />")
		prototype_files.write_files(self.doc.name, [{"path": "src/App.vue", "content": later}])
		versions.note_write(self.doc.name, ["src/App.vue"], {"src/App.vue"})
		versions.commit(self.doc, "The agent edited the page")

		with self.assertRaises(frappe.ValidationError) as caught:
			api.undo_variant_default("d2t-vdundo-work", "src/App.vue", sequence, "Spend summary", "bars")

		self.assertIn("the page changed since. Ask your agent instead.", str(caught.exception))
		self.assertEqual(self.source(), later)

	def version(self, sequence: int) -> str:
		return frappe.db.get_value(versions.VERSION, {"prototype": self.doc.name, "sequence": sequence})

	def test_undo_reads_the_action_not_the_wording(self):
		sequence = self.make("bars")
		frappe.db.set_value(versions.VERSION, self.version(sequence), "prompt", "Bars leads Spend summary now")

		api.undo_variant_default("d2t-vdundo-work", "src/App.vue", sequence, "Spend summary", "bars")

		self.assertEqual(self.source(), NESTED)

	def test_a_version_saved_before_the_action_field_still_undoes(self):
		sequence = self.make("bars")
		frappe.db.set_value(versions.VERSION, self.version(sequence), {"action": None, "action_label": None})

		api.undo_variant_default("d2t-vdundo-work", "src/App.vue", sequence, "Spend summary", "bars")

		self.assertEqual(self.source(), NESTED)

	def test_undo_only_undoes_a_make_default_version(self):
		with self.assertRaises(frappe.ValidationError):
			api.undo_variant_default("d2t-vdundo-work", "src/App.vue", 1, "Spend summary", "bars")

	def test_a_non_owner_cannot_undo(self):
		sequence = self.make("bars")
		with set_user(self.other):
			with self.assertRaises(frappe.DoesNotExistError):
				api.undo_variant_default("d2t-vdundo-work", "src/App.vue", sequence, "Spend summary", "bars")

		self.assertNotEqual(self.source(), NESTED)

class TestMakeDefaultOnTheViewer(IntegrationTestCase):
	"""The canvas tile and the Demo card make a default from the Viewer's shell, with the owner's session.

	The shell tells the page who is reading; the frame, which runs the Prototype's code, holds no
	credential for anyone. A signed-in reader of a public Prototype and a Guest see the canvas and
	the card, but their session cannot reach the owner's files.
	"""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.owner = utils.make_user("vdvown", "d2tvdvown")
		cls.reader = utils.make_user("vdvrdr", "d2tvdvrdr")
		for email in (cls.owner, cls.reader):
			cls.addClassCleanup(utils.drop_user, email)
		cls.doc = utils.make_prototype(cls.owner, "d2t-vdv-work", files={"src/App.vue": SIMPLE}, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.doc.name)
		cls.other = utils.make_prototype(cls.owner, "d2t-vdv-other", files={"src/App.vue": SIMPLE}, is_public=True)
		cls.addClassCleanup(utils.drop_prototype, cls.other.name)
		cls.path = f"/u/{utils.username_of(cls.owner)}/{cls.doc.slug}"

	def setUp(self):
		super().setUp()
		self.enterContext(patch.dict(frappe.flags, force_website_cache=False))
		self.enterContext(patch.object(frappe.local, "request", None, create=True))
		self.enterContext(patch.object(frappe.local, "no_cache", False, create=True))
		self.enterContext(patch.object(frappe.local, "form_dict", frappe._dict()))
		self.enterContext(patch.object(frappe.local, "response_headers", frappe._dict()))
		self.enterContext(patch.dict(frappe.local.response, from_cache=False))
		self.enterContext(patch("sketch.thumbnails.request_refresh"))

	def page(self, user: str, form: dict | None = None):
		frappe.local.no_cache = False
		frappe.local.response.from_cache = False
		frappe.local.response_headers = frappe._dict()
		path = self.path
		set_request(method="GET", path=path, query_string=urlencode(form or {}))
		url = frappe.local.request.url
		self.addCleanup(frappe.cache.hdel, "website_404", url)
		with set_user(user):
			# set_user starts an empty form_dict, so the query goes in after it.
			frappe.local.form_dict.update(form or {})
			response = get_response(path)
		self.assertEqual(response.status_code, 200, response.get_data(as_text=True)[:300])
		return response.get_data(as_text=True)

	def shell(self, user: str) -> dict:
		return utils.shell_slot(self.page(user))

	def frame(self, user: str, form: dict | None = None) -> dict:
		return utils.data_slot(self.page(user, form or {"frame": "1"}))

	def make_default_as(self, user: str):
		with set_user(user):
			return api.set_variant_default(self.doc.slug, "src/App.vue", "Spend summary", "budget-bars")

	def source(self) -> str:
		return prototype_files.read_text(self.doc.name, "src/App.vue")["content"]

	def test_the_owners_shell_holds_the_session_and_the_frame_holds_nothing(self):
		shell = self.shell(self.owner)
		self.assertEqual(shell["role"], "owner")
		self.assertTrue(shell["csrf_token"], "the shell's writes send it")
		self.assertEqual(utils.credential_keys(self.frame(self.owner)), [])

		self.addCleanup(prototype_files.write_files, self.doc.name, [{"path": "src/App.vue", "content": SIMPLE}])
		self.make_default_as(self.owner)
		self.assertEqual(self.source(), variant_default.record_slot(SIMPLE, "Spend summary", "budget-bars"))
		self.assertEqual(
			prototype_files.read_text(self.other.name, "src/App.vue")["content"], SIMPLE, "the owner's other prototype is untouched"
		)

	def test_a_signed_in_reader_of_a_public_prototype_cannot_move_the_owners_slot(self):
		shell = self.shell(self.reader)
		self.assertEqual(shell["role"], "viewer")
		self.assertEqual(utils.credential_keys(self.frame(self.reader)), [])
		with self.assertRaises(frappe.DoesNotExistError):
			self.make_default_as(self.reader)
		# Nor through the shell's session API, which has no default door at all.
		self.assertFalse(hasattr(viewer_api, "set_variant_default"))
		self.assertEqual(self.source(), SIMPLE)

	def test_a_guest_cannot_move_it(self):
		shell = self.shell("Guest")
		self.assertEqual((shell["role"], shell["csrf_token"]), ("guest", ""))
		self.assertEqual(utils.credential_keys(self.frame("Guest")), [])
		with self.assertRaises(frappe.DoesNotExistError):
			self.make_default_as("Guest")
		self.assertEqual(self.source(), SIMPLE)

	def test_a_check_request_gets_no_credential(self):
		stamp = signature.mint(self.doc.name, ttl_seconds=600)
		data = self.frame("Guest", {"exp": stamp["exp"], "sig": stamp["sig"]})
		self.assertEqual(data["chrome"], "off")
		self.assertEqual(utils.credential_keys(data), [])
