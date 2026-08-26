# How the Viewer and the checker read a private Prototype's files

Type: grilling
Status: resolved
Blocked by: 12 (resolved — unblocked)

## Question

The Viewer fetches a Prototype's source tree in the browser. Ticket 04 fetched
a `files.json` from disk; ticket 10 kept that. The MVP needs the real thing.

Decide:

- The endpoint the Viewer fetches to get `{ path: source }` for one Prototype,
  and how it is authorised for the owner, for a public link, and for neither.
- How the ticket 10 checker, a headless Chromium with no session, opens a
  **private** Prototype. Options: a short-lived signed URL minted per check, a
  cookie planted in the browser context, or the checker running as the owner
  through the same Sketch Token.
- Whether the Viewer's own HTML is served by a Frappe route per Prototype
  (`/u/<username>/<slug>`) or is one static page that reads the Prototype from
  the URL.
- Where the files live on disk under the site, and what the API does when a
  file has been deleted mid-check.

Ticket 12 decided the doctypes, the role, and that public links serve with
`ignore_permissions` after checking `is_public`. This ticket decides the wire.

## Answer

Resolved 2026-08-27 with Faris. **There is no files endpoint.** The Viewer's
HTML carries the source tree, the renderer is the only door, and the checker
opens the real URL with a 60-second signature.

### The renderer serves the pinned Runtime's own `viewer.html`

The `page_renderer` on `/u/<username>/<slug>` reads
`sketch/public/runtimes/<pin>/viewer.html` from disk and substitutes one slot.

This works because **`sketch/public/runtimes/` is gitignored build output**.
Every Runtime folder is regenerated from app source on deploy, and `build.sh`
already stamps a per-Pin copy of one source `viewer.html`
(`sed "s#RUNTIME#$BASE#g"`). The build gains a second placeholder: a
`<script id="sketch-data" type="application/json">` slot.

So the document is shared in **source**, at build time, and versioned with the
Pin at **runtime**. A Runtime that needs a different document ships its own,
and no shared-template problem exists.

Rejected: a Jinja template in app source that rebuilds the document from
`manifest.json`. It makes one document serve every Pin at runtime, and it
makes the renderer re-derive the import map and the stylesheet links that the
build already wrote correctly. `manifest.json` keeps its one job: telling the
SPA what the assets are.

Rejected: a static page plus a files endpoint. It splits one authorisation
across two doors, adds a request before the compiler can start, and gives a
private Prototype a Viewer shell that then fails inside the iframe, which
breaks ticket 12's 404-not-403 rule at the only place a user sees it.

### The files ship inside the page

The slot carries the whole tree as `{ path: source }`, plus `name`, `title`,
`pin`, `is_public`, whether the caller is the owner, and the resolved theme.
`boot.js` reads it from the DOM instead of `fetch('./files.json')`.

Measured: the sample Prototype is 7 files, 7.9 KB of source. Ticket 10's large
case, 30 files, is about 34 KB. Not a payload worth a second request.

**Must be built: the serialiser escapes `<` as `\u003c`.** Every Vue SFC with a
script block ends with `</script>`, which closes the JSON block early and
breaks the Viewer on the most ordinary file a Prototype can contain.
`frappe.as_json` does not do it.

### Headers

- `Cache-Control: no-store`. The files are in the page and change with no
  version to key on. The Runtime assets under `/assets/` are unaffected and
  stay cacheable forever, because the Pin is in the path.
- `Content-Security-Policy: frame-ancestors 'self'`. Frappe sets no
  `X-Frame-Options` and no CSP, so left alone any site could embed a
  Prototype. The Studio iframe is same-origin and still works. Public links
  open top-level, which is the shape ticket 14 chose. Opening this later is
  one header.

### Who gets served

```
path does not resolve to a Prototype  -> 404
is_public                             -> serve
caller is the owner                   -> serve
valid unexpired signature             -> serve
otherwise                             -> 404
```

One line longer than ticket 12 left it. A bad or expired signature is **not an
error**: it falls through, so a stale link to a public Prototype still works
and a private one still 404s.

### The checker opens the real URL with a signature

The MCP `check` handler signs `<hash id>:<exp>`, 60 seconds, with Frappe's own
secret (`verified_command.get_secret()`, so `site_config.secret` or the
encryption key, so no new secret to manage).

```
http://127.0.0.1:8007/u/faris/dashboard?theme=light&exp=1756312800&sig=9f3c…
```

`sketch-checkd` changes not at all: ticket 10's prototype already takes a URL
and navigates it. It reaches **`127.0.0.1:8007` with a `Host: sketch.localhost`
header**, never the public hostname. The tunnel goes out to Cloudflare and
back for every route in the walk, and ticket 10's 913 ms was measured against
localhost:8007.

Four properties:

- The signature covers the **hash id**, not the URL. Rename a slug or a
  username and an old signature signs nothing.
