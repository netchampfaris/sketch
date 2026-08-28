# Sketch MVP build contracts

The spec (`.scratch/sketch-mvp/spec.md`) decides *what*. This file fixes the
**seams** so parallel agents land on the same interfaces. Do not renegotiate a
contract here. If one is wrong, say so in your report and stop.

## Ground rules for every build agent

1. **Do not edit `sketch/hooks.py`.** The orchestrator owns it. Report the
   exact entries you need in your final report.
2. **Do not run any git command.** No add, commit, branch, checkout, stash.
   The orchestrator commits between waves.
3. **Stay inside your assigned paths.** Listed in your prompt. Touching another
   agent's path corrupts a parallel session.
4. Do not post, push, or write anywhere outside `/home/faris/benches`.
5. Never print or read anything under `~/.cloudflared`, and never print
   `site_config.json` secrets.
6. Verify by running. "Should work" is not done. Paste real output.
7. ASD-STE100 in every comment, docstring and report.
8. Build what the spec says. Make no new decisions. If the spec is silent and
   you must choose, pick the smallest option and flag it in your report.

## Module layout

| Path | Owner | Holds |
|---|---|---|
| `sketch/hooks.py` | orchestrator | every hook entry |
| `sketch/prototype.py` | A1 | Prototype lookup, create, slug, pin |
| `sketch/prototype_files.py` | A1 | the on-disk tree and the path guard |
| `sketch/sketch/doctype/sketch_prototype/` | A1 | doctype |
| `sketch/sketch/doctype/sketch_token/` | A1 | doctype |
| `sketch/fixtures/` | A1 | the `Sketch User` role fixture |
| `runtime/` | A2 | Runtime build source (from `runtime-prototype/`) |
| `sketch/skill/frappe-ui.md` | A2 | the served skill (nine specifiers) |
| `sketch/signup.py` | B1 | the `sign_up` override |
| `sketch/user_hooks.py` | B1 | `User.validate` username rules |
| `sketch/templates/includes/` | B1 | `signup_form_template` |
| `sketch/signature.py` | B2 | mint and verify |
| `sketch/viewer.py` | B2 | the `/u/<username>/<slug>` page_renderer |
| `sketch/auth.py` | B3 | the `auth_hooks` Sketch Token resolver |
| `sketch/mcp/` | B3 | `http.py`, `rpc.py`, `tools.py` |
| `checkd/` | C1 | the Node `sketch-checkd` service |
| `frontend/` | C2 | the SPA |
| `sketch/api.py` | C2 | whitelisted methods the SPA calls |
| `sketch/recipes/` | D1 | the nine vendored recipe trees |
| `sketch/tests/` | D2 | tests |

## Contract 1 — `sketch.prototype` (A1 writes; B2, B3, C2 call)

```python
def slugify(title: str) -> str:
    """Lowercase, [a-z0-9-], no doubled or trailing hyphen. Raises if empty."""

def newest_pin() -> str:
    """The newest version folder name under sketch/public/runtimes/.
    Raises frappe.ValidationError when none is built."""

def create(title: str) -> "Document":
    """Create a Sketch Prototype for the session user. Derives a unique slug
    from title, sets pin to newest_pin(). Does not create the directory."""

def resolve_public(username: str, slug: str):
    """Look a Prototype up by User.username and slug with ignore_permissions.
    Returns the Document, or None. The Viewer's only lookup. Never throws for
    a missing row."""

def resolve_owned(slug: str):
    """Look a Prototype up by slug for frappe.session.user, permission-checked.
    Raises frappe.DoesNotExistError when there is no such Prototype for this
    user. Every MCP tool and SPA method resolves this way."""

def public_url(doc) -> str:
    """The absolute https://sketch.netchamp.dev/u/<username>/<slug> URL."""
```

## Contract 2 — `sketch.prototype_files` (A1 writes; B2, B3, C2 call)

`name` is always the Prototype's **hash primary key**, never its slug.

```python
def prototype_dir(name: str) -> str:
    """Absolute path to
    sites/<site>/private/files/sketch/<name>. Does not create it."""

def safe_join(name: str, rel: str) -> str:
    """The path guard. Normalise rel, reject absolute paths, reject any '..'
    segment, reject a result that escapes prototype_dir after
    os.path.realpath. Raise frappe.ValidationError on any of them.
    Every agent-supplied path goes through this and nothing else."""

def list_files(name: str) -> list[dict]:   # [{"path": str, "size": int}], sorted by path
def read_files(name: str, paths: list[str]) -> list[dict]:  # [{"path", "content"}]
def write_files(name: str, files: list[dict]) -> list[str]  # files: [{"path","content"}] -> paths written
def edit_file(name: str, path: str, old_string: str, new_string: str) -> None
    """old_string must occur exactly once. Raise frappe.ValidationError with a
    readable message on zero matches and on more than one."""
def delete_file(name: str, path: str) -> None
def read_tree(name: str) -> dict[str, str]:
    """{relative path: source} for the whole tree. Best effort: a file that
    vanishes between the walk and the read is skipped, not an error.
    Returns {} when the directory does not exist."""
def delete_tree(name: str) -> None   # on_trash. Never raises for a missing directory.
```

