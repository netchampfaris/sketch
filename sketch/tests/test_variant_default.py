# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Make default moves one slot of a `<Variants>` set to the front of its file.

The first slot is the default, so the owner's pick becomes first and the rest
of the file stays byte for byte. The traps:

- A slot holds nested `<template>` elements and a `>` inside an attribute, so
  the end of a slot is found by tag depth, not by the first `</template>`.
- Indentation and the whitespace between slots keep their place.
- It refuses, with a message the owner can read, a set that is missing or
  repeated, an option that is not there, and an option already first.
- Only the owner may do it, through the session door and the signed one.
- The move is one version, with no agent prompt, and the version before it
  restores the old order.
"""

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, set_user

from sketch import api, prototype_files, signature, variant_default, versions
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

	def test_the_picked_slot_goes_first(self):
		out = variant_default.move_slot(SIMPLE, "Spend summary", "budget-bars")
		self.assertEqual(
			out,
			SIMPLE.replace(
				"""    <template #totals>
      <p>Totals</p>
    </template>
    <template #budget-bars>
      <p>Budget bars</p>
    </template>
""",
				"""    <template #budget-bars>
      <p>Budget bars</p>
    </template>
    <template #totals>
      <p>Totals</p>
    </template>
""",
			),
		)

	def test_moving_it_back_restores_the_file_byte_for_byte(self):
		moved = variant_default.move_slot(SIMPLE, "Spend summary", "budget-bars")
		self.assertEqual(variant_default.move_slot(moved, "Spend summary", "totals"), SIMPLE)

	def test_nested_templates_do_not_end_a_slot_early(self):
		out = variant_default.move_slot(NESTED, "Spend summary", "bars")
		start = out.index("<Variants")
		self.assertLess(out.index("#bars", start), out.index("#totals", start))
		self.assertLess(out.index("#totals", start), out.index("v-slot:timeline", start))
		# Nothing was lost or duplicated, only reordered.
		self.assertEqual(sorted(out.splitlines()), sorted(NESTED.splitlines()))

		# A slot with nested templates, an attribute holding `>` and a comment holding
		# a closing tag moves whole.
		out = variant_default.move_slot(NESTED, "Spend summary", "timeline")
		self.assertTrue(out.index("v-slot:timeline") < out.index("#totals"))
		self.assertIn("<!-- </template> inside a comment -->\n      </template>\n      <template #bars>", out)
		self.assertEqual(variant_default.move_slot(out, "Spend summary", "totals"), NESTED)

	def test_indentation_and_the_text_around_the_set_are_kept(self):
		source = "<template>\n\t<Variants name='A'>\n\t\t<template #one>1</template>\n\n\t\t<template #two>\n\t\t\t2\n\t\t</template>\n\t</Variants>\n</template>\n"
		out = variant_default.move_slot(source, "A", "two")
		self.assertEqual(
			out,
			"<template>\n\t<Variants name='A'>\n\t\t<template #two>\n\t\t\t2\n\t\t</template>\n\n\t\t<template #one>1</template>\n\t</Variants>\n</template>\n",
		)

	def test_slots_on_one_line_move_too(self):
		source = '<template><Variants name="A"><template #a>A</template><template #b>B</template></Variants></template>'
		out = variant_default.move_slot(source, "A", "b")
		self.assertEqual(out, '<template><Variants name="A"><template #b>B</template><template #a>A</template></Variants></template>')

	def test_a_set_that_is_not_there_is_refused(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			variant_default.move_slot(SIMPLE, "Nope", "totals")
		self.assertIn('There is no <Variants name="Nope">', str(caught.exception))

	def test_the_same_name_twice_is_refused(self):
		block = SIMPLE[SIMPLE.index("  <Variants") : SIMPLE.index("</template>\n", SIMPLE.index("</Variants>"))]
		twice = SIMPLE.replace(block, block + block)
		with self.assertRaises(frappe.ValidationError) as caught:
			variant_default.move_slot(twice, "Spend summary", "budget-bars")
		self.assertIn("2 times", str(caught.exception))

	def test_an_option_that_is_not_in_the_set_is_refused(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			variant_default.move_slot(SIMPLE, "Spend summary", "missing")
		self.assertIn('has no option "missing"', str(caught.exception))

	def test_the_default_is_already_first(self):
		with self.assertRaises(frappe.ValidationError) as caught:
			variant_default.move_slot(SIMPLE, "Spend summary", "totals")
		self.assertIn("already the default", str(caught.exception))


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

	def test_the_owner_moves_it_and_a_version_is_saved(self):
		out = api.set_variant_default(SLUG, "src/App.vue", "Spend summary", "budget-bars")

		self.assertEqual(self.source(), variant_default.move_slot(SIMPLE, "Spend summary", "budget-bars"))
		rows = api.list_versions(SLUG)
		self.assertEqual(rows[0]["sequence"], out["sequence"])
		self.assertEqual(rows[0]["prompt"], 'Made "Budget bars" the default for Spend summary')
		self.assertEqual(versions.pending(self.doc.name), [])

	def test_undo_is_one_more_version(self):
		api.set_variant_default(SLUG, "src/App.vue", "Spend summary", "budget-bars")
		api.set_variant_default(SLUG, "src/App.vue", "Spend summary", "totals")

		self.assertEqual(self.source(), SIMPLE)
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

	def test_the_signed_door_needs_this_scope(self):
		mint = lambda scope: signature.mint(self.doc.name, 60, scope)  # noqa: E731
		frappe.set_user("Guest")
		for scope in (signature.REVISION, signature.ANNOTATE, signature.VIEW):
			stamp = mint(scope)
			with self.assertRaises(frappe.DoesNotExistError):
				api.set_variant_default_signed(
					self.doc.name, str(stamp["exp"]), stamp["sig"], "src/App.vue", "Spend summary", "budget-bars"
				)

		self.assertEqual(self.source(), SIMPLE)

		stamp = mint(signature.VARIANT_DEFAULT)
		api.set_variant_default_signed(
			self.doc.name, str(stamp["exp"]), stamp["sig"], "src/App.vue", "Spend summary", "budget-bars"
		)
		self.assertEqual(self.source(), variant_default.move_slot(SIMPLE, "Spend summary", "budget-bars"))
		frappe.set_user("Administrator")
		self.assertEqual(
			versions.history(self.doc.name)[0]["prompt"], 'Made "Budget bars" the default for Spend summary'
		)


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
		self.assertEqual(top["prompt"], 'Undid making "Bars" the default for Spend summary')
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

	def test_undo_only_undoes_a_make_default_version(self):
		with self.assertRaises(frappe.ValidationError):
			api.undo_variant_default("d2t-vdundo-work", "src/App.vue", 1, "Spend summary", "bars")

	def test_a_non_owner_cannot_undo(self):
		sequence = self.make("bars")
		with set_user(self.other):
			with self.assertRaises(frappe.DoesNotExistError):
				api.undo_variant_default("d2t-vdundo-work", "src/App.vue", sequence, "Spend summary", "bars")

		self.assertNotEqual(self.source(), NESTED)

	def test_the_signed_undo_needs_this_scope(self):
		sequence = self.make("bars")
		frappe.set_user("Guest")
		stamp = signature.mint(self.doc.name, 60, signature.ANNOTATE)
		with self.assertRaises(frappe.DoesNotExistError):
			api.undo_variant_default_signed(
				self.doc.name, str(stamp["exp"]), stamp["sig"], "src/App.vue", str(sequence), "Spend summary", "bars"
			)

		stamp = signature.mint(self.doc.name, 60, signature.VARIANT_DEFAULT)
		api.undo_variant_default_signed(
			self.doc.name, str(stamp["exp"]), stamp["sig"], "src/App.vue", str(sequence), "Spend summary", "bars"
		)
		self.assertEqual(self.source(), NESTED)
