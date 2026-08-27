# Copyright (c) 2026, Faris Ansari and contributors
# For license information, please see license.txt

"""Fixtures and probes the Sketch tests share.

The site is shared with live work, so every fixture here carries the `d2t`
prefix, is created by the test that needs it, and is removed again in
tearDownClass. No test reads a row another agent left behind.

Several tests drive the live web server, because a `page_renderer` and an
`auth_hooks` entry only run inside a real request. Those tests skip with a
readable reason when the server is not up.
"""

import json
import os
import shutil
import subprocess
import unittest

import frappe
import requests

#: Every fixture name starts with this. It makes a leaked row easy to find.
PREFIX = "d2t"

TEST_ROLE = "Sketch User"

#: The site the web server answers for. Requests go to the loopback port and
#: carry this as the Host header, never the public hostname (trap 14).
SITE_HOST = "sketch.localhost"

RUNTIMES = ("public", "runtimes")

CHECKD_URL = os.environ.get("SKETCH_CHECKD_URL", "http://127.0.0.1:8010/check")


# --------------------------------------------------------------- the server


def webserver_port() -> int:
	"""The bench web server port, from common_site_config."""
	return int(frappe.get_conf().get("webserver_port") or 8000)


def base_url() -> str:
	"""The loopback base URL of the live site."""
	return f"http://127.0.0.1:{webserver_port()}"


def request(method: str, path: str, **kwargs) -> requests.Response:
	"""One HTTP request to the live site. Never follows a redirect.

	A redirect hides the status the test is about, so the caller sees the first
	answer and nothing else.
	"""
	headers = {"Host": SITE_HOST}
	headers.update(kwargs.pop("headers", None) or {})
	kwargs.setdefault("timeout", 60)
	kwargs.setdefault("allow_redirects", False)
	return requests.request(method, base_url() + path, headers=headers, **kwargs)


def webserver_reason() -> str | None:
	"""Why the live site cannot be used, or None when it is up."""
	try:
		response = request("GET", "/api/method/frappe.ping", timeout=5)
	except requests.RequestException as e:
		return f"no web server on {base_url()}: {e}"

	if response.status_code != 200:
		return f"{base_url()}/api/method/frappe.ping answered {response.status_code}"

	return None


def require_webserver() -> None:
	"""Skip the test when the live site is not answering."""
	reason = webserver_reason()
	if reason:
		raise unittest.SkipTest(reason)


def checkd_reason() -> str | None:
	"""Why `sketch-checkd` cannot be used, or None when it is up.

	The daemon answers 404 on any route but POST /check, so a 404 on GET is
	proof that it is listening.
	"""
	try:
		requests.get(CHECKD_URL, timeout=5)
	except requests.RequestException as e:
		return (
			f"sketch-checkd is not listening on {CHECKD_URL}: {e}. "
			"Start it with: systemctl --user start sketch-checkd"
		)

	return None


def require_checkd() -> None:
	"""Skip the test when `sketch-checkd` is not running."""
	reason = checkd_reason()
	if reason:
		raise unittest.SkipTest(reason)


def run_check(url: str, screenshot: bool = False) -> dict:
	"""One POST to sketch-checkd. Returns the parsed answer (contract 5)."""
	response = requests.post(
		CHECKD_URL,
		json={"url": url, "host": SITE_HOST, "screenshot": screenshot},
		timeout=180,
	)
	response.raise_for_status()
	return response.json()


# ---------------------------------------------------------------- the node side


def node_reason() -> str | None:
	"""Why the node cases cannot run, or None when they can."""
	if not shutil.which("node"):
		return "node is not on PATH"

	if not playwright_root():
		return (
			"playwright is not installed; expected it under "
			"checkd/node_modules or /tmp/pw-runner/node_modules"
		)

	if newest_runtime() is None:
		return "no Runtime is built under sketch/public/runtimes; run runtime/build.sh"

	return None


def playwright_root() -> str | None:
	"""A node_modules folder that holds playwright, or None."""
	candidates = (
		os.path.join(frappe.get_app_path("sketch"), "..", "checkd", "node_modules"),
		"/tmp/pw-runner/node_modules",
	)
	for root in candidates:
		if os.path.isdir(os.path.join(root, "playwright")):
			return os.path.abspath(root)

	return None


def run_node(script: str, *args, timeout: int = 600) -> subprocess.CompletedProcess:
	"""Run one node script from the sketch/tests folder."""
	path = os.path.join(os.path.dirname(os.path.abspath(__file__)), script)
	return subprocess.run(
		["node", path, *args],
		capture_output=True,
		text=True,
		timeout=timeout,
	)


# ---------------------------------------------------------------- the Runtime


