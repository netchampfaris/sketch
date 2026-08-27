# Sketch MVP: specification

Sketch is hosted at `sketch.netchamp.dev`. Anyone signs up. Their own agent
connects over MCP and writes high-fidelity frappe-ui prototypes. Sketch has no
agent panel of its own.

This spec is assembled from the resolved wayfinder tickets in
`.scratch/sketch-mvp/issues/`. Every decision here is closed. Where two tickets
disagree, this file carries the later one; the superseded text stays in the
ticket for the reasoning. Read a ticket when you want the argument, read this
file when you want the answer.

Terms are in `apps/sketch/CONTEXT.md`.

**Build this without making new decisions.** Section 14 lists the traps that
have already cost time once. Section 15 gives a build order.

---

## 1. Environment

Already built and running. Do not re-create it.

| Item | Value |
|---|---|
| Bench | `/home/faris/benches/sketch-bench` |
| Frappe | `develop` at `0219b22` |
| Python | 3.14.6 (uv), bench 5.31.0 |
| Site | `sketch.localhost`, MariaDB 10.11, `developer_mode` 1 |
| App | `apps/sketch`, branch `forge/mvp` |
| Ports | web 8007, socketio 9007, redis cache 13007, redis queue 11007, file watcher 6797, Vite dev 8087 |
| Passwords | `sites/sketch.localhost/site_config.json` (git-ignored) |
| Public URL | `https://sketch.netchamp.dev`, site `host_name` set |

Frontend pins, exact: frappe-ui `1.0.0-beta.55`, vue 3.5.41, vue-router 4.6.4,
vite 8.2.2, `@vitejs/plugin-vue` 6.0.8, tailwindcss 3.4.19, typescript 5.9.3,
yarn 1.22. `frontend/src/style.css` imports `frappe-ui/style.css` only; beta.55
already ships the `@tailwind` layers.

### Services

- `sketch-bench.service`, a systemd **user** unit, enabled, linger on. Restart
  with `systemctl --user restart sketch-bench.service`. Logs in
  `journalctl --user -u sketch-bench.service` and `sketch-bench/logs/`.
- The `Procfile` has **no `watch`**. Rebuild the frontend by hand:
  `cd apps/sketch/frontend && yarn build`.
- **New: `sketch-checkd.service`**, a second user unit next to it. Section 7.
- Scheduler is enabled. **Nothing is backed up.** The backup cron was deleted
  on purpose: it was database-only, and Prototype files live on disk, so it
  would restore rows with no files behind them. Do not add it back.

### Tunnel

Ingress in `~/.cloudflared/config.yml`: `^/socket.io` to `127.0.0.1:9007`,
everything else to `127.0.0.1:8007`, both with
`httpHostHeader: sketch.localhost`. The `http_status:404` catch-all stays last.
Never print or commit anything under `~/.cloudflared`.

### SMTP is a setup step, and it is not optional

Signup verification is a password-reset link sent by mail. With no outgoing
Email Account, `sign_up` still returns HTTP 200 and a green success banner, and
only an Error Log records the failure. Without SMTP every new user is stuck
with no way to see why. Configure an Email Account before opening signup.

---

## 2. Data model

**Two doctypes. Nothing else.** Files and Runtimes live on disk, and no row
describes them.

### `Sketch Prototype`

`autoname: hash`. Unique index on `(owner, slug)` through
`frappe.db.add_unique` (`database.py:1401`).

| Field | Type | Notes |
|---|---|---|
| `owner` | built-in | Frappe sets it. Drives `if_owner`. No separate `user` Link. |
| `title` | Data, reqd | Display name. `set_name` writes here. `name` is reserved (`model/__init__.py:86`). |
| `slug` | Data, reqd, read-only | Derived from `title` at creation. Frozen. |
| `pin` | Data, reqd, read-only | The frappe-ui version string. |
| `is_public` | Check, default 0 | |

No `url`, `file_count` or `size` field. All three are derived from disk, and a
stored copy drifts.

`on_trash` deletes the Prototype's directory. Without it, orphan directories
build up.

### `Sketch Token`

- One token per user. Header `Authorization: Bearer sk_...`.
- Stored in a Frappe `Password` field, encrypted at rest, read back with
  `get_decrypted_password`. Retrievable, not hashed: Settings shows the real
  token and a working connect snippet, always, plus one Regenerate button.
- Resolved by one function registered in `auth_hooks` (`auth.py:772-774`),
  which runs after core's own auth attempts.
- **The hook refuses every path except `/mcp`.** This is load-bearing. It is
  the whole reason `Sketch Token` was chosen over Frappe's `api_key`, which
  authenticates every Frappe endpoint. Widening it destroys the decision.
- Regenerate is a write, not a delete.

Cost, stated plainly: anyone with Desk read on `Sketch Token`, or a database
dump plus `site_config.json`, reads every user's token in the clear. That is
acceptable only while the token reaches `/mcp` and nothing else.

### Files: an on-disk tree

```
sites/sketch.localhost/private/files/sketch/<hash>/
  src/
    components/
    pages/
    App.vue
    router.ts
```

`<hash>` is the Prototype's **primary key**, never its slug. Slug is unique per
owner only, so two users with `dashboard` would share a directory.

There is **no `Sketch File` doctype**. Disk is the only truth. `list_files`
walks the tree. Every `path` argument in an MCP call is a full relative path
such as `src/pages/Home.vue`.

Two facts back this location: Frappe's `/private/files/` route refuses Guests
outright and then refuses any path with no `File` doc (`response.py:296`), and
no scheduled job sweeps `private/files` for orphans.

**Must be built: a path guard on every agent-supplied path.** `write_files` and
`edit_file` take paths from the agent. Reject `../` and absolute paths before
touching disk.

### Runtime: a folder, no doctype

Runtimes ship with the app at `sketch/public/runtimes/<version>/` with a
`manifest.json`. `pin` is a plain `Data` field holding the version string.
`create_prototype` reads the newest version off disk. The second frappe-ui
version is when a doctype earns its place, not now.

### Permissions

Role **`Sketch User`**, `user_type = Website User`, assigned at signup.

| Doctype | `Sketch User` |
|---|---|
| `Sketch Prototype` | create, plus read/write/delete with `if_owner` |
| `Sketch Token` | create/read/write with `if_owner`. No delete. |

`if_owner` makes Frappe add `owner = <user>` to every list query
(`db_query.py:1647-1659`), so `list_prototypes` and the SPA list are scoped
without Sketch writing a filter.

**Guest gets nothing** on either doctype. Public links are served by the Viewer
renderer alone, which reads the Prototype with `ignore_permissions=True` and
then applies the rules in section 6.

A `has_permission` hook cannot do this. Those hooks run after role permissions
and can only restrict (`permissions.py:499-505`).

**A private or missing Prototype returns 404, not 403.** A 403 confirms the URL
exists, which leaks that a user has a Prototype by that name.

Files inherit no Frappe permission, because they have no doctype. Every file
read or write resolves the Prototype through the permission-checked path first,
then touches disk.

