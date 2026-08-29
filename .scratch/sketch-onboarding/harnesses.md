# Connect snippets, one per harness

Verified against the vendor's own documentation on 2026-08-29. Agents wrote and checked
this table. `<token>` is the placeholder the UI replaces with the live token. `<endpoint>`
is the placeholder for `agentToken.endpoint`, today `https://sketch.netchamp.dev/mcp`.

| Harness | Config path or command | Top-level key | Static bearer | Restart |
|---|---|---|---|---|
| Claude Code | `claude mcp add`, writes `~/.claude.json` | `mcpServers` | native | no |
| Codex CLI | `~/.codex/config.toml` | `mcp_servers` | native | yes |
| OpenCode | `~/.config/opencode/opencode.json` | `mcp` | native | yes |
| Cursor | `~/.cursor/mcp.json` | `mcpServers` | native | not documented |
| VS Code | `.vscode/mcp.json` or the user file | `servers` | native | yes |
| Claude Desktop | `claude_desktop_config.json` | `mcpServers` | no, needs `mcp-remote` | yes |
| Gemini CLI | `~/.gemini/settings.json` | `mcpServers` | native | yes |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` | `mcpServers` | native | not documented |
| claude.ai web | UI only | none | **no** | n/a |

The top-level key is the number one setup failure. VS Code uses `servers`. OpenCode uses
`mcp`. Codex uses `mcp_servers`. Everybody else uses `mcpServers`.

## Claude Code

Help line: `Run this once. It adds Sketch to every project on this machine.`

```
claude mcp add --transport http --scope user sketch <endpoint> --header "Authorization: Bearer <token>"
```

Note: `--scope user` is not optional. Without it Claude Code binds Sketch to one directory.
Check it with `claude mcp list`. You want the line
`sketch: <endpoint> (HTTP) - Connected`.

Source https://code.claude.com/docs/en/mcp

## Codex CLI

Help line: `Add this to ~/.codex/config.toml, then restart Codex.`

```toml
[mcp_servers.sketch]
url = "<endpoint>"
http_headers = { Authorization = "Bearer <token>" }
```

Note: `codex mcp add` has no header flag, so edit the file by hand.
`experimental_use_rmcp_client` is no longer needed.

Source https://learn.chatgpt.com/docs/config-file/config-reference

## OpenCode

Help line: `Add this to ~/.config/opencode/opencode.json, then restart OpenCode.`

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "sketch": {
      "type": "remote",
      "url": "<endpoint>",
      "enabled": true,
      "oauth": false,
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```

Note: `type` is `remote`, not `http`. Keep `oauth` false, or a 401 starts an OAuth flow
instead of failing cleanly.

Source https://opencode.ai/docs/mcp-servers/ and the live schema

## Cursor

Help line: `Add this to ~/.cursor/mcp.json.`

```json
{
  "mcpServers": {
    "sketch": {
      "url": "<endpoint>",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```

Note: no `type` field. Cursor reads the transport from `url`. Do not use the `auth` object,
that is OAuth.

Source https://cursor.com/docs/context/mcp

## VS Code

Help line: `Run MCP: Open User Configuration, then add this. VS Code asks for the token the
first time.`

```json
{
  "inputs": [
    { "type": "promptString", "id": "sketch-token", "description": "Sketch MCP token", "password": true }
  ],
  "servers": {
    "sketch": {
      "type": "http",
      "url": "<endpoint>",
      "headers": { "Authorization": "Bearer ${input:sketch-token}" }
    }
  }
}
```

Note: the key is `servers`, not `mcpServers`. VS Code is the odd one out. This snippet
keeps the token out of the file on purpose, so it does not carry the live token.

Source https://code.visualstudio.com/docs/agents/reference/mcp-configuration, page dated
2026-08-26

## Claude Desktop

Help line: `Claude Desktop reads stdio servers only, so it needs the mcp-remote bridge. Add
this to claude_desktop_config.json, then restart Claude Desktop. Node 18 or newer is
required.`

macOS `~/Library/Application Support/Claude/claude_desktop_config.json`
Windows `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "sketch": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "<endpoint>", "--transport", "http-only",
               "--header", "Authorization:${AUTH_HEADER}"],
      "env": { "AUTH_HEADER": "Bearer <token>" }
    }
  }
}
```

Note: write `Authorization:${AUTH_HEADER}` with no space. Claude Desktop, Cursor and Codex
all mangle a space inside `args`. `--transport http-only` stops the default SSE probe
against an endpoint that answers POST only.

Source https://github.com/geelen/mcp-remote README

## Gemini CLI

Help line: `Run this once.`

```
gemini mcp add -s user -t http -H "Authorization: Bearer <token>" sketch <endpoint>
```

Or add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "sketch": {
      "type": "http",
      "url": "<endpoint>",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```

Note: `--scope` defaults to `project`, so pass `-s user`. Older docs say to use `httpUrl`;
that field is deprecated in the current source.

Source https://github.com/google-gemini/gemini-cli/blob/main/docs/tools/mcp-server.md

## Windsurf

Help line: `Add this to ~/.codeium/windsurf/mcp_config.json.`

```json
{
  "mcpServers": {
    "sketch": {
      "serverUrl": "<endpoint>",
      "headers": { "Authorization": "Bearer <token>" }
    }
  }
}
```

Note: the key is `serverUrl`, not `url`.

Source https://docs.devin.ai/desktop/cascade/mcp

## claude.ai on the web

Cannot connect. The custom connector dialog takes a URL, and Advanced settings offers an
OAuth client id and secret only. There is no token field and no header field. Claude
connects from Anthropic's cloud, so there is no local file to edit either.

Sketch will support claude.ai when OAuth ships. Use Claude Code, Codex, OpenCode, Cursor,
VS Code or Claude Desktop today.

Source https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp

## One open risk

Sketch answers POST only. A streamable HTTP client may open `GET /mcp` for the server to
client SSE stream. The MCP specification says a server with no SSE stream must answer 405,
and Sketch does. Gemini CLI is known to tolerate that. The other clients are untested
against Sketch itself. Every snippet above is verified against its vendor's documentation
and **not** against the live Sketch endpoint.
