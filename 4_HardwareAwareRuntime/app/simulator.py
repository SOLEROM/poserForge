#!/usr/bin/env python3
"""
Simulates a hardware sensor by writing periodic readings to a shared volume file.
Only runs in 'sim' profile. Writes to /data/sensor.dat (atomic rename so the
reader never sees a partial write).
"""

import json
import os
import random
import time

SENSOR_PATH = "/data/sensor.dat"
INTERVAL = float(os.getenv("SAMPLE_INTERVAL", "0.5"))


def generate_reading() -> dict:
    return {
        "ts": time.time(),
        "temp_c": round(random.uniform(38.0, 78.0), 2),
        "pressure_hpa": round(random.uniform(1008.0, 1022.0), 2),
        "humidity_pct": round(random.uniform(25.0, 85.0), 1),
        "source": "sim",
    }


def main():
    os.makedirs("/data", exist_ok=True)
    print(f"[simulator] Writing to {SENSOR_PATH} every {INTERVAL}s", flush=True)

    while True:
        reading = generate_reading()
        line = json.dumps(reading)

        # Atomic write: write to temp file then rename so reader never sees partial data
        tmp = SENSOR_PATH + ".tmp"
        with open(tmp, "w") as f:
            f.write(line + "\n")
        os.replace(tmp, SENSOR_PATH)

        print(f"[simulator] {line}", flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