---

## 3. Signup, username, roles

### Open signup is two settings

- Website Settings `disable_signup`, a Check that **defaults to 1**. Set it
  to 0.
- System Settings `max_signups_allowed_per_hour`, default 300.
- `disable_user_pass_login` only hides the form. It does not gate `sign_up`.

### Verification is the password-reset link

There is no separate verify-email token. The welcome mail carries
`/update-password?key=<plaintext>`; only the SHA-256 hash is stored. The link
expires after `reset_password_link_expiry_duration`, default 1200 s. Clicking
it sets the password and logs the user in.

### Role assignment

A new signup gets `user_type = "Website User"` (hardcoded) and the one role in
**Portal Settings `default_role`**. Set that to `Sketch User`.

**The `Sketch User` role fixture must set `desk_access = 0`.** `Role.desk_access`
defaults to 1, and `add_roles()` calls `save()`, so `set_system_user()` flips
the new user to System User during signup.

### Username

Sketch uses Frappe's `User.username`. No second field.

Format: **3-30 characters, `[a-z0-9-]`, starts with a letter, no doubled or
trailing hyphen, lowercase-normalised.** There is **no reserved list**; it was
dropped when URLs moved behind `/u/`, and no name matching that pattern can
collide with anything behind a prefix.

Enforcement is a `doc_events` hook on `User.validate`. `Document.hook`'s
`compose` runs the doc's own method first, then app hooks
(`document.py:2079-2090`), so the Sketch hook sees the value core already
blanked and throws.

Three things the hook must get right:

- **Scope it to Website Users.** It fires on every User save site-wide, so an
  unscoped throw breaks Desk user management.
- Core's `validate_username` (`user.py:766-781`) puts its `msgprint` and
  `suggest_username` inside `if self.user_type == "System User"`. For a Website
  User a collision blanks the username with **no message at all**.
- Core auto-fills `username = frappe.scrub(first_name)` when it is empty. The
  hook must not read an auto-derived value as user intent, and signup must set
  `username` explicitly so the auto-fill never runs.

**Usernames are frozen at signup.** `User.username` is read-only afterwards.
The case this kills: a user renames, a stranger takes the old name, and the old
public link keeps working while showing **their** Prototype. That is worse than
a 404. Cost: a typo at signup is permanent and the fix is a manual database
edit. Mitigation: show the live URL shape under the field as the user types.

### Collecting the username at signup

Core's `sign_up(email, full_name, redirect_to)` has a fixed signature and no
hook adds a field.

- Use `override_whitelisted_methods` to point
  `frappe.core.doctype.user.user.sign_up` at a Sketch method that also takes
  `username`. It is honoured on every entry path the login page uses.
- The override **must carry type annotations**
  (`require_type_annotated_api_methods = True` is already set in `hooks.py`).
- The override **must re-implement core's guards**: `is_signup_disabled()`, the
  hourly throttle, the existing-user branches, and
  `flags.ignore_password_policy`.
- Pair it with the `signup_form_template` hook for the input markup only. That
  hook adds markup and nothing else: core's `login.js` submit handler still
  sends three arguments, so the Sketch template must rebind the submit handler
  after `frappe.ready`. **Treat the rebind as the fragile part.** Core's
  `login.js` is not a stable API and changed shape between version-16 and
  develop.

### Landing on the SPA

`website_route_rules` **cannot claim `/`**: the resolver skips the map while
the path is `index`. Only `get_home_page()` decides what `/` renders.

- Use the `home_page` hook in `sketch/hooks.py`, or `add_to_apps_screen` with
  `route: "/"` so `get_default_path()` wins.
- Leave `User.default_workspace` unset. It overrides everything.
- `public/index.html` is never served.
- The scaffold currently serves the SPA at `/sketch` through
  `website_route_rules`. Moving it to `/` is implementation work in this spec.

Riding `develop` instead of `version-16` costs nothing here. Signup, roles,
`user_type` and landing are identical on both.

---

## 4. Routing

| Path | Served by |
|---|---|
| `/` | the SPA, through the `home_page` hook |
| `/u/<username>/<slug>` | the Viewer `page_renderer` (section 6) |
| `/mcp` | the MCP `page_renderer` (section 8) |
| `/assets/sketch/runtimes/<version>/…` | Frappe's existing assets symlink |

Custom `page_renderer` hooks run **first** inside `PathResolver.resolve()`,
ahead of `StaticPage`, `WebFormPage`, `DocumentPage`, `TemplatePage`,
`PrintPage` and `ListPage` (`path_resolver.py:55-64`). Frappe handles `/api/`,
`/backups`, `/private/files/` and `/.well-known/` earlier still
(`app.py:96-113`).

Prototype URLs sit behind `/u/` and not at the root. The root is not safe to
hand to usernames: because Sketch's renderer wins, an existing user would
shadow a **new core route**, so a user named `dashboard` would take
`/dashboard` away from the whole site, silently. `/u/` removes that class of
problem for two characters and keeps `/<username>` free for the browse page
already deferred.

`set_name` changes `title` only. The slug and the URL never move, so a shared
link never dies.

---

## 5. The Runtime

One shared browser bundle per supported frappe-ui version. Built by
`yarn build`, gitignored, shipped with the code.

Port the working Runtime from branch `forge/proto/04-runtime-bundle`, folder
`runtime-prototype/`, at commit `a4a932d`. It renders, and its numbers below
are measured, not estimated. Section 5.6 lists the changes it still needs.

### 5.1 Layout

`sketch/public/runtimes/<version>/`, served at
`/assets/sketch/runtimes/<version>/`.

```
frappe-ui.js  frappe-ui-list.js  frappe-ui-editor.js
frappe-ui-charts.js  frappe-ui-icons.js  dayjs.js
vueuse.js                                  # new, see 5.3
<shared chunks: Button, Tooltip, useId, useColorScheme, …>
vue.js  vue-router.js                      # esm-browser.prod, copied
frappe-ui.css  frappe-ui-components.css    # layer 1 + SFC styles
Inter.var.woff2
compiler.js  tailwind.js                   # the two compilers
viewer.html  boot.js  manifest.json
```

`manifest.json` names the assets, the import map, the stylesheets, and every
asset's raw and gzip size. The SPA reads it, so no filename is hard-coded.
Keep its one job: telling the SPA what the assets are. The renderer does not
read it.

`host.html` and `files.json` are prototype-only. Delete both, and delete
`make-files-json.mjs` with them (section 6).

### 5.2 Two CSS layers

1. Precompiled frappe-ui internals CSS, 46 KB gzip, loaded eagerly. Components
   are styled at first paint.
2. The in-browser Tailwind engine, for the utility classes a Prototype writes.

### 5.3 The import map

Static, written into `viewer.html` by the build. **Nine bare specifiers resolve
and nothing else**, plus two internal `sketch:` entries.

