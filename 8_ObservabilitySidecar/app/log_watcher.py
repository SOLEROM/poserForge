#!/usr/bin/env python3
"""
Log Watcher sidecar — tails the app log volume and pretty-prints entries.

Attachment: /logs VOLUME only (read-only).
Network:    none — does NOT need to reach the app over HTTP.

This demonstrates that sidecars can observe purely via shared filesystem
without any network access to the primary service.
"""

import json
import os
import time

LOG_PATH = "/logs/app.log"

# ANSI colours
RED    = "\033[31m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

LEVEL_COLOUR = {
    "INFO":    GREEN,
    "WARNING": YELLOW,
    "WARN":    YELLOW,
    "ERROR":   RED,
}


def format_entry(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    try:
        entry = json.loads(raw)
    except json.JSONDecodeError:
        return f"{DIM}{raw}{RESET}"

    ts    = entry.get("ts", "")
    ts_s  = ts[11:19] if len(ts) >= 19 else ts   # HH:MM:SS portion
    level = entry.get("level", "INFO")
    msg   = entry.get("msg", "")
    color = LEVEL_COLOUR.get(level, "")

    extras = {k: v for k, v in entry.items() if k not in ("ts", "level", "msg")}
    extras_str = "  " + "  ".join(f"{k}={v}" for k, v in extras.items()) if extras else ""

    return (
        f"{DIM}{ts_s}{RESET} "
        f"{color}{BOLD}{level:<7}{RESET} "
        f"{msg}"
        f"{DIM}{extras_str}{RESET}"
    )


def tail_forever(path: str) -> None:
    print(f"{CYAN}{BOLD}╔══════════════════════════════════╗{RESET}")
    print(f"{CYAN}{BOLD}║   Log Watcher Sidecar            ║{RESET}")
    print(f"{CYAN}{BOLD}║   volume: /logs  (read-only)     ║{RESET}")
    print(f"{CYAN}{BOLD}╚══════════════════════════════════╝{RESET}\n", flush=True)

    while not os.path.exists(path):
        print(f"{DIM}  waiting for {path} ...{RESET}", flush=True)
        time.sleep(1)

    with open(path, "r") as f:
        f.seek(0, 2)  # seek to end — only show new entries
        while True:
            line = f.readline()
            if line:
                formatted = format_entry(line)
                if formatted:
                    print(formatted, flush=True)
            else:
                time.sleep(0.1)


if __name__ == "__main__":
    tail_forever(LOG_PATH)
