# Which MCP protocol revision Sketch speaks

Ticket: `apps/sketch/.scratch/sketch-mvp/issues/18-mcp-protocol-revision.md`
Scope: the specification, the SDKs, and local client evidence.
Sections 1 to 6 are spec and SDK source. Section 7 is what was observed
on this box.

Source A: `modelcontextprotocol/modelcontextprotocol`, branch `main`,
HEAD `d8fdc88fb970313247d8a180ac1ec3f6a10a8885` (2026-08-26). Read 2026-08-27
over `raw.githubusercontent.com`. Files cited by repo path.
Source B: Builder's `/mcp`, `/home/faris/benches/builder-bench/apps/builder`,
branch `forge/mcp-server`, commit `98e8c6af`. Read 2026-08-27.
Source C: research note `09-builder-mcp-reuse.md` in this folder.

## Gist

- `2026-07-28` is current. The repo says so: "The **current** protocol version is
  [**2026-07-28**]" (`docs/docs/2026-07-28/learn/versioning.mdx`).
- Five released revisions: `2024-11-05`, `2025-03-26`, `2025-06-18`,
  `2025-11-25`, `2026-07-28`, plus `draft`.
- `2026-07-28` deletes `initialize`, `ping`, `Mcp-Session-Id`, the GET stream,
  and `Last-Event-ID`. Sketch's transport already has none of them.
- The new cost is per-request validation, not architecture: three required
  headers, two required `_meta` keys, one new error code, and `resultType` on
  every result.
- `server/discover` is mandatory for servers. Builder already has the method,
  but its result body is wrong in four fields.
- One endpoint can legally serve both eras. The spec names the pattern
  ("dual-era") and says the server picks by how the client opens.
- Both Tier 1 SDKs ship `2026-07-28`. Python `mcp` 2.1.1 since 2.0.0 on
  2026-07-28; TypeScript in the new v2 packages, `2.0.0` on 2026-07-27. TS v1
  `1.30.0` is 2025-era only.
- The asymmetry that decides this: the **TypeScript v2 client defaults to the
  legacy handshake**, so a `2026-07-28`-only Sketch would fail against it. Both
  clients fall back cleanly to `initialize` against a `2025-06-18` Sketch.

## 1. Revision list and dates

Canonical revision strings, from the schema directory
(`schema/`, listed via the GitHub contents API, 2026-08-27):

| Revision | `LATEST_PROTOCOL_VERSION` in its own `schema.ts` | State |
|---|---|---|
| `2024-11-05` | — (not read) | released |
| `2025-03-26` | — (not read) | released |
| `2025-06-18` | `"2025-06-18"` (`schema/2025-06-18/schema.ts:12`) | released |
| `2025-11-25` | `"2025-11-25"` (`schema/2025-11-25/schema.ts:12`) | released |
| `2026-07-28` | `"2026-07-28"` (`schema/2026-07-28/schema.ts:30`) | **current** |
| `draft` | — | in progress |

The same five appear in the docs navigation (`docs/docs.json`).

Between `2025-06-18` and `2026-07-28` there is exactly one released revision:
`2025-11-25`.

Current is stated normatively in `docs/docs/2026-07-28/learn/versioning.mdx`:

> The **current** protocol version is [**2026-07-28**](/specification/2026-07-28/).

Publication date: the commit `b488c16623` "Add 2026-07-28 MCP specification"
landed `schema/2026-07-28/schema.ts` on **2026-07-28T15:56:05Z**. So the
revision string is also its release date.

The format is defined in the same page:

> The Model Context Protocol uses string-based version identifiers following the
> format `YYYY-MM-DD`, to indicate the last date backwards incompatible changes
> were made.

## 2. `2026-07-28` in detail

### 2.1 `io.modelcontextprotocol/protocolVersion` in `_meta`

**The client sets it. On every request. The server MUST read it and MUST reject
a request that omits it.** Servers never echo it.

`docs/specification/2026-07-28/basic/index.mdx`, "Per-request protocol fields":

> Client requests carry the following `io.modelcontextprotocol/*` fields in
> `_meta`; fields marked as required **MUST** be included on every request.

The table marks `io.modelcontextprotocol/protocolVersion` (`string`) Required
**Yes**, and `io.modelcontextprotocol/clientCapabilities` (`ClientCapabilities`)
Required **Yes**. `io.modelcontextprotocol/clientInfo` and
`io.modelcontextprotocol/logLevel` are Required **No**.

Same page, the rejection rule:

> A request missing any required field is malformed; the server **MUST** reject
> it with JSON-RPC error code `-32602` (Invalid params). On HTTP, the response
> status **MUST** be `400 Bad Request`.

The schema agrees. `schema/2026-07-28/schema.ts:179-181`:

```ts
export interface RequestParams {
  _meta: RequestMetaObject;
}
```

`_meta` is not optional, and `RequestMetaObject`
(`schema/2026-07-28/schema.ts:63-111`) declares
`"io.modelcontextprotocol/protocolVersion": string;` and
`"io.modelcontextprotocol/clientCapabilities": ClientCapabilities;` with no `?`.

**What the server owes back**: not the version. It owes its own identity, and
only as a SHOULD. Same page, "Per-response protocol fields":

> Servers **SHOULD** include the following `io.modelcontextprotocol/*` field in
> every result's `_meta`, unless specifically configured not to do so, to
> identify themselves without relying on any prior connection state:
> `io.modelcontextprotocol/serverInfo`.

One more server obligation attaches to capabilities
(`docs/specification/2026-07-28/basic/index.mdx`):

> A server **MUST NOT** rely on capabilities the client has not declared. If
> processing a request requires a capability the client did not include in
> `io.modelcontextprotocol/clientCapabilities`, the server **MUST** return a
> `MissingRequiredClientCapabilityError` (`-32021`) whose
> `data.requiredCapabilities` lists the missing capabilities.

Sketch's 11 tools need no client capability, so `-32021` is dead code for
Sketch. It stays unimplemented at no risk.

### 2.2 The `MCP-Protocol-Version` HTTP header

**Required on every client-to-server POST. Never sent by the server.**

`docs/specification/2026-07-28/basic/transports/streamable-http.mdx`,
"Protocol Version Header":

