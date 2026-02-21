#!/usr/bin/env python3
"""Status task: inspect the current state of the shared data volume."""
import json
import os

DATA_DIR = os.environ.get("DATA_DIR", "/data")


def main():
    print("=== Volume Status ===")
    if not os.path.exists(DATA_DIR):
        print("(data directory not found)")
        return

    files = sorted(os.listdir(DATA_DIR))
    if not files:
        print("(volume is empty — run 'make seed' to start)")
        return

    print(f"Files: {', '.join(files)}")

    schema_file = os.path.join(DATA_DIR, "schema_version")
    if os.path.exists(schema_file):
        print(f"Schema: {open(schema_file).read().strip()}")

    records_file = os.path.join(DATA_DIR, "records.json")
    if os.path.exists(records_file):
        records = json.load(open(records_file))
        print(f"Records: {len(records)}")
        if records and "category" in records[0]:
            from collections import Counter
            cats = Counter(r["category"] for r in records)
            for cat, n in sorted(cats.items()):
                print(f"  {cat}: {n}")

    report_file = os.path.join(DATA_DIR, "report.json")
    if os.path.exists(report_file):
        r = json.load(open(report_file))
        vs = r["value_stats"]
        print(f"Report: {r['total_records']} records | avg={vs['avg']} min={vs['min']} max={vs['max']}")

    export_file = os.path.join(DATA_DIR, "export.csv")
    if os.path.exists(export_file):
        lines = open(export_file).readlines()
        headers = lines[0].strip() if lines else "?"
        print(f"Export: {max(0, len(lines) - 1)} rows | headers: {headers}")


if __name__ == "__main__":
    main()
