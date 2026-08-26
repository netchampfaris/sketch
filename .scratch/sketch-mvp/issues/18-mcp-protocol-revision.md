# Which MCP protocol revision Sketch speaks

Type: research
Status: resolved
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

Resolved 2026-08-27. Faris chose **dual-era**. Full report:
`../research/18-mcp-protocol-revision.md` (spec and SDKs in sections 1-6, local
client evidence in section 7).

### The decision

Sketch's `/mcp` serves **both eras on the one endpoint**: legacy `2025-06-18`
and modern `2026-07-28`. The server picks by how the client opens. The spec
names this pattern and permits one endpoint:

> A dual-era server selects its behavior from how the client opens. A request
> carrying modern per-request `_meta` is served statelessly according to this
> revision. An `initialize` request selects legacy semantics.

`2025-11-25` is not served. Its nine changes are OAuth discovery, icons,
elicitation, sampling, and tasks. None touch Sketch's 11 tools.

### Why not modern only

The newest TypeScript SDK client breaks against it.
`DEFAULT_VERSION_NEGOTIATION_MODE = 'legacy'`
(`packages/client/src/client/versionNegotiation.ts:112`, tag
`@modelcontextprotocol/core@2.0.0`, re-read by the orchestrating session). A
client built with defaults sends `initialize` and no modern headers. A
`2026-07-28`-only server has no `initialize` and answers `400`. The client has
no fall-forward.

### Why not legacy only

It works today, and that was verified, not assumed. But it ships two revisions
behind on day one, and the client's doomed probe costs a round trip on every
connection.

### What the clients actually do

- **Claude Code 2.1.246**: probes `server/discover` at `2026-07-28` with the
  `_meta` key and the header, fails schema validation against a Builder-shaped
  reply, falls back to `initialize` asking `2025-11-25`, accepts `2025-06-18`,
  and runs. Captured live against a byte-exact replica of Builder's handlers.
  No error reaches the user. Claude Code is not a default-configured TS client:
  it behaves as `mode: 'auto'`.
- **claude.ai**: the proxy leg on this box runs `"protocolEra":"legacy"` at
  `2025-11-25`, and the bundle hardcodes that header. Whether the hosted
  connector runner accepts a legacy-only third-party server is **unverified**;
  the connectors here are unauthenticated.
- Both SDK clients fall back to `initialize` against an old server. The Python
  probe is an explicit denylist.

### Two corrections to this ticket's premises

- **Builder is not `2025-06-18`-only.** `rpc.py:17` holds
  `PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26")`, and `server/discover`
  already exists at `rpc.py:90`. Ticket 08's amendment was right. What Builder
  lacks is the `2026-07-28` result shape, which is why the probe fails.
- **`server/discover` is not new in `2026-07-28`.** It is new as a server
  *requirement*. Builder's body is the wrong shape in four fields, so it is
  worse than useless to a modern client.

Builder also never reads the `MCP-Protocol-Version` header and never inspects
`params._meta`. An unknown version is silently downgraded to `2025-06-18`, with
no error. Verified by running the real handlers offline: `2026-07-28`,
`2025-11-25`, `banana`, `null` and a missing key all return `2025-06-18`.

### What the implementer builds

About **70 lines** in `rpc.py` and 1 to 3 in `http.py`. Section 6 of the report
itemises them. The load-bearing items:

- Branch on the presence of `params._meta["io.modelcontextprotocol/protocolVersion"]`.
  That one `if` is the era switch. Sketch keeps no session, so nothing else
  forks.
- **`rpc.handle` must be able to return HTTP 400.** Today it returns 200 for
  every protocol error. The `(status, payload)` tuple already carries a status,
  so the plumbing exists. This is the easiest thing to miss.
- Modern requires: three headers (`MCP-Protocol-Version`, `Mcp-Method`,
  `Mcp-Name`), two `_meta` keys (`protocolVersion`, `clientCapabilities`),
  `resultType` on every result, `ttlMs` and `cacheScope` on `tools/list`, and a
  real `DiscoverResult` with `serverInfo` moved into `_meta`.
- Two new error codes: `-32020` (header mismatch or missing) and `-32022`
  (`UnsupportedProtocolVersionError`, `data: {supported, requested}`). Both
  carry HTTP 400.
- Legacy keeps `initialize` and `ping`. Modern deletes them.
- `Mcp-Name` needs no Base64 sentinel decode. Sketch slugs are `[a-z0-9-]`.
  Record the limit.

Unchanged: the auth gate, the `page_renderer` hook, the 401 `WWW-Authenticate`
path, `tools.py`, `dispatch.py`, the batch reject, the notification 202, and
the `TOOLS` dict. No new dependency.

Ticket 08's `outputSchema` and `structuredContent` work is separate and still
needed.

### Known gaps

- No `2026-07-28`-only server was built, so the modern path is **unverified**
  against a running client. Only the legacy fallback was captured.
- The claude.ai hosted connector runner was not observed.
- Dual-era code outlives its last caller silently. Nothing in Sketch will say
  when the legacy branch stops being used.
