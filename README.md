# Sketch

High-fidelity frappe-ui prototypes, written by your own agent over MCP.

Sketch has no editor and no agent panel. You connect the agent you already use,
ask it to build something, and the prototype renders in the browser with real
frappe-ui components and real design tokens. Not a mock, not an image.

A Frappe app. Live at [sketch.netchamp.dev](https://sketch.netchamp.dev).

## How it works

1. You sign in with GitHub and copy your token from Settings.
2. Your agent connects to `https://<site>/mcp` with that token.
3. The agent writes Vue files into a Prototype: `src/pages`, `src/components`,
   `src/App.vue`, `src/router.ts`.
4. `check` compiles and mounts the tree in a real browser, walks the routes and
   returns compile errors, console errors and a screenshot per route.
5. `commit` records a version, with the prompt that produced it.

There is no backend inside a Prototype. Data lives in plain `ref`s in the
files, so a prototype is a self-contained tree that renders anywhere.

## Connect an agent

One command for Claude Code:

```bash
claude mcp add --transport http --scope user sketch \
  https://sketch.netchamp.dev/mcp \
  --header "Authorization: Bearer <your-token>"
```

`--scope user` is not optional. Without it, Claude Code binds Sketch to one
directory.

Settings carries a ready-made block for eight clients: Claude Code, Codex,
OpenCode, Cursor, VS Code, Claude Desktop, Gemini CLI and Windsurf. Each one
already holds your token.

The top-level config key is the usual failure. VS Code uses `servers`, OpenCode
uses `mcp`, Codex uses `mcp_servers`, everybody else uses `mcpServers`.

claude.ai custom connectors cannot work yet. The dialog takes a URL only and
sends no `Authorization` header.

## The tool surface

Twelve tools. Every one but `list_prototypes` and `create_prototype` takes the
`prototype` slug.

| Tool | What it does |
| --- | --- |
| `get_skill` | The frappe-ui skill for this server: components, tokens, icons, and the patterns that do not resolve. Read it first |
| `list_prototypes` | Your prototypes, with slug, pin, public flag and URL |
| `create_prototype` | An empty prototype. The slug and the public URL come from the name |
| `list_files` | Every file with its size, no content |
| `read_files` | Whole files, by relative path |
| `write_files` | Create a file, or replace one end to end |
| `edit_file` | Replace one exact string that occurs exactly once |
| `delete_file` | Remove one file |
| `check` | Compile, mount, walk the routes, report errors and screenshots |
| `commit` | Record a version, with the user's prompt |
| `set_name` | Rename. The slug never moves |
| `set_public` | Turn the public link on or off |

`/mcp` speaks streamable HTTP, POST only, and answers both the 2025-06-18 and
2026-07-28 protocol revisions. Every failure is JSON that names the fix.

## Install

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/netchampfaris/sketch --branch main
bench install-app sketch
```

The check step needs a browser. `checkd` is a small Node service that drives
it; `checkd/sketch-checkd.service` is the systemd unit.

## Develop

```bash
yarn install          # installs frontend/ too
yarn dev              # vite, the SPA
yarn build            # the SPA, then the runtime bundle
yarn build:runtime    # the runtime bundle alone
bench --site <test-site> run-tests --app sketch
```

Run the test suite on a test site only. It creates and drops users and
prototypes.

`pre-commit` handles formatting: ruff, eslint, prettier, pyupgrade.

```bash
cd apps/sketch && pre-commit install
```

## Layout

| Path | What lives there |
| --- | --- |
| `sketch/mcp/` | The `/mcp` endpoint: JSON-RPC transport, the tool surface, the error contract |
| `sketch/` | The Frappe app: doctypes, auth, the prototype file store, the viewer |
| `sketch/skill/` | The frappe-ui skill `get_skill` serves |
| `sketch/recipes/` | Starter trees offered at creation |
| `frontend/` | The Sketch SPA. Vue 3, vite, frappe-ui |
| `runtime/` | The shared browser bundle a Prototype renders with. One per frappe-ui version |
| `checkd/` | The Node service behind `check` |
| `.scratch/` | The MVP spec, the issue set and the design notes |

`CONTEXT.md` is the orientation document. Read it before changing anything.

## License

MIT
