from __future__ import annotations
"""
Generate minimal demo artifacts so the dashboard can run offline:
- data/processed/top10_trend.csv (synthetic small timeseries)
- logs/metrics_latest.csv (summary row)

If data/sample/data-sample.db exists, leave it as-is (dashboard can fallback).
"""
import csv
import os
from pathlib import Path
from datetime import date, timedelta
import json

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
LOGS = ROOT / "logs"


def ensure_dirs() -> None:
    PROC.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)


def write_top10_trend() -> int:
    path = PROC / "top10_trend.csv"
    today = date.today()
    rows = []
    # Three days × three players (spid)
    header = ["date", "234000001", "234000002", "234000003"]
    for i in range(3, 0, -1):
        d = today - timedelta(days=i)
        rows.append([d.isoformat(), 10 * i, 7 * i, 5 * i])
    with path.open("w", newline="", encoding="utf-8") as fo:
        w = csv.writer(fo)
        w.writerow(header)
        w.writerows(rows)
    return len(rows)


def write_metrics(rows: int) -> None:
    p = LOGS / "metrics_latest.csv"
    with p.open("w", newline="", encoding="utf-8") as fo:
        w = csv.DictWriter(fo, fieldnames=["ts", "requests", "success", "rate_limited", "failed", "rows"])
        w.writeheader()
        w.writerow({
            "ts": date.today().isoformat(),
            "requests": 0,
            "success": 0,
            "rate_limited": 0,
            "failed": 0,
            "rows": rows,
        })

    # structured log line
    j = {
        "ts": date.today().isoformat(),
        "module": "demo_data",
        "event": "emit_sample",
        "status": "ok",
        "rows": rows,
    }
    with (LOGS / "app.log").open("a", encoding="utf-8") as fo:
        fo.write(json.dumps(j, ensure_ascii=False) + "\n")


def main(quiet: bool = False) -> int:
    ensure_dirs()
    count = write_top10_trend()
    write_metrics(count)
    if not quiet:
        print(f"[demo] wrote top10_trend.csv rows={count}")
    return 0


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    raise SystemExit(main(quiet=args.quiet))

