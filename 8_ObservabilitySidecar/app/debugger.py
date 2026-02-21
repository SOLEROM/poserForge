#!/usr/bin/env python3
"""
Debugger sidecar — one-shot full inspection report.

Attachment: sidecar-net NETWORK + /logs VOLUME (read-only).

Combines BOTH observation channels:
  1. Network queries → live app state (health, metrics endpoint)
  2. Volume reads    → historical log analysis + scraped metrics history

Run with:  docker compose --profile debug run --rm debugger
"""

import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from urllib.request import urlopen
from urllib.error import URLError

APP_URL   = os.environ.get("APP_URL", "http://app:8080")
LOG_PATH  = "/logs/app.log"
METRICS_LOG = "/logs/metrics.jsonl"

BOLD  = "\033[1m"
DIM   = "\033[2m"
CYAN  = "\033[36m"
GREEN = "\033[32m"
YELLOW= "\033[33m"
RED   = "\033[31m"
RESET = "\033[0m"
SEP   = f"{CYAN}{'─' * 52}{RESET}"


def http_get(path: str) -> dict | str:
    try:
        resp = urlopen(f"{APP_URL}{path}", timeout=3)
        raw = resp.read().decode()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return raw
    except URLError as e:
        return {"__error__": str(e)}


def read_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    entries = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return entries


def section(title: str) -> None:
    print(f"\n{SEP}")
    print(f"{CYAN}{BOLD}  {title}{RESET}")
    print(SEP)


def main() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{CYAN}{BOLD}{'═' * 52}{RESET}")
    print(f"{CYAN}{BOLD}  DEBUGGER SIDECAR — Full Inspection Report{RESET}")
    print(f"{CYAN}{BOLD}  {now}{RESET}")
    print(f"{CYAN}{BOLD}{'═' * 52}{RESET}")

    # ── 1. App health via network ────────────────────────────────────────────
    section("1. App Health  (via network)")
    health = http_get("/health")
    if isinstance(health, dict) and "__error__" in health:
        print(f"  {RED}App unreachable: {health['__error__']}{RESET}")
    elif isinstance(health, dict):
        status = health.get("status", "?")
        color  = GREEN if status == "ok" else RED
        print(f"  Status : {color}{BOLD}{status}{RESET}")
        print(f"  Uptime : {health.get('uptime_s', '?')}s")
    else:
        print(f"  {YELLOW}Unexpected response: {health}{RESET}")

    # ── 2. Live metrics via network ──────────────────────────────────────────
    section("2. Live Metrics  (via network)")
    try:
        resp = urlopen(f"{APP_URL}/metrics", timeout=3)
        raw  = resp.read().decode()
        for line in raw.splitlines():
            if not line.startswith("#") and line.strip():
                parts = line.split()
                if len(parts) == 2:
                    print(f"  {parts[0]:<28} {BOLD}{parts[1]}{RESET}")
    except Exception as e:
        print(f"  {RED}Cannot fetch metrics: {e}{RESET}")

    # ── 3. Log analysis via volume ───────────────────────────────────────────
    section("3. Log Analysis  (via /logs volume)")
    logs = read_jsonl(LOG_PATH)
    if not logs:
        print(f"  {YELLOW}No log file at {LOG_PATH}{RESET}")
    else:
        levels   = Counter(e.get("level", "?") for e in logs)
        messages = Counter(e.get("msg", "?") for e in logs)

        print(f"  Total entries : {BOLD}{len(logs)}{RESET}")
        print(f"  By level:")
        for level, count in sorted(levels.items()):
            color = RED if level == "ERROR" else (YELLOW if "WARN" in level else GREEN)
            print(f"    {color}{level:<10}{RESET} {count}")

        print(f"  Top messages:")
        for msg, count in messages.most_common(6):
            print(f"    {count:3}×  {msg}")

        errors = [e for e in logs if e.get("level") == "ERROR"]
        if errors:
            n = min(3, len(errors))
            print(f"\n  {RED}Last {n} error(s):{RESET}")
            for e in errors[-n:]:
                ts  = e.get("ts", "?")[11:19]
                msg = e.get("msg", "?")
                rsn = e.get("reason", "")
                print(f"    {DIM}{ts}{RESET}  {RED}{msg}{RESET}  {DIM}{rsn}{RESET}")

    # ── 4. Metrics history from scraper volume ───────────────────────────────
    section("4. Metrics History  (from metrics-scraper via /logs volume)")
    history = read_jsonl(METRICS_LOG)
    if not history:
        print(f"  {DIM}No metrics history — is metrics-scraper running?{RESET}")
    else:
        first = history[0]
        last  = history[-1]
        delta_req = last.get("requests_total", 0) - first.get("requests_total", 0)
        print(f"  Snapshots collected : {BOLD}{len(history)}{RESET}")
        print(f"  First snapshot      : {first.get('ts','?')[11:19]}  "
              f"requests={first.get('requests_total',0):.0f}")
        print(f"  Latest snapshot     : {last.get('ts','?')[11:19]}   "
              f"requests={last.get('requests_total',0):.0f}")
        if len(history) >= 2:
            print(f"  Δ requests          : {GREEN}+{delta_req:.0f}{RESET} over {len(history)} scrapes")

    print(f"\n{DIM}Report complete.{RESET}\n")


if __name__ == "__main__":
    main()
