# Define the doctypes and permission model

Type: grilling
Status: resolved
Blocked by: 08 (resolved)

## Question

Decide the doctypes: Sketch Prototype (owner, name, slug, pin, is_public), how files are stored (child table rows or one JSON field or File docs), Sketch Runtime (version, folder), and where the per-user Token lives (Frappe api_key/api_secret or a Sketch-owned doc). Decide the role for signed-up users and the permission rules so a user only sees their prototypes and public links bypass login.

## Answer

Resolved 2026-08-26 with Faris.

Two doctypes: `Sketch Prototype` and `Sketch Token`. Nothing else. Files and
runtimes live on disk, and no row describes them.

### Files: an on-disk tree, no doctype

A Prototype is an app-like source tree:

```
src/
  components/
  pages/
  App.vue
  router.ts
```

Content lives at `sites/sketch.localhost/private/files/sketch/<name>/`,
where `<name>` is the Prototype's **hash primary key**, not its slug. Slug is
unique per owner only, so two users with `dashboard` would share a directory.
The path in an MCP call is the path inside that directory.

There is **no `Sketch File` doctype**. Disk is the only truth. `list_files`
walks the tree.

Rejected: a child table (every read and write loads and rewrites the whole
parent doc); one JSON field (`edit_file` rewrites the whole blob); Frappe
`File` docs (renames on hash collision, so `Home.vue` does not stay
`Home.vue`, plus a second permission layer).

A metadata-only `Sketch File` row was considered and dropped. Nothing sets
`title`: `write_files` takes `{path, content}` and `edit_file` takes
`path, old_string, new_string`, so the agent, the only writer, has no way to
supply one. Strip `title` and every remaining field is derivable from disk,
which makes the row a cache that can drift from what actually compiles.

### `Sketch Prototype`

`autoname: hash`. Unique index on `(owner, slug)` via
`frappe.db.add_unique` (`database.py:1401`).

| Field | Type | Notes |
|---|---|---|
| `owner` | built-in | Frappe sets it. Drives `if_owner`. No separate `user` Link. |
| `title` | Data, reqd | Display name. Cannot be `name`, which is reserved (`model/__init__.py:86`). `set_name` writes here. |
| `slug` | Data, reqd, read-only | Derived from `title` at creation, frozen. |
| `pin` | Data, reqd, read-only | The frappe-ui version string. |
| `is_public` | Check, default 0 | |

No `url`, `file_count` or `size`. All three are derived, and storing them
re-creates the cache problem above.

Rejected: a composite name such as `faris/dashboard`. It ties the primary
key to the username, so a username change would rewrite every Prototype row
and every link to it, and `/` in a Frappe doc name needs URL-encoding
through the Desk.

### Runtime: a folder, no doctype

Runtimes ship with the app at `sketch/public/runtimes/<version>/` with a
`manifest.json`. `pin` is a plain `Data` field. `create_prototype` reads the
newest version off disk.

A runtime is built by `yarn build` and ships with the code, so a row
describing it is a second copy of a fact the filesystem owns. The MVP
supports one version, so a Link's referential integrity guards a state that
cannot occur yet. Add the doctype with the second frappe-ui version, backed
by a scan of the folder that effort needs anyway.

Must be built: the Viewer fails with a readable error, not a blank iframe,
when `pin` names a folder that is not on disk.

### Token: `Sketch Token`, Bearer, `auth_hooks`

Frappe's `api_key`/`api_secret` was rejected. It authenticates **every**
Frappe endpoint, so a leaked Sketch token would be a site-wide REST API
credential, and signup is open to anyone. It also gives one secret per user,
so regenerating it is the only revocation and it kills the live connection
with no way to stage a replacement.

`Sketch Token` instead:

- Header `Authorization: Bearer sk_...`.
- Resolved by one function registered in `auth_hooks`
  (`auth.py:772-774`), which runs after core's own auth attempts.
- The hook **refuses any path except `/mcp`**. This is load-bearing, not a
  nicety: the security argument above depends on it.
- One token per user. Stored in a Frappe `Password` field, encrypted at
  rest, read back with `get_decrypted_password`.
- Settings shows the real token and a working connect snippet, always, plus
  one Regenerate button.

Retrievable, not hashed. Hashing forces show-once, and show-once with a
single token means a lost token can only be replaced by Regenerate, which
silently breaks the user's live agent connection. The alternative is several
named tokens, which needs a create/name/list/revoke screen in a UI that has
three screens. One user connects one agent.

Cost, stated plainly: anyone with Desk read on `Sketch Token`, or a DB dump
plus `site_config.json`, reads every user's token in the clear. Acceptable
while the token reaches only `/mcp`.

Context: core's `validate_auth` sends `Bearer` to the OAuth path and only
accepts API keys as `token <key>:<secret>` or `Basic` (`auth.py:640-741`).
`auth_hooks` is the supported door for a third scheme.