> Every POST request to the MCP endpoint **MUST** include an
> `MCP-Protocol-Version` header.

> The header value **MUST** match the `io.modelcontextprotocol/protocolVersion`
> field carried in the request body's `_meta`. If the values do not match, the
> server **MUST** reject the request with `400 Bad Request` and a
> `HeaderMismatch` JSON-RPC error.

Two more headers join it in the same revision, same file, "Standard Request
Headers":

| Header | Source field | Required for |
|---|---|---|
| `Mcp-Method` | `method` | All requests |
| `Mcp-Name` | `params.name` or `params.uri` | `tools/call`, `resources/read`, `prompts/get` |

> These headers are **REQUIRED** for compliance.

**When the header is absent**, the server has a choice, and it is spelled out:

> A server that supports clients implementing protocol versions earlier than
> `2025-06-18` (which did not define the `MCP-Protocol-Version` header) **MAY**
> treat a request that omits the header as protocol version `2025-03-26`. A
> server that does not support such clients **MUST** reject a request without
> the header per [Server Validation].

Server Validation names the failure list and the code (same file):

> When rejecting a request due to header validation failure, servers **MUST**
> return HTTP status `400 Bad Request` and **MUST** include a JSON-RPC error
> response using the following error code: `-32020` `HeaderMismatch`.

> Validation failure conditions include: A required standard header
> (`MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name`) is missing.

For comparison, the old rule Sketch inherits. `2025-06-18` made the header a
client MUST but let the server guess:

> For backwards compatibility, if the server does _not_ receive an
> `MCP-Protocol-Version` header, and has no other way to identify the version
> ... the server **SHOULD** assume protocol version `2025-03-26`.
> (`docs/specification/2025-06-18/basic/transports.mdx:251-254`)

> If the server receives a request with an invalid or unsupported
> `MCP-Protocol-Version`, it **MUST** respond with `400 Bad Request`.
> (same file, `:256-257`)

Builder never reads the header at all. Ticket 08 already recorded that gap.
Under `2025-06-18` it is a missed MUST on the server side only for the invalid
case, because Builder answers everything with 200.

### 2.3 `server/discover`

**Mandatory for servers. Optional for clients. It does not replace
`initialize`, because `initialize` no longer exists.**

`docs/specification/2026-07-28/server/discover.mdx`:

> `server/discover` lets a client query a server's supported protocol versions,
> capabilities, and identity before sending any other requests. Servers **MUST**
> implement it.

> Calling `server/discover` is optional for clients — a client may invoke any RPC
> inline and handle `UnsupportedProtocolVersionError` if the server does not
> support the requested version.

`docs/specification/2026-07-28/basic/versioning.mdx` repeats it:

> Servers **MUST** implement `server/discover`. Clients **MAY** call it before
> sending any other requests to learn the server's supported versions up front,
> but are not required to.

`initialize` is gone from the schema. `schema/2026-07-28/schema.ts` has no
`InitializeRequest` and no `method: "initialize"`. Nor `ping`. The changelog
(`docs/specification/2026-07-28/changelog.mdx`, major change 2 and 5):

> Make MCP stateless: remove the `initialize`/`notifications/initialized`
> handshake.

> Remove `ping`, `logging/setLevel`, and `notifications/roots/list_changed`.

**The exact result body.** `DiscoverResult extends CacheableResult`
(`schema/2026-07-28/schema.ts:678-696`), and `CacheableResult extends Result`
(`:1081-1110`). Stacking the three:

| Field | Required | From |
|---|---|---|
| `resultType` | yes | `Result` (`schema.ts:234`) |
| `supportedVersions: string[]` | yes | `DiscoverResult` |
| `capabilities: ServerCapabilities` | yes | `DiscoverResult` |
| `ttlMs: number` | yes | `CacheableResult` |
| `cacheScope: "public" \| "private"` | yes | `CacheableResult` |
| `instructions?: string` | no | `DiscoverResult` |
| `_meta["io.modelcontextprotocol/serverInfo"]` | SHOULD | `ResultMetaObject` (`schema.ts:143-158`) |

The canonical example (`docs/specification/2026-07-28/server/discover.mdx`):

```json
{
  "jsonrpc": "2.0",
  "id": "discover-1",
  "result": {
    "resultType": "complete",
    "supportedVersions": ["2026-07-28"],
    "capabilities": { "tools": {}, "resources": {} },
    "_meta": {
      "io.modelcontextprotocol/serverInfo": { "name": "ExampleServer", "version": "1.0.0" }
    },
    "instructions": "This server provides weather and resource utilities.",
    "ttlMs": 3600000,
    "cacheScope": "public"
  }
}
```

Builder's `handle_discover` (`builder/ai/mcp/rpc.py:88-95`) returns
`supportedVersions`, `capabilities`, `serverInfo`, `instructions`. Four
mismatches against the above: no `resultType`, no `ttlMs`, no `cacheScope`, and
`serverInfo` at the top level instead of inside `_meta`. So Sketch inherits the
method name and must rewrite the body.

### 2.4 `UnsupportedProtocolVersionError`

Code **`-32022`**. HTTP **400**. `data` carries `supported` and `requested`.

`schema/2026-07-28/schema.ts:450`:

```ts
export const UNSUPPORTED_PROTOCOL_VERSION = -32022;
```

