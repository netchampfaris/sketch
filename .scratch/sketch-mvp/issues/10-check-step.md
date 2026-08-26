# Prototype the check step: compile, render, screenshot

Type: prototype
Status: open
Blocked by: 04

## Question

Prototype a worker path that takes a prototype id, compiles every file server-side with the same compiler the Runtime uses, then opens the viewer URL in headless Chrome (Playwright chromium already in ~/.cache/ms-playwright), captures console errors and one screenshot per route, and returns them as MCP content. Must not run inside a Frappe web worker request. Decide: RQ job plus polling, or a separate Node service. Measure latency.

## Comments

### 2026-08-26 — from ticket 08

- `check({ prototype, screenshot })`. Screenshots are opt-in, one image per
  route. Errors are always returned as text.
- The MCP transport is stateless POST-only with no SSE, so `check` **cannot
  stream progress**. Either it returns fast enough for a synchronous
  JSON-RPC reply, or it becomes a job plus a separate poll tool. Decide
  which, and measure against the latency numbers this ticket asks for.
- Return compile errors as `file:line:col message`. The compiler is
  `@vue/compiler-sfc` + `sucrase` (ticket 05); check `parse().errors` first,
  or template errors report at generated-code positions.
- Use `structuredContent` for the error lists, not a text blob.
