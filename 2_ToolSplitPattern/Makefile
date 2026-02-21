.PHONY: build up down logs submit query report test clean reset

API_PORT ?= 8080
JOB_NAME ?= demo-job
JOB_CMD  ?= echo hello world
JOB_ID   ?=

build:
	docker compose build

up:
	docker compose up -d api
	@echo "Service running at http://localhost:$(API_PORT)/health"

down:
	docker compose down

logs:
	docker compose logs -f api

# Run one-shot tools (service auto-started via depends_on if not already up)
submit:
	docker compose run --rm \
	  -e JOB_NAME="$(JOB_NAME)" \
	  -e JOB_CMD="$(JOB_CMD)" \
	  submit

query:
	docker compose run --rm -e JOB_ID="$(JOB_ID)" query

report:
	docker compose run --rm report

test:
	@bash tests/test_integration.sh

clean:
	docker compose down --remove-orphans

reset:
	docker compose down -v --remove-orphans
	@echo "All containers and volumes removed."