## Contract 3 — `sketch.signature` (B2 writes; B3 calls `mint`)

```python
def mint(prototype_name: str, ttl_seconds: int = 60) -> dict:
    """Returns {"exp": <int unix seconds>, "sig": <hex str>}."""

def verify(prototype_name: str, exp, sig) -> bool:
    """True only for an unexpired signature over this exact hash id.
    Never raises. A malformed exp or sig is False, not an error."""
```

Algorithm, fixed:

```python
secret = frappe.utils.verified_command.get_secret()
message = f"{prototype_name}:{exp}"
sig = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
```

Compare with `hmac.compare_digest`. The signature covers the hash id, so a
renamed slug or username signs nothing (spec 7.2).

## Contract 4 — the Runtime data slot (A2 stamps; B2 substitutes; A2's boot.js reads)

`build.sh` stamps into each per-Pin `viewer.html` this **exact** line:

```html
<script id="sketch-data" type="application/json">SKETCH_DATA</script>
```

The renderer reads the file and does one `str.replace("SKETCH_DATA", payload, 1)`.
No Jinja, no template engine, no rebuild from `manifest.json` (spec 6.1).

Payload, a single JSON object:

```json
{
  "files":     { "src/App.vue": "<source>", "src/router.ts": "<source>" },
  "name":      "<hash primary key>",
  "title":     "Issue tracker",
  "slug":      "issue-tracker",
  "pin":       "1.0.0-beta.55",
  "is_public": false,
  "is_owner":  true,
  "theme":     "light"
}
```

`theme` is always resolved to `"light"` or `"dark"`, never `"system"` (spec 12).

**The serialiser escapes `<` as `\u003c`** before substitution. `frappe.as_json`
does not do it. Escape `>` and `&` too while you are there. This is trap 1 and
the single most likely thing to be missed.

## Contract 5 — the `sketch-checkd` wire (C1 serves; B3 calls)

`POST http://127.0.0.1:8010/check`, `Content-Type: application/json`.

Request:

```json
{ "url": "http://127.0.0.1:8007/u/<username>/<slug>?theme=light&exp=<ts>&sig=<hex>",
  "host": "sketch.localhost",
  "screenshot": true }
```

`host` is sent as the HTTP `Host` header on every request the browser makes
(trap 14). The caller never sends the public hostname.

The `url` and `host` above show the beta site, `sketch.localhost` on port 8007.
A test run never uses them. It uses the test site, `sketch-test.localhost` on
port 8017, and the test builds both values from the site it runs on. See
CONTEXT.md.

Response, HTTP 200:

```json
{ "status": "ok | errors | compile-failed | link-failed | boot-failed | empty",
  "errors":   [ {"kind","file","line","column","message"} ],
  "warnings": [ {"kind","file","message"} ],
  "consoleErrors": [],
  "routes":  ["/", "/about"],
  "skipped": [ {"route": "/issue/:id", "reason": "route takes a parameter"} ],
  "timings": {"compileMs": 55, "mountMs": 55, "tailwindMs": 302},
  "screenshots": [ {"route": "/", "png_base64": "..."} ] }
```

On its own failure checkd returns HTTP 200 with `status: "boot-failed"` and one
entry in `errors`, so the agent always gets a readable answer. It returns 5xx
only when the request itself is malformed.

`skipped` is never omitted. A silent cap reads as "everything is fine" (trap 12).

## Contract 6 — hook entries

You do not write these. Report the ones you need, in this shape, in your final
report:

```python
doc_events = {"User": {"validate": "sketch.user_hooks.validate_username"}}
page_renderer = ["sketch.viewer.SketchViewerRenderer"]
auth_hooks = ["sketch.auth.validate_sketch_token"]
override_whitelisted_methods = {"frappe.core.doctype.user.user.sign_up": "sketch.signup.sign_up"}
home_page = "sketch"
signup_form_template = "sketch/templates/includes/signup_extra.html"
fixtures = ["Role"]
```
