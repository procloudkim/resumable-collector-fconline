from __future__ import annotations
"""
One-shot pipeline runner (immediate execution).

Run on demand:
  python scripts/schedule_fetch.py --date 2025-09-11 --players pairs.json --use-selenium
"""

import argparse
import subprocess
import sys
from datetime import date, timedelta


def run_cmd(args: list[str], title: str) -> None:
    print(f"[RUN] {title}: {' '.join(args)}", flush=True)
    subprocess.run([sys.executable] + args, check=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=(date.today() - timedelta(days=1)).isoformat())
    ap.add_argument("--players", default="pairs.json")
    ap.add_argument("--use-selenium", action="store_true")
    ap.add_argument("--resolve-ouid", action="store_true", default=True)
    ap.add_argument("--no-resolve-ouid", action="store_false", dest="resolve_ouid")
    ap.add_argument("--run-ranker-stats", action="store_true", default=True)
    ap.add_argument("--no-ranker-stats", action="store_false", dest="run_ranker_stats")
    ap.add_argument("--run-preprocess-top10", action="store_true", default=False)
    args = ap.parse_args(argv)

    # 1) Rankers Top18 + OUID
    if args.resolve_ouid:
        run_cmd(["-m", "crawler.rankers.cli", "--top", "18", "--resolve-ouid", "--date", args.date],
                f"Rankers scrape + OUID (date={args.date})")

    # 2) Daily Trade (same day for start/end)
    trade_args = [
        "-m", "crawler.daily_trade.cli",
        "--start-date", args.date,
        "--end-date", args.date,
        "--players", args.players,
        "--export-csv",
    ]
    if args.use_selenium:
        trade_args.append("--use-selenium")
    run_cmd(trade_args, f"Daily trade crawl (date={args.date})")

    # 3) Ranker stats
    if args.run_ranker_stats:
        run_cmd(["scripts/fetch_ranker_stats.py", "--pairs", args.players], "Ranker stats fetch")

    # 4) Top10 preprocess
    if args.run_preprocess_top10:
        run_cmd(["scripts/preprocess_top10.py"], "Preprocess top10 trend")

    print("[DONE] Pipeline completed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