`schema/2026-07-28/schema.ts:483-497` gives the shape: `error.code` is
`-32022`, `error.data.supported: string[]` ("Protocol versions the server
supports. The client should choose a mutually supported version from this list
and retry"), `error.data.requested: string`.

The doc comment on the interface:

> Returned when the request's protocol version is unknown to the server or
> unsupported (e.g., a known experimental or draft version the server has chosen
> not to implement). For HTTP, the response status code MUST be
> `400 Bad Request`.

The obligation to send it, from
`docs/specification/2026-07-28/basic/versioning.mdx`:

> If the server does not implement the requested version (whether the version is
> unknown to the server, or is a known version the server has chosen not to
> support), it **MUST** respond with an `UnsupportedProtocolVersionError` listing
> the versions it does support.

Canonical payload
(`schema/2026-07-28/examples/UnsupportedProtocolVersionError/unsupported-version.json`):

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32022,
    "message": "Unsupported protocol version",
    "data": { "supported": ["2026-07-28", "2025-11-25"], "requested": "1900-01-01" }
  }
}
```

The client side is a SHOULD, not a MUST
(`docs/specification/2026-07-28/basic/versioning.mdx`):

> The client **SHOULD** select a mutually supported version from the `supported`
> list and retry the request, or surface an error to the user if no compatible
> version exists.

### 2.5 The error-code range, which bites Builder's 405 body

`docs/specification/2026-07-28/basic/index.mdx`, "Error Codes":

> **`-32000` to `-32019` — legacy.** Codes in this sub-range were allocated by
> implementations before this policy was introduced. New codes **MUST NOT** be
> allocated in this sub-range, and new implementations **SHOULD NOT** use codes
> from this sub-range at all.

Builder's non-POST branch returns `-32000` (`builder/ai/mcp/http.py:34`). Under
`2026-07-28` that is a SHOULD NOT. One-line fix.

The three codes the revision defines: `-32020` `HeaderMismatch`, `-32021`
`MissingRequiredClientCapability`, `-32022` `UnsupportedProtocolVersion`.

### 2.6 Everything else that touches a stateless POST-only server

**Removed, and Sketch never had it.** From
`docs/specification/2026-07-28/basic/transports/streamable-http.mdx`, the
opening note: "Removal of the GET stream endpoint. Removal of protocol-level
sessions." And the compatibility section spells out the server's duty:

> A server that supports only this revision and receives such traffic from an
> older client **SHOULD** respond as follows:
> - HTTP GET or DELETE to the MCP endpoint: respond with `405 Method Not Allowed`.
> - An `Mcp-Session-Id` header on a request: ignore it, and do not mint or echo session IDs.
> - A `Last-Event-ID` header: ignore it; streams are not resumable.

Sketch already 405s GET (`builder/ai/mcp/http.py:33-35`) and never touches the
other two. Note one gap: Frappe raises `NotFound` for `PUT`/`DELETE` before the
renderer runs (research note 09, section 1), so `DELETE /mcp` answers **404**,
not 405. That is a SHOULD, not a MUST.

**Result shape.** Every result now needs `resultType`
(`schema/2026-07-28/schema.ts:218-235`):

> Servers implementing this protocol version MUST include this field. For
> backward compatibility, when a client receives a result from a server
> implementing an earlier protocol version (which does not include
> `resultType`), the client MUST treat the absent field as `"complete"`.

`ResultType` is `"complete" | "input_required" | string`. Sketch always sends
`"complete"`.

**`tools/list` gains two required fields.** `ListToolsResult extends
PaginatedResult, CacheableResult` (`schema/2026-07-28/schema.ts:1779-1781`), so
`ttlMs` and `cacheScope` are mandatory. The changelog, minor change 5:

> Require `ttlMs` and `cacheScope` fields on results returned by `tools/list`,
> `prompts/list`, `resources/list`, `resources/read`, and
> `resources/templates/list` via a new `CacheableResult` interface.

Also, from `docs/specification/2026-07-28/server/tools.mdx`, a constraint Sketch
already satisfies:

> This set **MAY** be empty and **MAY** change over time ... but **MUST NOT**
> vary per-connection or as a side effect of other requests on the connection.
> The set **MAY** vary by the authorization presented on the request.

**`tools/call` is unchanged in the parts Sketch uses.** `CallToolResult`
(`schema/2026-07-28/schema.ts:1809-1846`) still has `content: ContentBlock[]`,
`structuredContent?: unknown`, `isError?: boolean`. `Tool` still has
`outputSchema?` (`:2005`) and `annotations?: ToolAnnotations` (`:2012`) with
`readOnlyHint` (`:1923`) and `destructiveHint` (`:1933`). Ticket 08's
structured-output plan and the destructive annotations survive the move
unchanged. `structuredContent` got looser, not stricter (changelog, minor change
10: "Loosen `inputSchema` and `outputSchema` to allow any JSON Schema 2020-12
keywords, and `structuredContent` to allow any JSON value").

**Auth.** No change that affects a Bearer token. The auth chapter is still
opt-in for HTTP (`docs/specification/2026-07-28/basic/index.mdx`):

> Implementations using an HTTP-based transport **SHOULD** conform to this
> specification ... Additionally, clients and servers **MAY** negotiate their own
> custom authentication and authorization strategies.

The `2026-07-28` auth changes are all on the OAuth path: RFC 9207 `iss`
validation, `application_type` on Dynamic Client Registration, issuer-bound
client credentials, and DCR itself deprecated in favour of Client ID Metadata
Documents (changelog, minor changes 7-9 and Deprecated 4). Sketch's `Sketch
Token` Bearer scheme (ticket 12) is untouched. The deferred OAuth item in the
map now carries one extra note: DCR, which Frappe already implements
(`register_client`), is Deprecated as of `2026-07-28`, earliest removal "First
revision released on or after 2027-07-28"
(`docs/specification/2026-07-28/deprecated.mdx`).

**Elicitation, sampling, roots, logging.** Not in Sketch, and moving away.
Roots, Sampling and Logging are Deprecated in `2026-07-28` (changelog,
Deprecated 1; `deprecated.mdx`). Server-initiated requests are replaced by
MRTR: the server answers `resultType: "input_required"` and the client retries
(changelog, major change 7). Sketch needs none of it.

**SSE.** Still allowed but never required of the server. The client must accept
both (`streamable-http.mdx`):

> If the body is a JSON-RPC _request_, the server **MUST** return either
> `Content-Type: application/json` (a single JSON object) or
> `Content-Type: text/event-stream` (an SSE response stream). The client
> **MUST** support both.

So Sketch's plain-JSON reply stays legal, and `check` still cannot stream
progress. Ticket 10's conclusion holds.

**Icons.** Optional, unchanged in kind. `Tool extends BaseMetadata, Icons`
(`schema.ts:1973`). Icons arrived in `2025-11-25` (its changelog, major change
2). Sketch can ignore them.

**Statelessness is now normative prose**, which is worth quoting because it
describes what Sketch already built (`basic/index.mdx`):

> The Model Context Protocol (MCP) is a **stateless protocol**: all the
> information needed to process a request is contained in the request itself.
> ... Servers **MUST NOT** rely on prior requests over the same connection to
> establish context (e.g., capabilities, protocol version, client identity).

## 3. Backward compatibility, precisely

The ticket's claim is correct. The normative text is
`docs/specification/2026-07-28/basic/versioning.mdx`, section "Backward
Compatibility with Initialization-Based Versions". It defines two words:

> - **Modern**: protocol versions that convey version, identity, and
>   capabilities as per-request metadata (revision `2026-07-28` and later).
> - **Legacy**: protocol versions that establish a session with an `initialize`
>   handshake (`2025-11-25` and earlier).
> - **Dual-era**: an implementation that supports both modern and legacy
>   versions.

So `2025-06-18` is legacy by definition.

### 3.1 Sketch ships only `2025-06-18`, a `2026-07-28` client connects

Two outcomes, decided by whether the client is modern-only or dual-era. The
compatibility matrix in the same file:

| Client | Server | Outcome (quoted) |
|---|---|---|
| Modern | Legacy | "Fails. The server may reject the request with an implementation-defined error, stay silent, or even process an era-ambiguous method under legacy semantics." |
| Dual-era | Legacy | "Works. ... HTTP: the modern request returns a `4xx` without a recognized modern error body, and the client falls back to `initialize`." |

The HTTP fallback rule the dual-era client follows
(`streamable-http.mdx`, "Backward Compatibility"):

> A client that supports both modern (per-request-metadata) MCP versions and a
> legacy version that requires an `initialize` handshake **MAY** detect which era
> the server implements by attempting a modern request first. On
> `400 Bad Request`, the client **SHOULD** inspect the response body before
> falling back ...
> - If the body is empty or is not a recognized modern JSON-RPC error, fall back
>   to `initialize` and continue with the legacy version for subsequent requests.

**Read literally, Sketch has a hazard here.** The spec's fallback trigger is
`400 Bad Request`. Builder answers every JSON-RPC problem with **HTTP 200** and
an error body (`builder/ai/mcp/rpc.py:40-63`; research note 09, section 5).
Nothing Sketch returns is a `400`, so the "inspect the body of a 400" branch
never runs.

**In the SDKs it is not a hazard.** Section 5.3 shows the real client logic is
a denylist: anything that is not positive evidence of a modern server falls
back to `initialize`. Builder's `server/discover` reply fails that test twice
over, and the client connects on the legacy path. So the matrix row "Modern |
Legacy: Fails" describes a modern-**only** client. Both Tier 1 SDKs ship
dual-era clients, and only an explicit version pin turns off the fallback.

Untested against a real client; see "Not verified".

### 3.2 Sketch ships only `2026-07-28`, a `2025-06-18`-era client connects

It fails, and the spec says how:

> | Legacy | Modern | Fails. ... HTTP: the request is missing the required
> headers and is rejected per [server validation] with `400 Bad Request` (a
> client on the deprecated HTTP+SSE transport fails at its opening `GET`
> instead). Legacy clients have no fall-forward mechanism. |

One softening duty on the server:

> A server that supports only [modern] versions **SHOULD** name the protocol
> versions it supports in any error it returns to an `initialize` request, on
> any transport: legacy clients have no fall-forward mechanism, and this message
> may be the only diagnostic they can surface to users.

### 3.3 Serving both from one endpoint

Yes, the spec blesses it. Same file:

> A server that wishes to support both [legacy] clients (which expect an
> `initialize` handshake) and [modern] clients (which use per-request metadata)
> **MAY** implement both behaviors.

> A dual-era **server** selects its behavior from how the client opens:
> - A request carrying modern per-request `_meta` is served statelessly
>   according to this revision.
> - An `initialize` request selects legacy semantics, scoped to the stdio
>   process (stdio) or the session (HTTP), as specified by the negotiated legacy
>   protocol version.
>
> A dual-era server **MAY** serve both eras concurrently on the same endpoint or
> process.

For a legacy client the matrix says "Legacy | Dual-era: Works."

**What it costs in Sketch's code.** The branch is one `if` on the presence of
`params._meta["io.modelcontextprotocol/protocolVersion"]`, because Sketch keeps
no session and legacy `initialize` is already answered statelessly
(`builder/ai/mcp/rpc.py:78-85`). The real cost is two result shapes for the
same three methods:

- `tools/list`: modern adds `resultType`, `ttlMs`, `cacheScope`. Legacy must not
  have them (harmless if present, but `resultType` is meaningless pre-`2026-07-28`).
- `tools/call`: modern adds `resultType`.
- `server/discover`: legacy has no such method; modern needs the full
  `DiscoverResult`.
- `initialize` and `ping` stay for legacy only.

Estimate: about **15 extra lines** on top of the modern-only port, plus a
`resultType`-injection switch in `result()`. There is no session store and no
second transport, which is what usually makes dual-era expensive.

## 4. `2025-11-25`, the middle option

Its changelog (`docs/specification/2025-11-25/changelog.mdx`) lists nine major
changes. Scored against Sketch's 11 tools and a Bearer-token endpoint:

| Change | Wanted by Sketch |
|---|---|
| OpenID Connect Discovery for auth server discovery (PR 797) | No. OAuth is deferred. |
| Icons on tools, resources, templates, prompts (SEP-973) | No. Cosmetic. |
| Incremental scope consent via `WWW-Authenticate` (SEP-835) | No. |
| Tool-name guidance (SEP-986) | No code change. |
| `ElicitResult` / `EnumSchema` rework (SEP-1330) | No. No elicitation. |
| URL mode elicitation (SEP-1036) | No. |
| Tool calling in sampling (SEP-1577) | No. No sampling. |
| OAuth Client ID Metadata Documents (SEP-991) | No, and it is where `2026-07-28` goes anyway. |
| Experimental tasks (SEP-1686) | No. Moved out of core in `2026-07-28`. |

Minor changes worth naming: "Clarify that input validation errors should be
returned as Tool Execution Errors rather than Protocol Errors to enable model
self-correction (SEP-1303)", and "Establish JSON Schema 2020-12 as the default
dialect". Sketch's `isError` convention (ticket 08, via `dispatch.py`) already
matches SEP-1303.

Handshake mechanics are identical to `2025-06-18`. Version negotiation is still
`initialize` (`docs/specification/2025-11-25/basic/lifecycle.mdx:165-176`):

> If the server supports the requested protocol version, it **MUST** respond
> with the same version. Otherwise, the server **MUST** respond with another
> protocol version it supports. ... If the client does not support the version in
> the server's response, it **SHOULD** disconnect.

**Verdict: `2025-11-25` buys Sketch nothing.** It costs one string in
`PROTOCOL_VERSIONS` and delivers no feature Sketch's tool surface uses. As a
declared version it is slightly more current than `2025-06-18`; as work, it is
noise.

## 5. SDK reality

Sketch uses no SDK. Read this as what clients in the wild speak.

Both Tier 1 SDKs ship `2026-07-28` today. Both also default to, or fall back
to, the legacy handshake. Agents read the source at the release tags named
below on 2026-08-27; the two constant blocks were re-checked by hand.

### 5.1 TypeScript, `modelcontextprotocol/typescript-sdk`

The repo is a monorepo with two live lines.

| Line | Package | Version | Released |
|---|---|---|---|
| v1 | `@modelcontextprotocol/sdk` | 1.30.0 | 2026-07-27 |
| v2 | `@modelcontextprotocol/{core,client,server,node,...}` | 2.0.0 | 2026-07-27 |

`packages/core/src/constants.ts:1-3`, at tag
`@modelcontextprotocol/core@2.0.0`:

```ts
export const LATEST_PROTOCOL_VERSION = '2025-11-25';
export const DEFAULT_NEGOTIATED_PROTOCOL_VERSION = '2025-03-26';
export const SUPPORTED_PROTOCOL_VERSIONS = [LATEST_PROTOCOL_VERSION, '2025-06-18', '2025-03-26', '2024-11-05', '2024-10-07'];
```

That list is the **handshake era only**. The modern era has its own registry,
`packages/core-internal/src/shared/protocolEras.ts:25,33`, same tag:

```ts
export const FIRST_MODERN_PROTOCOL_VERSION = '2026-07-28';
export const SUPPORTED_MODERN_PROTOCOL_VERSIONS = [FIRST_MODERN_PROTOCOL_VERSION];
```

So in TypeScript, `LATEST_PROTOCOL_VERSION` still reads `2025-11-25`. It does
not mean the SDK is behind. It means the name was kept for the legacy list.

v1 `1.30.0` is 2025-era only. An agent grepped the full tag archive and found
zero occurrences of `2026-07-28`, `server/discover`, `-32022`, or
`io.modelcontextprotocol/protocolVersion`.

**The default matters more than the constants.** `docs/protocol-versions.md` at
tag `@modelcontextprotocol/core@2.0.0`:

> `mode` takes three values; the first is the default.
> - Absent, or `mode: 'legacy'` — the 2025 `initialize` handshake, byte for
>   byte. No probe.
> - `mode: 'auto'` — probe with `server/discover`; fall back to `initialize`
>   against a 2025-only server.
> - `mode: { pin: '2026-07-28' }` — that revision or nothing. A pin never falls
>   back.

The code says the same, `packages/client/src/client/versionNegotiation.ts:98-112`
at the same tag (read by hand):

```ts
     * @default 'legacy'
     */
    mode?: VersionNegotiationMode;
