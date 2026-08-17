from __future__ import annotations
import argparse
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from . import setup_logger
from .fetcher import get_dailytrade_page, get_dailytrade_page_any
from .parser import (
    parse_daily_trade,
    parse_daily_top_players,
    PlayerTarget,
    LayoutChangedError,
)
from .writer import (
    connect,
    init_schema,
    is_visited,
    mark_visited,
    upsert_daily_trade,
    upsert_daily_top_players,
    append_csv,
    DB_PATH_DEFAULT,
)


def _date_range(start: str, end: str) -> List[str]:
    s = datetime.strptime(start, "%Y-%m-%d").date()
    e = datetime.strptime(end, "%Y-%m-%d").date()
    cur = s
    out = []
    while cur <= e:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def _load_players(path: Path) -> List[PlayerTarget]:
    """플레이어 목록 로드(JSON/CSV)

    왜(WHY): 대상 선수 집합을 넘겨주어 파서가 표에서 해당 선수만 취합하도록 한다.
    어떻게(HOW): JSON이면 list[dict] 형태, CSV이면 spid,name_kor,name_eng 헤더를 파싱한다.
    """
    import csv

    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        out: List[PlayerTarget] = []
        for it in data:
            out.append(PlayerTarget(spid=int(it["spid"]) if "spid" in it else int(it["id"]),
                                    name_kor=it.get("name_kor") or it.get("name"),
                                    name_eng=it.get("name_eng") or it.get("name_en")))
        return out
    # CSV
    out: List[PlayerTarget] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        # spid 컬럼 자동 추출
        spid_col = None
        for k in reader.fieldnames or []:
            kk = (k or "").strip().lower()
            if kk in ("spid", "id"):
                spid_col = k
                break
        for row in reader:
            spid = int(row[spid_col]) if spid_col and row.get(spid_col) else None
            if not spid:
                continue
            out.append(PlayerTarget(spid=spid,
                                    name_kor=row.get("name_kor") or row.get("name"),
                                    name_eng=row.get("name_eng") or row.get("name_en")))
    return out


