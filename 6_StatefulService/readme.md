# 6_StatefulService — Stateful Service Pattern

> **Core idea:** Application state lives in a named volume, not in the container.
> The container is disposable; the data is not.

---

## What this pattern teaches

| Concern | How it's handled |
|---|---|
| **Session data** | Stored as JSON files in `/data/sessions/` (named volume) |
| **Event log** | Append-only `/data/events.jsonl` (named volume) |
| **Lifecycle counters** | `startup_count`, `crash_count` in `/data/stats.json` (named volume) |
| **Container identity** | Short UUID generated at boot — changes every restart |
| **Crash recovery** | `restart: unless-stopped`; Docker restarts the container automatically |
| **Offline inspection** | `inspector` service reads the volume directly — no running service needed |

The key observation: after a restart, rebuild, or crash, the **container_id**
changes (proves a new container) but the sessions and counters are unchanged
(proves data survived).

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  host :8091                                         │
│         │                                           │
│  ┌──────▼───────┐   restart:unless-stopped          │
│  │   app        │─── /health /state /sessions       │
│  │  (Flask)     │─── /events /crash                 │
│  └──────┬───────┘                                   │
│         │  volume mount                             │
│  ┌──────▼──────────────────────┐                    │
│  │  poserforge-stateful-data   │  (named volume)    │
│  │  /data/sessions/*.json      │                    │
│  │  /data/events.jsonl         │                    │
│  │  /data/stats.json           │                    │
│  └──────────────────────────────┘                   │
│         │  volume mount                             │
│  ┌──────▼───────┐   profile: inspect                │
│  │  inspector   │─── reads /data directly           │
│  │  (one-shot)  │─── works when app is stopped      │
│  └──────────────┘                                   │
└─────────────────────────────────────────────────────┘
```

---

## Quick start

```bash
make build          # build image
make up             # start service on http://localhost:8091
make state          # show container identity + persisted counters
```

---

## Walkthrough — lifecycle in action

### 1. Create sessions

```bash
make session-create NAME=alice NOTE="first session"
make session-create NAME=bob   NOTE="second session"
make session-list
```

```json
{
  "sessions": [
    { "id": "3f2a…", "name": "alice", "access_count": 0, "created_at": "…" },
    { "id": "9c1b…", "name": "bob",   "access_count": 0, "created_at": "…" }
  ],
  "count": 2
}
```

### 2. Restart the container — sessions survive

```bash
make restart
make session-list        # same sessions still here
make state               # startup_count incremented, container_id changed
```

```json
{
  "container_id": "a9f09b61",    ← new container instance
  "startup_count": 2,            ← persisted counter, incremented
  "live_sessions": 2             ← sessions survived
}
```

### 3. Simulate a crash — service auto-recovers

```bash
make crash
# Docker's restart:unless-stopped kicks in automatically
# After ~5 seconds the service is healthy again
make state
```

```json
{
  "container_id": "935414ac",    ← yet another new container
  "startup_count": 3,
  "crash_count": 1,              ← crash was recorded before exit
  "live_sessions": 2             ← still here
}
```

### 4. Inspect the volume offline

```bash
make down            # stop and remove the service container
make inspect         # inspector mounts the same volume, no HTTP needed
```

```
──────────────────────────────────────────────────────────────
  PERSISTENT STATS
──────────────────────────────────────────────────────────────
  startup_count                3
  crash_count                  1
  total_sessions               2
  total_requests               47

──────────────────────────────────────────────────────────────
  SESSIONS
──────────────────────────────────────────────────────────────
  ID                                    NAME                  ACCESSES  CREATED
  ··············································································
  3f2a…  alice                 0  2026-02-21T10:00:00Z
  9c1b…  bob                   0  2026-02-21T10:00:05Z

  Total: 2

──────────────────────────────────────────────────────────────
  RECENT EVENTS  (last 10)
──────────────────────────────────────────────────────────────
  2026-02-21T10:00:00Z  [a9f09b61]  startup  {'startup_count': 1, 'crash_count': 0}
  2026-02-21T10:01:00Z  [a9f09b61]  session_created  {'session_id': '3f2a…', 'name': 'alice'}
  2026-02-21T10:01:05Z  [a9f09b61]  session_created  {'session_id': '9c1b…', 'name': 'bob'}
  2026-02-21T10:02:00Z  [935414ac]  startup  {'startup_count': 2, 'crash_count': 0}
  2026-02-21T10:03:00Z  [935414ac]  crash_triggered  {'crash_count': 1}
  2026-02-21T10:03:05Z  [f1d8ca22]  startup  {'startup_count': 3, 'crash_count': 1}
```

### 5. Upgrade the image without losing data

```bash
# Edit app/service.py, then:
make build           # rebuild image with new code
make down
make up              # new container, same volume, data preserved
make state           # startup_count is now 4, all sessions intact
```

---

## API reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Container liveness, uptime, container_id |
| `GET` | `/state` | In-memory + all persisted counters |
| `POST` | `/sessions` | Create session `{"name":"…","data":{…}}` |
| `GET` | `/sessions` | List all sessions |
| `GET` | `/sessions/<id>` | Get session by ID |
| `PUT` | `/sessions/<id>` | Update session, increments access_count |
| `DELETE` | `/sessions/<id>` | Delete session |
| `GET` | `/events?limit=N` | Tail the event log (default 50) |
| `POST` | `/crash` | Simulate hard crash (records crash_count first) |

---

## Makefile reference

```bash
make build                          # build image
make up                             # start service
make down                           # stop and remove containers
make restart                        # restart app container
make logs                           # follow service logs
make shell                          # sh into running container

make session-create NAME=x NOTE=y   # create a session
make session-list                   # list all sessions
make session-get    ID=<uuid>       # get one session
make session-delete ID=<uuid>       # delete one session

make events                         # tail the event log
make state                          # show current state
make crash                          # trigger crash + show recovery

make inspect                        # run inspector (works offline)
make test                           # run 15-test integration suite

make clean                          # remove containers + local image
make reset                          # full teardown including volume
```

---

## Key design decisions

**`restart: unless-stopped`** — Docker automatically restarts the container
after a crash. Combined with volume-persisted state, this gives a
self-healing service with no external orchestration.

**Atomic writes** — Both `service.py` and `inspector.py` write to a `.tmp`
file first, then rename it atomically. This prevents partial reads if the
process is killed mid-write.

**Inspector has no `depends_on`** — It reads the volume directly and works
regardless of whether the `app` service is running. This is intentional: it
models an audit/debug tool that can operate on offline data.

**In-memory vs persisted state** — `container_id`, `uptime_seconds`, and
`requests_this_instance` are ephemeral (container-local). `startup_count`,
`crash_count`, and `total_sessions` are durable. The `/state` endpoint shows
both clearly, demonstrating the boundary.