...
const DEFAULT_VERSION_NEGOTIATION_MODE: VersionNegotiationMode = 'legacy';
```

A TypeScript v2 client built with defaults opens with `initialize`. It never
learns Sketch is old, because it never asks. **It also cannot reach a
modern-only server**: `initialize` does not exist there, and the POST carries
none of the required headers, so it earns a `400`.

The `_meta` keys are all exported (`packages/core/src/constants.ts:19,28,37,45`:
`PROTOCOL_VERSION_META_KEY`, `CLIENT_INFO_META_KEY`, `SERVER_INFO_META_KEY`,
`CLIENT_CAPABILITIES_META_KEY`). `-32022` is at
`packages/core-internal/src/types/errors.ts:169`.

One released bug, reported by the agent and not re-checked by hand: at v2.0.0
the modern path tolerates a **missing** `MCP-Protocol-Version` header and
dispatches with HTTP 200; only a mismatch gives `-32020`
(`packages/core-internal/src/shared/inboundClassification.ts:20,53-58`). `main`
fixes it, unreleased as of 2026-08-27.

### 5.2 Python, `modelcontextprotocol/python-sdk`

Current release **`mcp` 2.1.1**, tag `v2.1.1`, published 2026-08-25. Types moved
into a separate `mcp-types` distribution.

`src/mcp-types/mcp_types/version.py:24-59`, at tag `v2.1.1` (read by hand):

```python
KNOWN_PROTOCOL_VERSIONS: Final[tuple[str, ...]] = (
    "2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25", "2026-07-28",
)
HANDSHAKE_PROTOCOL_VERSIONS: Final[tuple[str, ...]] = (
    "2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25",
)
MODERN_PROTOCOL_VERSIONS: Final[tuple[str, ...]] = ("2026-07-28",)
SUPPORTED_PROTOCOL_VERSIONS: tuple[str, ...] = (*HANDSHAKE_PROTOCOL_VERSIONS, *MODERN_PROTOCOL_VERSIONS)
LATEST_PROTOCOL_VERSION: Final[str] = KNOWN_PROTOCOL_VERSIONS[-1]
```

`LATEST_PROTOCOL_VERSION` is `"2026-07-28"`. `SUPPORTED_PROTOCOL_VERSIONS`
carries its own deprecation docstring: "Deprecated: prefer
HANDSHAKE_PROTOCOL_VERSIONS or MODERN_PROTOCOL_VERSIONS."

`2026-07-28` landed in `mcp` 2.0.0, released 2026-07-28, the same day as the
spec. The version registry above is already final at tag `v2.0.0`.

**The Python default is `auto`, not legacy.** `docs/protocol-versions.md` at
`v2.1.1`:

> You didn't pass `mode`, so you got the default: `"auto"`. Entering
> `async with` sends a single `server/discover` probe at the newest version
> this SDK speaks.

`-32022` is `src/mcp-types/mcp_types/jsonrpc.py:79`. The server's default
`server/discover` handler returns
`DiscoverResult(supported_versions=list(MODERN_PROTOCOL_VERSIONS), ...)`
(`src/mcp/server/lowlevel/server.py:667-671`). The client stamps the header on
both eras (`src/mcp/client/session.py:153-157`), and the modern server path
rejects an absent header with `-32020` (`src/mcp/shared/inbound.py:448-456`).

### 5.3 The probe is a denylist, which is what saves an old Sketch

This is the finding that matters for Sketch, and it comes out of the Python
probe. `src/mcp/client/_probe.py` at tag `v2.1.1`, module docstring:

> The `server/discover` probe is sent at the newest modern version. Anything
> that is not positive evidence the peer is a modern MCP server falls back to
> the legacy `initialize` handshake — a *denylist* (only the disjoint-modern
> case raises) rather than an allowlist of fallback codes.

> A successful `DiscoverResult` whose `supportedVersions` shares no modern
> version with this client is treated the same way: the server speaks discover
> but advertises only handshake-era versions, which is a legacy advertisement,
> not an incompatibility.

The code path, `_probe.py:99-113`:

```python
try:
    result = types.DiscoverResult.model_validate(raw)
