# 8 — Observability Sidecar Pattern

Auxiliary containers that observe or debug a primary service **without modifying it**.
Sidecars attach to shared networks and volumes to gain visibility into the application,
and are enabled only when needed — keeping the production runtime minimal.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Docker Compose Project                 │
│                                                             │
│  ┌──────────────────────────────┐                           │
│  │         app (always on)      │ ← POST /process           │
│  │  python main.py :8080        │ ← POST /fail              │
│  │  writes → /logs/app.log      │ ← GET  /metrics           │
│  │  exposes Prometheus metrics  │ ← GET  /health            │
│  └──────┬───────────────────────┘                           │
│         │   ┌────────────────────────────────────────┐      │
│         │   │           poserforge-sidecar-logs       │      │
│    vol  ├──▶│  /logs/app.log        (written by app) │      │
│    rw   │   │  /logs/metrics.jsonl  (written by      │      │
│         │   │                        metrics-scraper) │      │
│         │   └──────────┬─────────────────┬───────────┘      │
│         │              │ vol :ro          │ vol rw           │
│  ┌──────┴──────────────▼──────┐   ┌──────▼─────────────┐   │
│  │  log-watcher  (observe)    │   │ metrics-scraper     │   │
│  │  tails app.log             │   │  (observe)          │   │
│  │  pretty-prints to stdout   │   │  polls /metrics     │   │
│  │  NO network — volume only  │   │  stores to jsonl    │   │
│  └────────────────────────────┘   └──────┬──────────────┘   │
│                                          │ net              │
│                                   poserforge-sidecar-net    │
│                                          │                  │
│  ┌───────────────────────────────────────▼──────────────┐   │
│  │  debugger  (debug)  — ONE-SHOT                       │   │
│  │  reads /logs volume  +  queries app via network      │   │
│  │  prints full inspection report, then exits           │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Services

| Service | Profile | Attaches to | Purpose |
|---|---|---|---|
| `app` | *(always)* | `sidecar-net` + `/logs` vol | Primary workload |
| `log-watcher` | `observe` | `/logs` vol only (read-only) | Live log tail & pretty-print |
| `metrics-scraper` | `observe` | `sidecar-net` + `/logs` vol | Poll /metrics, store history |
| `debugger` | `debug` | `sidecar-net` + `/logs` vol (read-only) | One-shot inspection report |

---

## Quick Start

```bash
# 1. Build the image
make build

# 2. Start the app (minimal — no sidecars)
make up

# 3. Generate some traffic
make process TASK=hello
make process TASK=world
make fail    REASON=oops

# 4. Inspect metrics and health
make metrics
make health
```

---

## Runtime Modes

### App only (production-like)

```bash
make up
```

Starts only the `app` service. No sidecars. Minimal runtime.

### With observability sidecars

```bash
make observe
```

Adds `log-watcher` + `metrics-scraper` alongside the app.

Follow their output live:

```bash
# All services
docker compose --profile observe logs -f

# Just the log watcher
docker compose --profile observe logs -f log-watcher

# Just the metrics scraper
docker compose --profile observe logs -f metrics-scraper
```

**Log watcher output** (colour-coded by level):
```
╔══════════════════════════════════╗
║   Log Watcher Sidecar            ║
║   volume: /logs  (read-only)     ║
╚══════════════════════════════════╝

13:42:01 INFO    app ready  port=8080
13:42:05 INFO    processing task  task=hello  elapsed_s=0.05
13:42:07 ERROR   task failed  reason=oops
```

**Metrics scraper output** (dashboard, every 5 s):
```
── Metrics Scraper [13:42:10] scrape #1 ──

  Uptime           12s
  Requests total   5  (+5)
  Requests OK      3  (+3)
  Requests ERR     2 (40.0%)  (+2)
  Process OK       2
  Process ERR      1
  stored → /logs/metrics.jsonl
```

### One-shot debug report

```bash
make debug
```

Starts the app (if not already running) and launches the `debugger` sidecar as a one-shot container that reads both the log volume and live network endpoints, then exits.

**Sample output:**

```
════════════════════════════════════════════════════
  DEBUGGER SIDECAR — Full Inspection Report
  2026-02-21 13:43:00
════════════════════════════════════════════════════

────────────────────────────────────────────────────
  1. App Health  (via network)
────────────────────────────────────────────────────
  Status : ok
  Uptime : 47s

────────────────────────────────────────────────────
  2. Live Metrics  (via network)
────────────────────────────────────────────────────
  requests_total               8
  requests_ok                  5
  requests_err                 3
  process_ok                   4
  process_err                  1
  uptime_seconds               47.2

────────────────────────────────────────────────────
  3. Log Analysis  (via /logs volume)
────────────────────────────────────────────────────
  Total entries : 14
  By level:
    ERROR      2
    INFO       12
  Top messages:
      4×  processing task
      3×  task complete
      2×  health check
      2×  metrics scraped
      2×  task failed
      1×  app ready

  Last 2 error(s):
    13:42:07  task failed  oops
    13:42:09  task failed  deliberate

────────────────────────────────────────────────────
  4. Metrics History  (from metrics-scraper via /logs volume)
────────────────────────────────────────────────────
  Snapshots collected : 3
  First snapshot      : 13:42:05  requests=3
  Latest snapshot     : 13:42:15  requests=8
  Δ requests          : +5 over 3 scrapes

Report complete.
```

### Everything at once

```bash
make full
```

Starts all services + runs the debugger report immediately.

---

## App Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Liveness probe (`{"status":"ok","uptime_s":…}`) |
| `/process` | POST | Simulate work; body: `{"task":"name"}` |
| `/fail` | POST | Simulate failure; body: `{"reason":"why"}` |
| `/metrics` | GET | Prometheus text exposition format |

```bash
# Make a task
curl -X POST http://localhost:8092/process \
  -H 'Content-Type: application/json' \
  -d '{"task":"my-job"}'

# Force an error
curl -X POST http://localhost:8092/fail \
  -H 'Content-Type: application/json' \
  -d '{"reason":"bad-input"}'

# Read raw Prometheus metrics
curl http://localhost:8092/metrics
```

---

## Key Design Principles

**No app code changes required.**
The application writes JSONL logs to a named volume and exposes a `/metrics` endpoint.
Sidecars attach to these interfaces. Neither `log_watcher.py` nor `metrics_scraper.py`
import anything from `main.py`.

**Two observation channels, kept separate.**

| Channel | Used by |
|---|---|
| Shared volume (`/logs`) | `log-watcher` (volume-only, no network) |
| Network + volume | `metrics-scraper`, `debugger` |

The `log-watcher` intentionally has **no network entry** in `docker-compose.yml`,
proving it can observe purely via the filesystem.

**Profiles control operational overhead.**

```bash
make up       # prod: app only
make observe  # dev/ops: app + passive sidecars
make debug    # troubleshooting: one-shot report
```

Sidecars add zero overhead to the production runtime.

---

## Cleanup

```bash
make down     # stop all containers (preserves volumes)
make clean    # stop + remove local images
make reset    # full teardown including named volumes
```

---

## Tests

```bash
make test
```

Runs `tests/test_sidecar.sh` — 28 integration tests covering:
- Image build
- App health, process, fail, metrics endpoints
- Log volume creation and valid JSONL content
- Sidecar startup under the `observe` profile
- Metrics history file written by scraper
- Debugger one-shot report (all 4 sections)
- Network isolation: log-watcher has no network; metrics-scraper does
