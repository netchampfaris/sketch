# Run sketch-bench as a service

Type: task
Status: open
Blocked by: 

## Question

Run `sketch-bench` under a systemd user service like `builder-bench.service`, so `sketch.localhost:8007` stays up after a `bench start` session ends. Enable the scheduler on `sketch.localhost` so daily backups run. Record: the unit name, how to restart it, where logs go, where backups land. Do not publish anything; the tunnel route is ticket 02.