except ValidationError:
    await session.initialize()  # unparseable result → not modern evidence
    return
if not any(v in result.supported_versions for v in MODERN_PROTOCOL_VERSIONS):
    await session.initialize()
    return
```

Builder's `server/discover` (`builder/ai/mcp/rpc.py:88-95`) hits **both**
branches. Its body omits `cacheScope`, which the pydantic model declares with
no default (`src/mcp-types/mcp_types/_v2026_07_28/__init__.py:3148`), so
`model_validate` raises. And its `supportedVersions` is
`["2025-06-18", "2025-03-26"]`, which shares nothing with
`MODERN_PROTOCOL_VERSIONS`. Either way the client falls back to `initialize`
and connects.

The same file says the other clients behave the same way (`_probe.py:106-109`):

> A discover-answering server that advertises no modern version (go-sdk's
> stateful streamable default does this) is an explicit legacy advertisement:
> fall back like the `-32022` branch above instead of letting `adopt()` raise.
> The ts and go clients fall back here too.

Only `mode: { pin: '2026-07-28' }` refuses to fall back, and a pin is opt-in.

### 5.4 What an old server gets at `initialize`

TypeScript, `packages/client/src/client/client.ts:1041-1073` at tag
`@modelcontextprotocol/core@2.0.0`, reported by the agent:

```ts
if (!legacyVersions.includes(result.protocolVersion)) {
    throw new Error(`Server's protocol version is not supported: ${result.protocolVersion}`);
}
```

Python, `src/mcp/client/session.py:658-680` at `v2.1.1`:

```python
protocol_version=LATEST_HANDSHAKE_VERSION,
...
if result.protocol_version not in HANDSHAKE_PROTOCOL_VERSIONS:
    raise RuntimeError(f"Unsupported protocol version from the server: {result.protocol_version}")