| Specifier | Asset |
|---|---|
| `vue` | `vue.js` |
| `vue-router` | `vue-router.js` |
| `frappe-ui` | `frappe-ui.js` |
| `frappe-ui/list` | `frappe-ui-list.js` |
| `frappe-ui/editor` | `frappe-ui-editor.js` |
| `frappe-ui/charts` | `frappe-ui-charts.js` |
| `frappe-ui/icons` | `frappe-ui-icons.js` |
| `dayjs` | `dayjs.js` |
| `@vueuse/core` | **to build** |
| `sketch:compiler` | `compiler.js` |
| `sketch:tailwind` | `tailwind.js` |

`vue` and `vue-router` are external to the frappe-ui build, so the Prototype,
frappe-ui and vue-router share one Vue instance.

**Each frappe-ui export subpath needs its own asset.** `frappe-ui/list` is not
in the root barrel. Rollup splits the shared chunks, so `Button`, `Tooltip`,
`useId`, `dayjs` and `useColorScheme` exist once across the entries. The editor
and charts download only when a Prototype imports them.

`@vueuse/core` **14.4.0** is the ninth specifier, added because the Compose
recipe imports it. Version tracks frappe-ui's own dependency
(`@vueuse/core ^14.1.0`), never a separately chosen one. Whole barrel, minified
ESM with `vue` external: 135 KB raw, 49 KB gzip, and lower in practice because
frappe-ui already pulls part of it. It downloads only when a Prototype imports
it.

`frappe-ui/experimental` is **not** in the map. `Accordion`, `Calendar`,
`FloatingWindow`, `MultiEmailInput` and `CodeEditor` are unavailable.

**Adding a specifier touches four places**: the Runtime build entry,
`manifest.json`, the `viewer.html` import map, and the skill's own list of what
resolves. `sketch/tests/test_skill_names.py` exists to catch that drift.

### 5.4 The compilers

`@vue/compiler-sfc` (esm-browser) plus `sucrase` for type stripping. The same
pair as `@vue/repl`, whose `src/transform.ts` is the working reference. Sketch
owns about 100 lines of glue: parse, `compileScript`, `compileStyleAsync`, TS
strip, import rewrite, style injection.

Rules the glue must follow:

- **Check `parse().errors` first and stop on any error.** With
  `compileScript({ inlineTemplate: true })`, template expression errors do not
  throw. The compiler emits invalid JS and the failure surfaces later as a
  sucrase error at a generated-code position.
- **Use `compileTemplate` when the descriptor has neither `script` nor
  `scriptSetup`.** `compileScript` needs a script block, so a template-only SFC
  throws "SFC contains no `<script>` tags".
- Call sucrase with `transforms: ['typescript'], disableESTransforms: true`.
  Without the flag it rewrites class fields and optional chaining to helpers
  that evergreen browsers do not need.
- Set `filePath` on the sucrase call so the file name lands in the error.
- Surface every error as `file:line:col message`.

Accepted costs: sucrase drops `export namespace` blocks silently and treats
`const enum` as `enum`; Sketch strips types only, so neither matters. Sucrase
is in maintenance mode. If it stalls, `esbuild-wasm` is a drop-in for the strip
step with the same call shape.

TypeScript is stripped in the browser, never type-checked.

### 5.5 Tailwind at runtime

Self-host the MIT `tailwindcss@3.4` engine in the browser with the frappe-ui
preset. Nothing else runs that preset: it is code, with four plugins using
`addComponents`, `@apply`, `matchUtilities` and `<alpha-value>` colours. twind
and UnoCSS drop `text-sm-medium`, `focus-ring`, `prose-v3` and `.form-input`.
The Play CDN runs it but is proprietary and served only from
`cdn.tailwindcss.com`, so it fails self-hosting. A safelist can never cover
`w-[13px]`.

The engine needs the Node shims in `runtime-prototype/tailwind/shims/`.
`make-lucide-map.mjs` writes all 2,035 lucide icons as data URIs at build time;
the map is generated, never committed. Classes added after first paint get
styles. Arbitrary values work.

### 5.6 Changes the ported Runtime still needs

1. **`boot.js` reads the source tree from the DOM**, not `fetch('./files.json')`.
   The renderer fills a `<script id="sketch-data" type="application/json">`
   slot. Delete `files.json` and `make-files-json.mjs`.
2. **`build.sh` gains a second placeholder.** It already stamps a per-Pin
   `viewer.html` with `sed "s#RUNTIME#$BASE#g"`. It now stamps the empty data
   slot too, which the renderer substitutes per request.
3. **The blob-URL linker becomes a module registry**, so import cycles work.
   Ticket 04's `cycle` error goes away, and so does ticket 10's cycle case.
4. **`.css` imports are injected as a stylesheet.** Today `import './style.css'`
   resolves to a blob that does not exist and rewrites to `undefined`.
5. **A precondition check on `src/App.vue`, and a new status `empty`** for a
   Prototype with no files. Today a missing `App.vue` becomes
   `import(undefined)` and the agent gets a message about `undefined`, not
   about the file. A brand-new Prototype is `empty` until a recipe or the agent
   writes to it.
6. **Drop the Inter italic face.** 297 KB gzip, half the font payload, for text
   almost no Prototype sets in italic. Removing it is one file and one line in
   `inter.css`. Adding it back is the same.
7. **Add `@vueuse/core`** to the build entry, the manifest, the import map and
   the skill (section 5.3).

Deliberately unchanged: **the Runtime owns the mount**. A Prototype that owns
`createApp` can skip `FrappeUIProvider`, skip the error handler, or never call
`mount`, and then `check` reports nothing useful.

### 5.7 The mount contract

A Prototype ships **no entry file**. `boot.js` imports `src/App.vue` and the
routes from `src/router.ts`, creates the **hash-mode** router, and calls
`createApp(App).use(router).use(FrappeUI)` with `FrappeUIProvider` mounted.

So `src/router.ts` exports a **routes array**, not a router. The skill says so.

Linking: compile every file, resolve relative specifiers (`.ts`, `.js`, `.vue`,
`/index.*`), register each module, and leave bare specifiers to the import map.

`FrappeUIProvider` is not optional. Without it `dialog.confirm()` and
`toast.success()` do nothing, report no error, and `check` says `ok`.

### 5.8 The `upload_file` stub

`/api/method/upload_file` is the only endpoint any frappe-ui component calls on
its own: `FileUploader`, the editor's `media-upload-engine.ts`, and the
TextEditor paste extension. Nothing else needs stubbing.

**It goes over `XMLHttpRequest`, not `fetch`.** Both call sites
(`src/utils/fileUploadHandler.ts:134`, `src/utils/useFileUpload.ts:257`) open
an XHR for upload progress. The Viewer subclasses `XMLHttpRequest` and returns
a data-URL File doc. A `fetch` patch would stub nothing.

### 5.9 What the Runtime reports

`boot.js` sets `window.__sketch` and posts the same object to `parent`:

