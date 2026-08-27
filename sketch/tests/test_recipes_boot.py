# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Every vendored recipe boots clean through `check`.

Spec 13 calls this the highest-value new test. A recipe is the tree an agent
starts from, so a recipe that does not boot breaks every Prototype made from
it, and the agent reads the breakage as its own mistake.

One test per recipe, named after the recipe, so a failing run names the tree
that is broken. Each one writes the recipe into a throwaway Prototype, signs a
loopback Viewer URL, and asks `sketch-checkd` for the answer.

The bar (verify-a-recipe.md):

- `status` is `ok`
- `errors` is `[]`
- `consoleErrors` is `[]`
- at least one route was walked, so the page is not blank

`sketch-checkd` is a systemd user unit. When it is not listening every case
skips with the command that starts it. A skip is not a pass.
"""

import os
import unittest
from pathlib import Path

from frappe.tests import IntegrationTestCase

from sketch.tests import utils

RECIPES = Path(__file__).resolve().parent.parent / "recipes"


def recipe_slugs() -> list[str]:
	"""Every recipe directory that holds a `src` folder, sorted.

	Read from disk at import time so the test count matches the tree, even when
	`sketch-checkd` is down and every case skips.
	"""
	if not RECIPES.is_dir():
		return []

	return sorted(entry.name for entry in RECIPES.iterdir() if (entry / "src").is_dir())


def read_recipe(slug: str) -> dict:
	"""The `src/...` tree of one recipe as {path: source}."""
	root = RECIPES / slug
	tree = {}
	for dirpath, _, filenames in os.walk(root / "src"):
		for filename in sorted(filenames):
			absolute = os.path.join(dirpath, filename)
			relative = os.path.relpath(absolute, root).replace(os.sep, "/")
			tree[relative] = Path(absolute).read_text(encoding="utf-8")

	return tree


def summarise(answer: dict) -> str:
	"""A readable one-block failure message. The raw answer is too long."""
	lines = [f"status={answer.get('status')}", f"routes={answer.get('routes')}"]
	for entry in answer.get("errors") or []:
		lines.append(f"  error: {entry}")
	for entry in answer.get("consoleErrors") or []:
		lines.append(f"  consoleError: {entry}")
	for entry in answer.get("warnings") or []:
		lines.append(f"  warning: {entry}")
	for entry in answer.get("skipped") or []:
		lines.append(f"  skipped: {entry}")

	return "\n".join(lines)


class TestRecipesBoot(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_runtime()
		cls.user = utils.make_user("recipe", "d2trecipe")
		cls.addClassCleanup(utils.drop_user, cls.user)

	def boot(self, slug: str) -> dict:
		"""Write one recipe into a throwaway Prototype and check it.

		The two requirements sit here, not in setUp, so the case that only
		counts the recipes still runs when the daemon is down.
		"""
		utils.require_webserver()
		utils.require_checkd()

		tree = read_recipe(slug)
		self.assertIn("src/App.vue", tree, f"recipe {slug} has no src/App.vue")

		doc = utils.make_prototype(self.user, f"d2t-rc-{slug}", files=tree)
		self.addCleanup(utils.drop_prototype, doc.name)
		return utils.run_check(utils.signed_viewer_url(doc, ttl_seconds=600))

	def assert_boots_clean(self, slug: str) -> None:
		answer = self.boot(slug)
		report = summarise(answer)
		self.assertIn("skipped", answer, "check must always say what it skipped (trap 12)")
		self.assertEqual(answer["errors"], [], report)
		self.assertEqual(answer["consoleErrors"], [], report)
		self.assertEqual(answer["status"], "ok", report)
		self.assertTrue(answer["routes"], f"recipe {slug} walked no route:\n{report}")

	def test_at_least_one_recipe_exists(self):
		"""Without this, an empty recipes folder is a green run."""
		self.assertTrue(recipe_slugs(), f"no recipe with a src folder under {RECIPES}")


def add_case(slug: str) -> None:
	"""One test method per recipe, so a failure names the recipe."""

	def case(self, slug=slug):
		self.assert_boots_clean(slug)

	case.__name__ = f"test_recipe_{slug}_boots_clean"
	case.__doc__ = f"The {slug} recipe boots with no error and no console error."
	setattr(TestRecipesBoot, case.__name__, case)


for _slug in recipe_slugs():
	add_case(_slug)


if __name__ == "__main__":
	unittest.main()