```

Both offer their newest handshake version, and both accept any counter-offer
inside their handshake list. `2025-06-18` is in both lists. So a
`2025-06-18` server still completes the handshake with a current SDK client.

### 5.5 Summary

| | TS `sdk` 1.30.0 | TS v2 `core` 2.0.0 | Python `mcp` 2.1.1 |
|---|---|---|---|
| Released | 2026-07-27 | 2026-07-27 | 2026-08-25 |
| Speaks `2026-07-28` | no | yes | yes (since 2.0.0, 2026-07-28) |
| Handshake list includes `2025-06-18` | yes | yes | yes |
| Client default | handshake | handshake (`legacy`) | probe then fall back (`auto`) |
| `server/discover`, `-32022`, `_meta` version | no | yes | yes |

## 6. Cost estimate: `2025-06-18` to `2026-07-28` in the hand-rolled handler

Baseline: `builder/ai/mcp/rpc.py` (128 lines) and `http.py` (46 lines), which
ticket 09 says Sketch copies with small edits.

New work, by file:

**`http.py`**. Headers are only readable here, but the body is only parsed in
`rpc.py`, so header/body comparison must move into `rpc.handle`. Pass
`frappe.request.headers` in, or read `frappe.request` inside `rpc`.

1. Change the non-POST error code off `-32000` (`http.py:34`). **1 line.**
2. Add `DELETE` to the 405 branch. Dead code on Frappe today, because core
   raises `NotFound` first (research note 09, section 1). **0-2 lines,
   optional.**

**`rpc.py`**. Six new branches:

3. Extract `_meta` from `params`. Reject a missing
   `io.modelcontextprotocol/protocolVersion` or
   `io.modelcontextprotocol/clientCapabilities` with `-32602` and HTTP **400**.
   **~10 lines.**
4. Compare the `MCP-Protocol-Version` header to the `_meta` value. Mismatch or
   missing header, missing `Mcp-Method`, missing `Mcp-Name` on `tools/call`:
   HTTP **400** plus `-32020`. `Mcp-Name` needs the Base64 sentinel decode only
   if a slug is ever non-ASCII; Sketch slugs are `[a-z0-9-]`, so skip it and
   note the limit. **~20 lines.**
5. Reject an unsupported version with HTTP **400** plus `-32022` and
   `data: {supported, requested}`. **~8 lines.**
6. Rewrite `handle_discover` to a real `DiscoverResult`: add `resultType`,
   `ttlMs`, `cacheScope`, move `serverInfo` into `_meta`. **~8 lines.**
7. Add `resultType: "complete"` and `_meta.io.modelcontextprotocol/serverInfo`
   in `result()`, so every method gets both for free. **~5 lines.**
8. Add `ttlMs` and `cacheScope` to `handle_tools_list`. **2 lines.**
9. Drop `initialize` and `ping` from `METHODS`, or keep them behind the
   dual-era `if`. **2 lines either way.**

**Unchanged**: the parse-error, batch-reject, notification-202, unknown-method,
`RpcError` and crash branches; `tools/list` item shape; `tools/call` content and
`isError`; the `TOOLS` dict; `dispatch.py`; `http.py`'s auth gate; the
`page_renderer` hook.

**Not needed at all**: `subscriptions/listen`, MRTR / `input_required`,
sampling, roots, logging, tasks, extensions, session storage, SSE, cursors.

Totals: about **55 new lines** in `rpc.py`, **1 to 3** in `http.py`, one new
constant tuple, two new error codes (`-32020` and `-32022`), and one behaviour
change that is easy to miss: **`rpc.handle` must now be able to return HTTP
400**. Today it returns 200
for every protocol error and 202 for notifications
(`builder/ai/mcp/rpc.py:40-63`). The `(status, payload)` tuple already carries
a status, so the plumbing exists.

No new dependency. No change to `tools.py`, `dispatch.py`, `hooks.py`, the
`Sketch Token` auth hook, or the 401 `WWW-Authenticate` path.

Dual-era on top of that: **~15 lines** more (section 3.3).

## 7. Local client evidence

Gathered on this box on 2026-08-27 by a second agent. Sources: Builder's
`/mcp` source, the installed Claude Code bundle, past MCP session logs, and a
live capture. The orchestrating session verified the cleanup afterwards:
nothing listens on the stub port, `~/.claude.json` still holds only `builder`,
and Builder's tree is clean on `forge/mcp-server`.

### 7.1 Builder's version handling, exactly

Branch `forge/mcp-server`, HEAD `98e8c6aff0d6d1ca79280f3019147079bdd9edb7`.
Five lines carry the whole of it. A grep for version strings across `builder/`
and `docs/` returns only these:

| Fact | Location |
|---|---|
| Hardcoded list | `rpc.py:17` — `PROTOCOL_VERSIONS = ("2025-06-18", "2025-03-26")` |
| Reads the client's ask | `rpc.py:79` — `requested = params.get("protocolVersion")` |
| Echo or force | `rpc.py:81` — `requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]` |
| `server/discover` body | `rpc.py:90` — `"supportedVersions": list(PROTOCOL_VERSIONS)` |
| Method table | `rpc.py:122-128` — `initialize`, `server/discover`, `ping`, `tools/list`, `tools/call` |

- An unknown version gets **no error**. Not `-32022`, not `-32602`, not a 4xx.
  Builder returns a normal success result carrying `2025-06-18`.
- The `MCP-Protocol-Version` request header is **never read**. `http.py` touches
  the method (`:35`), the session user (`:37`), the permission (`:39`), and the
  body (`:41`). A grep for any header name in `builder/ai/mcp/` returns nothing.
- `params._meta` is **never inspected** (`rpc.py:44-67`).

The real handlers were run offline in the Builder venv, `frappe.init` only, no
DB and no service:

```
'2026-07-28' -> 2025-06-18      '2024-11-05' -> 2025-06-18
'2025-11-25' -> 2025-06-18      'banana'     -> 2025-06-18
'2025-06-18' -> 2025-06-18      None         -> 2025-06-18
'2025-03-26' -> 2025-03-26      key absent   -> 2025-06-18
discover -> ["2025-06-18", "2025-03-26"]
```

This corrects the ticket. Ticket 18 says Builder knows `2025-06-18` only.
Builder knows two revisions and already has a `server/discover` method. Ticket
08's amendment (`08-mcp-tool-surface.md:153-156`) was right. What Builder does
**not** have is the `2026-07-28` result shape for that method, which is why the
probe below fails.

### 7.2 What Claude Code speaks

CLI **2.1.246**. Bundle
`/home/faris/.nvm/versions/node/v24.18.0/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe`,
248 MB, mtime 2026-08-26 22:10 +0530.

Version strings in the bundle: `2026-07-28` (25 hits), `2025-11-25` (7),
`2025-06-18` (4), `2025-03-26` (6), `2024-11-05` (5), `2024-10-07`.

The client's own supported list, offset 213583348:

```js
m2s=[$an,ZAe,"2025-06-18","2025-03-26","2024-11-05","2024-10-07"]
//   $an="2026-07-28"  ZAe="2025-11-25"
```

Negotiation path, all offsets in the same binary:

- "Modern" is a string compare: `function wO(e){return e>=yen}`, `yen="2026-07-28"`
  (offset 207723932).
- `connect()` runs a `server/discover` probe first (offset ~207995000) and
  validates the reply against the `2026-07-28` result schema. On failure, or on
  no modern overlap, the verdict is `{kind:"legacy"}`.
- `_legacyHandshake` (offset 208031770) then sends `initialize` asking
  `2025-11-25`, and accepts any reply version in the pre-2026 list:
  `if(!n.includes(o.protocolVersion)) throw Error(...)`. `2025-06-18` is in `n`.
- After negotiation the client stamps `mcp-protocol-version` on every request
  (offset 208012684). Servers may ignore it.

**Claude Code is not a default-configured TypeScript client.** It runs the probe,
so it behaves as `mode: 'auto'` (section 5.1), not as the `'legacy'` default.

### 7.3 Live capture against a Builder-shaped server

The Builder bench was not running and was not started. A stub on
`127.0.0.1:8765` reproduced `rpc.py` for `initialize`, `server/discover`,
`ping`, `tools/list`, and the 202 and 405 branches. Section 7.1 shows the real
handlers give identical output. The real CLI was pointed at it with
`--strict-mcp-config`.

```
REQ headers: user-agent: claude-code/2.1.246 (sdk-ts, agent-sdk/0.3.217)
             mcp-method: server/discover   mcp-protocol-version: 2026-07-28
