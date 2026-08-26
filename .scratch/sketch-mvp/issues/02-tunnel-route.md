# Route sketch.netchamp.dev through the tunnel

Type: task
Status: resolved
Blocked by: 01

## Question

Add a Cloudflare ingress for `sketch.netchamp.dev` that rewrites the origin host to `sketch.localhost`, sends `^/socket.io` to 9007 and everything else to 8007, keeping the final 404 catch-all. Create the DNS route. Follow the devbox-services skill. Record the resulting public URL and the login page status. Do not expose files under ~/.cloudflared.

## Answer

Done on 2026-08-26 at Faris's direct request, in the same session as ticket 16. A subagent did the work; the orchestrating session verified each URL.

- Public URL: `https://sketch.netchamp.dev`. The Sketch SPA is at `https://sketch.netchamp.dev/sketch`. `/` is Frappe's default www index.
- Ingress in `~/.cloudflared/config.yml`: `^/socket.io` → `127.0.0.1:9007`, everything else → `127.0.0.1:8007`, both with `httpHostHeader: sketch.localhost`. The `http_status:404` catch-all stays last. `cloudflared tunnel ingress validate` returned OK. Backup at `~/.cloudflared/config.yml.bak-2026-08-26`.
- DNS: `cloudflared tunnel route dns netchamp-devbox sketch.netchamp.dev` added the CNAME to the tunnel.
- `cloudflared-netchamp.service` restarted once. Four tunnel connections registered. builder, gameplan-localhost, and t3code routes still return 200.
- Site `host_name` set to `https://sketch.netchamp.dev`.
- Status codes: `/login` 200, `/api/method/ping` 200 (`pong`), `/sketch` 200 with the built index and its JS/CSS assets, `/socket.io/?EIO=4&transport=polling` 200.
- Not verified: rendering in a browser. Only status codes and HTML were checked.
