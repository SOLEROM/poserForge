COMPOSE     := docker compose
METRICS_PORT ?= 8088

.PHONY: build sim hw down logs latest history stats test clean reset

## Build the shared image
build:
	$(COMPOSE) build

## Start in simulation mode (simulator + sensor + metrics)
sim: build
	$(COMPOSE) --profile sim up -d
	@echo "Metrics dashboard: http://localhost:$(METRICS_PORT)"

## Start in hardware mode (sensor reads /dev/hwsensor; no simulator)
## Override HW_DEVICE to point at a real device, e.g.: make hw HW_DEVICE=/dev/ttyUSB0
hw: build
	SENSOR_SOURCE=hw $(COMPOSE) up -d
	@echo "Metrics dashboard: http://localhost:$(METRICS_PORT)"

## Stop all services (works for both profiles)
down:
	$(COMPOSE) --profile sim down

## Follow logs from all running services
logs:
	$(COMPOSE) --profile sim logs -f

## Quick-view helpers
latest:
	curl -s http://localhost:$(METRICS_PORT)/latest | python3 -m json.tool

history:
	curl -s "http://localhost:$(METRICS_PORT)/history?n=10" | python3 -m json.tool

stats:
	curl -s http://localhost:$(METRICS_PORT)/stats | python3 -m json.tool

## Run the full integration test suite
test: build
	bash tests/test_runtime.sh

## Remove containers and locally-built image
clean:
	$(COMPOSE) --profile sim down --rmi local

## Full teardown including named volumes
reset:
	$(COMPOSE) --profile sim down --rmi local -v