```json
{ "status": "ok | errors | compile-failed | link-failed | boot-failed | empty",
  "errors": [ { "kind": "compile", "file": "src/pages/About.vue",
                "line": 3, "column": 5, "message": "Element is missing end tag." } ],
  "warnings": [ { "kind": "unresolved-component", "file": "…", "message": "…" } ],
  "consoleErrors": [],
  "routes": ["/", "/about"],
  "timings": { "compileMs": 55, "mountMs": 55, "tailwindMs": 302 },
  "tailwind": {} }
```

It also exposes `window.__sketchGoto(path)` so `check` drives the router
directly, never through the DOM.

Error classes verified against the production build: SFC parse errors, TS
syntax errors, unresolvable relative imports, a bad named import from
`frappe-ui` (`boot-failed`), and Vue runtime errors.

**Unresolved components are recovered without a dev build.** The template
compiler emits `_resolveComponent("Badgee")` for every tag it could not bind to
an import. Scan the generated code for those names, filter them against
`app._context.components` after the plugins install, plus `RouterView` and
`RouterLink`, and report the rest as `warnings`. Zero false positives on the
sample tree.

**Prop type warnings stay lost.** They do not justify a second asset set per
Pin and a `@vue/devtools-api` shim.

**Status is recomputed after the route walk.** A route reached during the walk
can throw, and a status fixed at mount would still read `ok`.

### 5.10 Build traps

- **`define: { 'process.env.NODE_ENV': '"production"' }`** in the Vite lib
  build. Vite does not substitute it in lib mode. reka-ui guards its dev
  warnings with it, so without the define `process` is undefined,
  `DialogContentImpl` throws inside `setup()`, and every Dialog renders as an
  empty comment node.
- **Use `vue-router.esm-browser.prod.js`.** The dev build imports
  `@vue/devtools-api`, which no import map entry covers.

### 5.11 Cost, measured

Headless Chromium on this box, against the live bench.

| Group | gzip |
|---|---|
| Eager render payload | 320 KB |
| The two compilers | 543 KB |
| Inter (roman only) | 262 KB |

Boot to painted: **426 ms**, of which Tailwind's first compile is about 286 ms.
A later batch of 12 new classes compiles in 112-126 ms. The Tailwind engine is
the only step that scales with the Prototype, and layer 1 means the page is
already styled while it runs.

All of it is static, cacheable, and shared by every Prototype on the same Pin.

Not measured: Firefox, Safari, cold cache, a Prototype with 50 files.

### 5.12 A missing Runtime fails loudly

When `pin` names a folder that is not on disk, the Viewer returns **500 with a
readable message**, never a blank iframe.

---

## 6. The Viewer

**There is no files endpoint.** The renderer is the only door, and it carries
the files inside the page.

### 6.1 The renderer serves the pinned Runtime's own `viewer.html`

The `page_renderer` on `/u/<username>/<slug>` reads
`sketch/public/runtimes/<pin>/viewer.html` from disk and substitutes one slot.

This works because `sketch/public/runtimes/` is gitignored build output. Every
Runtime folder is regenerated from app source on deploy, and `build.sh` already
stamps a per-Pin copy of one source `viewer.html`. So the document is shared in
**source**, at build time, and versioned with the Pin at **runtime**. A Runtime
that needs a different document ships its own.

Do not rebuild the document from `manifest.json` in a Jinja template. That
makes one document serve every Pin at runtime and re-derives the import map and
the stylesheet links the build already wrote correctly.

### 6.2 The slot

`<script id="sketch-data" type="application/json">` carries the whole tree as
`{ path: source }`, plus `name`, `title`, `pin`, `is_public`, whether the caller
is the owner, and the resolved theme.

Measured: 7 files is 7.9 KB of source, 30 files is about 34 KB. Not a payload
worth a second request.

**Must be built: the serialiser escapes `<` as `\u003c`.** Every Vue SFC with a
script block ends with `</script>`, which closes the JSON block early and breaks
the Viewer on the most ordinary file a Prototype can contain. `frappe.as_json`
does not do it. This is the single most likely thing to be missed in this
section.

### 6.3 Who gets served

```
path does not resolve to a Prototype  -> 404
is_public                             -> serve
caller is the owner                   -> serve
valid unexpired signature             -> serve
otherwise                             -> 404
```

A bad or expired signature is **not an error**. It falls through, so a stale
link to a public Prototype still works and a private one still 404s.

### 6.4 Headers

- `Cache-Control: no-store`. The files are in the page and change with no
  version to key on. Runtime assets under `/assets/` are unaffected and stay
  cacheable forever, because the Pin is in the path.
- `Content-Security-Policy: frame-ancestors 'self'`. Frappe sets no
  `X-Frame-Options` and no CSP, so left alone any site could embed a Prototype.
  The Studio iframe is same-origin and still works. Public links open
  top-level.

### 6.5 The renderer decides "may you see this". Nothing else.

Every fact about the tree is the Viewer's to report, because `check` reads the
Viewer, not the renderer. A missing `App.vue` returned as an HTTP error is
invisible to the agent.

| Case | Result |
|---|---|
| Doc exists, directory missing | Serve. Viewer reports `empty` |
| Directory exists, no `src/App.vue` | Serve. Viewer reports one clear error |
| A file vanishes between the walk and the read | Skip it. One walk, best effort |
| `pin` names a Runtime folder not on disk | 500 with a readable message |

### 6.6 The iframe

A Prototype renders in a **same-origin iframe**: its own document, its own
global `fetch`, its own stylesheet, its own `window.onerror`. Sketch chrome
stays outside it. Rendering in the SPA window was rejected: patching `fetch`
there would break Sketch's own API calls, prototype Tailwind would collide with
Sketch's stylesheet, and a prototype crash could take the SPA down.

Same-origin means Prototype code can reach `parent` and Sketch's cookies, and
signup is open to anyone. Sandboxing is on the map under Not yet specified. It
is not in the MVP.

---

## 7. `check` and `sketch-checkd`

`check` is **one synchronous MCP call**. There is no server-side compile, no RQ
job, and no poll tool.

```
agent -> POST /mcp  check(prototype, screenshot)
      -> Frappe web worker: HTTP POST 127.0.0.1:8010
      -> sketch-checkd (Node, one Chromium): open the Viewer, read
         window.__sketch, walk the routes, screenshot each
      -> back up the same wire, in one JSON-RPC reply
```

The web worker never runs a browser. It blocks on one local HTTP call.

Port the working service from branch `forge/proto/10-check-step`, folder
`check-prototype/`.

### 7.1 No second compiler

The Viewer already compiles, links, mounts and reports. A compiler on the
server is a second source of truth that can disagree with what the user sees.
`check` opens the Viewer URL and reads `window.__sketch`.

### 7.2 How `check` opens a private Prototype

The MCP handler signs `<hash id>:<exp>`, 60 seconds, with Frappe's own secret
(`verified_command.get_secret()`, so `site_config.secret` or the encryption
key). No new secret to manage.

```
http://127.0.0.1:8007/u/<username>/<slug>?theme=light&exp=<ts>&sig=<hex>
```

