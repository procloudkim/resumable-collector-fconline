from __future__ import annotations

"""
Reconcile logo image paths in DB to existing local files with variant fallback.

Goal: If a stored league/team/nation logo path does not exist, try alternative
      variants (light↔dark, small↔large) and update DB to an existing file.

Usage (PowerShell):
  python project/scripts/reconcile_logo_paths.py \\
    --db project/db/best_price_new.db \\
    --images-root data/images \\
    --dry-run  # to preview only
"""

import argparse
import sqlite3
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


def ensure_columns(cur: sqlite3.Cursor) -> None:
    for col in ("nation_logo_path", "league_logo_path", "team_logo_path"):
        existing = {row[1] for row in cur.execute("PRAGMA table_info(best_price_daily)")}
        if col not in existing:
            cur.execute(f"ALTER TABLE best_price_daily ADD COLUMN {col} TEXT")


def choose_existing(candidates: Iterable[Path]) -> Optional[Path]:
    for p in candidates:
        try:
            if p.exists() and p.stat().st_size > 0:
                return p
        except Exception:
            # Ignore inaccessible paths
            pass
    return None


def league_candidates(root: Path, code: str) -> List[Path]:
    cU, cL = code.upper(), code.lower()
    rels = [
        Path("logos/league/dark") / f"{cL}.png",
        Path("logos/league/dark") / f"{cU}.png",
        Path("logos/league/light") / f"{cL}.png",
        Path("logos/league/light") / f"{cU}.png",
    ]
    return [root / r for r in rels]


def team_candidates(root: Path, code: str) -> List[Path]:
    cU, cL = code.upper(), code.lower()
    rels = [
        Path("logos/team/dark/small") / f"{cU}.png",
        Path("logos/team/dark/small") / f"{cL}.png",
        Path("logos/team/light/small") / f"{cU}.png",
        Path("logos/team/light/small") / f"{cL}.png",
        Path("logos/team/dark/large") / f"{cU}.png",
        Path("logos/team/dark/large") / f"{cL}.png",
        Path("logos/team/light/large") / f"{cU}.png",
        Path("logos/team/light/large") / f"{cL}.png",
    ]
    return [root / r for r in rels]


def nation_candidates(root: Path, code: str) -> List[Path]:
    cU, cL = code.upper(), code.lower()
    rels = [
        Path("logos/nation/small") / f"{cU}.png",
        Path("logos/nation/small") / f"{cL}.png",
    ]
    return [root / r for r in rels]


def reconcile_paths(conn: sqlite3.Connection, images_root: Path, dry_run: bool = False) -> Tuple[int, int, int]:
    cur = conn.cursor()
    ensure_columns(cur)
    conn.commit()

    updated = 0
    examined = 0
    skipped = 0

    # Process per code to avoid per-row filesystem checks
    for col, fn in (
        ("nation", nation_candidates),
        ("league", league_candidates),
        ("team", team_candidates),
    ):
        code_col = f"{col}_code"
        path_col = f"{col}_logo_path"
        rows = cur.execute(
            f"SELECT DISTINCT {code_col}, COALESCE({path_col}, '') FROM best_price_daily "
            f"WHERE {code_col} IS NOT NULL AND {code_col}<>''"
        ).fetchall()
        for code, current in rows:
            examined += 1
            code = str(code)
            cand = fn(images_root, code)
            chosen = choose_existing(cand)
            if not chosen:
                skipped += 1
                continue
            new_path = str(chosen.as_posix())
            if current == new_path and current:
                skipped += 1
                continue
            if dry_run:
                updated += 1
                continue
            cur.execute(
                f"UPDATE best_price_daily SET {path_col} = ? WHERE {code_col} = ?",
                (new_path, code),
            )
            updated += cur.rowcount
            conn.commit()

    return examined, updated, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description="Reconcile logo paths in DB with local files (variant fallback)")
    ap.add_argument("--db", type=Path, default=Path("project/db/best_price_new.db"))
    ap.add_argument("--images-root", type=Path, default=Path("data/images"))
    ap.add_argument("--dry-run", action="store_true")
    ns = ap.parse_args()

    if not ns.db.exists():
        print(f"[ERR] DB not found: {ns.db}")
        return 2
    conn = sqlite3.connect(ns.db)
    try:
        examined, updated, skipped = reconcile_paths(conn, ns.images_root, ns.dry_run)
        mode = "DRY-RUN" if ns.dry_run else "APPLIED"
        print(f"[{mode}] examined={examined} updated_rows={updated} skipped={skipped}")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

