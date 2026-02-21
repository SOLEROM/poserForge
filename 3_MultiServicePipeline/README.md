# 3 — Multi-Service Pipeline Pattern

Demonstrates **Docker Compose as an orchestration layer** for a pipeline of cooperating services.
Each container represents exactly one logical stage of processing.
Services discover each other by service name over the internal Compose network.
Final results are persisted to a shared named volume.

---

## Architecture

```
User
 │  POST /submit  {"text": "..."}
 ▼
┌──────────┐        HTTP        ┌──────────┐        HTTP        ┌───────────┐        HTTP        ┌───────────┐
│ gateway  │ ────────────────→  │  ingest  │ ────────────────→  │ normalize │ ────────────────→  │  analyze  │
│  :8088   │  http://ingest:5001│  :5001   │  http://normalize: │  :5002    │  http://analyze:   │  :5003    │
│ (public) │                    │          │  5002              │           │  5003              │           │
└──────────┘                    └──────────┘                    └───────────┘                    └─────┬─────┘
     │                                                                                                  │
     │  GET /result/{id}                                                                                │ writes
     │                                                     ┌─────────────────────────────────┐         │
     └─────────────────────────────────────────────────────│   pipeline-data  (named volume) │ ←───────┘
                                                           └─────────────────────────────────┘
```

### Stages

| Service     | Port  | Responsibility                                                         |
|-------------|-------|------------------------------------------------------------------------|
| `gateway`   | 8088  | Public HTTP API. Routes submissions downstream, serves results from volume |
| `ingest`    | 5001  | Assigns a UUID job ID, forwards `{job_id, text}` to normalize          |
| `normalize` | 5002  | Lowercases, strips punctuation, tokenises into words, forwards to analyze |
| `analyze`   | 5003  | Computes word-frequency stats, writes `{job_id}.json` to shared volume |

Only `gateway` is exposed on the host; all other services live on the internal `pipeline-net` network and communicate by service name.

---

## Quick start

```bash
# 1 – Build images (one shared Dockerfile, different CMD per service)
make build

# 2 – Start the full pipeline stack
make up

# 3 – Submit some text
make submit TEXT="Docker Compose makes multi-service pipelines easy"

# Output:
# {
#   "job_id": "e3f12…",
#   "status": "accepted"
# }

# 4 – Retrieve the result (use the job_id from the previous step)
make result ID=e3f12…

# Output:
# {
#   "job_id": "e3f12…",
#   "total_words": 6,
#   "unique_words": 6,
#   "top_words": [["docker", 1], ["compose", 1], …],
#   "avg_word_len": 5.0
# }
```

---

## All make targets

```
make build    Build all service images
make up       Start the stack; waits until gateway is healthy
make down     Stop containers (volumes preserved)
make logs     Tail logs from all four services
make submit   POST text through the pipeline   TEXT="…" (optional override)
make result   GET a result by job ID           ID=<job_id>
make test     Run the 10-test integration suite
make clean    Stop + remove containers
make reset    Stop + remove containers AND named volumes
```

---

## Running the tests

```bash
make up     # stack must be running
make test
```

Expected output:

```
=== MultiServicePipeline Integration Tests ===
Gateway: http://localhost:8088

1. Gateway /health
  PASS: gateway returns status=ok
2. Submit job — nine unique words
  PASS: submit returned job_id=…
3. Result available for job
  PASS: result found for job_id=…
4. total_words = 9
  PASS: total_words=9 (correct)
5. unique_words = 8  ("the" appears twice)
  PASS: unique_words=8 (correct)
6. Top word is "the" (2 occurrences)
  PASS: top word is 'the'
7. Submit job with repeated words
  PASS: top word is 'world' (3 occurrences)
8. Punctuation is stripped (normalize stage)
  PASS: punctuation stripped → total_words=4
9. Unknown job_id → 404
  PASS: unknown job_id returns 404
10. Empty text → 400
  PASS: empty text returns 400

Results: 10 passed, 0 failed
```

---

## HTTP API reference

### `POST /submit`
Submit text to the pipeline.

```bash
curl -X POST http://localhost:8088/submit \
  -H 'Content-Type: application/json' \
  -d '{"text": "Hello world hello"}'
```
```json
{ "job_id": "550e8400-e29b-41d4-a716-446655440000", "status": "accepted" }
```

### `GET /result/{job_id}`
Retrieve the analysis result once the pipeline has completed (synchronous — available immediately after `/submit` returns).

```bash
curl http://localhost:8088/result/550e8400-e29b-41d4-a716-446655440000
```
```json
{
  "job_id":       "550e8400-e29b-41d4-a716-446655440000",
  "total_words":  3,
  "unique_words": 2,
  "top_words":    [["hello", 2], ["world", 1]],
  "avg_word_len": 4.33
}
```

### `GET /health`
Liveness check for the gateway.

```bash
curl http://localhost:8088/health
```
```json
{ "status": "ok", "service": "gateway" }
```

---

## Project structure

```
3_MultiServicePipeline/
├── Dockerfile              # Single image shared by all services
├── docker-compose.yml      # 4-service pipeline + network + volume
├── requirements.txt        # flask, requests
├── .env                    # GATEWAY_PORT=8088
├── Makefile
├── app/
│   ├── gateway.py          # Stage 0 — public HTTP API
│   ├── ingest.py           # Stage 1 — job ID assignment
│   ├── normalize.py        # Stage 2 — text cleaning & tokenisation
│   └── analyze.py          # Stage 3 — word-frequency analysis + persistence
└── tests/
    └── test_pipeline.sh    # 10-case bash integration suite
```

---

## Key design points

- **One image, four roles** — a single `Dockerfile` builds one image; each service in `docker-compose.yml` overrides the default `CMD` to run a different script.
- **Service-name DNS** — containers call each other by service name (`http://ingest:5001`, `http://normalize:5002`, …). No hardcoded IPs.
- **Ordered startup via health checks** — `depends_on: condition: service_healthy` ensures Compose starts services in the correct pipeline order: `analyze → normalize → ingest → gateway`.
- **Hybrid data flow** — inter-stage communication is HTTP (network API); final persistence is a shared named volume (`pipeline-data`). The gateway reads results directly from the volume, avoiding a reverse HTTP call through the chain.
- **Loose coupling** — any stage can be restarted independently (`docker compose restart normalize`) without affecting the others.

---

## Customisation

| Variable       | Default | Description                            |
|----------------|---------|----------------------------------------|
| `GATEWAY_PORT` | `8088`  | Host port that maps to the gateway     |

Override in `.env` or on the command line:

```bash
GATEWAY_PORT=9090 docker compose up -d
```
