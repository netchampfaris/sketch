# Prototype the check step: compile, render, screenshot

Type: prototype
Status: open
Blocked by: 04

## Question

Prototype a worker path that takes a prototype id, compiles every file server-side with the same compiler the Runtime uses, then opens the viewer URL in headless Chrome (Playwright chromium already in ~/.cache/ms-playwright), captures console errors and one screenshot per route, and returns them as MCP content. Must not run inside a Frappe web worker request. Decide: RQ job plus polling, or a separate Node service. Measure latency.
