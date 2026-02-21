#!/usr/bin/env python3
"""
Submit Tool — one-shot job submission.

Connects to the running service via the shared Docker network,
posts a new job, and exits immediately.
"""

import json
import os
import sys
import time

import requests

API_URL  = os.environ.get("API_URL",  "http://api:8080")
JOB_NAME = os.environ.get("JOB_NAME", "demo-job")
JOB_CMD  = os.environ.get("JOB_CMD",  "echo hello world")


def wait_for_service(retries: int = 10, delay: float = 1.0) -> bool:
    for i in range(retries):
        try:
            r = requests.get(f"{API_URL}/health", timeout=2)
            if r.ok:
                return True
        except Exception:
            pass
        print(f"  [submit] waiting for service... ({i + 1}/{retries})", flush=True)
        time.sleep(delay)
    return False


def main() -> int:
    print(f"[submit] API: {API_URL}", flush=True)
    if not wait_for_service():
        print("[submit] ERROR: service unavailable", flush=True)
        return 1

    payload = {"name": JOB_NAME, "cmd": JOB_CMD}
    print(f"[submit] Submitting: {payload}", flush=True)

    r = requests.post(f"{API_URL}/jobs", json=payload, timeout=5)
    r.raise_for_status()

    job = r.json()
    print(f"[submit] Accepted — id={job['id']} status={job['status']}", flush=True)
    print(json.dumps(job, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
