# Sketch: context

Sketch is hosted at `sketch.netchamp.dev`. Anyone signs up. Their own agent connects over MCP and writes high-fidelity frappe-ui prototypes. Sketch has no agent panel of its own.

The wayfinder map for the MVP spec lives in `.scratch/sketch-mvp/map.md`.

## Glossary

- **Prototype**: an app-like source tree (`src/pages`, `src/components`, `src/App.vue`, `src/router.ts`) of Vue SFC and `.ts`/`.js` files, owned by one User, rendered in the browser. High fidelity: real frappe-ui components and tokens, not a mock. The files live on disk; no doctype describes them.
- **Viewer**: the page a Prototype renders in, at `/u/<username>/<slug>`. Its own document, its own global `fetch`, its own stylesheet. Sketch chrome lives outside it, and every link to it opens a new tab.
- **Thumbnail**: the picture on a gallery or feed card. One PNG per theme, captured in the background after commits, runtime changes, or owner gallery reads and stored outside the source tree. A card draws this, never a live Viewer: an iframe per card boots a Runtime per card.
- **Runtime**: the shared browser bundle (Vue, vue-router, frappe-ui, Tailwind, SFC compiler, TS stripper) that renders a Prototype. One Runtime per supported frappe-ui version. Each version has its own pinned build inputs in `runtime/versions/<version>/`, so a new version never changes an old one. `yarn runtime:add [version]` adds a version. See `runtime/README.md`.
- **Pin**: the frappe-ui version a Prototype targets. Chosen at creation: the newest built Runtime, in version order. The owner can switch it to another installed version. A Prototype renders with the Runtime that matches its Pin. Keep every version that a Prototype pins: its Runtime must build on a fresh server.
- **Check**: optional hosted rendering verification when the agent cannot use the user’s browser. Returns compile errors, console errors, and optional screenshots. It does not capture Thumbnails or test interactions.
- **Username**: the unique, user-chosen name that prefixes every Prototype URL. `sketch.netchamp.dev/u/<username>/<slug>`. 3-30 characters, `[a-z0-9-]`, starts with a letter, lowercase. Chosen at signup and never changed, because it is in every public link.
- **Slug**: the URL segment for one Prototype, derived from its name at creation and never changed. Unique per Username.
- **Public**: an owner-set toggle. When on, anyone with the URL can view the Prototype read-only, without Sketch chrome.
- **Token**: the per-user Bearer credential an agent sends to `/mcp`.
- **Recipe**: a starter Prototype tree the user picks when creating a Prototype in the Sketch UI. Eight come from `ui.frappe.io/recipes`, plus Blank. The agent has no recipe tool: it meets a Recipe as working code, not as a document.
- **Fixture**: sample data for a Prototype. Always inline, in plain `ref`s inside the prototype files. There is no Fixture API and no backend.

## Production

`https://sketch.netchamp.dev` runs on Frappe Cloud v2: site
`sketch.mumbai.frappe.cloud`, a pilot bench on its own VM. The Cloudflare
tunnel on forge relays the hostname to it. `sketch-checkd` runs on that VM as
a `systemctl --user` unit, outside pilot. Pilot installs the app from `main`
and downloads the assets that `.github/workflows/assets.yml` builds.

## Sites: which one takes a test run

The forge bench has two sites. They do different jobs.

| Site | Job | Tests |
| --- | --- | --- |
| `sketch.localhost` | The old beta site, frozen in read-only maintenance mode since 2026-10-10. Holds the pre-migration data as a fallback. Web port 8007. | **Never.** `allow_tests` is off, so `run-tests` refuses. |
| `sketch-test.localhost` | The test site. MariaDB, the same engine as the beta site. Database `sketch_test`, own files, web port 8017. | Always. |

Never put `allow_tests` back on `sketch.localhost`. The suite creates and
deletes rows, so a run there can damage real user data.

Run the suite:

```bash
cd /home/faris/benches/sketch-bench
# 1. The test site needs its own web server. Some tests drive a live request.
bench --site sketch-test.localhost serve --port 8017 --noreload &
# 2. The suite.
bench --site sketch-test.localhost run-tests --app sketch
```

The tests read the port from the site config, so they never call port 8007.
Without a server on 8017 the web tests skip and give the reason. `sketch-checkd`
on port 8010 is shared by both sites. It takes the target URL and the `Host`
header from the test, so it needs no change.
