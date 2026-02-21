# 7 — Disposable Task Runner Pattern

Containers designed to execute **a single task and terminate immediately**. Compose standardises runtime dependencies, environment variables, and volume access without maintaining any long-running processes. Every container is ephemeral; the shared named volume carries all persistent state.

---

## Pattern summary

| Concept | Implementation |
|---|---|
| Task isolation | Each task is a separate Compose service |
| State persistence | Named volume `poserforge-task-data` |
| No daemon | Zero long-lived containers — every run exits on completion |
| Reproducibility | Same image, same env for every invocation |
| Dependency drift | Eliminated — host has no runtime deps |

---

## Demo: data lifecycle pipeline

Five disposable tasks operate on a shared JSON dataset, simulating a real maintenance pipeline:

```
seed → migrate → analyze → cleanup → export
```

| Task | What it does |
|---|---|
| `seed` | Creates 20 records on the volume (schema v1). Idempotent — skips if data exists. |
| `migrate` | Upgrades records v1 → v2: adds `category` and `normalized_value` fields. Idempotent. |
| `analyze` | Computes value stats and category breakdown; writes `report.json`. |
| `cleanup` | Removes records older than `CLEANUP_DAYS` (default 30 days). |
| `export` | Writes the current dataset to `export.csv`. |
| `status` | Inspects volume state — works at any point in the pipeline. |

---

## Quick start

```bash
# Build the image
make build

# Run the full pipeline in sequence
make all-tasks

# Or run tasks individually
make seed
make migrate
make analyze
make cleanup
make export

# Inspect volume state at any point
make status

# Run integration tests (16 tests, resets volume first)
make test

# Tear down and wipe the volume
make reset
```

---

## Running tasks directly with Compose

```bash
docker compose run --rm seed
docker compose run --rm migrate
docker compose run --rm analyze
docker compose run --rm cleanup
docker compose run --rm export
docker compose run --rm status
```

Each command spins up a container, runs the task, and exits. No background services are started.

---

## Configuration

All behaviour is driven by environment variables in `.env`:

| Variable | Default | Description |
|---|---|---|
| `DATA_DIR` | `/data` | Mount path inside the container |
| `RECORDS_COUNT` | `20` | Number of records to seed |
| `CLEANUP_DAYS` | `30` | Remove records older than this many days |

Override at runtime:

```bash
docker compose run --rm -e RECORDS_COUNT=50 seed
docker compose run --rm -e CLEANUP_DAYS=7 cleanup
```

---

## Volume files

After running the full pipeline the named volume contains:

```
/data/
├── schema_version   # current schema: "v1" or "v2"
├── records.json     # live dataset (v2 after migrate)
├── report.json      # stats output from analyze
└── export.csv       # CSV snapshot from export
```

Inspect the raw volume from outside Compose at any time:

```bash
docker run --rm -v poserforge-task-data:/data python:3.11-slim \
  python -c "import json; d=json.load(open('/data/records.json')); print(len(d), 'records')"
```

---

## Project structure

```
7_DisposableTask/
├── Dockerfile            # python:3.11-slim, stdlib only
├── docker-compose.yml    # one service per task, shared volume
├── .env                  # default overrides
├── Makefile              # host-side shortcuts
├── app/
│   ├── seed.py           # create initial dataset (v1)
│   ├── migrate.py        # upgrade v1 → v2
│   ├── analyze.py        # stats report
│   ├── cleanup.py        # remove stale records
│   ├── export.py         # CSV export
│   └── status.py         # volume inspector
└── tests/
    └── test_tasks.sh     # 16-test bash integration suite
```

---

## Why this pattern

- **No host dependencies** — Python, data tools, or CLIs run in the container.
- **Deterministic** — the same image and env produce the same result every time.
- **Composable** — tasks chain naturally via shared volume state; each step is independently re-runnable.
- **Lightweight** — no daemon to manage or health-check; `docker compose run --rm` is the entire execution model.
- **Idempotent tasks** — `seed` and `migrate` are safe to re-run; the pipeline is resumable at any stage.
