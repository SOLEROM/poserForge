#!/usr/bin/env python3
"""Seed task: create initial dataset (schema v1) on the shared volume."""
import datetime
import json
import os
import random

DATA_DIR = os.environ.get("DATA_DIR", "/data")
RECORDS_COUNT = int(os.environ.get("RECORDS_COUNT", "20"))


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    records_file = os.path.join(DATA_DIR, "records.json")
    schema_file = os.path.join(DATA_DIR, "schema_version")

    if os.path.exists(records_file):
        print("[seed] records.json already exists — skipping (delete volume to re-seed)")
        return

    now = datetime.datetime.utcnow()
    records = []
    for i in range(1, RECORDS_COUNT + 1):
        # First 5 records are old (40-90 days ago), rest are recent (0-28 days)
        if i <= 5:
            days_ago = random.randint(40, 90)
        else:
            days_ago = random.randint(0, 28)

        created = (now - datetime.timedelta(days=days_ago)).isoformat() + "Z"
        records.append({
            "id": i,
            "name": f"record_{i:03d}",
            "value": round(random.uniform(1.0, 100.0), 2),
            "created_at": created,
        })

    tmp = records_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump(records, f, indent=2)
    os.rename(tmp, records_file)

    with open(schema_file, "w") as f:
        f.write("v1")

    print(f"[seed] Created {len(records)} records (5 old / 15 recent), schema: v1")


if __name__ == "__main__":
    main()