REQ body: {"method":"server/discover","params":{"_meta":{
    "io.modelcontextprotocol/protocolVersion":"2026-07-28",
    "io.modelcontextprotocol/clientInfo":{...},
    "io.modelcontextprotocol/clientCapabilities":{"roots":{...},"elicitation":{}}}}}
RESP 200: {"result":{"supportedVersions":["2025-06-18","2025-03-26"],
           "capabilities":{"tools":{}}}}

REQ body: {"method":"initialize","params":{"protocolVersion":"2025-11-25",...}}
RESP 200: {"result":{"protocolVersion":"2025-06-18",
           "serverInfo":{"name":"frappe-builder","version":"1.0.0-dev"}}}

REQ notifications/initialized -> 202 empty
REQ GET /mcp                  -> 405 (Allow: POST), client continued
REQ tools/list                -> 200, tools returned
```

The probe reply carries no `resultType` and offers no modern version, so it
fails twice over. The client falls back with no error shown to the user.

A `notifications/cancelled` appeared once before `tools/list`. That is a stub
artifact: `http.server` is single-threaded, so the SSE `GET` blocked the
concurrent `POST`. Builder runs under werkzeug's threaded server.

Header matrix against the same stub: `MCP-Protocol-Version: 9999-99-99` is
ignored, 200, `protocolVersion` `2025-06-18`.

### 7.4 A real session, unstubbed

`/home/faris/.cache/claude-cli-nodejs/-home-faris-benches-builder-bench/mcp-logs-builder/2026-08-13T12-12-53-591Z.jsonl`,
CLI 2.1.231 against the live Builder `/mcp`:

```
Successfully connected (transport: http) in 127ms
Connection established with capabilities: {"hasTools":true,...
  "serverVersion":{"name":"frappe-builder","version":"1.0.0-dev"}}
