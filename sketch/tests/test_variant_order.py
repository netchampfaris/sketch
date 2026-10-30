# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Options keep the place of the version that first held them (sketch/variant_order.py).

Only files a version filed count, never the rest of the tree its manifest holds, and an
adopted variant keeps the place of the teammate's file it was moved from.
"""

from unittest import TestCase
from unittest.mock import patch

from sketch import variant_order

PAGE = """<template>
  <Variants name="Deal card">
    <template #plain>…</template>
    <template #big>…</template>
  </Variants>
</template>
"""
REORDERED = """<template>
  <Variants name="Deal card">
    <template #fresh>…</template>
    <template #big>…</template>
    <template #plain>…</template>
  </Variants>
</template>
"""
BLOBS = {"p1": PAGE, "p2": REORDERED, "lucia": "<variant set='Deal card' name='Final' />", "daniel": "<variant set='Deal card' name='Kanban' />"}


def fold(steps):
	state = {"shape": 1, "upto": 0, "manifest": {}, "slots": {}, "extras": {}, "files": {}}
	with patch("sketch.snapshots.read_blob", lambda _name, sha: BLOBS[sha].encode()):
		for seq, (manifest, filed) in enumerate(steps, start=1):
			variant_order._read_version("x", state, seq, manifest, set(filed))
	return state


class TestFirstSeen(TestCase):
	def test_a_slot_keeps_the_version_it_first_appeared_in(self):
		state = fold([({"src/Page.vue": "p1"}, ["src/Page.vue"]), ({"src/Page.vue": "p2"}, ["src/Page.vue"])])

		self.assertEqual(state["slots"]["src/Page.vue"]["Deal card"], {"plain": 1, "big": 1, "fresh": 2})

	def test_a_teammates_file_counts_from_their_own_commit_not_the_owners_tree(self):
		lucia = "src/variants/@lucia/final.vue"
		daniel = "src/variants/@daniel/kanban.vue"
		state = fold(
			[
				({"src/Page.vue": "p1", lucia: "lucia", daniel: "daniel"}, ["src/Page.vue"]),
				({"src/Page.vue": "p1", lucia: "lucia", daniel: "daniel"}, [lucia]),
				({"src/Page.vue": "p1", lucia: "lucia", daniel: "daniel"}, [daniel]),
			]
		)

		# Lucía's came first, so it sorts first, whatever the usernames say.
		self.assertEqual(state["extras"], {"@lucia/final": 2, "@daniel/kanban": 3})

	def test_an_adopted_variant_keeps_its_place(self):
		lucia = "src/variants/@lucia/final.vue"
		adopted = "src/variants/adopted/final.vue"
		state = fold(
			[
				({"src/Page.vue": "p1"}, ["src/Page.vue"]),
				({"src/Page.vue": "p1", lucia: "lucia"}, [lucia]),
				({"src/Page.vue": "p2", lucia: "lucia"}, ["src/Page.vue"]),
				# Adopting moves the file byte for byte, in one version.
				({"src/Page.vue": "p2", adopted: "lucia"}, [adopted]),
			]
		)

		self.assertEqual(state["extras"]["adopted/final"], 2)