`sketch-checkd` reaches **`127.0.0.1:8007` with a `Host: sketch.localhost`
header**, never the public hostname. The tunnel goes out to Cloudflare and back
on every route in the walk, and the numbers below were measured against
localhost.

Four properties:

- The signature covers the **hash id**, not the URL. Rename a slug or a
  username and an old signature signs nothing.
- `theme` sits outside the signature. It picks a stylesheet, not a permission,
  so `check` forces light without re-signing.
- Frappe's own `verify_request` is unusable: it calls `respond_as_web_page` on
  a bad signature, which is a rendered error page, not a 404. And
  `get_signed_params` carries no expiry, so the expiry is a signed parameter
  Sketch adds and checks itself.
- Prototype code can read the signature from `location`. It unlocks only the
  Prototype that code is already inside.

Rejected and not to be revisited: a planted session cookie (grants the whole
site as the owner to run one screenshot), the Sketch Token (the `auth_hooks`
path scope is load-bearing), and fulfilling the HTML through `page.route` (the
browser never visits the real URL, so the renderer and the `<` escaping go
untested by the one tool that exists to catch that class of failure).

### 7.3 The service

- **A daemon, not one process per check.** The daemon is 350 ms faster. The gap
  is Node boot and the Playwright import, not the browser: Chromium launches in
  45 ms. One process per check is the fallback if a second daemon is unwanted.
- One browser, one **fresh context per check**.
- **Cap concurrency and queue past it.** 1, 2, 4 and 8 concurrent checks all
  pass, but 8 at once degrades to 3.1 s each. About 250 MB resident idle.
- A systemd user unit, `sketch-checkd.service`, next to `sketch-bench.service`.

### 7.4 The route walk and screenshots

- Drive the router through `window.__sketchGoto(path)`, never through the DOM.
- Routes with a param (`/issue/:id`) cannot be visited blind. **Report them as
  skipped, with the reason.**
- **Cap the walk at 20 routes. Hard-timeout the check at 30 s.** Say plainly
  what was skipped: a silent cap reads as "everything is fine".
- Screenshots are opt-in, one PNG per **static** route, 1280x800, light theme
  only. 28-35 KB each, 37-47 KB as base64. Keep PNG; JPEG q70 saves about 20%
  and is not worth the loss for a design tool.

### 7.5 Return shape

`structuredContent`, plus one image content block per route when `screenshot`
is set. Render errors as `file:line:col message`.

```json
{ "status": "ok | errors | compile-failed | link-failed | boot-failed | empty",
  "errors": [ { "kind": "compile", "file": "src/pages/About.vue",
                "line": 3, "column": 5, "message": "Element is missing end tag." } ],
  "warnings": [ { "kind": "unresolved-component", "file": "…", "message": "…" } ],
  "routes": ["/", "/about"],
  "timings": { "compileMs": 55, "mountMs": 55, "tailwindMs": 302 } }
```

Import cycles are no longer an error: the module registry in section 5.6 makes
them work.

### 7.6 Latency, measured

Median of 5, or of 3 for the slower cases. Sample: 7 files, 2 routes.

| Case | ms |
|---|---|
| End to end through Frappe, with screenshots | **913** |
| Node service, with screenshots | 951 |
| Node service, no screenshots | 813 |
| One process per check (no daemon) | 1299 |
| Compile error, fails before mount | 210 |
| Runtime throw on a walked route | 825 |
| 30 files, 12 routes, with screenshots | 2578 |

Inside one run: 25 ms for the browser context, 570 ms to load and report, then
160 ms per route with a screenshot and 80 ms without.

0.9 s fits inside one tool call. A job plus a poll would cost an extra agent
round trip, slower than the check itself, and a twelfth tool.

### 7.7 Keep the production Runtime

No dev asset set. The production build catches every error class that matters
(section 5.9). A dev build would cost a `@vue/devtools-api` shim and a second
asset set per Pin, to recover prop type warnings alone.

---

## 8. The MCP server

`POST /mcp`, stateless streamable HTTP. Wired with **one `page_renderer` hook
entry**, not a whitelisted method and not a route rule. POST reaches website
renderers on both Frappe lines.

Copy `http.py` and `rpc.py` from Builder's `builder/ai/mcp/` on branch
`forge/mcp-server`. Full reading in `research/09-builder-mcp-reuse.md`.

### 8.1 Keep, drop, rewrite

**Keep:** the transport, the Guest 401 with
`WWW-Authenticate: Bearer resource_metadata=".../.well-known/oauth-protected-resource"`,
the JSON-RPC parser and error shapes, the module-level `TOOLS` dict with
`READ_ONLY` / `DESTRUCTIVE` sets and an `annotations()` function
(`tools.py:78-137`), the savepoint and rollback around each handler, the batch
reject, GET answered 405 with `Allow: POST`, and notifications dropped with 202.

**Drop:** `ctx.py`, `pages.py`, the block model, the page lock
(`builder.ai.locks`), `McpCtx` snapshots and the realtime mirror, agent-registry
reuse, `CLIENT_OPS` / `SCRIPT_TWINS` / `CONFIRM_KINDS`, the confirm-gate
machinery, the injected `page` param, and every `Builder Page` tool. Sketch
tools declare `prototype` directly.

**Rewrite:** the permission check, `INSTRUCTIONS`, the server name, and
`server/discover` (section 8.3).

### 8.2 Auth

`/mcp` authenticates a `Sketch Token` sent as `Authorization: Bearer sk_...`,
resolved by one function in `auth_hooks` (`auth.py:772-774`). **The function
refuses every path except `/mcp`.**

This is Sketch's auth, not Frappe core's. Core's `validate_auth` routes
`Bearer` to the OAuth path and accepts API keys only as `token <key>:<secret>`
or `Basic` (`auth.py:640-741`), so `auth_hooks` is the supported door for a
third scheme. Frappe's `api_key`/`api_secret` was rejected because it
authenticates every Frappe endpoint, and signup is open to anyone.

OAuth for claude.ai connectors stays deferred. The 401 header above is still
correct and still wanted.

### 8.3 Protocol: dual-era

**One endpoint serves both eras.** Legacy `2025-06-18` and modern `2026-07-28`.
The server picks by how the client opens. The spec names this pattern and
permits one endpoint.

`2025-11-25` is **not served**. Its nine changes are OAuth discovery, icons,
elicitation, sampling and tasks. None touch Sketch's 11 tools.

Modern-only was rejected: the newest TypeScript SDK client defaults to
`mode: 'legacy'` (`DEFAULT_VERSION_NEGOTIATION_MODE`,
`packages/client/src/client/versionNegotiation.ts:112`), sends `initialize`,
and would get a 400 with no fall-forward. Legacy-only works today, verified live
with Claude Code 2.1.246, but ships two revisions behind and costs a doomed
probe on every connection.

About 70 lines in `rpc.py` and 1 to 3 in `http.py`. Itemised in section 6 of
`research/18-mcp-protocol-revision.md`.

