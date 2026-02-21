# 4 — Hardware-Aware Runtime

A Docker Compose pattern for deploying to hardware-constrained or accelerator-enabled systems.
The same container image runs in **simulation mode** (on any dev host) or **hardware mode** (on a real target with device nodes) by switching a runtime profile and one environment variable.

## Design Goals

| Concern | How it's handled |
|---|---|
| Device access | `devices:` maps a host node to `/dev/hwsensor` inside the container |
| Runtime profiles | Compose `--profile sim` adds the simulator; no profile = hw target mode |
| Same image, two runtimes | `SENSOR_SOURCE=sim\|hw` switches the sensor reader; image is identical |
| Boot/embedded deployment | `restart: unless-stopped` on all app services |
| Persistent runtime data | Named volume `poserforge-runtime-data` survives container restarts |

## Architecture

```
  ┌──────────────────────────────────────────────────────┐
  │  profile: sim                                        │
  │  ┌────────────┐  /data/sensor.dat   ┌─────────────┐ │
  │  │ simulator  │ ──────────────────► │   sensor    │ │
  │  │ (fake data)│                     │ (reads file)│ │
  │  └────────────┘                     └──────┬──────┘ │
  │                                            │        │
  │  profile: hw (no --profile flag)           │        │
  │  ┌────────────┐  /dev/hwsensor      ┌──────┘        │
  │  │ host device│ ──────────────────► │   sensor      │
  │  │ /dev/X     │ (devices: mapping)  │ (reads device)│
  │  └────────────┘                     └──────┬────────┘
  │                                            │         │
  │              /data/latest.json             │         │
  │              /data/history.jsonl  ◄────────┘         │
  │                                            │         │
  │                                     ┌──────▼──────┐  │
  │                                     │   metrics   │  │
  │                                     │  HTTP :8080 │  │
  │                                     └─────────────┘  │
  └──────────────────────────────────────────────────────┘
                          host port: METRICS_PORT (8089)
```

**Services:**

- **simulator** (`--profile sim` only) — writes fake temperature/pressure/humidity readings every 0.5 s to `/data/sensor.dat` in the shared volume
- **sensor** (always present) — reads from the file (sim) or device node (hw), writes `/data/latest.json` and appends to `/data/history.jsonl`; `restart: unless-stopped`
- **metrics** (always present) — stdlib HTTP server on internal port 8080 exposing sensor data via REST; `restart: unless-stopped`

## Quick Start

### Simulation mode (works on any host)

```bash
make sim                      # build + start with --profile sim
curl http://localhost:8089/latest | python3 -m json.tool
```

### Hardware mode (requires a real device on the target)

```bash
# Default: /dev/urandom mapped as /dev/hwsensor (useful for dev testing)
make hw

# Real device on an embedded target:
make hw HW_DEVICE=/dev/ttyUSB0
# or
HW_DEVICE=/dev/i2c-1 SENSOR_SOURCE=hw docker compose up -d
```

### Common commands

```bash
make build     # build the shared image
make sim       # start in simulation mode
make hw        # start in hardware mode
make down      # stop all services
make logs      # follow logs from all services
make latest    # GET /latest (pretty-printed)
make history   # GET /history?n=10
make stats     # GET /stats
make test      # run the full integration test suite (10 tests)
make clean     # remove containers + local image
make reset     # full teardown including named volume
```

## API Endpoints

All endpoints are served on `http://localhost:${METRICS_PORT}` (default: **8089**).

| Endpoint | Description |
|---|---|
| `GET /health` | `{"status": "ok"}` — liveness check |
| `GET /latest` | Most recent sensor reading |
| `GET /history?n=N` | Last N readings (default 20) |
| `GET /stats` | min/max/avg over last 100 readings |

### Example responses

```bash
$ curl -s http://localhost:8089/latest | python3 -m json.tool
{
  "ts": 1771662900.088,
  "temp_c": 57.42,
  "pressure_hpa": 1014.31,
  "humidity_pct": 63.5,
  "source": "sim"        # "hw" in hardware mode
}

$ curl -s http://localhost:8089/stats | python3 -m json.tool
{
  "samples": 42,
  "source": "sim",
  "temp_c":        { "min": 38.30, "max": 77.03, "avg": 57.61 },
  "pressure_hpa":  { "min": 1008.19, "max": 1021.93, "avg": 1015.02 },
  "humidity_pct":  { "min": 25.50, "max": 84.90, "avg": 58.30 }
}
```

## Runtime Profile Switching

The key insight of this pattern: the **image is identical** in both modes.
Runtime behaviour is configured entirely through environment variables and the device mapping.

| Variable | sim | hw |
|---|---|---|
| `SENSOR_SOURCE` | `sim` (default) | `hw` |
| `HW_DEVICE` | `/dev/urandom` (default, ignored) | `/dev/ttyUSB0` or similar |
| `METRICS_PORT` | `8089` | `8089` |
| Compose `--profile` | `--profile sim` | _(no flag)_ |

On a real embedded target you would:
1. Set `HW_DEVICE` to the actual device node
2. Run `docker compose up -d` (no `--profile sim`)
3. Add `restart: always` or configure systemd to start Compose on boot

## Adapting to Real Hardware

The `sensor` service is pre-wired to read 8 bytes from `/dev/hwsensor` in hw mode.
To adapt to a real device protocol, edit `app/sensor.py → read_from_device()`:

```python
def read_from_device() -> dict | None:
    # Replace with your device's actual read protocol, e.g.:
    # - serial.read(n) for UART
    # - smbus2.read_i2c_block_data() for I2C
    # - v4l2 capture for camera
    with open(DEVICE_PATH, "rb") as f:
        raw = f.read(8)
    ...
```

The Compose device mapping stays the same — only the Python driver changes.

## Test Results

```
========================================
  Hardware-Aware Runtime — Test Suite
========================================
  PASS [1]:  image builds successfully
  PASS [2]:  sim profile started (simulator + sensor + metrics)
  PASS [3]:  metrics service is healthy
  PASS [4]:  /health returns {status: ok}
  PASS [5]:  /latest returns reading with all expected fields
  PASS [6]:  source='sim' in simulation mode
  PASS [7]:  /history has 10 readings (≥3)
  PASS [8]:  /stats returns min/max/avg over 10 samples
  PASS [9]:  sensor restart policy is 'unless-stopped'
  PASS [10]: hardware mode reads /dev/hwsensor; source='hw'
========================================
  Results: 10 passed, 0 failed
========================================
```
