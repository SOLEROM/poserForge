# ─────────────────────────────────────────────────────────────────────────────
# poserForge — Makefile convenience targets
# Run these on the HOST to manage the dev container lifecycle.
# ─────────────────────────────────────────────────────────────────────────────

COMPOSE = docker compose
SERVICE = devenv

.PHONY: build up down shell test logs clean reset

## build   — build (or rebuild) the dev container image
build:
	$(COMPOSE) build --no-cache

## up      — start the container in the background
up:
	$(COMPOSE) up -d

## down    — stop the container (volumes preserved)
down:
	$(COMPOSE) down

## shell   — enter an interactive bash shell in the running container
shell: up
	$(COMPOSE) exec $(SERVICE) bash

## test    — run all tests inside the container
test: up
	@echo "── Python tests ─────────────────────────────────────"
	$(COMPOSE) exec $(SERVICE) python3 -m pytest tests/ -v
	@echo ""
	@echo "── Node.js tests ────────────────────────────────────"
	$(COMPOSE) exec $(SERVICE) node tests/test_node.js

## logs    — tail container logs
logs:
	$(COMPOSE) logs -f $(SERVICE)

## clean   — stop container and remove build artifacts volume
clean: down
	docker volume rm -f poserforge-build-artifacts

## reset   — full teardown: stop + remove ALL named volumes
reset: down
	$(COMPOSE) down -v
	@echo "All named volumes removed. Re-run 'make build up' for a fresh start."
