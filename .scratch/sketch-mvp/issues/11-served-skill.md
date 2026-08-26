# What the served frappe-ui skill contains

Type: grilling
Status: open
Blocked by: 08 (resolved — unblocked)

## Question

Decide what get_skill returns for a given pin: the frappe-ui skill on this box (SKILL.md, COMPONENTS.md, TOKENS.md, DESIGN.md) trimmed for the Runtime, plus Sketch-specific rules: the `src/` file layout, `router.ts`, imports available, what is not available (no server, no backend, no Vite plugins). Decide how the skill is stored and versioned with the Runtime folder.

## Comments

### 2026-08-26 — from ticket 07 (closed out of scope)

Unblocked from 07. Two rules the skill must carry:

- Prototype data lives in plain `ref`s. Show the loading pattern:
  `onMounted(() => setTimeout(...))` for a skeleton, then rows, then the
  empty state.
- Forbid `useList`, `useDoc`, `useCall`, `useDoctype`, `useNewDoc`,
  `createResource`, `createListResource`, `createDocumentResource`,
  `frappeRequest`, `call`. There is no server. They will throw.

### 2026-08-26 — from ticket 12

- The skill documents an app-like tree: `src/components`, `src/pages`,
  `src/App.vue`, `src/router.ts`. Paths in every MCP call are full relative
  paths such as `src/pages/Home.vue`.
- **No Fixture API.** Ticket 07 closed it out of scope and the question text
  above is corrected. All fixture data is inline in plain `ref`s inside the
  prototype files.
- Storage: the skill ships in the runtime folder it belongs to,
  `sketch/public/runtimes/<version>/`, so it is versioned with the Pin by
  construction. No doctype (ticket 12).
