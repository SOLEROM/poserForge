# 2 · Service + Tool Split Pattern

> A long-running background **service** owns state and endpoints.
> Disposable **tool containers** share its image and operate against it, then exit.

---

## Concept

```
┌─────────────────────────────────────────────┐
│  docker compose up -d api                   │
│                                             │
│  ┌──────────────────────┐                   │
│  │  api  (daemon)       │  :8088            │
│  │  Flask job-tracker   │◄──────── host     │
│  │  persists jobs.json  │                   │
│  └──────────┬───────────┘                   │
│             │ poserforge-toolnet             │
│  ┌──────────▼───────────┐                   │
│  │  poserforge-workspace│  (named volume)   │
│  └──────────┬───────────┘                   │
│             │                               │
│  ┌──────────▼──────────────────────────┐    │
│  │  tools  (one-shot, --rm)            │    │
│  │  submit ──► POST /jobs ──► exit     │    │
│  │  query  ──► GET  /jobs ──► exit     │    │
│  │  report ──► read volume ──► exit    │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

All containers share **one image** (`posertool:latest`).
The daemon runs continuously; tools spin up, do one thing, and disappear.

---

## Quick start

```bash
# 1. Build the shared image
make build

# 2. Start the daemon
make up
# → Service running at http://localhost:8088/health

# 3. Submit jobs (tool container starts, posts job, exits)
make submit
make submit JOB_NAME=compress JOB_CMD="gzip /workspace/data.txt"

# 4. Query what was submitted
make query                      # list all jobs
make query JOB_ID=afac4946     # specific job by id

# 5. Generate a report (reads shared volume directly — no HTTP)
make report

# 6. Tear down
make down     # stop daemon, keep volume
make reset    # stop daemon + wipe volume
```

---

## Services

### `api` — daemon

The only service started by `docker compose up`. Owns the job registry.

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Liveness probe |
| `/jobs` | GET | List all jobs |
| `/jobs` | POST | Submit a new job |
| `/jobs/<id>` | GET | Get one job by id |

State is persisted to `/workspace/jobs.json` on the shared volume so it
survives tool container restarts (but not `make reset`).

### `submit` — tool

Posts a new job to the service and prints the response.

```bash
# Override via env
make submit JOB_NAME="nightly-build" JOB_CMD="make -C /src all"

# Or via docker compose directly
docker compose run --rm \
  -e JOB_NAME="scan" \
  -e JOB_CMD="trivy image myapp" \
  submit
```

### `query` — tool

Fetches job status from the service.

```bash
make query                    # all jobs
make query JOB_ID=<id>        # one job

# Example output
# [query] Total jobs: 3
# { "count": 3, "jobs": [ ... ] }
```

### `report` — tool

Reads `jobs.json` from the shared volume **without** going through the
HTTP API. Demonstrates that tools can access shared state independently.

```bash
make report

# ══════════════════════════════════════════════════════
#             JOB TRACKER REPORT
# ══════════════════════════════════════════════════════
#   Total jobs  : 3
#   completed   : 3
#
#   Recent jobs (up to 10):
#   [afac4946] batch-1    completed  2026-02-21T07:44:36
# ══════════════════════════════════════════════════════
```

---

## Full example session

```bash
$ make build
[+] Building posertool:latest ...

$ make up
Container poserforge-api  Started
Service running at http://localhost:8088/health

$ make submit JOB_NAME=index JOB_CMD="reindex --all"
[submit] Accepted — id=3f9a1b2c status=pending

$ make submit JOB_NAME=backup JOB_CMD="tar -czf /workspace/bak.tgz /data"
[submit] Accepted — id=7e4d0a55 status=pending

$ make query
[query] Total jobs: 2
{
  "count": 2,
  "jobs": [
    { "id": "3f9a1b2c", "name": "index",  "status": "completed", ... },
    { "id": "7e4d0a55", "name": "backup", "status": "completed", ... }
  ]
}

$ make query JOB_ID=3f9a1b2c
{ "id": "3f9a1b2c", "name": "index", "status": "completed", ... }

$ make report
══════════════════════════════════════════════════════
            JOB TRACKER REPORT
══════════════════════════════════════════════════════
  Total jobs  : 2
  completed   : 2

  Recent jobs (up to 10):
  [3f9a1b2c] index   completed  2026-02-21T...
  [7e4d0a55] backup  completed  2026-02-21T...
══════════════════════════════════════════════════════

$ make reset
Container poserforge-api  Removed
Volume poserforge-workspace  Removed
All containers and volumes removed.
```

---

## Running the tests

```bash
make test
```

The integration script (`tests/test_integration.sh`) performs a full
lifecycle: build → start service → submit 3 jobs → query → volume check →
report → assert no lingering containers → assert daemon still alive → teardown.

Expected output:

```
════════════════════════════════════════
  Results: 8 passed, 0 failed
════════════════════════════════════════
```

---

## File layout

```
2_ToolSplitPattern/
├── Dockerfile                 # shared image: python:3.11-slim + flask + requests
├── docker-compose.yml         # api (daemon) + submit / query / report (tools)
├── .env                       # API_PORT=8088, JOB_NAME, JOB_CMD, JOB_ID defaults
├── Makefile                   # host-side shortcuts
├── app/
│   ├── service.py             # Flask job-tracker daemon
│   ├── submit.py              # tool: submit a job
│   ├── query.py               # tool: query job status
│   └── report.py              # tool: report from shared volume (no HTTP)
└── tests/
    └── test_integration.sh    # 8-test bash integration suite
```

---

## Key design decisions

**Single image, multiple roles** — the Dockerfile builds one image used by
all four services. The role is determined by the `command:` in
`docker-compose.yml`, keeping the environment identical across daemon and tools.

**`depends_on: condition: service_healthy`** — tools automatically wait for
the daemon's healthcheck before starting. Running `docker compose run --rm submit`
is safe even if the daemon isn't up yet; Compose will start it first.

**Shared named volume** — `poserforge-workspace` is the single source of
truth for job state. The service writes it; the `report` tool reads it
directly, showing how tools can bypass the API when appropriate.

**`--rm` enforced by Makefile** — tools leave no containers behind. The host
stays clean regardless of how many times tools are invoked.
