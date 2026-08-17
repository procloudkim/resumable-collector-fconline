from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Dict, Any, Optional, Tuple
import sqlite3
import csv
import time

from . import setup_logger

DB_PATH_DEFAULT = Path("data") / "data.db"
CSV_DIR = Path("data") / "processed"
CSV_DIR.mkdir(parents=True, exist_ok=True)


def connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """SQLite 연결 생성

    왜(WHY): 기존 앱 DB(`data/data.db`)에 테이블을 확장해 동일한 저장소를 유지한다.
    무엇(WHAT): 지정 경로로 SQLite 연결을 생성하고 동시성/복구 친화 PRAGMA를 적용한다.
    어떻게(HOW): WAL 모드와 busy_timeout을 설정하고, 설정값을 안전 로그로 남긴다.
    """
    logger = setup_logger()
    path = db_path or DB_PATH_DEFAULT
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    # 동시 접근/락 안정성 향상
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        logger.info("event=db_pragma path=%s wal=on sync=NORMAL busy_timeout_ms=5000", str(path))
    except Exception:
        logger.warning("event=db_pragma_failed path=%s", str(path))
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """크롤러 확장 테이블 생성

    왜(WHY): daily_trade / daily_top_players / visited_log 테이블이 없을 수 있다.
    무엇(WHAT): 3개 테이블을 IF NOT EXISTS로 생성한다.
    어떻게(HOW): 단일 트랜잭션으로 스키마를 적용하고 커밋한다.
    """
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_trade(
            date TEXT NOT NULL,
            spid INTEGER NOT NULL,
            player_name TEXT,
            avg_price BIGINT,
            max_price BIGINT,
            min_price BIGINT,
            trade_count INTEGER,
            max_enhance_level INTEGER,
            source TEXT DEFAULT 'web',
            PRIMARY KEY(date, spid)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_top_players(
            date TEXT NOT NULL,
            spid INTEGER NOT NULL,
            rank INTEGER,
            pick_rate REAL,
            PRIMARY KEY(date, spid)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS visited_log(
            key TEXT PRIMARY KEY,
            created_at TEXT
        )
        """
    )
    # 일자·선수별 사용 빈도(픽) 시계열 저장 테이블
    # WHY: 특정 시기에 특정 선수가 얼마나 '사용되었는지'를 시계열로 분석하기 위해
    # WHAT: date, spid, matchtype별 pick_count와 그날 집계에 사용된 분모(sample_match_count)
    # HOW: matchtype이 비지정인 경우 0으로 저장하여 PK 충돌을 방지하고 멱등 UPSERT 수행
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_pick(
            date TEXT NOT NULL,
            spid INTEGER NOT NULL,
            matchtype INTEGER DEFAULT 0,
            pick_count INTEGER NOT NULL,
            sample_match_count INTEGER NOT NULL,
            source TEXT DEFAULT 'api',
            PRIMARY KEY(date, spid, matchtype, source)
        )
        """
    )
    # 조회 성능 향상을 위한 보조 인덱스
    # WHY: 대시보드/리포트에서 date, spid 조건 조회가 빈번함
    # WHAT: (date, spid) 결합 인덱스
    # HOW: IF NOT EXISTS로 중복 생성 방지
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_daily_pick_date_spid ON daily_pick(date, spid)"
    )

    # 정규화된 픽률 뷰
    # WHY: pick_rate = pick_count / sample_match_count 를 매번 계산하지 않고 뷰로 제공
    # WHAT: date, spid, matchtype 별 pick_rate 산출, 0으로 나누기 방지(NULLIF)
    # HOW: CREATE VIEW IF NOT EXISTS 로 안전 생성
    try:
        cur.execute(
            """
            CREATE VIEW IF NOT EXISTS daily_pick_rate_view AS
            SELECT
              date,
              spid,
              matchtype,
              (1.0 * pick_count) / NULLIF(sample_match_count, 0) AS pick_rate,
              source
            FROM daily_pick
            """
        )
    except sqlite3.OperationalError:
        # 일부 구버전 SQLite 환경에서 VIEW 권한 문제 시 무시
        pass
    conn.commit()


def is_visited(conn: sqlite3.Connection, key: str) -> bool:
    """visited_log 체크

    왜(WHY): 동일 키의 중복 작업을 피하기 위해 이미 처리한 적이 있는지 확인한다.
    무엇(WHAT): visited_log 테이블에 key가 존재하는지 조회한다.
    어떻게(HOW): 단건 SELECT 후 존재 여부를 bool로 반환한다.
    """
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM visited_log WHERE key=?", (key,))
    return cur.fetchone() is not None


def mark_visited(conn: sqlite3.Connection, key: str) -> None:
    """visited_log 기록

    왜(WHY): 성공적으로 처리한 작업의 키를 기록해 재수집/중복 작성을 방지한다.
    무엇(WHAT): key를 PK로 하여 현재 시각과 함께 기록한다.
    어떻게(HOW): INSERT OR REPLACE를 사용하고 커밋한다.
    """
    cur = conn.cursor()
    cur.execute("INSERT OR REPLACE INTO visited_log(key, created_at) VALUES(?, datetime('now'))", (key,))
    conn.commit()