```

Dozens of successful `tools/call` entries follow. The log does not print the
negotiated version.

### 7.5 The claude.ai connector

Not observable from here. The claude.ai Gmail and Google Calendar connectors are
registered but unauthenticated in this session, so no connector handshake
against a third-party server could be captured.

One local log covers the Claude Code to Anthropic-proxy leg only,
`.../mcp-logs-claude-ai-Gmail/2026-08-26T21-53-32-662Z.jsonl`:

```
Stateless claudeai-proxy — resolving MCP initialize from cached projection
Connection established with capabilities: {... "protocolEra":"legacy",
  "negotiatedProtocolVersion":"2025-11-25"}
```

The bundle matches. At offset 210373253 the claude.ai path skips `initialize`
and hardcodes the header:

```js
return {"anthropic-mcp-client-capabilities": t, "MCP-Protocol-Version": ZAe}  // ZAe = "2025-11-25"
```

So the claude.ai plumbing on this box runs legacy-era at `2025-11-25` as of
2026-08-26. Whether the hosted connector runner accepts a legacy-only
third-party server is **unverified**.

### 7.6 What this settles

- A `2025-06-18`-only Sketch **works with Claude Code 2.1.246 today**. Observed,
  not inferred: sections 7.2 and 7.3.
- Section 3.1 of this note is no longer theory for one client. A modern client
  meeting an old server falls back and connects.
- Cost of staying old: one wasted round trip per connection for a doomed probe.
- Builder's `server/discover` is worse than useless to a modern client. Its body
  is the wrong shape, so it buys nothing that dropping it would lose.
- The bundle names the failure case that ends this: "supportedProtocolVersions
  contains no pre-2026-07-28 protocol version". Today's CLI is not that client.

## Recommendation

Ship **dual-era**, and treat `2026-07-28`-only as the follow-up once the client
evidence in the sibling note says legacy clients are gone.

The reason is one asymmetry in the SDKs, not a reading of the spec. A
modern-only server is the option that breaks a **current** client:

- The TypeScript v2 client's default negotiation mode is `'legacy'`
  (`versionNegotiation.ts:112`, section 5.1). With defaults it sends
  `initialize` and no modern headers. A `2026-07-28`-only Sketch answers `400`
  and the client has no fall-forward (section 3.2).
- The Python client's default is `'auto'`. It probes, so it reaches either
  server (section 5.2).
- Both clients fall back to `initialize` against a `2025-06-18` server, and both
  keep `2025-06-18` in their handshake lists (sections 5.3, 5.4).

So today, on client compatibility alone, the old revision is the safe one and
the new one is the risk. That inverts the usual instinct.

The trade-off, stated plainly:

- **`2025-06-18` only.** Zero new code. Works with every SDK client except an
  explicit `{ pin: '2026-07-28' }`. Sketch ships two revisions behind on day
  one, and the gap grows every release.
- **`2026-07-28` only.** About 55 lines (section 6). Correct by the spec, and
  broken against a default-configured TypeScript v2 client.
- **Dual-era.** About 70 lines. Nothing fails. The spec names the pattern and
  permits one endpoint (section 3.3). The cost is two result shapes to keep in
  step, and legacy code that outlives its last caller silently.

Two facts push the other way, toward `2026-07-28`-only: Sketch has no users, so
there is no compatibility debt to protect; and the transport Sketch copied is
already stateless and POST-only, which is the shape `2026-07-28` wants. The
work is validation code, not architecture, in every option.

The decision is Faris's.

## Not verified

- Sketch's `/mcp` does not exist yet, so nothing was tested against Sketch
  itself. Section 7.3 pointed a real client at a byte-exact replica of Builder's
  handlers instead, which is the transport Sketch copies. Section 3.2, the
  modern-only case, stays **unverified** against a running client: no
  `2026-07-28`-only server was built.
- No SDK was installed or run. Every SDK claim is source at a named release
  tag. These lines were re-read by hand: TS `packages/core/src/constants.ts`,
  TS `packages/core-internal/src/shared/protocolEras.ts`, TS
  `packages/client/src/client/versionNegotiation.ts`, TS
  `docs/protocol-versions.md`, Python `src/mcp-types/mcp_types/version.py`,
  Python `src/mcp/client/_probe.py`, Python `docs/protocol-versions.md`,
  Python `_v2026_07_28/__init__.py` `DiscoverResult`. The rest of section 5,
  including the TypeScript `client.ts` and `streamableHttp.ts` quotes, the
  release dates, and the v2.0.0 missing-header bug, comes from an agent's
  reading and was **not** re-checked line by line.
- Section 5.3's claim that Builder's `server/discover` body fails
  `DiscoverResult.model_validate` is inferred from the required `cache_scope`
  field. Not executed.
- The `2024-11-05` and `2025-03-26` `schema.ts` files were not opened. Their
  revision strings are taken from the `schema/` directory names and the docs
  navigation only.
- No SEP PR body was read in full. SEP numbers (2575, 2567, 2322, 2549, 2243,
  2577, 2596) come from the changelog entries that cite them.
- The publication dates of `2024-11-05`, `2025-03-26`, `2025-06-18` and
  `2025-11-25` were not checked against commit history. Only `2026-07-28` was
  (`b488c16623`, 2026-07-28T15:56:05Z).
- Whether any normative text sets a support window for older protocol
  revisions: none found. The deprecation policy in
  `docs/specification/2026-07-28/deprecated.mdx` covers features, not
  revisions.
