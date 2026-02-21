#!/usr/bin/env python3
"""
Sensor reader — runs in both sim and hw modes.

  sim mode (SENSOR_SOURCE=sim):
    Polls /data/sensor.dat written by the simulator container.

  hw mode (SENSOR_SOURCE=hw):
    Opens /dev/hwsensor (mapped from HW_DEVICE on the host) and interprets
    the raw bytes as scaled sensor values. On /dev/urandom this produces
    realistic-looking random readings; on real hardware the mapping would
    match the device's binary protocol.

Writes:
  /data/latest.json  — most recent reading (atomic rename)
  /data/history.jsonl — append-only log (trimmed to MAX_HISTORY lines)
"""

import json
import os
import time

SENSOR_SOURCE = os.getenv("SENSOR_SOURCE", "sim")
SENSOR_FILE = "/data/sensor.dat"
DEVICE_PATH = "/dev/hwsensor"
INTERVAL = float(os.getenv("SAMPLE_INTERVAL", "1"))
LATEST_PATH = "/data/latest.json"
HISTORY_PATH = "/data/history.jsonl"
MAX_HISTORY = 1000


def read_from_file() -> dict | None:
    try:
        with open(SENSOR_FILE) as f:
            line = f.readline().strip()
        if line:
            return json.loads(line)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return None


def read_from_device() -> dict | None:
    """Read 8 raw bytes from the device node and scale them to sensor ranges."""
    try:
        with open(DEVICE_PATH, "rb") as f:
            raw = f.read(8)
        if len(raw) < 4:
            return None
        temp_c = round(38.0 + (raw[0] / 255.0) * 42.0, 2)
        pressure_hpa = round(1008.0 + (raw[1] / 255.0) * 16.0, 2)
        humidity_pct = round((raw[2] / 255.0) * 100.0, 1)
        return {
            "ts": time.time(),
            "temp_c": temp_c,
            "pressure_hpa": pressure_hpa,
            "humidity_pct": humidity_pct,
            "source": "hw",
        }
    except Exception as e:
        print(f"[sensor] device read error: {e}", flush=True)
        return None


def save_reading(reading: dict):
    line = json.dumps(reading)

    # Atomic write of latest.json
    tmp = LATEST_PATH + ".tmp"
    with open(tmp, "w") as f:
        f.write(line + "\n")
    os.replace(tmp, LATEST_PATH)

    # Append to history
    with open(HISTORY_PATH, "a") as f:
        f.write(line + "\n")

    # Trim history if it grows too large
    try:
        with open(HISTORY_PATH) as f:
            lines = f.readlines()
        if len(lines) > MAX_HISTORY:
            with open(HISTORY_PATH, "w") as f:
                f.writelines(lines[-MAX_HISTORY:])
    except Exception:
        pass


def main():
    os.makedirs("/data", exist_ok=True)
    print(f"[sensor] Starting in '{SENSOR_SOURCE}' mode, interval={INTERVAL}s", flush=True)

    while True:
        reading = read_from_device() if SENSOR_SOURCE == "hw" else read_from_file()

        if reading is None:
            print("[sensor] No data yet, retrying in 1s...", flush=True)
            time.sleep(1)
            continue

        save_reading(reading)
        print(
            f"[sensor] {reading['source']} → "
            f"temp={reading['temp_c']}°C  "
            f"pressure={reading['pressure_hpa']}hPa  "
            f"humidity={reading['humidity_pct']}%",
            flush=True,
        )
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
