# Sketch: context

Sketch is hosted at `sketch.netchamp.dev`. Anyone signs up. Their own agent connects over MCP and writes high-fidelity frappe-ui prototypes. Sketch has no agent panel of its own.

The wayfinder map for the MVP spec lives in `.scratch/sketch-mvp/map.md`.

## Glossary

- **Prototype**: a set of Vue SFC files, `.ts`/`.js` files, and a `routes.js`, owned by one User, rendered in the browser. High fidelity: real frappe-ui components and tokens, not a mock.
- **Runtime**: the shared browser bundle (Vue, vue-router, frappe-ui, Tailwind, SFC compiler, TS stripper) that renders a Prototype. One Runtime per supported frappe-ui version.
- **Pin**: the frappe-ui version a Prototype targets. Set at creation. A Prototype renders with the Runtime that matches its Pin.
- **Fixture**: sample data declared inside Prototype files. Stubbed resources resolve from Fixtures instead of a server.
- **Check**: the MCP step the agent runs once at the end of a user request. Returns compile errors, console errors, and a screenshot.
- **Public link**: an owner-set toggle. When on, anyone with the URL can view the Prototype read-only, without Sketch chrome.
- **Token**: the per-user Bearer credential an agent sends to `/mcp`.
