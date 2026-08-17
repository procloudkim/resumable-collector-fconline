from __future__ import annotations

import os
import sqlite3
from typing import Iterable, Optional, Tuple

import pandas as pd


REQUIRED_COLS = [
    "video_id",
    "video_title",
    "comment_id",
    "author",
    "text",
    "like_count",
    "published_at",
    "updated_at",
    "is_reply",
    "parent_id",
]


def _detect_table(conn: sqlite3.Connection) -> Optional[str]:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    names = [r[0] for r in cur.fetchall()]
    # Prefer common names
    for cand in ("comments", "comments_all", "main", "data"):
        if cand in names:
            return cand
    # Fallback: first table
    return names[0] if names else None


def load_comments(csv_path: Optional[str] = None, db_path: Optional[str] = None, table: Optional[str] = None) -> pd.DataFrame:
    if csv_path and os.path.isfile(csv_path):
        df = pd.read_csv(csv_path)
    elif db_path and os.path.isfile(db_path):
        conn = sqlite3.connect(db_path)
        try:
            tbl = table or _detect_table(conn)
            if not tbl:
                raise RuntimeError("No table found in SQLite DB")
            df = pd.read_sql_query(f"SELECT * FROM {tbl}", conn)
        finally:
            conn.close()
    else:
        raise FileNotFoundError("Provide existing csv_path or db_path")

    # Ensure required columns exist (tolerate missing updated_at/parent_id)
    if "published_at" not in df.columns and "created_at" in df.columns:
        df["published_at"] = df["created_at"]
    # parse timestamp
    if "published_at" in df.columns:
        df["published_at"] = pd.to_datetime(df["published_at"], errors="coerce", utc=True)
    return df


def save_csv(df: pd.DataFrame, out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df.to_csv(out_path, index=False)


def save_sqlite(df: pd.DataFrame, db_path: str, table: str = "comments_scored") -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        df.to_sql(table, conn, if_exists="replace", index=False)
        # Indexes to speed querying
        try:
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_comment_id ON {table}(comment_id)")
            conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_video_id ON {table}(video_id)")
            conn.commit()
        except sqlite3.DatabaseError:
            pass
    finally:
        conn.close()

