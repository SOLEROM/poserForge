.PHONY: build up observe debug full down logs process fail metrics health test clean reset

COMPOSE = docker compose
PORT    ?= 8092
TASK    ?= demo-task
REASON  ?= simulated-failure

## ── Build ────────────────────────────────────────────────────────────────────
build:
	$(COMPOSE) build

## ── Runtime modes ────────────────────────────────────────────────────────────

# App only — minimal production-like runtime
up:
	$(COMPOSE) up -d
	@echo "App running at http://localhost:$(PORT)"

# App + log-watcher + metrics-scraper sidecars
observe:
	$(COMPOSE) --profile observe up -d
	@echo "App + observability sidecars running"
	@echo "Follow sidecar output:  docker compose --profile observe logs -f log-watcher metrics-scraper"

# One-shot debug report (starts app first if not running)
debug:
	$(COMPOSE) up -d
	$(COMPOSE) --profile debug run --rm debugger

# Everything at once
full:
	$(COMPOSE) --profile observe up -d
	$(COMPOSE) --profile debug run --rm debugger

## ── Stop ─────────────────────────────────────────────────────────────────────
down:
	$(COMPOSE) --profile observe --profile debug down

## ── Logs ─────────────────────────────────────────────────────────────────────
logs:
	$(COMPOSE) --profile observe logs -f

## ── App interaction ──────────────────────────────────────────────────────────
process:
	curl -s -X POST http://localhost:$(PORT)/process \
	  -H 'Content-Type: application/json' \
	  -d '{"task":"$(TASK)"}' | python3 -m json.tool

fail:
	curl -s -X POST http://localhost:$(PORT)/fail \
	  -H 'Content-Type: application/json' \
	  -d '{"reason":"$(REASON)"}' | python3 -m json.tool || true

metrics:
	curl -s http://localhost:$(PORT)/metrics

health:
	curl -s http://localhost:$(PORT)/health | python3 -m json.tool

## ── Tests ────────────────────────────────────────────────────────────────────
test:
	bash tests/test_sidecar.sh

## ── Cleanup ──────────────────────────────────────────────────────────────────
clean:
	$(COMPOSE) --profile observe --profile debug down --rmi local 2>/dev/null || true

reset:
	$(COMPOSE) --profile observe --profile debug down -v --rmi local 2>/dev/null || true
	docker volume rm poserforge-sidecar-logs 2>/dev/null || true