def _validate_trade_row(r: Dict[str, Any]) -> tuple[bool, str | None]:
    """daily_trade 행 유효성 검사

    왜(WHY): DB 무결성을 보장하고 잘못된 파싱/입력을 조기에 차단하기 위함.
    무엇(WHAT): date 형식, spid 정수/양수, 가격/거래량의 범위를 점검한다.
    어떻게(HOW): 규칙을 위반하면 (False, 사유)를 반환한다.
    """
    import re
    date = r.get("date")
    spid = r.get("spid")
    if not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date or ""):
        return False, "bad_date"
    try:
        spid_int = int(spid)
        if spid_int <= 0:
            return False, "bad_spid"
    except Exception:
        return False, "bad_spid"

    def nonneg(x):
        return x is None or (isinstance(x, int) and x >= 0)

    if not (nonneg(r.get("avg_price")) and nonneg(r.get("max_price")) and nonneg(r.get("min_price"))):
        return False, "bad_price"
    tc = r.get("trade_count")
    if not (tc is None or (isinstance(tc, int) and tc >= 0)):
        return False, "bad_trade_count"
    maxp, minp = r.get("max_price"), r.get("min_price")
    if isinstance(maxp, int) and isinstance(minp, int) and maxp < minp:
        return False, "max_lt_min"
    return True, None


def upsert_daily_trade(conn: sqlite3.Connection, rows: Iterable[Dict[str, Any]]) -> int:
    """daily_trade UPSERT

    왜(WHY): 일자-선수 기준으로 중복 저장을 피하고 최신 값으로 반영해야 한다.
    무엇(WHAT): (date, spid) PK에 대해 멱등 UPSERT 수행.
    어떻게(HOW): 입력을 검증 후 executemany로 배치 처리하고, 커밋은 1회 수행한다.
    """
    logger = setup_logger()
    cur = conn.cursor()
    valid_params: list[tuple] = []
    skipped = 0
    for r in rows:
        ok, reason = _validate_trade_row(r)
        if not ok:
            skipped += 1
            logger.warning("event=skip_invalid_row table=daily_trade reason=%s spid=%s date=%s", reason, r.get("spid"), r.get("date"))
            continue
        valid_params.append((
            r.get("date"), r.get("spid"), r.get("player_name"), r.get("avg_price"), r.get("max_price"),
            r.get("min_price"), r.get("trade_count"), r.get("max_enhance_level"), r.get("source") or "web",
        ))
    if not valid_params:
        logger.info("event=upsert_trade count=0 skipped=%d", skipped)
        return 0
    cur.executemany(
        """
        INSERT OR REPLACE INTO daily_trade
        (date, spid, player_name, avg_price, max_price, min_price, trade_count, max_enhance_level, source)
        VALUES(?,?,?,?,?,?,?,?,?)
        """,
        valid_params,
    )
    conn.commit()
    logger.info("event=upsert_trade count=%d skipped=%d", len(valid_params), skipped)
    return len(valid_params)


def upsert_daily_top_players(conn: sqlite3.Connection, rows: Iterable[Dict[str, Any]]) -> int:
    """daily_top_players UPSERT

    왜(WHY): 일자-선수 기준으로 TopN 기록 중복 없이 반영한다.
    무엇(WHAT): (date, spid) PK 기준 INSERT OR REPLACE. spid가 없는 행은 스킵한다.
    어떻게(HOW): 간단한 유효성 검사 후 executemany로 배치 처리한다.
    """
    import re
    logger = setup_logger()
    cur = conn.cursor()
    params: list[tuple] = []
    skipped = 0
    for r in rows:
        date = r.get("date")
        spid = r.get("spid")
        if spid is None or not isinstance(spid, int):
            skipped += 1
            logger.warning("event=skip_invalid_row table=daily_top_players reason=bad_spid spid=%s date=%s", spid, date)
            continue
        if not isinstance(date, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date or ""):
            skipped += 1
            logger.warning("event=skip_invalid_row table=daily_top_players reason=bad_date spid=%s date=%s", spid, date)
            continue
        params.append((date, spid, r.get("rank"), r.get("pick_rate")))
    if not params:
        logger.info("event=upsert_topn count=0 skipped=%d", skipped)
        return 0
    cur.executemany(
        """
        INSERT OR REPLACE INTO daily_top_players
        (date, spid, rank, pick_rate)
        VALUES(?,?,?,?)
        """,
        params,
    )
    conn.commit()
    logger.info("event=upsert_topn count=%d skipped=%d", len(params), skipped)
    return len(params)


def append_csv(filename: Path, rows: Iterable[Dict[str, Any]], fieldnames: List[str]) -> int:
    """CSV에 행 추가(단순 append)

    왜(WHY): 가벼운 외부 분석/공유용으로 CSV 포맷이 유용하다.
    어떻게(HOW): 파일 존재 여부에 따라 헤더를 쓰고, 이후 행을 추가한다. 멱등성이 중요하면
    호출 측에서 visited_log 등으로 제어한다.
    """
    filename.parent.mkdir(parents=True, exist_ok=True)
    exists = filename.exists()
    count = 0
    with filename.open("a", encoding="utf-8", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=fieldnames)
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fieldnames})
            count += 1
    setup_logger().info("event=append_csv path=%s count=%d", filename, count)
    return count


__all__ = [
    "connect",
    "init_schema",
    "is_visited",
    "mark_visited",
    "upsert_daily_trade",
    "upsert_daily_top_players",
    "append_csv",
    "DB_PATH_DEFAULT",
]
