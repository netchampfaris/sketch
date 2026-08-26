# Run sketch-bench as a service

Type: task
Status: resolved
Blocked by: 

## Question

Run `sketch-bench` under a systemd user service like `builder-bench.service`, so `sketch.localhost:8007` stays up after a `bench start` session ends. Enable the scheduler on `sketch.localhost` so daily backups run. Record: the unit name, how to restart it, where logs go, where backups land. Do not publish anything; the tunnel route is ticket 02.

## Answer

Done on 2026-08-26, together with ticket 02 at Faris's request.

- Unit: `~/.config/systemd/user/sketch-bench.service`, same shape as `builder-bench.service`. Enabled and active. `Linger=yes`, so it survives logout.
- Restart: `systemctl --user restart sketch-bench.service`. Logs: `journalctl --user -u sketch-bench.service`, plus `sketch-bench/logs/`.
- `Procfile` omits `watch`, like builder-bench, to avoid OOM next to the other benches. Rebuild the frontend by hand: `cd apps/sketch/frontend && yarn build`.
- Scheduler enabled on `sketch.localhost`. Backups land in `sites/sketch.localhost/private/backups`.
- Listening: 8007 web, 9007 socketio, 13007 redis cache, 11007 redis queue.
- Not verified: that a scheduled backup has run (none due yet).
