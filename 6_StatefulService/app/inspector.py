#!/usr/bin/env python3
"""
Volume inspector — reads /data directly, no HTTP required.

Demonstrates that persisted state is accessible even when the service
container is completely stopped or removed.
"""

import json
import sys
from pathlib import Path

DATA_DIR     = Path("/data")
SESSIONS_DIR = DATA_DIR / "sessions"
EVENTS_FILE  = DATA_DIR / "events.jsonl"
STATS_FILE   = DATA_DIR / "stats.json"


def hr(char="─", width=62):
    print(char * width)


def section(title: str):
    hr()
    print(f"  {title}")
    hr()


def main():
    if not DATA_DIR.exists():
        print("ERROR: /data volume not found or empty")
        sys.exit(1)

    section("PERSISTENT STATS")
    if STATS_FILE.exists():
        stats = json.loads(STATS_FILE.read_text())
        for k, v in stats.items():
            print(f"  {k:<28} {v}")
    else:
        print("  (no stats yet)")

    section("SESSIONS")
    sessions = sorted(SESSIONS_DIR.glob("*.json")) if SESSIONS_DIR.exists() else []
    if sessions:
        print(f"  {'ID':<36}  {'NAME':<20}  {'ACCESSES':>8}  CREATED")
        hr("·")
        for p in sessions:
            s = json.loads(p.read_text())
            print(f"  {s['id']:<36}  {s.get('name',''):<20}"
                  f"  {s.get('access_count', 0):>8}  {s.get('created_at', '')}")
    else:
        print("  (no sessions)")
    print(f"\n  Total: {len(sessions)}")

    section("RECENT EVENTS  (last 10)")
    if EVENTS_FILE.exists():
        lines = [l for l in EVENTS_FILE.read_text().splitlines() if l.strip()]
        for line in lines[-10:]:
            e      = json.loads(line)
            cid    = e.get("container", "")[:8]
            extras = {k: v for k, v in e.items()
                      if k not in ("ts", "time", "event", "container")}
            suffix = f"  {extras}" if extras else ""
            print(f"  {e['time']}  [{cid}]  {e['event']}{suffix}")
        print(f"\n  Total events: {len(lines)}")
    else:
        print("  (no events yet)")

    hr("═")
    print()


if __name__ == "__main__":
    main()
