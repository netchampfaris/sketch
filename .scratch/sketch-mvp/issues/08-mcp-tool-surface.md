# Define the MCP tool surface and server instructions

Type: grilling
Status: resolved
Blocked by: 

## Question

Decide the exact tool list, arguments, and return shapes: list_prototypes, create_prototype (name, pin), read_files, write_files (many files per call), delete_file, check, get_skill, set_public. Decide the server instructions text: call get_skill first, write freely, call check once at the end of each user request. Decide destructive annotations. Builder's tools are the reference.

## Answer

Resolved 2026-08-26 with Faris. Reference: Builder's `builder/ai/mcp/`
on branch `forge/mcp-server` (ticket 09).

### Tool surface: 11 tools

| Tool | Arguments | Returns | Annotation |
|---|---|---|---|
| `list_prototypes` | — | id, name, slug, pin, is_public, url per Prototype | readOnly |
| `create_prototype` | `name` (required) | the Prototype record | — |
| `list_files` | `prototype` | path and size per file, no content | readOnly |
| `read_files` | `prototype`, `paths[]` | path and content per file | readOnly |
| `write_files` | `prototype`, `files[{path, content}]` | paths written | — |
| `edit_file` | `prototype`, `path`, `old_string`, `new_string` | ok, or a no-match error | — |
| `delete_file` | `prototype`, `path` | ok | **destructive** |
| `check` | `prototype`, `screenshot` (bool) | compile errors, console errors, images | readOnly |
| `get_skill` | `prototype` | the full skill for that Pin, one blob | readOnly |
| `set_public` | `prototype`, `is_public` | the Prototype record | **destructive** |
| `set_name` | `prototype`, `name` | the Prototype record | — |

`delete_prototype` is **not** in the surface. Deleting is a human act in the
Sketch UI. A confused agent must not be able to destroy a user's work behind
one permission prompt.

`create_prototype` takes **no `pin`**. Launch supports only the newest
`1.0.0-beta.x`, so the server picks it and records it. One less argument the
agent can get wrong.

`name` is **required** on `create_prototype`. No "Untitled". The slug is
derived from the name at creation and frozen, so a good name up front is
what keeps the URL honest.

### Identity and URLs

- Every user picks a unique **Username** at signup.
- A Prototype's **Slug** is derived from its name at creation and never
  changes. Unique per Username.
- Public URL: `sketch.netchamp.dev/<username>/<slug>`. Root level, no
  prefix.
- `set_name` changes the display name only. The slug and the URL stay put,
  so a shared link never dies.
- Tools address a Prototype by its slug, scoped to the authenticated user.
- `create_prototype` returns the record as **structured fields**, never
  prose. Builder's `create_page` returns prose and every caller has to
  regex `id=(page-[0-9a-f]+)` out of it.

Root-level usernames need a reserved list, because they sit next to
Frappe's own routes: `app`, `api`, `assets`, `files`, `private`, `login`,
`method`, `mcp`, `sketch`, `me`, `settings`, `new`, `p`, `u`, plus every
Website Route on the site. Sketch must also enforce the username itself:
Frappe's `User.username` is `Data`, `unique: 1`, but `validate_username`
(`frappe/core/doctype/user/user.py:766-781`) only calls `msgprint` on a
collision and then sets `self.username = ""`. A user can end up with no
username at all.

Rejected: per-user slug as the tool argument (rename breaks links, agent
can invent a slug); opaque id in the URL (unreadable, and it does not
support browsing by user later); subdomain per user (wildcard DNS, tunnel
route and TLS certificate).

### `write_files` plus `edit_file`

Prototype files live on Sketch's server, so the client agent has no local
disk and no Edit tool to point at them. With `write_files` alone, every
tweak re-sends the whole file: a frappe-ui page SFC is 150-300 lines, about
2-4k tokens, so ten iterations cost 20-40k tokens in rewrites.

`edit_file` takes an exact `old_string` that must match once. It cuts
iteration cost by roughly 10x on a large SFC. Accepted cost: a second
concept in the skill, and the no-match failure the agent must recover from
by re-reading.

### `check`

Screenshots are **on request**: `check({ prototype, screenshot: true })`.
Errors are always returned as text.

