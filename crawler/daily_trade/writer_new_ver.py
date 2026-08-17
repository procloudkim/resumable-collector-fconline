from __future__ import annotations

"""
New-version wrapper for storage (DB/CSV) utilities.

Safe place to add schema-adjusted writes or new quality gates later.
"""

from .writer import (
    DB_PATH_DEFAULT,
    connect,
    init_schema,
    is_visited,
    mark_visited,
    upsert_daily_trade,
    upsert_daily_top_players,
    append_csv,
)

__all__ = [
    "DB_PATH_DEFAULT",
    "connect",
    "init_schema",
    "is_visited",
    "mark_visited",
    "upsert_daily_trade",
    "upsert_daily_top_players",
    "append_csv",
]

