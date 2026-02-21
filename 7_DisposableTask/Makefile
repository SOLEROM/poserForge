.PHONY: build seed migrate analyze cleanup export status all-tasks test clean reset

COMPOSE = docker compose

build:
	$(COMPOSE) build

seed:
	$(COMPOSE) run --rm seed

migrate:
	$(COMPOSE) run --rm migrate

analyze:
	$(COMPOSE) run --rm analyze

cleanup:
	$(COMPOSE) run --rm cleanup

export:
	$(COMPOSE) run --rm export

status:
	$(COMPOSE) run --rm status

# Run the full task pipeline in sequence
all-tasks: seed migrate analyze cleanup export

test: build
	@bash tests/test_tasks.sh

clean:
	$(COMPOSE) down --remove-orphans

reset: clean
	docker volume rm poserforge-task-data 2>/dev/null || true
	@echo "Volume removed. Run 'make seed' to start fresh."
