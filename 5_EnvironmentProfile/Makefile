.PHONY: build dev test-run prod up down logs health stats debug test clean reset

API_PORT ?= 8090

## build — build the shared image
build:
	docker compose build

## dev — start api + devtools (APP_ENV=development)
dev:
	APP_ENV=development docker compose --profile dev up

## test-run — run one-shot tester against api (APP_ENV=test)
test-run:
	APP_ENV=test docker compose --profile test run --rm tester

## prod — start api + monitor (APP_ENV=production)
prod:
	APP_ENV=production docker compose --profile prod up

## up — start api only (no profile)
up:
	APP_ENV=development docker compose up -d

## down — stop all services across all profiles
down:
	docker compose --profile dev --profile test --profile prod down

## logs — tail logs for currently running services
logs:
	docker compose --profile dev --profile prod logs -f

## health — show /health response
health:
	@curl -s http://localhost:$(API_PORT)/health | python3 -m json.tool

## stats — show /stats response
stats:
	@curl -s http://localhost:$(API_PORT)/stats | python3 -m json.tool

## debug — show /debug response (dev only)
debug:
	@curl -s http://localhost:$(API_PORT)/debug | python3 -m json.tool

## test — run the full integration test suite
test:
	bash tests/test_profiles.sh

## clean — stop all services, remove containers
clean:
	docker compose --profile dev --profile test --profile prod down --remove-orphans

## reset — full teardown including volumes and images
reset:
	docker compose --profile dev --profile test --profile prod down --rmi all -v --remove-orphans
