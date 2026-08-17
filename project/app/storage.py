from __future__ import annotations

"""
저장(Storage): CSV(원자적) 라이터 + SQLite 로더(UPSERT/PK/인덱스)

WHY: 실행 중에는 단일 writer로 CSV만 기록하고, 종료 후 SQLite로 적재해 중복 없는 통합을 보장한다.
HOW: 월별 CSV를 임시 파일에 쓴 뒤 rename(원자적). SQLite는 stg→본 UPSERT 규칙으로 덮어쓰기 전략을 분리한다.
"""

import csv
import sqlite3
from pathlib import Path
from typing import Iterable, List, Dict

from .utils import ensure_dir, atomic_write

REQUIRED_COLUMNS = [
    "date",
    "spid",
    "player_name",
    "season_code",
    "position",
    "ovr",
    "pay",
    "enhance",
    "price_value",
    "price_text",
    "nation_code",
    "league_code",
    "team_code",
    "nation_logo_path",
    "league_logo_path",
    "team_logo_path",
    "player_image_path",
]

# 각 컬럼의 SQLite 타입 정의(스키마 마이그레이션에 사용)
COLUMN_TYPES: Dict[str, str] = {
    "date": "TEXT",
    "spid": "INTEGER",
    "player_name": "TEXT",
    "season_code": "TEXT",
    "position": "TEXT",
    "ovr": "INTEGER",
    "pay": "INTEGER",
    "enhance": "INTEGER",
    "price_value": "BIGINT",
    "price_text": "TEXT",
    "nation_code": "TEXT",
    "league_code": "TEXT",
    "team_code": "TEXT",
    "nation_logo_path": "TEXT",
    "league_logo_path": "TEXT",
    "team_logo_path": "TEXT",
    "player_image_path": "TEXT",
}


def monthly_csv_path(csv_dir: Path, date_str: str) -> Path:
    ym = date_str[:7]
    return csv_dir / f"bestprice_{ym}.csv"


def append_rows_atomic(csv_path: Path, rows: List[Dict]) -> int:
    """월별 CSV에 행을 원자적으로 추가

    WHY: 부분 쓰기 방지. 기존 파일을 읽어 + 신규 행을 합쳐 임시 파일에 쓴 뒤 교체한다.
    HOW: 파일이 크면 비효율적이나 1회성 실행 안정성을 우선한다.
    """
    ensure_dir(csv_path.parent)
    existing: List[Dict] = []
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8", newline="") as f:
            r = csv.DictReader(f)
            existing = list(r)
    merged = existing + rows
    header = REQUIRED_COLUMNS
    # 임시 버퍼에 작성 후 원자 교체
    from io import StringIO

    buf = StringIO()
    w = csv.DictWriter(buf, fieldnames=header)
    w.writeheader()
    for row in merged:
        w.writerow({k: row.get(k) for k in header})
    atomic_write(csv_path, buf.getvalue().encode("utf-8"))
    return len(rows)


