#!/usr/bin/env python3
"""
Report Tool — reads the shared volume directly (no HTTP).

Demonstrates that tool containers can access shared state independently
of the service API, operating on the same persistent workspace volume.
"""

import json
import os
import sys
from collections import Counter
from pathlib import Path

WORKSPACE  = Path(os.environ.get("WORKSPACE", "/workspace"))
JOBS_FILE  = WORKSPACE / "jobs.json"


def main() -> int:
    print(f"[report] Workspace: {WORKSPACE}", flush=True)

    if not JOBS_FILE.exists():
        print("[report] No jobs.json found — run 'make submit' first.", flush=True)
        return 0

    jobs = json.loads(JOBS_FILE.read_text())

    width = 54
    print("=" * width)
    print("            JOB TRACKER REPORT")
    print("=" * width)
    print(f"  Total jobs  : {len(jobs)}")

    statuses = Counter(j["status"] for j in jobs.values())
    for status, count in sorted(statuses.items()):
        print(f"  {status:12s}: {count}")

    print()
    print("  Recent jobs (up to 10):")
    for job in list(jobs.values())[-10:]:
        submitted = (job.get("submitted_at") or "?")[:19]
        print(f"  [{job['id']}] {job['name']:<20s} {job['status']:<10s} {submitted}")

    print("=" * width)
    return 0


if __name__ == "__main__":
    sys.exit(main())
