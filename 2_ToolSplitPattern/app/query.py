#!/usr/bin/env python3
"""
Query Tool — one-shot job status query.

Fetches a single job (JOB_ID env) or the full job list from the service.
Exits immediately after printing results.
"""

import json
import os
import sys
import time

import requests

API_URL = os.environ.get("API_URL", "http://api:8080")
JOB_ID  = os.environ.get("JOB_ID",  "").strip()


def wait_for_service(retries: int = 10, delay: float = 1.0) -> bool:
    for i in range(retries):
        try:
            r = requests.get(f"{API_URL}/health", timeout=2)
            if r.ok:
                return True
        except Exception:
            pass
        print(f"  [query] waiting for service... ({i + 1}/{retries})", flush=True)
        time.sleep(delay)
    return False


def main() -> int:
    print(f"[query] API: {API_URL}", flush=True)
    if not wait_for_service():
        print("[query] ERROR: service unavailable", flush=True)
        return 1

    if JOB_ID:
        print(f"[query] Fetching job {JOB_ID}", flush=True)
        r = requests.get(f"{API_URL}/jobs/{JOB_ID}", timeout=5)
        if r.status_code == 404:
            print(f"[query] Job {JOB_ID!r} not found", flush=True)
            return 1
        r.raise_for_status()
        print(json.dumps(r.json(), indent=2), flush=True)
    else:
        print("[query] Listing all jobs", flush=True)
        r = requests.get(f"{API_URL}/jobs", timeout=5)
        r.raise_for_status()
        data = r.json()
        print(f"[query] Total jobs: {data['count']}", flush=True)
        print(json.dumps(data, indent=2), flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