What to build:

- **Branch on the presence of
  `params._meta["io.modelcontextprotocol/protocolVersion"]`.** That one `if` is
  the era switch. Sketch keeps no session, so nothing else forks.
- **`rpc.handle` must be able to return HTTP 400.** Builder returns 200 for
  every protocol error. The `(status, payload)` tuple already carries a status,
  so the plumbing exists. **This is the easiest thing to miss in the port.**
- Modern requires three headers: `MCP-Protocol-Version`, `Mcp-Method`,
  `Mcp-Name`. Builder reads none of them.
- Modern requires two `_meta` keys:
  `io.modelcontextprotocol/protocolVersion` and
  `io.modelcontextprotocol/clientCapabilities`.
- **Every modern result carries `resultType`.** `tools/list` also carries
  `ttlMs` and `cacheScope`. Legacy results carry none of them.
- **Rewrite `server/discover`, do not copy it.** Builder has the method
  (`rpc.py:90`) but its body is wrong in four fields: no `resultType`, no
  `ttlMs`, no `cacheScope`, and `serverInfo` is not in `_meta`.
- Two new error codes, both HTTP 400: **`-32020`** for a header mismatch or a
  missing header, **`-32022`** `UnsupportedProtocolVersionError` with
  `data: {supported, requested}`.
- **Legacy keeps `initialize` and `ping`. Modern deletes them.**
- `Mcp-Name` needs no Base64 sentinel decode, because Sketch slugs are
  `[a-z0-9-]`. Record that limit in the code.

Builder's `PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26")` is superseded.
Builder silently downgrades an unknown version to `2025-06-18` with no error;
Sketch must not.

**Known gap:** the modern path is unverified against a running client. No
`2026-07-28`-only server was built, and only the legacy fallback was captured
live. Verify it against Claude Code before calling `/mcp` done.

### 8.4 Structured output

Builder flattens every result to one text blob (`dispatch.py:80`) and decides
`isError` by testing whether that text starts with `"FAILED"`
(`dispatch.py:18`). Sketch returns structured fields, so it needs the
structured-output path instead: `outputSchema` on the tool and
`structuredContent` on the result, for `create_prototype`, `list_prototypes`,
`list_files`, `read_files`, `check` and `set_public`. Set `isError`
explicitly; a prefix test cannot read a structured result.

`create_prototype` returns the record as structured fields, never prose.
Builder's `create_page` returns prose and every caller has to regex
`id=(page-[0-9a-f]+)` out of it.

### 8.5 The tools: eleven, and no more

| Tool | Arguments | Returns | Annotation |
|---|---|---|---|
| `list_prototypes` | — | id, title, slug, pin, is_public, url per Prototype | readOnly |
| `create_prototype` | `name` (required) | the Prototype record | — |
| `list_files` | `prototype` | path and size per file, no content | readOnly |
| `read_files` | `prototype`, `paths[]` | path and content per file | readOnly |
| `write_files` | `prototype`, `files[{path, content}]` | paths written | — |
| `edit_file` | `prototype`, `path`, `old_string`, `new_string` | ok, or a no-match error | — |
| `delete_file` | `prototype`, `path` | ok | **destructive** |
| `check` | `prototype`, `screenshot` (bool) | compile errors, console errors, images | readOnly |
| `get_skill` | — | the full skill, one blob | readOnly |
| `set_public` | `prototype`, `is_public` | the Prototype record | **destructive** |
| `set_name` | `prototype`, `name` | the Prototype record | — |

Notes that are decisions, not detail:

- **No `delete_prototype`.** Deleting is a human act in the Sketch UI. A
  confused agent must not destroy a user's work behind one permission prompt.
  MCP refuses delete by exposing no tool, not by permission.
- **`create_prototype` takes `name` only.** No `pin`: launch supports one
  Runtime, so the server picks it. No recipe: recipes are chosen in the UI and
  nowhere else, and the agent has no recipe tool by design. A Prototype created
  over MCP is `empty` until the agent writes to it.
- **`name` is required.** No "Untitled". The slug is derived from the name at
  creation and frozen, so a good name up front keeps the URL honest.
- **`get_skill` takes no arguments.** One file serves every Pin.
- `set_name` keeps its tool name and its `name` argument, which is what the
  agent types. It writes `title`.
- Tools address a Prototype by its **slug**, scoped to the authenticated user.
- **`edit_file` earns its place.** With `write_files` alone every tweak
  re-sends the whole file: a frappe-ui page SFC is 150-300 lines, about 2-4k
  tokens, so ten iterations cost 20-40k tokens in rewrites. `edit_file` takes
  an exact `old_string` that must match once, and cuts iteration cost by
  roughly 10x. Accepted cost: the agent must recover from a no-match by
  re-reading.
- **Screenshots are opt-in.** Errors are always returned as text. The known
  risk is that agents skip optional work, and the mitigation must be built:
  both the tool description and `INSTRUCTIONS` state the rule as a workflow
  step, not an option. A screenshot costs about `(width x height) / 750`
  tokens, so roughly 1,400 at 1280x800.

### 8.6 `INSTRUCTIONS`

Always in context, about 1.2k characters. Ship this text.

```
Sketch MCP server: write high-fidelity frappe-ui prototypes that render in the browser.

Workflow: call get_skill first. Then list_prototypes or create_prototype, write the files, and call check with screenshot: true once at the end of each user request. Every tool except list_prototypes and create_prototype takes a `prototype` argument: the slug returned by create_prototype.

A Prototype is an app-like source tree that lives on this server, not on your disk. Pages go in src/pages/, shared components in src/components/, with src/App.vue and src/router.ts at the top. Every path you pass is a full relative path such as src/pages/Home.vue. Use write_files for new or rewritten files and edit_file for small changes to an existing one.

There is no server and no backend. Data lives in plain refs inside the prototype files. Never import useList, useDoc, useCall, useDoctype, useNewDoc, createResource, createListResource, createDocumentResource, frappeRequest or call. They will throw.

TypeScript is stripped, not type-checked. Tailwind classes, frappe-ui components and frappe-ui tokens all work; get_skill documents them.

check returns compile errors, console errors, and one image per route when screenshot is true. Fix every error before you report done. delete_file and set_public are annotated destructive, so your client asks before running them.
```

---

## 9. The served skill

Already written and committed: **`sketch/skill/frappe-ui.md`**, 2,949 words,
one blob, eight sections. `get_skill()` returns the file.

It is in **app source, not in the Runtime folder**. Reach is the reason: a
skill inside a Runtime folder is frozen for every Prototype already pinned to
that Runtime, so a correction never arrives. In app source, editing it is an
app deploy and every Prototype sees the new text at once.

It is a **Sketch-owned rewrite**, not a trim of the box frappe-ui skill. Too
much of the box skill is wrong here rather than surplus, and a trim leaves the
original reading as authoritative.

Cost accepted: one file serves every Pin, so at a second Pin it describes one
frappe-ui version while some Prototypes render with another. A skill per Pin is
on the map under Not yet specified.

