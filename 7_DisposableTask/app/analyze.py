#!/usr/bin/env python3
"""Analyze task: compute statistics and write report.json to the shared volume."""
import collections
import datetime
import json
import os

DATA_DIR = os.environ.get("DATA_DIR", "/data")


def main():
    records_file = os.path.join(DATA_DIR, "records.json")
    report_file = os.path.join(DATA_DIR, "report.json")
    schema_file = os.path.join(DATA_DIR, "schema_version")

    if not os.path.exists(records_file):
        print("[analyze] No records.json found — run seed first")
        raise SystemExit(1)

    with open(records_file) as f:
        records = json.load(f)

    schema = "unknown"
    if os.path.exists(schema_file):
        schema = open(schema_file).read().strip()

    values = [r["value"] for r in records]

    report = {
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
        "schema_version": schema,
        "total_records": len(records),
        "value_stats": {
            "min": round(min(values), 2),
            "max": round(max(values), 2),
            "avg": round(sum(values) / len(values), 2),
        },
    }

    if schema == "v2":
        cats = collections.Counter(r.get("category", "unknown") for r in records)
        report["by_category"] = dict(cats)

    tmp = report_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump(report, f, indent=2)
    os.rename(tmp, report_file)

    vs = report["value_stats"]
    print(f"[analyze] {len(records)} records | avg={vs['avg']} min={vs['min']} max={vs['max']}")
    if "by_category" in report:
        for cat, n in sorted(report["by_category"].items()):
            print(f"  {cat}: {n}")
    print(f"[analyze] Report written to {report_file}")


if __name__ == "__main__":
    main()