def main(argv: Optional[List[str]] = None) -> int:
    """CLI 엔트리포인트

    왜(WHY): 자동화 파이프라인(C 단계)에서 기간별로 안정적으로 수집하기 위해 CLI 인터페이스가 필요하다.
    어떻게(HOW): 시작/종료일과 대상 선수 목록을 받아 일자별 크롤링→파싱→DB upsert를 수행한다.
    멱등성은 visited_log와 PK 업서트를 이용한다.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-date", required=True)
    ap.add_argument("--end-date", required=True)
    ap.add_argument("--players", required=True, help="JSON/CSV with fields [spid,name_kor,name_eng]")
    ap.add_argument("--only-topN", action="store_true", help="TopN 표만 수집")
    ap.add_argument("--dry-run", action="store_true", help="DB/CSV 쓰기 생략(파싱만)")
    ap.add_argument("--db", default=str(DB_PATH_DEFAULT))
    ap.add_argument("--use-selenium", action="store_true", help="Use Selenium to fetch pages")
    ap.add_argument("--headful", action="store_true", help="Run Selenium in visible(headful) mode")
    ap.add_argument("--pause-on-captcha", action="store_true", help="Pause and wait for manual CAPTCHA solve when detected")
    ap.add_argument("--export-csv", action="store_true", help="CSV에도 append")
    args = ap.parse_args(argv)

    logger = setup_logger()
    # 인자 검증: 날짜 범위
    try:
        dates = _date_range(args.start_date, args.end_date)
    except Exception:
        logger.error("event=arg_error reason=bad_date_range start=%s end=%s", args.start_date, args.end_date)
        return 2
    # 플레이어 목록 로드
    ppath = Path(args.players)
    if not ppath.exists():
        logger.error("event=arg_error reason=players_not_found path=%s", str(ppath))
        return 2
    players = _load_players(ppath)
    if not players and not args.only_topN:
        logger.error("event=arg_error reason=empty_players path=%s", str(ppath))
        return 2
    logger.info(
        "event=cli_start db=%s dates=%d players=%d only_topN=%s dry_run=%s export_csv=%s",
        args.db, len(dates), len(players), args.only_topN, args.dry_run, args.export_csv,
    )

    conn = connect(Path(args.db))
    init_schema(conn)

    total_trade = 0
    total_topn = 0
    total_csv = 0
    # Optional Selenium driver
    driver = None
    if args.use_selenium:
        try:
            from crawler.selenium_utils import create_driver, apply_stealth  # lazy import
            driver = create_driver(headless=not args.headful)
            # Light stealth to reduce bot flags
            apply_stealth(driver)
        except Exception as e:
            logger.error("event=selenium_init_failed err=%s", e)
            driver = None

    for d in dates:
        key_trade = f"dailytrade:{d}:trade"
        key_topn = f"dailytrade:{d}:topn"

        # Fetch HTML (requests default, Selenium if enabled)
        html = get_dailytrade_page_any(
            d,
            use_selenium=bool(driver),
            driver=driver,
            pause_on_captcha=args.pause_on_captcha,
        )
        if not html:
            logger.warning("event=html_empty date=%s", d)
            # 스냅샷 저장
            raw_dir = Path("data") / "raw" / "html"
            raw_dir.mkdir(parents=True, exist_ok=True)
            (raw_dir / f"{d.replace('-', '')}.html").write_text("", encoding="utf-8")
            continue

        # TopN만 원하는 경우
        if args.only_topN:
            try:
                top_rows = parse_daily_top_players(html, d)
            except LayoutChangedError:
                logger.warning("event=layout_changed section=topn date=%s", d)
                raw_dir = Path("data") / "raw" / "html"
                raw_dir.mkdir(parents=True, exist_ok=True)
                (raw_dir / f"{d.replace('-', '')}.html").write_text(html, encoding="utf-8")
                continue
            upserted_top = 0
            if not args.dry_run:
                if is_visited(conn, key_topn):
                    logger.info("event=visited_skip key=%s date=%s section=topn", key_topn, d)
                else:
                    with conn:
                        upserted_top = upsert_daily_top_players(conn, top_rows)
                        mark_visited(conn, key_topn)
                    logger.info("event=visited_marked key=%s", key_topn)
            if args.export_csv and top_rows:
                total_csv += append_csv(Path("data/processed/daily_top_players.csv"), top_rows, ["date", "spid", "rank", "pick_rate", "player_name"])
            total_topn += upserted_top
            continue

        # Trade 표 수집
        try:
            trade_rows = parse_daily_trade(html, d, players)
        except LayoutChangedError:
            logger.warning("event=layout_changed section=trade date=%s", d)
            raw_dir = Path("data") / "raw" / "html"
            raw_dir.mkdir(parents=True, exist_ok=True)
            (raw_dir / f"{d.replace('-', '')}.html").write_text(html, encoding="utf-8")
            continue
        upserted = 0
        if not args.dry_run:
            if is_visited(conn, key_trade):
                logger.info("event=visited_skip key=%s date=%s section=trade", key_trade, d)
            else:
                with conn:
                    upserted = upsert_daily_trade(conn, trade_rows)
                    mark_visited(conn, key_trade)
                logger.info("event=visited_marked key=%s", key_trade)
        if args.export_csv and trade_rows:
            total_csv += append_csv(Path("data/processed/daily_trade.csv"), trade_rows,
                                    ["date", "spid", "player_name", "avg_price", "max_price", "min_price", "trade_count", "max_enhance_level", "source"])
        total_trade += upserted
        logger.info("event=cli_day_done date=%s upserted_trade=%d upserted_top=%d csv_appended_total=%d", d, upserted, 0, total_csv)

    # Cleanup driver
    if driver is not None:
        try:
            driver.quit()
        except Exception:
            pass

    logger.info("event=cli_done total_upserted_trade=%d total_upserted_top=%d total_csv_appended=%d dates=%d", total_trade, total_topn, total_csv, len(dates))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
