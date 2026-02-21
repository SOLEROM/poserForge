#!/usr/bin/env python3
"""Cleanup task: remove records older than CLEANUP_DAYS from the dataset."""
import datetime
import json
import os

DATA_DIR = os.environ.get("DATA_DIR", "/data")
CLEANUP_DAYS = int(os.environ.get("CLEANUP_DAYS", "30"))


def main():
    records_file = os.path.join(DATA_DIR, "records.json")

    if not os.path.exists(records_file):
        print("[cleanup] No records.json found — nothing to clean")
        return

    with open(records_file) as f:
        records = json.load(f)

    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=CLEANUP_DAYS)
    kept = []
    removed_ids = []

    for r in records:
        ts = r["created_at"].rstrip("Z")
        created = datetime.datetime.fromisoformat(ts)
        if created >= cutoff:
            kept.append(r)
        else:
            removed_ids.append(r["id"])

    tmp = records_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump(kept, f, indent=2)
    os.rename(tmp, records_file)

    print(f"[cleanup] Threshold: {CLEANUP_DAYS} days (before {cutoff.date()})")
    print(f"[cleanup] Removed {len(removed_ids)} records, {len(kept)} remaining")
    if removed_ids:
        print(f"[cleanup] Removed IDs: {removed_ids}")


if __name__ == "__main__":
    main()
