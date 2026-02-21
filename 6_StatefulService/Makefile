COMPOSE  = docker compose
APP_PORT ?= 8091

.PHONY: build up down restart logs shell \
        session-create session-list session-get session-delete \
        events state crash inspect \
        test clean reset

build:
	$(COMPOSE) build

up:
	$(COMPOSE) up -d
	@echo "Service at http://localhost:$(APP_PORT)"

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) restart app

logs:
	$(COMPOSE) logs -f app

shell:
	$(COMPOSE) exec app sh

# ── Session shortcuts ──────────────────────────────────────────────────────────
session-create:
	curl -s -X POST http://localhost:$(APP_PORT)/sessions \
	  -H "Content-Type: application/json" \
	  -d '{"name":"$(NAME)","data":{"note":"$(NOTE)"}}' | python3 -m json.tool

session-list:
	curl -s http://localhost:$(APP_PORT)/sessions | python3 -m json.tool

session-get:
	@test -n "$(ID)" || (echo "Usage: make session-get ID=<session-id>" && exit 1)
	curl -s http://localhost:$(APP_PORT)/sessions/$(ID) | python3 -m json.tool

session-delete:
	@test -n "$(ID)" || (echo "Usage: make session-delete ID=<session-id>" && exit 1)
	curl -s -X DELETE http://localhost:$(APP_PORT)/sessions/$(ID) | python3 -m json.tool

# ── Observability ──────────────────────────────────────────────────────────────
events:
	curl -s "http://localhost:$(APP_PORT)/events?limit=20" | python3 -m json.tool

state:
	curl -s http://localhost:$(APP_PORT)/state | python3 -m json.tool

# ── Lifecycle demos ────────────────────────────────────────────────────────────
crash:
	@echo "Triggering crash (restart: unless-stopped will recover it)..."
	curl -s -X POST http://localhost:$(APP_PORT)/crash || true
	@sleep 5
	@echo "--- state after auto-recovery ---"
	@curl -s http://localhost:$(APP_PORT)/state | python3 -m json.tool

inspect:
	$(COMPOSE) --profile inspect run --rm inspector

# ── Test / housekeeping ────────────────────────────────────────────────────────
test:
	bash tests/test_stateful.sh

clean:
	$(COMPOSE) down --rmi local

reset:
	$(COMPOSE) down -v --rmi local
	docker volume rm poserforge-stateful-data 2>/dev/null || true