- `theme` is outside the signature. It picks a stylesheet, not a permission,
  so `check` forces light without re-signing.
- Frappe's own `verify_request` is unusable here: it calls
  `respond_as_web_page` on a bad signature, which is a rendered error page,
  not a 404. And `get_signed_params` **carries no expiry**, so the expiry is a
  signed parameter Sketch adds and checks itself.
- Prototype code can read the signature from `location`. It unlocks only the
  Prototype that code is already inside.

Rejected: **a planted session cookie**. Frappe sets `sid` with
`httponly=True` (`auth.py:407`), so Prototype code could not read it. But it
grants the whole site as the owner to run one screenshot, and leaves a session
to delete on every path including the failures. Same effort, far more granted.

Rejected: **the Sketch Token**. The `auth_hooks` function refuses every path
except `/mcp`, and ticket 12 called that load-bearing. Widening it destroys the
reason `Sketch Token` was chosen over Frappe's `api_key` at all.

Rejected: **the worker hands `sketch-checkd` the rendered HTML**, fulfilled
through `page.route`. It needs no credential, which is why it looks best. But
the browser never visits the real URL, so the renderer is untested by `check`,
including the `</script>` escaping above, which is exactly the class of
failure `check` exists to catch.

### On disk

`sites/sketch.localhost/private/files/sketch/<hash>/`, as ticket 12 said.
Checked before accepting it:

- Frappe's `/private/files/` route refuses Guests outright, then refuses any
  path with no `File` doc (`response.py:296`). Prototype files have no `File`
  doc, so that route cannot serve them.
- There is **no orphan-file sweeper** in Frappe's scheduler. Nothing deletes
  files under `private/files` for lacking a `File` doc.

### The renderer decides "may you see this". Nothing else.

Every fact about the tree is the Viewer's to report, because `check` reads the
Viewer, not the renderer. A missing `App.vue` returned as an HTTP error is
invisible to the agent; the same fact as a `boot.js` error reaches it through
the channel that already exists.

| Case | Result |
|---|---|
| Doc exists, directory missing | Serve. Viewer reports `empty` |
| Directory exists, no `src/App.vue` | Serve. Viewer reports one clear error |
| A file vanishes between the walk and the read | Skip it. One walk, best effort |
| `pin` names a Runtime folder not on disk | 500 with a readable message, not the Viewer |

The last is the exception, and ticket 12 already called it a must-build: fail
loudly, never a blank iframe.

### Usernames are frozen at signup

`User.username` is an ordinary editable field. Nothing in Frappe freezes it and
nothing rewrites links when it changes, and the username is in every public
link.

Sketch makes it read-only after signup. The case this kills: you rename, a
stranger takes your old name, and your old public link keeps working while
showing **their** Prototype. That is worse than a 404.

Rejected: rename with the old name retired forever. It fixes the takeover but
needs a table of retired names, the third doctype ticket 12 turned down, to
buy a rename in a product with three screens.

Cost, plainly: a typo at signup is permanent and the fix is a manual database
edit. Mitigation is showing the live URL shape under the field as the user
types it.

### Runtime work this forces

Four changes to what ticket 04 delivered. The first is required by this
ticket; the rest were agreed alongside it, because an agent writes them
without thinking and today each fails with a message that does not explain
itself.

1. `boot.js` reads the tree from the DOM, not `fetch('./files.json')`.
2. The blob-URL linker becomes a module registry, so **import cycles work**.
   Ticket 04's `cycle` error goes away.
3. **`.css` imports** are injected as a stylesheet instead of resolving to
   `undefined`.
4. A precondition check on `src/App.vue`, and a new status **`empty`** for a
   Prototype with no files. A brand-new Prototype is in that state until a
   recipe or the agent writes to it.

Deliberately not changed: the Runtime still owns the mount. A Prototype that
owns `createApp` can skip `FrappeUIProvider`, skip the error handler, or never
call `mount`, and then `check` reports nothing useful.

### Considered and ruled out: a real Vite dev server in the browser

Faris asked. Verified against the installed code: Vite 8.2.2's export map has
one entry, `./dist/node/index.js`. It depends on `rolldown` and
`lightningcss`, and both ship as **native `.node` binaries**. Neither runs in a
browser. "Vite in the browser" means "Node in the browser", which means
WebContainers.

It would buy real fidelity: `main.ts`, history routing, asset imports, any npm
package, and real HMR. It costs: Node boot plus `npm install` per Prototype
instead of a measured 426 ms; ticket 10's 913 ms voided; a public read-only
link that boots a Node VM; previews on `*.webcontainer.io` with a domain that
changes per session; and a licence question, since production commercial use
needs one and Sketch is open signup on a public URL.

Not in the MVP. It voids tickets 04, 05, 06 and 10, so it is a restart, not a
ticket. On the map as a post-MVP direction.
