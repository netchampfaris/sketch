/**
 * The whole setup, as one instruction to the user's agent. One prompt for
 * every app (decision 87): the agent knows which client it runs in.
 *
 * `<endpoint>` and `<token>` are the placeholders `fillPrompt()` substitutes, the
 * same pair the old snippets used.
 *
 * The three client facts in the second paragraph are the number one setup
 * failure, and each one is verified against the vendor's own documentation
 * (.scratch/sketch-onboarding/harnesses.md): the top-level key differs per
 * client, a whole-file paste destroys the user's other MCP servers, and a 401
 * starts an OAuth flow in clients that assume OAuth. They must survive
 * verbatim. An agent that guesses these writes a config that loads without an
 * error and serves no tools.
 *
 * The last paragraph asks for a tool call, so the agent proves the connection
 * instead of reporting that it edited a file. It then asks the agent to onboard
 * the user, because Sketch has no editor and no tour: a user whose tools work
 * still does not know what to say next. `get_skill` is the server's own
 * instruction sheet (`sketch/mcp/tools.py:615`), so the agent teaches from the
 * current document and not from memory.
 */
export const SETUP_PROMPT = `Add the Sketch MCP server to this client, at user scope so it works in all my projects, not just this one.

  URL: <endpoint>
  Transport: streamable HTTP, POST only
  Header: Authorization: Bearer <token>

Use this client's own way to add an MCP server: its CLI command if it has one, otherwise its MCP config file. Merge the entry into that file, do not overwrite it, or I lose my other MCP servers. The top-level key differs per client: \`servers\` in VS Code, \`mcp\` in OpenCode, \`mcp_servers\` in Codex, \`mcpServers\` in the rest. Sketch authenticates with the static header above, so do not set up OAuth. Restart the client if it reads its config only at start, then call the Sketch tool that lists my prototypes and tell me what it returned.

When that works, onboard me. Call \`get_skill\` to read how Sketch works. Then tell me in a few lines what a prototype is, how I ask you to build or change one, and where I open it. Offer to build a small one now.`

/** Put the live token and endpoint into the prompt. This is what Copy sends. */
export function fillPrompt(token: string, endpoint: string): string {
  let out = SETUP_PROMPT
  if (endpoint) out = out.split('<endpoint>').join(endpoint)
  if (token) out = out.split('<token>').join(token)
  return out
}
