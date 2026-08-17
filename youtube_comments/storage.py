from __future__ import annotations

import csv
import os
import sqlite3
from typing import Iterable, List, Optional

from .fetcher import Comment


def ensure_parent_dir(path: str) -> None:
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def save_csv(comments: Iterable[Comment], path: str) -> None:
    ensure_parent_dir(path)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
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
        )
        for c in comments:
            w.writerow(
                [
                    c.video_id,
                    c.video_title,
                    c.comment_id,
                    c.author or "",
                    c.text.replace("\r", " ").replace("\n", " "),
                    c.like_count,
                    c.published_at or "",
                    c.updated_at or "",
                    1 if c.is_reply else 0,
                    c.parent_id or "",
                ]
            )


def init_db(db_path: str) -> None:
    ensure_parent_dir(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS comments (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              video_id TEXT NOT NULL,
              video_title TEXT,
              comment_id TEXT NOT NULL UNIQUE,
              author TEXT,
              text TEXT,
              like_count INTEGER,
              published_at TEXT,
              updated_at TEXT,
              is_reply INTEGER DEFAULT 0,
              parent_id TEXT,
              created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Best-effort migration for older schema
        cols = {row[1] for row in conn.execute("PRAGMA table_info(comments)").fetchall()}
        if "is_reply" not in cols:
            conn.execute("ALTER TABLE comments ADD COLUMN is_reply INTEGER DEFAULT 0")
        if "parent_id" not in cols:
            conn.execute("ALTER TABLE comments ADD COLUMN parent_id TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_video ON comments(video_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_comments_parent ON comments(parent_id)")
        conn.commit()


def upsert_comments(db_path: str, comments: Iterable[Comment]) -> int:
    ensure_parent_dir(db_path)
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.executemany(
            """
            INSERT OR IGNORE INTO comments
            (video_id, video_title, comment_id, author, text, like_count, published_at, updated_at, is_reply, parent_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    c.video_id,
                    c.video_title,
                    c.comment_id,
                    c.author or "",
                    c.text,
                    int(c.like_count),
                    c.published_at or "",
                    c.updated_at or "",
                    1 if c.is_reply else 0,
                    c.parent_id or "",
                )
                for c in comments
            ],
        )
        conn.commit()
        return cur.rowcount or 0


def delete_by_video(db_path: str, video_id: str) -> int:
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM comments WHERE video_id = ?", (video_id,))
        conn.commit()
        return cur.rowcount or 0
