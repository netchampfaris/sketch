# Scaffold sketch-bench and the sketch app

Type: task
Status: resolved
Blocked by: 

## Question

Create /home/faris/benches/sketch-bench with `bench init --frappe-branch develop --python <uv python3.14> --skip-assets`, ports web 8007, socketio 9007, redis cache 13007, redis queue 11007, developer_mode on. Create the site `sketch.localhost` (MariaDB). Run `bench new-app sketch`, install it, init git in apps/sketch on a `forge/mvp` branch, add a frappe-ui frontend per the frappe-ui skill SETUP.md (frappe-ui@beta). Create CONTEXT.md at the app root from the map glossary and move this tracker into `apps/sketch/.scratch/sketch-mvp/`. Record: paths, Administrator password location, exact frappe-ui version installed, first `bench start` result.

## Answer

Done on 2026-08-26. A subagent ran the steps; the orchestrating session verified each item on disk.

- Bench: `/home/faris/benches/sketch-bench`. Python `/home/faris/.local/share/uv/python/cpython-3.14-linux-x86_64-gnu/bin/python3.14` (3.14.6). bench 5.31.0. Frappe `develop` at `0219b22` (2026-08-26), init with `--skip-assets`.
- Ports: web 8007, socketio 9007, redis cache and socketio 13007, redis queue 11007, file watcher 6797. `developer_mode` 1. `default_site` `sketch.localhost`. Vite dev port 8087 (frappe-ui plugin default: 8080 + 7).
- Site: `sketch.localhost` on MariaDB 10.11. DB `sketch`, user `sketch`. MariaDB root has no usable password from the `faris` account, so the DB and user were created with `sudo mysql` (unix-socket root) and the site with `bench new-site --no-setup-db --db-name sketch --db-password ...`.
- Passwords: `sites/sketch.localhost/site_config.json` holds `db_password` and `admin_password` (Administrator). The file is git-ignored.
- App: `apps/sketch`. Title Sketch, publisher Faris Ansari, license MIT. Installed on the site (`sketch 0.0.1`). Branch `forge/mvp`. Commits: `7b8f473 feat: Initialize App`, `e12acd5 feat: add frappe-ui frontend scaffold`, `129bb97 docs: add CONTEXT.md and wayfinder tracker`.
- Frontend: `apps/sketch/frontend`, yarn 1.22. frappe-ui `1.0.0-beta.55` (exact pin), vite 8.2.2, @vitejs/plugin-vue 6.0.8, tailwindcss 3.4.19, vue 3.5.41, vue-router 4.6.4, typescript 5.9.3. No unplugin packages needed. `yarn build`: 1027 modules in 2.4 s. Output in `sketch/public/frontend`; index copied to `sketch/www/sketch.html`. Served at `/sketch` through `website_route_rules`. `frontend/src/style.css` only imports `frappe-ui/style.css`; beta.55 already ships the `@tailwind` layers, so SETUP.md's extra lines would duplicate them. Same as Gameplan.
- First `bench start`: `/api/method/ping` returned `pong` 6 s after start. `GET /sketch` returned 200 with the built index. No error lines in `logs/first-start.log`. Clean shutdown. No listeners left on 8007/9007/13007/11007.
- `apps/sketch/CONTEXT.md` holds the glossary. Tracker moved to `apps/sketch/.scratch/sketch-mvp/`. The old `/home/faris/benches/.scratch` is removed.
- Scaffold defaults the spec may still change: SPA at `/sketch`; Vite 8 (SETUP.md says Vite 5, which targets the 0.1.x line).
- Not verified: rendering in a browser. Only HTTP status and HTML content were checked.
