"""
cache.py — SQLite 스키마/캐시 헬퍼
"""
from __future__ import annotations
from pathlib import Path
import sqlite3

DB_PATH = Path("data") / "data.db"

def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_schema() -> None:
    with connect() as conn:
        cur = conn.cursor()
        # 닉네임→OUID
        cur.execute("""
        CREATE TABLE IF NOT EXISTS ouid_map(
          nickname TEXT PRIMARY KEY,
          ouid     TEXT NOT NULL
        )""")
        # 처리한 match_id
        cur.execute("""
        CREATE TABLE IF NOT EXISTS seen_match(
          match_id TEXT PRIMARY KEY
        )""")
        # 임의 메타
        cur.execute("""
        CREATE TABLE IF NOT EXISTS meta(
          k TEXT PRIMARY KEY,
          v TEXT NOT NULL
        )""")
        # 선수 캐시(선택)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS players(
          spid INTEGER PRIMARY KEY,
          name_kor TEXT,
          name_eng TEXT,
          image_path TEXT,
          updated_at TEXT
        )""")
        # 랭커 스탯 스냅샷
        cur.execute("""
        CREATE TABLE IF NOT EXISTS ranker_stats(
          spid INTEGER,
          po INTEGER,
          create_date TEXT,
          dribble INTEGER,
          dribble_try INTEGER,
          dribble_success INTEGER,
          pass_try INTEGER,
          pass_success INTEGER,
          block INTEGER,
          tackle INTEGER,
          assist INTEGER,
          goal INTEGER,
          match_count INTEGER,
          PRIMARY KEY(spid, po, create_date)
        )""")
        # 인덱스(조회 빈도 높은 컬럼)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ranker_stats_date ON ranker_stats(create_date)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ranker_stats_spid ON ranker_stats(spid)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_ranker_stats_po   ON ranker_stats(po)")
        conn.commit()

def get_ouid(nickname: str) -> str | None:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT ouid FROM ouid_map WHERE nickname=?", (nickname,))
        row = cur.fetchone()
        return row[0] if row else None

def set_ouid(nickname: str, ouid: str) -> None:
    with connect() as conn:
        conn.execute("INSERT OR REPLACE INTO ouid_map(nickname, ouid) VALUES(?,?)", (nickname, ouid))
        conn.commit()

def is_seen(match_id: str) -> bool:
    with connect() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM seen_match WHERE match_id=?", (match_id,))
        return cur.fetchone() is not None

def mark_seen(match_id: str) -> None:
    with connect() as conn:
        conn.execute("INSERT OR IGNORE INTO seen_match(match_id) VALUES(?)", (match_id,))
        conn.commit()