def require_runtime() -> None:
	"""Skip the test when no Runtime is built.

	Every Prototype pins a Runtime version, so a fixture cannot be created
	without one. The Runtime is a build artifact and is not in git.
	"""
	if newest_runtime() is None:
		raise unittest.SkipTest(
			"no Runtime is built under sketch/public/runtimes; run runtime/build.sh"
		)


def newest_runtime() -> str | None:
	"""The newest built Runtime version, or None when none is built."""
	root = frappe.get_app_path("sketch", *RUNTIMES)
	if not os.path.isdir(root):
		return None

	versions = sorted(entry for entry in os.listdir(root) if os.path.isdir(os.path.join(root, entry)))
	return versions[-1] if versions else None


# ---------------------------------------------------------------- fixtures


def make_user(suffix: str, username: str) -> str:
	"""Create one Website User with the Sketch User role. Returns the email.

	The row is removed first when it survived an earlier crash, so a rerun is
	always clean.
	"""
	email = f"{PREFIX}-{suffix}@example.com"
	drop_user(email)

	doc = frappe.new_doc("User")
	doc.email = email
	doc.first_name = f"Sketch Test {suffix}"
	doc.username = username
	doc.user_type = "Website User"
	doc.send_welcome_email = 0
	doc.enabled = 1
	doc.append("roles", {"role": TEST_ROLE})
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return email


def drop_user(email: str) -> None:
	"""Remove a test user and everything it owns. Safe when it is not there."""
	if not email.startswith(PREFIX):
		raise ValueError(f"refusing to delete {email}: it is not a d2t fixture")

	for name in frappe.get_all("Sketch Prototype", filters={"owner": email}, pluck="name"):
		drop_prototype(name)

	for name in frappe.get_all("Sketch Token", filters={"user": email}, pluck="name"):
		frappe.delete_doc("Sketch Token", name, force=True, ignore_permissions=True)

	if frappe.db.exists("User", email):
		frappe.delete_doc("User", email, force=True, ignore_permissions=True, delete_permanently=True)

	frappe.db.commit()


def make_prototype(owner: str, slug: str, files: dict | None = None, is_public: bool = False, title: str | None = None):
	"""Create one Prototype owned by `owner`, with an optional file tree.

	Frappe writes the session user into `owner` on insert, so the session is
	switched first. Without that the row lands on the caller and every
	/u/<username>/<slug> lookup misses.
	"""
	from frappe.tests import set_user

	from sketch import prototype, prototype_files

	with set_user(owner):
		doc = frappe.new_doc("Sketch Prototype")
		doc.title = title or slug
		doc.slug = slug
		doc.pin = prototype.newest_pin()
		doc.is_public = 1 if is_public else 0
		doc.insert(ignore_permissions=True)

	if doc.owner != owner:
		raise AssertionError(f"the prototype landed on {doc.owner}, not {owner}")

	if files:
		prototype_files.write_files(
			doc.name, [{"path": path, "content": content} for path, content in files.items()]
		)

	frappe.db.commit()
	return doc


def drop_prototype(name: str) -> None:
	"""Delete one Prototype and its tree. Safe when it is not there."""
	from sketch import prototype_files

	if frappe.db.exists("Sketch Prototype", name):
		frappe.delete_doc("Sketch Prototype", name, force=True, ignore_permissions=True)
	else:
		prototype_files.delete_tree(name)

	frappe.db.commit()


def username_of(email: str) -> str:
	return frappe.db.get_value("User", email, "username")


def signed_viewer_url(doc, theme: str = "light", ttl_seconds: int = 600) -> str:
	"""A loopback Viewer URL for one Prototype, signed for ttl_seconds."""
	from sketch import signature

	stamp = signature.mint(doc.name, ttl_seconds=ttl_seconds)
	username = username_of(doc.owner)
	return (
		f"{base_url()}/u/{username}/{doc.slug}"
		f"?theme={theme}&exp={stamp['exp']}&sig={stamp['sig']}"
	)


def data_slot(html: str) -> dict:
	"""Parse the `sketch-data` slot out of a served Viewer document.

	The slot is read the way a browser reads it: everything up to the first
	`</script`. When the serialiser forgets to escape `<`, a Prototype file
	that holds `</script>` cuts the block short here and the parse fails. That
	is trap 1, and it is the whole point of reading it this way.
	"""
	opening = '<script id="sketch-data" type="application/json">'
	start = html.find(opening)
	if start < 0:
		raise AssertionError("the served document has no sketch-data slot")

	start += len(opening)
	end = html.find("</script", start)
	if end < 0:
		raise AssertionError("the sketch-data slot is never closed")

	return json.loads(html[start:end])
