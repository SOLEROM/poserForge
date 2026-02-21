#!/usr/bin/env python3
"""
Metrics Scraper sidecar — polls app /metrics endpoint and stores time-series.

Attachment: sidecar-net NETWORK (to reach app) + /logs VOLUME (to store data).

Polls every SCRAPE_INTERVAL seconds.  Stores each snapshot as a JSONL entry
in /logs/metrics.jsonl so the debugger sidecar can read history without
needing its own network scrape.
"""

import json
import os
import time
from datetime import datetime, timezone
from urllib.request import urlopen
from urllib.error import URLError

APP_URL        = os.environ.get("APP_URL", "http://app:8080")
SCRAPE_INTERVAL = int(os.environ.get("SCRAPE_INTERVAL", 5))
METRICS_LOG    = "/logs/metrics.jsonl"

BOLD   = "\033[1m"
DIM    = "\033[2m"
CYAN   = "\033[36m"
GREEN  = "\033[32m"
YELLOW = "\033[33m"
RED    = "\033[31m"
RESET  = "\033[0m"


def parse_prometheus(text: str) -> dict:
    """Parse Prometheus text exposition format into a flat dict."""
    metrics = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        parts = line.split()
        if len(parts) == 2:
            try:
                metrics[parts[0]] = float(parts[1])
            except ValueError:
                pass
    return metrics


def scrape() -> dict | None:
    try:
        resp = urlopen(f"{APP_URL}/metrics", timeout=3)
        return parse_prometheus(resp.read().decode())
    except (URLError, Exception):
        return None


def store(metrics: dict) -> None:
    entry = {"ts": datetime.now(timezone.utc).isoformat(), **metrics}
    os.makedirs("/logs", exist_ok=True)
    with open(METRICS_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def display(metrics: dict, prev: dict | None, scrape_n: int) -> None:
    now = datetime.now().strftime("%H:%M:%S")

    def delta(key: str) -> str:
        if prev and key in prev:
            d = metrics.get(key, 0) - prev.get(key, 0)
            return f" {DIM}(+{d:.0f}){RESET}" if d > 0 else ""
        return ""

    req_total = metrics.get("requests_total", 0)
    req_ok    = metrics.get("requests_ok", 0)
    req_err   = metrics.get("requests_err", 0)
    uptime    = metrics.get("uptime_seconds", 0)
    proc_ok   = metrics.get("process_ok", 0)
    proc_err  = metrics.get("process_err", 0)

    err_pct   = (req_err / req_total * 100) if req_total > 0 else 0.0
    err_color = RED if err_pct > 10 else (YELLOW if err_pct > 0 else GREEN)

    print(
        f"\n{CYAN}{BOLD}── Metrics Scraper [{now}] scrape #{scrape_n} ──{RESET}\n"
        f"  {BOLD}Uptime          {RESET} {uptime:.0f}s\n"
        f"  {BOLD}Requests total  {RESET} {req_total:.0f}{delta('requests_total')}\n"
        f"  {BOLD}Requests OK     {RESET} {GREEN}{req_ok:.0f}{RESET}{delta('requests_ok')}\n"
        f"  {BOLD}Requests ERR    {RESET} {err_color}{req_err:.0f} ({err_pct:.1f}%){RESET}{delta('requests_err')}\n"
        f"  {BOLD}Process OK      {RESET} {proc_ok:.0f}{delta('process_ok')}\n"
        f"  {BOLD}Process ERR     {RESET} {proc_err:.0f}{delta('process_err')}\n"
        f"  {DIM}stored → /logs/metrics.jsonl{RESET}",
        flush=True,
    )


def main() -> None:
    print(
        f"{CYAN}{BOLD}╔══════════════════════════════════╗{RESET}\n"
        f"{CYAN}{BOLD}║   Metrics Scraper Sidecar        ║{RESET}\n"
        f"{CYAN}{BOLD}║   target: {APP_URL}/metrics{RESET}\n"
        f"{CYAN}{BOLD}║   interval: {SCRAPE_INTERVAL}s                  ║{RESET}\n"
        f"{CYAN}{BOLD}╚══════════════════════════════════╝{RESET}",
        flush=True,
    )

    prev     = None
    scrape_n = 0

    while True:
        metrics = scrape()
        if metrics:
            scrape_n += 1
            store(metrics)
            display(metrics, prev, scrape_n)
            prev = metrics
        else:
            print(f"{YELLOW}  scrape failed — retrying in {SCRAPE_INTERVAL}s{RESET}", flush=True)
        time.sleep(SCRAPE_INTERVAL)


if __name__ == "__main__":
    main()