### Username: Frappe's `User.username`

Sketch adds a `doc_events` hook on `User.validate`. `Document.hook`'s
`compose` runs the doc's own method first, then app hooks
(`document.py:2079-2090`), so the Sketch hook sees the value core already
blanked and throws.

Core is worse than ticket 08 described. In `validate_username`
(`user.py:766-781`) the `msgprint` and `suggest_username` sit inside
`if self.user_type == "System User"`. Sketch's users are Website Users, so a
collision blanks the username with **no message at all**. Core also
auto-fills `username = frappe.scrub(first_name)` when it is empty, which can
invent a name behind the user's back.

Must be built:

- Scope the hook to Website Users. It fires on every User save site-wide,
  so an unscoped throw breaks Desk user management.
- Signup sets `username` explicitly, so core's `first_name` auto-fill never
  runs.

Format: 3-30 characters, `[a-z0-9-]`, starts with a letter, no doubled or
trailing hyphen, lowercase-normalised so `Faris` and `faris` cannot both
exist.

Rejected: a Sketch-owned username field. `User.username` already carries the
unique index, shows in the Desk, and serves login-by-username. A second
field means two things a user can call "my username", and they can disagree.

### URLs: `/u/<username>/<slug>` — amends ticket 08

Ticket 08 decided root level with no prefix. That is now `/u/`.

The root is not safe. Frappe's `app.py:96-113` handles `/api/`, `/backups`,
`/private/files/` and `/.well-known/` before the website router, so Sketch
can never serve a username there. Everything else reaches
`PathResolver.resolve()`, where custom `page_renderer` hooks run **first**,
ahead of `StaticPage`, `WebFormPage`, `DocumentPage`, `TemplatePage`,
`PrintPage` and `ListPage` (`path_resolver.py:55-64`).

So Sketch's renderer wins, and the danger is the reverse of what ticket 08
assumed. A new core route does not shadow an existing user. An existing user
shadows a new core route: a user named `dashboard` takes `/dashboard` away
from the whole site, silently, for everyone. On an unstable `develop`
branch, new routes will appear.

`/u/` removes the entire class of problem for two characters, and keeps
`/<username>` free for the browse page already deferred.

**The reserved username list is dropped.** Its only job was defending the
site root. The format rule above replaces it, because no name matching
`[a-z0-9-]` can collide with anything behind a prefix.

Rejected: `/@faris/dashboard`. Reads better, but `@` in a path segment trips
link parsers and copy-paste.

### Permissions

Role **`Sketch User`**, `user_type = Website User`, assigned at signup.

| Doctype | `Sketch User` |
|---|---|
| `Sketch Prototype` | create, plus read/write/delete with `if_owner` |
| `Sketch Token` | create/read/write with `if_owner`. No delete: regenerate is a write. |

`if_owner` makes Frappe add `owner = <user>` to every list query
(`db_query.py:1647-1659`), so `list_prototypes` and the SPA list are scoped
without Sketch writing a filter.

**Guest gets nothing** on either doctype.

Public links are served by the Viewer renderer alone. It reads the Prototype
with `ignore_permissions=True`, then serves only if `is_public` or the
caller is the owner.

A `has_permission` hook cannot do this. Those hooks run after role
permissions and can only **restrict**: returning `False` denies, returning
`True` grants nothing (`permissions.py:499-505`). A Guest with no role
permission stays denied whatever the hook says.

Rejected: giving Guest role read plus a `permission_query_conditions` hook
limiting it to `is_public = 1`. That makes every public Prototype queryable
through the generic REST API, with one hook standing between that and a full
listing. The renderer has to exist anyway, and it turns on one boolean.

Two rules inside it:

- A private or missing Prototype returns **404, not 403**. A 403 confirms
  the URL exists, which leaks that a user has a Prototype by that name.
- Deletion is UI-only (ticket 08 has no `delete_prototype`). The `if_owner`
  delete permission lets the owner delete from the SPA. MCP refuses delete
  by exposing no tool, not by permission.

Files inherit no Frappe permission, because they have no doctype. Every file
read or write resolves the Prototype through the permission-checked path
first, then touches disk.

### Must be built, not assumed

- A path guard on every agent-supplied path. `write_files` and `edit_file`
  take paths from the agent, so `../` and absolute paths must be rejected
  before touching disk.
- `on_trash` on Prototype deletes the tree, or orphan directories build up.
- Nothing else. The backup line that stood here is withdrawn: the
  sketch-bench backup cron is deleted (ticket 16 amendment). Prototypes are
  not backed up and are treated as disposable.
- The `auth_hooks` path scope, the Viewer's runtime-missing error, the
  Website-User scope on the username hook, and 404-not-403. All listed
  above.