Faris chose this over attaching screenshots automatically whenever the
error lists are empty. The known risk is that agents skip optional work.
Mitigation, and it must be built: both the tool description and
`INSTRUCTIONS` state the rule as a workflow step, not an option. "Call
`check` with `screenshot: true` once at the end of each user request."

A screenshot costs about `(width x height) / 750` tokens, so roughly 1,400
at 1280x800. A 5-route Prototype checked ten times is about 70k tokens of
images.

Left to ticket 10: whether `check` is a synchronous MCP call or a job plus
polling, and how routes are enumerated for screenshots.

### Skill delivery

`INSTRUCTIONS` carries only the rules an agent must not get wrong, about
1.2k characters, always in context. `get_skill` returns the full reference
in one blob, fetched once per session.

Sizing: the frappe-ui skill on this box is 4,976 words across 5 files.
Dropping `SETUP.md` (no Vite, no install in a Prototype) leaves about 4,240
words, roughly 8k tokens, plus about 1k of Sketch-specific rules. One blob
at ~9k tokens is cheap once per session.

Rejected: a one-line `INSTRUCTIONS` pointing at the tool (if the agent
skips `get_skill`, nothing in context stops it writing `useList`); a
sectioned `get_skill(topic)` (agents under-fetch, and a missed tokens
section is how off-palette colours get invented).

### `INSTRUCTIONS` text

```
Sketch MCP server: write high-fidelity frappe-ui prototypes that render in the browser.

Workflow: call get_skill first. Then list_prototypes or create_prototype, write the files, and call check with screenshot: true once at the end of each user request. Every tool except list_prototypes and create_prototype takes a `prototype` argument: the slug returned by create_prototype.

A Prototype is Vue SFC files, .ts/.js modules, and a routes.js that declares the pages. The files live on this server, not on your disk. Use write_files for new or rewritten files and edit_file for small changes to an existing one.

There is no server and no backend. Data lives in plain refs inside the prototype files. Never import useList, useDoc, useCall, useDoctype, useNewDoc, createResource, createListResource, createDocumentResource, frappeRequest or call. They will throw.

TypeScript is stripped, not type-checked. Tailwind classes, frappe-ui components and frappe-ui tokens all work; get_skill documents them.

check returns compile errors, console errors, and one image per route when screenshot is true. Fix every error before you report done. delete_file and set_public are annotated destructive, so your client asks before running them.
```

### Kept from Builder

`http.py` and `rpc.py` verbatim (ticket 09): the `McpPageRenderer` at
`POST /mcp`, stateless JSON-RPC, no batching, 401 with the
`WWW-Authenticate` header for OAuth discovery. The `TOOLS` dict plus an
`annotations(name)` function reading `READ_ONLY` and `DESTRUCTIVE` sets
(`tools.py:78-137`). Dropped: `ctx.py`, `pages.py`, the block model, the
confirm-gate machinery, and the injected `page` param (Sketch tools declare
`prototype` directly).

### 2026-08-26 — amendment: transport and structured output

Builder's transport is already stateless streamable HTTP (SEP-2575, see the
`rpc.py` docstring): no session ids, no handshake state, `server/discover`
implemented, batching rejected, GET answered 405 with `Allow: POST`,
notifications dropped with 202. `PROTOCOL_VERSIONS = ("2025-06-18",
"2025-03-26")`. Sketch keeps all of this.

Three things Sketch must add rather than copy:

- **`outputSchema` and `structuredContent`.** Builder flattens every result
  to one text blob (`dispatch.py:80`) and decides `isError` by testing
  whether that text starts with `"FAILED"` (`dispatch.py:18`). The decision
  above says `create_prototype` returns structured fields, never prose, so
  it needs the 2025-06-18 structured-output fields. Applies to
  `create_prototype`, `list_prototypes`, `list_files`, `read_files`,
  `check` and `set_public`.
- **Validate the `MCP-Protocol-Version` request header.** The string appears
  nowhere in Builder's `mcp/`.
- **Confirm the current protocol revision** before the copy lands.
  `2025-06-18` is the newest Builder knows. Not verified against the spec.

Consequence for ticket 10: there is no SSE and no server-initiated stream,
so `check` cannot send progress notifications. It must either return fast
synchronously or become a job plus a poll tool.
