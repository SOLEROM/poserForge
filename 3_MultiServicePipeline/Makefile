COMPOSE  = docker compose
BASE_URL = http://localhost:${GATEWAY_PORT:-8088}

.PHONY: build up down logs submit result test clean reset

## Build all service images
build:
	$(COMPOSE) build

## Start the full pipeline stack in the background
up:
	$(COMPOSE) up -d
	@printf "Waiting for gateway"; \
	for i in $$(seq 1 30); do \
		curl -sf $(BASE_URL)/health >/dev/null 2>&1 \
			&& printf " ready\n" && break \
			|| printf "."; \
		sleep 2; \
	done
	@echo "Stack up → $(BASE_URL)"

## Stop and remove containers (volumes preserved)
down:
	$(COMPOSE) down

## Tail logs from all services
logs:
	$(COMPOSE) logs -f

## Submit text through the pipeline.  Override: make submit TEXT="your text here"
submit:
	@TEXT="$${TEXT:-The quick brown fox jumps over the lazy dog}"; \
	curl -s -X POST $(BASE_URL)/submit \
		-H 'Content-Type: application/json' \
		-d "{\"text\":\"$$TEXT\"}" | python3 -m json.tool

## Fetch a result by job ID.  Usage: make result ID=<job_id>
result:
	@[ -n "$$ID" ] || (echo "Usage: make result ID=<job_id>" && exit 1)
	@curl -s $(BASE_URL)/result/$$ID | python3 -m json.tool

## Run the integration test suite (requires stack to be up)
test:
	@bash tests/test_pipeline.sh

## Stop containers (leave volumes)
clean:
	$(COMPOSE) down --remove-orphans

## Full teardown: stop containers AND delete volumes
reset:
	$(COMPOSE) down -v --remove-orphans
	@echo "All containers and volumes removed."
