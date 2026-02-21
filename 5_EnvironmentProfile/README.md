# 5 — Environment Profile Pattern

> **Pattern:** Compose profiles define multiple runtime topologies inside a single project file.
> Switch environments by changing a startup parameter — never by editing config.

---

## Concept

A single `docker-compose.yml` describes four services. Only `api` runs in every mode; the three companion services are profile-gated and only start when their profile is activated.

```
docker compose up                       → api only          (default / no profile)
docker compose --profile dev  up        → api + devtools
docker compose --profile test run tester→ api + tester (one-shot)
docker compose --profile prod up        → api + monitor
```

The **`APP_ENV`** variable drives how the api behaves within each topology:

| Mode | `APP_ENV` | Services | `/debug` | Logging |
|------|-----------|----------|----------|---------|
| no profile | `development` | `api` | 200 OK | verbose |
| `dev` | `development` | `api` + `devtools` | 200 OK | verbose |
| `test` | `test` | `api` + `tester` | 403 blocked | silent |
| `prod` | `production` | `api` + `monitor` | 403 blocked | structured JSON |

---

## File Layout

```
5_EnvironmentProfile/
├── Dockerfile              # single image for all four services
├── docker-compose.yml      # all topologies in one file
├── .env                    # default overrides (APP_ENV, API_PORT)
├── Makefile                # convenience targets
├── app/
│   ├── api.py              # Flask API — behaviour driven by APP_ENV
│   ├── devtools.py         # dev companion — live debug dashboard
│   ├── tester.py           # one-shot integration test runner
│   └── monitor.py          # prod health poller with alerting
└── tests/
    └── test_profiles.sh    # bash suite — 15 tests across all profiles
```

---

## Quick Start

### 1. Build

```bash
make build
# or: docker compose build
```

### 2. Development mode — api + live debug companion

```bash
make dev
# or: APP_ENV=development docker compose --profile dev up
```

The `devtools` service polls `/health`, `/debug`, and `/stats` every 3 s and
prints a live dashboard:

```
[DEVTOOLS] ── poll #1 ──────────────────────────────
  status  : ok  env=development
  uptime  : 12.3s
  requests: {'/health': 3, '/debug': 1, '/stats': 1}
  store   : {} (0 keys)
```

While `dev` is running you can interact with the api directly:

```bash
make health   # → {"env": "development", "status": "ok"}
make debug    # → full internal state dump
make stats    # → uptime + per-endpoint request counts

# store and retrieve a value
curl -s -X POST http://localhost:8090/data \
     -H 'Content-Type: application/json' \
     -d '{"key":"name","value":"alice"}' | python3 -m json.tool

curl -s http://localhost:8090/data/name | python3 -m json.tool
```

### 3. Test mode — one-shot tester

```bash
make test-run
# or: APP_ENV=test docker compose --profile test run --rm tester
```

Compose starts `api` (if not already running), waits for it to be healthy, then
runs `tester` and removes the container on exit. `tester` exits 0 on success,
1 on failure.

```
[TESTER] running API integration tests …
  PASS  GET /health returns 200
  PASS  health.status == ok
[TESTER] api reports APP_ENV=test
  PASS  POST /data returns 200
  PASS  POST /data ok=True
  PASS  GET /data/<key> returns 200
  PASS  GET /data/<key> correct value
  PASS  GET /data/missing returns 404
  PASS  GET /stats returns 200
  PASS  stats has uptime_seconds
  PASS  stats has requests map
  PASS  GET /debug blocked in non-dev

[TESTER] 11/11 passed
```

### 4. Production mode — api + health monitor

```bash
make prod
# or: APP_ENV=production docker compose --profile prod up
```

The `monitor` service polls `/health` and `/stats` every 5 s and emits
structured JSON log lines:

```json
{"level": "info", "source": "monitor", "msg": "healthy | env=production uptime=18.4s total_requests=12"}
```

Three consecutive failures trigger an ALERT log:

```json
{"level": "ALERT", "source": "monitor", "msg": "service appears DOWN — 3 consecutive failures"}
```

The `/debug` endpoint is blocked in production:

```bash
curl http://localhost:8090/debug
# → {"error": "debug endpoint only available in development mode"}  HTTP 403
```

### 5. No-profile mode — bare api

```bash
make up
# or: APP_ENV=development docker compose up -d
```

Starts only `api`. Profile-gated services (`devtools`, `tester`, `monitor`) are
not created.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service liveness + current env |
| `POST` | `/data` | Store `{"key":"…","value":"…"}` |
| `GET` | `/data/<key>` | Retrieve stored value |
| `GET` | `/stats` | Uptime + per-endpoint request counts |
| `GET` | `/debug` | Internal state dump (**dev only**) |

---

## Running the Test Suite

```bash
make test
# or: bash tests/test_profiles.sh
```

The suite spins each profile up in isolation and verifies:

1. Image builds successfully
2. No-profile mode: only `api` starts; env reported as `development`
3. `dev` profile: `devtools` container running; `/debug` returns 200
4. `test` profile: `tester` exits 0; all 11 API tests pass
5. `prod` profile: `monitor` container running; `/debug` returns 403; env reported as `production`

Expected output:

```
╔══════════════════════════════════════════════════╗
║    5_EnvironmentProfile — integration tests      ║
╚══════════════════════════════════════════════════╝

─── 1: Build ──────────────────────────────────────
  PASS  docker compose build succeeds

─── 2: No-profile mode (api only) ─────────────────
  PASS  GET /health → 200
  PASS  api reports env=development
  PASS  devtools absent without --profile dev
  PASS  monitor absent without --profile prod

─── 3: Dev profile (api + devtools) ───────────────
  PASS  GET /health → 200 (dev)
  PASS  api reports env=development (dev profile)
  PASS  GET /debug → 200 in dev mode
  PASS  devtools container running in dev profile

─── 4: Test profile (one-shot tester) ─────────────
  PASS  tester container exits 0

─── 5: Prod profile (api + monitor) ───────────────
  PASS  GET /health → 200 (prod)
  PASS  api reports env=production
  PASS  GET /debug → 403 in prod (blocked)
  PASS  GET /stats → 200 in prod
  PASS  monitor container running in prod profile

══════════════════════════════════════════════════════
  Results: 15 passed, 0 failed
══════════════════════════════════════════════════════
ALL TESTS PASSED
```

---

## Makefile Reference

```
make build      build the shared image
make dev        start api + devtools  (Ctrl-C to stop)
make test-run   run one-shot tester   (auto-starts api)
make prod       start api + monitor   (Ctrl-C to stop)
make up         start api only, detached
make down       stop all services across all profiles
make logs       tail logs for running services
make health     curl /health
make stats      curl /stats
make debug      curl /debug  (dev only)
make test       run bash integration test suite
make clean      stop all, remove containers
make reset      full teardown — containers + volumes + images
```

---

## Key Design Points

**Single image, four services.** The `Dockerfile` builds one image; each service
selects its script via the `command:` field in `docker-compose.yml`.

**Profiles gate services.** `devtools`, `tester`, and `monitor` carry a `profiles:`
key so they are invisible to plain `docker compose up`.

**`APP_ENV` drives behaviour.** The api reads `APP_ENV` at startup and adapts
logging format, endpoint availability, and verbosity — no code branches on
service names.

**`depends_on: condition: service_healthy`** ensures profile companions only
start once the api passes its healthcheck, whether they were launched with `up`
or `run`.

**Named resources prevent collisions** across projects on the same host:

```yaml
networks:
  profile-net:
    name: poserforge-profile-net

volumes:
  profile-data:
    name: poserforge-profile-data
```
