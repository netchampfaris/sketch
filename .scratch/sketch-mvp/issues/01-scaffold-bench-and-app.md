# Scaffold sketch-bench and the sketch app

Type: task
Status: claimed
Blocked by: 

## Question

Create /home/faris/benches/sketch-bench with `bench init --frappe-branch develop --python <uv python3.14> --skip-assets`, ports web 8007, socketio 9007, redis cache 13007, redis queue 11007, developer_mode on. Create the site `sketch.localhost` (MariaDB). Run `bench new-app sketch`, install it, init git in apps/sketch on a `forge/mvp` branch, add a frappe-ui frontend per the frappe-ui skill SETUP.md (frappe-ui@beta). Create CONTEXT.md at the app root from the map glossary and move this tracker into `apps/sketch/.scratch/sketch-mvp/`. Record: paths, Administrator password location, exact frappe-ui version installed, first `bench start` result.
