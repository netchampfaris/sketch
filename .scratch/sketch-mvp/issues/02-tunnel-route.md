# Route sketch.netchamp.dev through the tunnel

Type: task
Status: open
Blocked by: 01

## Question

Add a Cloudflare ingress for `sketch.netchamp.dev` that rewrites the origin host to `sketch.localhost`, sends `^/socket.io` to 9007 and everything else to 8007, keeping the final 404 catch-all. Create the DNS route. Follow the devbox-services skill. Record the resulting public URL and the login page status. Do not expose files under ~/.cloudflared.