Rules the skill carries that the implementer must keep true:

- Every lucide icon works. No list, no subset.
- Only the listed specifiers resolve. **Update the count from eight to nine and
  add the `@vueuse/core` row** (section 5.3). The file currently says eight.
- `dayjs` is frappe-ui's instance, with nine plugins already applied. Never
  call `.extend`.
- Sketch owns the theme. Never `useColorScheme`, `setColorScheme` or
  `ThemeSwitcher` in Prototype code, and never write `localStorage`.
- Data lives in plain `ref`s. The loading pattern is
  `onMounted(() => setTimeout(...))` for a skeleton, then rows, then the empty
  state.
- Forbidden imports: `useList`, `useDoc`, `useCall`, `useDoctype`,
  `useNewDoc`, `createResource`, `createListResource`,
  `createDocumentResource`, `frappeRequest`, `call`. There is no server.
- `src/router.ts` exports a routes array, not a router. Hash mode. Never
  `createWebHistory`.
- `FileUploader` works, because the Viewer stubs `upload_file`.

`sketch/tests/test_skill_names.py` keeps the skill honest: seven tests that
pull every import specifier, imported name and component tag out of the fenced
code blocks and assert each resolves against the newest built Runtime, and that
the six components the skill says are missing really are missing. It skips when
no Runtime is built.

---

## 10. Recipes

A Recipe is a starter Prototype tree the user picks when creating a Prototype
**in the Sketch UI**. There is no `get_recipe` tool and the skill does not index
them: the agent meets a Recipe as working code, not as a document.

- **The set is the eight from `ui.frappe.io/recipes`, plus Blank**: Discussions,
  Compose, Deals, Tickets, Mail, Files, Tasks, Accounting. Source is
  `docs/components/recipes/*.vue` in the frappe-ui repo.
- **Desktop variants only.** The Viewer and `check` are a 1280x800 frame, and a
  mobile recipe renders wrong in it.
- **Vendored into Sketch**, at `sketch/recipes/<slug>/src/…`, checked into git.
  They must be adapted anyway: each recipe is one component, and a Prototype is
  a tree with `src/App.vue`, `src/router.ts` and `src/pages/`. Fetching them at
  build time would make the build need network, and the docs are not on npm.
- **Compose imports `@vueuse/core`**, the Runtime's ninth specifier. Every
  other recipe stays inside the existing eight.

Cost, plainly: vendored recipes drift from upstream. Adapting them is a day,
not an hour. Tasks is 1,323 lines and Discussions is 1,121.

**Must be built: a test that every recipe boots clean through `check`.** The
only local checkout of the recipes is frappe-ui `1.0.0-beta.28`, 27 versions
behind the Pin. Nothing else would catch a recipe that no longer compiles.

---

## 11. The Sketch UI

Faris chose **B — Studio**. The prototype is preserved on branch
`forge/proto/14-sketch-ui` at commit `4d9536d`; run it with `yarn dev` from
`apps/sketch/frontend` and open
`/sketch/prototype/sketch-ui/list?variant=B`. **It is a primary source, not
implementation code. Rewrite the direction, do not lift the files.**

Load the `frappe-ui` skill before styling anything. Use design tokens, never an
invented spacing, radius or colour value.

### Shell

- A persistent **14 rem sidebar** on desktop. It holds the Sketch identity,
  Prototypes and Settings navigation, a small agent-connection status, and the
  signed-in User at the bottom.
- The **theme control sits in the sidebar footer**, next to the User. It is a
  display preference, not an account setting.

### Prototypes screen

- Header reads **Your studio**, shows the Prototype count, and carries one
  solid **New prototype** action.
- A responsive visual gallery. Each item has a rendered-preview area, name,
  short description, updated time, a Public/Private switch, and an overflow
  menu.
- **Rename and Delete live in the overflow menu**, because they are UI-only
  actions. Delete uses a destructive confirmation.
- When Public is on, the item shows a Public badge and the copyable
  `/u/<username>/<slug>` URL. Turning Public off hides the URL.

### Creating a Prototype

A **"Select a Recipe" picker** appears when a Prototype is created in the UI.
This is the only place a Recipe is chosen. Creation is now both a human act
(with a Recipe) and an agent act (`create_prototype`, which produces an `empty`
Prototype).

### Settings

Same app sidebar and header. The body has a narrow local navigation column and
a content column: **Profile**, then **Agent connection**.

- Profile shows Username with this help text, verbatim: **3–30 characters. Use
  lowercase letters, numbers, and hyphens. Start with a letter.** The field is
  read-only after signup (section 3).
- Agent connection shows one readable Token with **Copy token** and
  **Regenerate** actions, then the `https://sketch.netchamp.dev/mcp` endpoint
  and a **Copy config** action. It is not a token list: one user, one token.

### Viewer route

The Prototype document at `/u/<username>/<slug>` fills the viewport and has
**no Sketch sidebar, header, account controls, or other Sketch chrome**.
Everything visible there belongs to the Prototype.

### Components

`Button`, `Dropdown`, `Switch`, `FormControl`, `Avatar`, `Badge`, the
imperative `dialog` and `toast` APIs, and the modern `List`, `ListRow` and
`ListCell` family from `frappe-ui/list`. Semantic surface, ink and outline
tokens throughout.

---

## 12. Theme

Dark mode is in the MVP.

- **Sketch owns the theme.** The Sketch UI has a `light | dark | system`
  control in the sidebar footer, built on frappe-ui's `ThemeSwitcher` and
  `useColorScheme`. It writes `localStorage['theme']`.
- **The Viewer resolves in this order:** a `theme` parameter in the URL, then
  `localStorage['theme']`, then `prefers-color-scheme`. It sets `data-theme` on
  its own `<html>`, to `light` or `dark`, never `system`, and **never writes
  `localStorage`**.
- One rule covers all three cases: the owner inside Sketch chrome, the owner in
  the fullscreen route, and a visitor on a public link.
- **`check` passes `theme=light`** to force light, so its screenshots stay
  deterministic. A headless Chromium can be started with a dark colour-scheme
  preference, and a screenshot that flips theme between runs is not a signal
  the agent can read.
- Prototype code must never touch the theme. The Viewer and the Sketch UI share
  an origin and both use the `theme` key, so a Prototype that sets it
  overwrites its author's preference.

Dark screenshots in `check` are on the map under Not yet specified. One PNG per
static route, light only.

---

## 13. Tests

Exists already:

- `sketch/tests/test_skill_names.py`. Seven tests. Keep it green when the
  specifier list changes.

To build:

- **Every recipe boots clean through `check`** (section 10). The highest-value
  new test.
- **The `<` escaping.** A Prototype file containing `</script>` renders in
  the Viewer.
- **The path guard.** `../`, absolute paths, and symlink escapes are rejected
  by `write_files`, `edit_file` and `delete_file`.
- **404, not 403.** A private Prototype and a missing Prototype return the same
  status to a stranger.
