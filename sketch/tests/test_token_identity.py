# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""A Sketch Token names its owner, and nobody else.

The doctype is named `field:user` and `sketch.auth` reads that field as the
identity of an `/mcp` request. A Sketch User used to hold `create` and `write`
on the doctype with `if_owner`, and Frappe never applies `if_owner` to
`create`: `Document.insert` forces `owner` alone, so the `user` Link field
stayed caller-controlled. One REST insert of
`{"user": "victim@example.com", "token": "sk_chosen"}` minted a working /mcp
credential for the victim.

Three fixes are tested here, because all three rewrote the same rows:

- the identity guard (`SketchToken.validate`) and the patch that removes any
  row already planted,
- the `enabled` check in `resolve`, so a banned account's token dies with it,
- the `token_hash` index, so `resolve` reads one row instead of decrypting
  every row on the site.

The in-process cases never skip. The REST case needs the live server, because
the permission rows only apply to a real request.
"""

import json
import unittest

import frappe
from frappe.tests import IntegrationTestCase

from sketch.patches.v1_0 import backfill_sketch_token_hash, drop_foreign_sketch_tokens
from sketch.sketch.doctype.sketch_token import sketch_token
from sketch.tests import utils


class TestTokenIdentity(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.user = utils.make_user("ident", "d2tident")
		cls.addClassCleanup(utils.drop_user, cls.user)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		super().tearDownClass()

	def setUp(self):
		"""One good row per case.

		`IntegrationTestCase` rolls the database back once per class, not once
		per test, so a case that clobbers the row would be read by the next
		one. `regenerate` writes the secret and the hash together, so every
		case starts from a row Sketch itself minted.
		"""
		sketch_token.get_or_create(self.user)
		self.token = sketch_token.regenerate(self.user)
		frappe.db.commit()

	def row(self, user: str) -> dict:
		return frappe.db.get_value(
			"Sketch Token", {"user": user}, ["name", "user", "owner", "token_hash"], as_dict=True
		)

	# ------------------------------------------------------- the identity guard

	def test_the_row_is_named_and_owned_by_the_same_user(self):
		"""Both halves of the identity. `name` is the user because `autoname`
		is `field:user`, and `owner` is what the `if_owner` read rule reads."""
		row = self.row(self.user)

		self.assertEqual(row.name, self.user)
		self.assertEqual(row.owner, self.user)

	def test_an_insert_without_the_mint_flag_is_refused(self):
		"""The guard that survives a permission change. Every path but
		`get_or_create` and `regenerate` lands here, `ignore_permissions`
		included."""
		victim = utils.make_user("identvic", "d2tidentvic")
		self.addCleanup(utils.drop_user, victim)

		doc = frappe.new_doc("Sketch Token")
		doc.user = victim
		doc.token = "sk_chosen"

		with self.assertRaises(frappe.PermissionError):
			doc.insert(ignore_permissions=True)

		self.assertIsNone(self.row(victim))

	def test_a_save_without_the_mint_flag_is_refused(self):
		"""The write half. A REST write of an existing row lands here."""
		doc = frappe.get_doc("Sketch Token", self.user)

		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)

	def test_a_row_cannot_be_pointed_at_another_user(self):
		"""Defence in depth. Even with the flag, `user` has to be `owner`."""
		victim = utils.make_user("identvic2", "d2tidentvic2")
		self.addCleanup(utils.drop_user, victim)

		doc = frappe.get_doc("Sketch Token", self.user)
		doc.user = victim
		doc.flags.minted_by_sketch = True

		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)

	def test_a_planted_row_authenticates_nobody_after_the_patch(self):
		"""`drop_foreign_sketch_tokens`, on the shape the exploit leaves: the
		row is named for the victim and owned by the attacker."""
		victim = utils.make_user("identpat", "d2tidentpat")
		self.addCleanup(utils.drop_user, victim)
		planted = sketch_token.get_or_create(victim)
		frappe.db.set_value("Sketch Token", victim, "owner", self.user, update_modified=False)
		frappe.db.commit()

		drop_foreign_sketch_tokens.execute()

		self.assertIsNone(self.row(victim))
		self.assertIsNone(sketch_token.resolve(planted))

	def test_the_patch_keeps_every_honest_row(self):
		"""A row minted by Sketch always has `user == owner`."""
		drop_foreign_sketch_tokens.execute()

		self.assertEqual(sketch_token.resolve(self.token), self.user)

	# ------------------------------------------------------ the disabled user

	def test_a_disabled_user_authenticates_with_no_token(self):
		"""Disable is the site's only ban, and `frappe.set_user` checks
		nothing. Without this the banned account keeps every /mcp tool."""
		frappe.db.set_value("User", self.user, "enabled", 0)
		frappe.db.commit()
		self.addCleanup(self.enable, self.user)

		self.assertIsNone(sketch_token.resolve(self.token))

	def test_the_token_works_again_when_the_ban_is_lifted(self):
		"""The check reads the User row, so it needs no token change."""
		frappe.db.set_value("User", self.user, "enabled", 0)
		frappe.db.commit()
		self.enable(self.user)

		self.assertEqual(sketch_token.resolve(self.token), self.user)

	def enable(self, user: str) -> None:
		frappe.db.set_value("User", user, "enabled", 1)
		frappe.db.commit()

	# ---------------------------------------------------------- the hash index

	def test_minting_stores_the_hash(self):
		self.assertEqual(self.row(self.user).token_hash, sketch_token.token_hash(self.token))

	def test_regenerating_stores_the_new_hash(self):
		"""A stale hash would lock the user out of the token they just made."""
		fresh = sketch_token.regenerate(self.user)

		self.assertEqual(self.row(self.user).token_hash, sketch_token.token_hash(fresh))
		self.assertEqual(sketch_token.resolve(fresh), self.user)

	def test_resolve_reads_the_hash_and_not_every_row(self):
		"""Clear the index and the good token stops resolving. That is the
		proof that `resolve` no longer decrypts the whole table."""
		frappe.db.set_value("Sketch Token", self.user, "token_hash", None, update_modified=False)

		self.assertIsNone(sketch_token.resolve(self.token))

	def test_a_planted_hash_does_not_authenticate(self):
		"""The hash is the index, the encrypted token is the authority."""
		other = sketch_token.new_token()
		frappe.db.set_value(
			"Sketch Token", self.user, "token_hash", sketch_token.token_hash(other), update_modified=False
		)

		self.assertIsNone(sketch_token.resolve(other))

	def test_a_token_with_the_wrong_prefix_costs_no_query(self):
		"""The prefix guard, pinned by the query it saves.

		`resolve` runs before authentication, so junk from an unauthenticated
		caller must stop at the prefix. The None on its own proves nothing: a
		hash lookup for junk finds no row and answers None as well. The query
		count is what fails when the guard goes.
		"""
		with self.assertQueryCount(0):
			self.assertIsNone(sketch_token.resolve("nope"))
			self.assertIsNone(sketch_token.resolve(""))

	def test_the_backfill_patch_restores_an_old_row(self):
		"""Every row minted before the field existed. Without the backfill the
		agent holding that token gets a 401."""
		frappe.db.set_value("Sketch Token", self.user, "token_hash", None, update_modified=False)

		backfill_sketch_token_hash.execute()

		self.assertEqual(self.row(self.user).token_hash, sketch_token.token_hash(self.token))
		self.assertEqual(sketch_token.resolve(self.token), self.user)


class TestTokenIdentityOverHttp(IntegrationTestCase):
	"""The exploit itself, over the wire. The permission rows only apply to a
	real request, so an in-process insert cannot show this."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		utils.require_webserver()
		cls.attacker = utils.make_user("identatk", "d2tidentatk")
		cls.addClassCleanup(utils.drop_user, cls.attacker)
		cls.victim = utils.make_user("identtgt", "d2tidenttgt")
		cls.addClassCleanup(utils.drop_user, cls.victim)
		cls.auth = utils.api_auth_header(cls.attacker)

	@classmethod
	def tearDownClass(cls):
		frappe.set_user("Administrator")
		super().tearDownClass()

	def test_a_user_cannot_mint_a_token_for_another_user(self):
		"""The account takeover. The insert used to land, and
		`Authorization: Bearer sk_chosen` then ran every /mcp tool as the
		victim."""
		response = utils.request(
			"POST",
			"/api/resource/Sketch Token",
			headers={**self.auth, "Content-Type": "application/json"},
			data=json.dumps({"user": self.victim, "token": "sk_chosen"}),
		)

		self.assertNotEqual(response.status_code, 200, response.text[:400])
		frappe.db.commit()
		self.assertIsNone(frappe.db.get_value("Sketch Token", {"user": self.victim}, "name"))
		self.assertIsNone(sketch_token.resolve("sk_chosen"))

	def test_a_disabled_account_gets_a_401_on_mcp(self):
		"""The ban, on the path the token opens."""
		token = sketch_token.get_or_create(self.attacker)
		frappe.db.set_value("User", self.attacker, "enabled", 0)
		frappe.db.commit()
		self.addCleanup(self.enable, self.attacker)

		response = utils.request(
			"POST",
			"/mcp",
			headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
			data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping", "params": {}}),
		)

		self.assertEqual(response.status_code, 401, response.text[:400])
		self.assertIn("invalid_token", response.text)

	def enable(self, user: str) -> None:
		frappe.db.set_value("User", user, "enabled", 1)
		frappe.db.commit()


if __name__ == "__main__":
	unittest.main()
