# Which MCP protocol revision Sketch speaks

Type: research
Status: open
Blocked by:

## Question

The map recorded `2025-06-18` as the revision Builder knows, and flagged it as
unverified. It is verified now, and it is out of date.

The current revision is **2026-07-28**. `2025-11-25` sits between. `2026-07-28`
is **not handshake-based**: the version rides per-request in the
`io.modelcontextprotocol/protocolVersion` `_meta` key and in the
`MCP-Protocol-Version` header, `server/discover` is a mandatory RPC returning
supported versions and capabilities, and an unsupported version comes back as
`UnsupportedProtocolVersionError`. The spec defines backward compatibility with
the handshake-based revisions, so shipping the old one is not broken.

Tickets 08 and 09 build on Builder's `/mcp`, which knows `2025-06-18` only.

Decide which revision Sketch ships, by finding out what the clients actually
require:

- What do Claude Code and the claude.ai connector negotiate today, and do they
  still accept a `2025-06-18` server?
- What does `2026-07-28` cost on top of the stateless POST-only transport
  ticket 09 copied: `server/discover`, the `_meta` version key, the header, the
  error type.
- Whether the two can be served together, and at what cost.

Source: https://modelcontextprotocol.io/specification/versioning, read
2026-08-27.

This is the one open item that can make the endpoint unusable on day one.

## Answer
