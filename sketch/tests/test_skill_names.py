"""The served skill must only name things the Runtime can resolve.

A wrong name in the skill breaks every Prototype that trusts it, and the agent
has no way to tell a typo from a component it has not met. The failure is also
silent at build time: the skill is prose, so nothing checks it.

This test reads the skill, pulls every import specifier and every component
name out of its fenced code blocks, and asserts each one resolves against the
Runtime that ships beside it.
"""

import json
import re
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
SKILL = APP / "skill" / "frappe-ui.md"
RUNTIMES = APP / "public" / "runtimes"

# Rendered by the Runtime itself, not imported by a Prototype.
BUILTIN_TAGS = {
	"RouterView",
	"RouterLink",
	"Transition",
	"TransitionGroup",
	"KeepAlive",
	"Teleport",
	"Suspense",
	"component",
	"template",
	"slot",
}

# Named in the skill precisely because the Runtime does not have them, so the
# agent does not reach for one. `test_absent_names_really_are_absent` asserts
# each is still missing: add one to a Runtime bundle and this list must shrink.
ABSENT_ON_PURPOSE = {
	"Accordion",
	"Calendar",
	"Card",
	"CodeEditor",
	"FloatingWindow",
	"MultiEmailInput",
}

# PascalCase in prose that names a browser API, not a component.
NOT_A_COMPONENT = {"XMLHttpRequest", "Intl", "NumberFormat", "DateTimeFormat"}

FENCE = re.compile(r"^```(\w*)\n(.*?)^```", re.M | re.S)
IMPORT = re.compile(r"""import\s+(?:([\w*{}\s,]+?)\s+from\s+)?['"]([^'"]+)['"]""")
NAMED = re.compile(r"\{([^}]*)\}")
# A component tag is PascalCase. Plain HTML is lowercase, so this never sees it.
TAG = re.compile(r"<([A-Z]\w+)")
TEMPLATE = re.compile(r"<template>\n(.*)\n</template>", re.S)


def template_of(body: str) -> str:
	"""Only the template renders tags. `ref<Issue[]>` in the script is a generic."""
	match = TEMPLATE.search(body)
	return match.group(1) if match else body


def newest_runtime() -> Path | None:
	"""The Runtime is a build artifact and is not in git, so it may be absent."""
	if not RUNTIMES.is_dir():
		return None
	versions = sorted(p for p in RUNTIMES.iterdir() if p.is_dir())
	return versions[-1] if versions else None


def bundle_exports(path: Path) -> set:
	"""The names an ESM bundle actually exports, read from its export block."""
	match = re.search(r"export\s*\{([^}]*)\}\s*;?\s*$", path.read_text(), re.S)
	if not match:
		return set()
	names = set()
	for part in match.group(1).split(","):
		part = part.strip()
		if part:
			names.add(re.split(r"\s+as\s+", part)[-1].strip())
	return names


class TestSkillNames(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		cls.runtime = newest_runtime()
		if cls.runtime is None:
			raise unittest.SkipTest(
				f"no Runtime built under {RUNTIMES}; run runtime-prototype/build.sh"
			)
		cls.manifest = json.loads((cls.runtime / "manifest.json").read_text())
		cls.import_map = cls.manifest["importMap"]
		cls.exports = {
			specifier: bundle_exports(cls.runtime / filename)
			for specifier, filename in cls.import_map.items()
			if not specifier.startswith("sketch:")
		}
		cls.blocks = [
			(lang, body)
			for lang, body in FENCE.findall(SKILL.read_text())
			if lang in ("vue", "ts", "js")
		]

	def test_skill_and_runtime_exist(self):
		self.assertTrue(SKILL.exists(), f"{SKILL} is missing")
		self.assertTrue(self.blocks, "the skill has no vue/ts/js code blocks to check")

	def test_every_import_specifier_resolves(self):
		"""A bare import the Runtime cannot resolve is a boot failure."""
		for lang, body in self.blocks:
			for _, specifier in IMPORT.findall(body):
				if specifier.startswith("."):
					continue  # a Prototype's own file
				with self.subTest(specifier=specifier):
					self.assertIn(
						specifier,
						self.import_map,
						f"the skill imports {specifier!r}, which is not in the Runtime import map",
					)

	def test_every_imported_name_is_exported(self):
		"""A named import the bundle does not export is `undefined` at run time."""
		for lang, body in self.blocks:
			for clause, specifier in IMPORT.findall(body):
				if not clause or specifier.startswith("."):
					continue
				if specifier not in self.exports:
					continue
				named = NAMED.search(clause)
				if not named:
					continue  # a default import; the name is the caller's choice
				for name in named.group(1).split(","):
					name = re.split(r"\s+as\s+", name.strip())[0].strip()
					if not name or name.startswith("type "):
						continue
					with self.subTest(specifier=specifier, name=name):
						self.assertIn(
							name,
							self.exports[specifier],
							f"the skill imports {{{name}}} from {specifier!r}, which does not export it",
						)

	def test_every_component_used_is_imported(self):
		"""In a whole-file example, an unimported tag renders nothing and errors nothing."""
		for lang, body in self.blocks:
			# Fragments show one component in isolation and omit the imports on
			# purpose. Only a block with its own <script setup> claims to be a
			# complete file, so only that one must import what it renders.
			if lang != "vue" or "<script setup" not in body:
				continue
			imported = set()
			for clause, _ in IMPORT.findall(body):
				named = NAMED.search(clause or "")
				if named:
					for name in named.group(1).split(","):
						name = re.split(r"\s+as\s+", name.strip())[-1].strip()
						if name:
							imported.add(name)
			for tag in set(TAG.findall(template_of(body))):
				if tag in BUILTIN_TAGS:
					continue
				with self.subTest(tag=tag):
					self.assertIn(
						tag,
						imported,
						f"the skill renders <{tag}> without importing it",
					)

	def test_every_component_in_a_fragment_exists(self):
		"""A fragment need not import, but it must not invent a component."""
		known = set().union(*self.exports.values()) if self.exports else set()
		for lang, body in self.blocks:
			if lang != "vue" or "<script setup" in body:
				continue
			for tag in set(TAG.findall(template_of(body))):
				if tag in BUILTIN_TAGS:
					continue
				with self.subTest(tag=tag):
					self.assertIn(
						tag,
						known,
						f"the skill renders <{tag}>, which no Runtime bundle exports",
					)

	def test_every_component_named_in_prose_exists(self):
		"""The catalog must not name a component the Runtime dropped."""
		known = set().union(*self.exports.values()) if self.exports else set()
		text = SKILL.read_text()
		# Section 8 is the list of things that are deliberately missing, so it
		# is the one place a name may not resolve.
		catalog = text.split("## 8. What does not exist")[0]
		for name in set(re.findall(r"`([A-Z]\w+)`", FENCE.sub("", catalog))):
			if name in BUILTIN_TAGS or name in NOT_A_COMPONENT or name in ABSENT_ON_PURPOSE:
				continue
			with self.subTest(name=name):
				self.assertIn(
					name,
					known,
					f"the skill names `{name}`, which no Runtime bundle exports",
				)

	def test_absent_names_really_are_absent(self):
		"""If the Runtime gains one of these, the skill is now lying about it."""
		known = set().union(*self.exports.values()) if self.exports else set()
		for name in ABSENT_ON_PURPOSE:
			with self.subTest(name=name):
				self.assertNotIn(
					name,
					known,
					f"the skill says `{name}` does not exist, but the Runtime exports it",
				)


if __name__ == "__main__":
	unittest.main()