def load_into_sqlite(db_path: Path, csv_files: Iterable[Path]) -> int:
    """CSV를 staging에 로드 후 본 테이블로 UPSERT

    PK: (date, spid, season_code, enhance)
    가격: 신규값 우선, 텍스트/메타는 COALESCE.
    """
    ensure_dir(db_path.parent)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS best_price_daily(
          date TEXT NOT NULL,
          spid INTEGER NOT NULL,
          player_name TEXT,
          season_code TEXT,
          position TEXT,
          ovr INTEGER,
          pay INTEGER,
          enhance INTEGER,
          price_value BIGINT,
          price_text TEXT,
          nation_code TEXT,
          league_code TEXT,
          team_code TEXT,
          nation_logo_path TEXT,
          league_logo_path TEXT,
          team_logo_path TEXT,
          player_image_path TEXT,
          PRIMARY KEY(date, spid, season_code, enhance)
        )
        """
    )
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS best_price_daily_stg(
          date TEXT,
          spid INTEGER,
          player_name TEXT,
          season_code TEXT,
          position TEXT,
          ovr INTEGER,
          pay INTEGER,
          enhance INTEGER,
          price_value BIGINT,
          price_text TEXT,
          nation_code TEXT,
          league_code TEXT,
          team_code TEXT,
          nation_logo_path TEXT,
          league_logo_path TEXT,
          team_logo_path TEXT,
          player_image_path TEXT
        )
        """
    )
    # 기존 DB가 오래된 스키마일 수 있으므로, 누락 컬럼을 자동 추가(안전 마이그레이션)
    def _ensure_columns(table: str) -> None:
        existing = {row[1] for row in cur.execute(f"PRAGMA table_info({table})")}
        missing = [c for c in REQUIRED_COLUMNS if c not in existing]
        for col in missing:
            coltype = COLUMN_TYPES.get(col, "TEXT")
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
    _ensure_columns("best_price_daily")
    _ensure_columns("best_price_daily_stg")
    # 인덱스
    cur.execute("CREATE INDEX IF NOT EXISTS idx_bpd_date ON best_price_daily(date)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_bpd_spid ON best_price_daily(spid)")
    cur.execute(
        "CREATE INDEX IF NOT EXISTS idx_bpd_season_enh ON best_price_daily(season_code, enhance)"
    )
    cur.execute("CREATE INDEX IF NOT EXISTS idx_bpd_price ON best_price_daily(price_value)")
    conn.commit()

    cur.execute("DELETE FROM best_price_daily_stg")
    conn.commit()

    # CSV 적재
    import csv as _csv

    total = 0
    for path in csv_files:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8", newline="") as f:
            r = _csv.DictReader(f)
            rows = [tuple(row.get(k) for k in REQUIRED_COLUMNS) for row in r]
        if not rows:
            continue
        cur.executemany(
            f"""
            INSERT INTO best_price_daily_stg ({','.join(REQUIRED_COLUMNS)})
            VALUES({','.join(['?']*len(REQUIRED_COLUMNS))})
            """,
            rows,
        )
        total += len(rows)
    conn.commit()

    # UPSERT 규칙: price_* 신규 우선, 나머지 COALESCE
    cur.execute(
        """
        INSERT INTO best_price_daily(
          date, spid, player_name, season_code, position,
          ovr, pay, enhance, price_value, price_text,
          nation_code, league_code, team_code,
          nation_logo_path, league_logo_path, team_logo_path,
          player_image_path
        )
        SELECT s.date, s.spid,
               COALESCE(s.player_name, t.player_name),
               s.season_code,
               COALESCE(s.position, t.position),
               COALESCE(s.ovr, t.ovr),
               COALESCE(s.pay, t.pay),
               COALESCE(s.enhance, t.enhance),
               COALESCE(s.price_value, t.price_value),
               COALESCE(s.price_text, t.price_text),
               COALESCE(s.nation_code, t.nation_code),
               COALESCE(s.league_code, t.league_code),
               COALESCE(s.team_code, t.team_code),
               COALESCE(s.nation_logo_path, t.nation_logo_path),
               COALESCE(s.league_logo_path, t.league_logo_path),
               COALESCE(s.team_logo_path, t.team_logo_path),
               COALESCE(s.player_image_path, t.player_image_path)
        FROM best_price_daily_stg s
        LEFT JOIN best_price_daily t
          ON t.date=s.date AND t.spid=s.spid AND t.season_code=s.season_code AND t.enhance=s.enhance
        ON CONFLICT(date, spid, season_code, enhance) DO UPDATE SET
          player_name=excluded.player_name,
          position=excluded.position,
          ovr=excluded.ovr,
          pay=excluded.pay,
          enhance=excluded.enhance,
          price_value=excluded.price_value,
          price_text=excluded.price_text,
          nation_code=excluded.nation_code,
          league_code=excluded.league_code,
          team_code=excluded.team_code,
          nation_logo_path=excluded.nation_logo_path,
          league_logo_path=excluded.league_logo_path,
          team_logo_path=excluded.team_logo_path,
          player_image_path=excluded.player_image_path
        """
    )
    conn.commit()
    conn.close()
    return total
