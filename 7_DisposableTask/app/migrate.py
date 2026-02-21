#!/usr/bin/env python3
"""Migrate task: upgrade dataset from schema v1 to v2.

v1 fields: id, name, value, created_at
v2 adds:   category (low/medium/high), normalized_value (0.0-1.0)
"""
import json
import os

DATA_DIR = os.environ.get("DATA_DIR", "/data")


def get_category(value: float) -> str:
    if value < 33.33:
        return "low"
    elif value < 66.67:
        return "medium"
    return "high"


def main():
    records_file = os.path.join(DATA_DIR, "records.json")
    schema_file = os.path.join(DATA_DIR, "schema_version")

    if not os.path.exists(records_file):
        print("[migrate] No records.json found — run seed first")
        raise SystemExit(1)

    schema = "v1"
    if os.path.exists(schema_file):
        schema = open(schema_file).read().strip()

    if schema == "v2":
        print("[migrate] Already at schema v2 — nothing to do")
        return

    if schema != "v1":
        print(f"[migrate] Unknown schema version '{schema}' — cannot migrate")
        raise SystemExit(1)

    with open(records_file) as f:
        records = json.load(f)

    migrated = 0
    for r in records:
        if "category" not in r:
            r["category"] = get_category(r["value"])
            r["normalized_value"] = round(r["value"] / 100.0, 4)
            migrated += 1

    tmp = records_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump(records, f, indent=2)
    os.rename(tmp, records_file)

    with open(schema_file, "w") as f:
        f.write("v2")

    print(f"[migrate] Migrated {migrated} records: v1 → v2")
    print("[migrate] Added fields: category, normalized_value")


if __name__ == "__main__":
    main()
