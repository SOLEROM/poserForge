#!/usr/bin/env python3
"""Export task: write records.json as export.csv to the shared volume."""
import csv
import json
import os

DATA_DIR = os.environ.get("DATA_DIR", "/data")


def main():
    records_file = os.path.join(DATA_DIR, "records.json")
    export_file = os.path.join(DATA_DIR, "export.csv")

    if not os.path.exists(records_file):
        print("[export] No records.json found — run seed first")
        raise SystemExit(1)

    with open(records_file) as f:
        records = json.load(f)

    if not records:
        print("[export] No records to export")
        return

    fieldnames = list(records[0].keys())

    tmp = export_file + ".tmp"
    with open(tmp, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)
    os.rename(tmp, export_file)

    print(f"[export] Exported {len(records)} records to export.csv")
    print(f"[export] Fields: {', '.join(fieldnames)}")


if __name__ == "__main__":
    main()