- **The `auth_hooks` path scope.** A valid Sketch Token is rejected on every
  path except `/mcp`.
- **The signature.** A valid one serves a private Prototype; an expired one and
  a wrong one both fall through to 404; a stale one still serves a public
  Prototype.
- **The Runtime error classes.** Port `runtime-prototype/test-errors.mjs`.
- **The MCP era switch.** A legacy `initialize` and a modern `_meta` request
  both work against the one endpoint, and an unsupported version returns
  `-32022` with HTTP 400.

---

## 14. Traps

Each of these has already cost time once, or is named in a ticket as the single
most likely thing to be missed.

1. **The Viewer serialiser must escape `<` as `\u003c`.** Otherwise the
   `</script>` in any Vue file breaks the page. `frappe.as_json` does not do it.
2. **`rpc.handle` must be able to return HTTP 400.** Builder returns 200 for
   every protocol error.
3. **`define: { 'process.env.NODE_ENV': '"production"' }`** in the Vite lib
   build, or every Dialog renders as an empty comment node.
4. **Use `vue-router.esm-browser.prod.js`.** The dev build imports
   `@vue/devtools-api`, which no import map entry covers.
5. **`FrappeUIProvider` must mount**, or `dialog.confirm()` and
   `toast.success()` do nothing and `check` says `ok`.
6. **The `Sketch User` role fixture must set `desk_access = 0`**, or signup
   flips the new user to System User.
7. **Scope the `User.validate` hook to Website Users**, or it breaks Desk user
   management site-wide.
8. **The `auth_hooks` function must refuse every path except `/mcp`.** The
   whole security argument for `Sketch Token` rests on it.
9. **Guard every agent-supplied path** before touching disk.
10. **`on_trash` must delete the Prototype directory**, or orphans build up.
11. **A missing Runtime folder returns 500 with a readable message**, never a
    blank iframe.
12. **`check` must say what it skipped.** A silent 20-route cap reads as
    "everything is fine".
13. **Recompute `check` status after the route walk.** A throw on a walked
    route must not report `ok`.
14. **`sketch-checkd` must call `127.0.0.1:8007` with a
    `Host: sketch.localhost` header**, never the public hostname. The public
    host routes every request out to Cloudflare and back.
15. **Do not restore the backup cron.** It was database-only, and Prototype
    files live on disk.
16. **Adding an import specifier touches four places**: build entry, manifest,
    import map, skill.
17. **The `signup_form_template` submit rebind is fragile.** Core's `login.js`
    is not a stable API.
18. **Set up SMTP before opening signup.** Signup returns 200 even when the
    mail fails.

---

## 15. Build order

Each step ends with something runnable.

1. **Doctypes, role, permissions.** `Sketch Prototype`, `Sketch Token`, the
   `Sketch User` role fixture with `desk_access = 0`, the `if_owner` rules, the
   on-disk tree helpers with the path guard, `on_trash`.
2. **Signup.** The `sign_up` override with `username`, the
   `signup_form_template`, the `User.validate` hook, Portal Settings, Website
   Settings, SMTP. Verify a real signup end to end.
3. **The Runtime.** Port `runtime-prototype/`, apply the seven changes in
   section 5.6, wire `yarn build`, keep `test_skill_names.py` green.
4. **The Viewer renderer.** `/u/<username>/<slug>`, the data slot, the escaping,
   the four-branch auth ladder, the headers. Render a hand-written Prototype.
5. **`sketch-checkd`.** Port `check-prototype/`, add the systemd unit, add the
   signed-URL minting on the Frappe side.
6. **The MCP server.** Port `http.py` and `rpc.py`, add auth, add the era
   switch, add the 11 tools with `outputSchema`. Verify against Claude Code,
   both eras.
7. **The SPA.** Move it to `/`, then build the Studio screens.
8. **Recipes.** Vendor and adapt the eight, add Blank, add the boot test.

Steps 3, 4 and 5 are the critical path: `check` needs the Viewer, and the
Viewer needs the Runtime.

---

## 16. Not in the MVP

Deferred, and each is on the map with its reasoning.

- Abuse controls for open signup: prototype count, file size, `check` rate,
  storage per user. Ticket 10 gives the numbers to rate-limit against.
- OAuth for claude.ai connectors.
- A second frappe-ui version, and moving a Prototype's Pin.
- A skill per Pin.
- Snapshots or revert history.
- Live reload of the Viewer when the agent writes files.
- Type checking (`vue-tsc`) inside `check`.
- Dark-mode screenshots in `check`.
- Iframe sandboxing.
- Onboarding copy for a user with no Prototypes.
- Mobile recipe variants.

Ruled out of scope, and not to be reopened inside this effort:

- **A Fixture API and stubbed resources.** No frappe-ui component fetches its
  own data, so a Prototype needs no stubs to render. Data lives in `ref`s.
- **A real Vite dev server in the browser, in a WebContainer.** Verified: Vite
  8.2.2 has one entry point, `dist/node/index.js`, and depends on `rolldown`
  and `lightningcss`, both native `.node` binaries. It would void tickets 04,
  05, 06 and 10, so it is a restart, not a ticket.
- **Browsing other users' public Prototypes.** Usernames are in the MVP, so
  `/u/<username>` can be added later without moving a single URL.
- An in-browser code editor. The agent is the editor.
- Sharing to a specific other user. Only owner-private or public link.
- A Sketch-owned agent or chat panel.
- A mock API backend per Prototype.
- The frappe-ui `0.1.x` line.

---

## 17. Sources

Tickets are in `.scratch/sketch-mvp/issues/`, research reports in
`.scratch/sketch-mvp/research/`.

| Section | Ticket |
|---|---|
| 1 Environment | 01 scaffold, 02 tunnel, 16 service |
| 2 Data model | 12 data model |
| 3 Signup | 13 signup on develop, 12 data model |
| 4 Routing | 12 data model, 08 tool surface |
| 5 Runtime | 04 runtime bundle, 05 SFC compiler, 06 runtime Tailwind, 11 served skill |
| 6 Viewer | 17 viewer file access, 04 runtime bundle |
| 7 check | 10 check step, 17 viewer file access |
| 8 MCP | 08 tool surface, 09 Builder MCP reuse, 18 protocol revision |
| 9 Skill | 11 served skill |
| 10 Recipes | 14 UI prototype, 11 served skill |
| 11 UI | 14 UI prototype |
| 12 Theme | 11 served skill, 10 check step |
| 16 Out of scope | 07 fixtures, 17 viewer file access |

Prototype branches, all preserved:

| Branch | Commit | Holds |
|---|---|---|
| `forge/proto/04-runtime-bundle` | `a4a932d` | `runtime-prototype/`, the working Runtime |
| `forge/proto/10-check-step` | `3bec4ec` | `check-prototype/`, `sketch-checkd` and its measurements |
| `forge/proto/14-sketch-ui` | `4d9536d` | `frontend/src/prototype/`, the A/B/C UI prototype |
