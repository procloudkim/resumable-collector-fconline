from __future__ import annotations
import argparse
from pathlib import Path
from datetime import datetime
from typing import List

from crawler.daily_trade import setup_logger
from crawler.rankers.scraper import scrape_top_nicknames, DEFAULT_RANKING_URL
from app.core.utils import get_env


def append_csv(path: Path, date_str: str, nicks: List[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    import csv
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "nickname"])
        if not exists:
            w.writeheader()
        for nick in nicks:
            w.writerow({"date": date_str, "nickname": nick})
    return path


def resolve_ouids(nicks: List[str], api_key: str, save_ranker_sample: bool = True) -> int:
    # Reuse existing pipeline to fill ouid_map (and optional ranker_sample)
    from scripts.seed_ouids import run as seed_run
    return seed_run(None, nicks, api_key, save_ranker_sample)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scrape Top-N ranker nicknames and optionally resolve to OUIDs")
    ap.add_argument("--url", default=DEFAULT_RANKING_URL)
    ap.add_argument("--top", type=int, default=18)
    ap.add_argument("--date", default=datetime.now().date().isoformat())
    ap.add_argument("--out", type=Path, default=Path("data/processed/daily_rankers.csv"))
    ap.add_argument("--resolve-ouid", action="store_true", help="Resolve nicknames to OUID via Open API")
    ap.add_argument("--api-key", default=get_env("NEXON_OPENAPI_API_KEY"))
    ap.add_argument("--headful", action="store_true", help="Run browser in headful (visible) mode for debugging")
    args = ap.parse_args(argv)

    logger = setup_logger()
    logger.info("event=ranker_cli_start url=%s top=%d date=%s out=%s resolve_ouid=%s",
                args.url, args.top, args.date, str(args.out), args.resolve_ouid)

    nicks = scrape_top_nicknames(args.url, top=args.top, headless=(not args.headful))
    append_csv(args.out, args.date, nicks)
    logger.info("event=ranker_csv_appended count=%d path=%s", len(nicks), str(args.out))

    if args.resolve_ouid:
        if not args.api_key:
            logger.error("event=missing_api_key for_ouid_resolution var=NEXON_OPENAPI_API_KEY")
            return 2
        saved = resolve_ouids(nicks, args.api_key, save_ranker_sample=True)
        logger.info("event=ranker_ouid_saved count=%d", saved)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
