from __future__ import annotations

"""
Apply Korean labels for nation/league/team codes into DB using a JSON mapping.

Mapping file format (UTF-8 JSON): config/logo_labels_ko.json
{
  "nation": { "18": "대한민국", "34": "스페인" },
  "league": { "L350": "프리미어리그" },
  "team":   { "L95": "레알 마드리드" }
}

If the file does not exist, this script can create a sample from current DB
codes with empty labels when called with --init-sample.

Usage:
  python project/scripts/apply_logo_labels.py --db project/db/best_price_new.db --init-sample
  # Edit config/logo_labels_ko.json, then
  python project/scripts/apply_logo_labels.py --db project/db/best_price_new.db
"""

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Dict


def ensure_columns(cur: sqlite3.Cursor) -> None:
    existing = {row[1] for row in cur.execute("PRAGMA table_info(best_price_daily)")}
    for col in ("nation_label_ko", "league_label_ko", "team_label_ko"):
        if col not in existing:
            cur.execute(f"ALTER TABLE best_price_daily ADD COLUMN {col} TEXT")


def dump_sample(conn: sqlite3.Connection, out_path: Path) -> None:
    cur = conn.cursor()
    sample = {
        "nation": sorted(
            {str(r[0]) for r in cur.execute(
                "SELECT DISTINCT nation_code FROM best_price_daily WHERE nation_code IS NOT NULL AND nation_code<>''"
            ).fetchall() if r and r[0] is not None}
        ),
        "league": sorted(
            {str(r[0]) for r in cur.execute(
                "SELECT DISTINCT league_code FROM best_price_daily WHERE league_code IS NOT NULL AND league_code<>''"
            ).fetchall() if r and r[0] is not None}
        ),
        "team": sorted(
            {str(r[0]) for r in cur.execute(
                "SELECT DISTINCT team_code FROM best_price_daily WHERE team_code IS NOT NULL AND team_code<>''"
            ).fetchall() if r and r[0] is not None}
        ),
    }
    # Initialize with empty labels
    data = {k: {code: "" for code in sample[k]} for k in ("nation", "league", "team")}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[INIT] Wrote sample mapping with current codes -> {out_path}")


def apply_labels(conn: sqlite3.Connection, mapping: Dict[str, Dict[str, str]]) -> int:
    cur = conn.cursor()
    ensure_columns(cur)
    conn.commit()
    updated = 0
    for grp, col_code, col_label in (
        ("nation", "nation_code", "nation_label_ko"),
        ("league", "league_code", "league_label_ko"),
        ("team", "team_code", "team_label_ko"),
    ):
        mp = mapping.get(grp, {}) or {}
        items = [(v.strip(), k) for k, v in mp.items() if isinstance(v, str) and v.strip()]
        if not items:
            continue
        cur.executemany(
            f"UPDATE best_price_daily SET {col_label} = ? WHERE {col_code} = ?",
            items,
        )
        updated += cur.rowcount
    conn.commit()
    return updated


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply Korean labels for nation/league/team codes into DB")
    ap.add_argument("--db", type=Path, default=Path("project/db/best_price_new.db"))
    ap.add_argument("--config", type=Path, default=Path("config/logo_labels_ko.json"))
    ap.add_argument("--init-sample", action="store_true", help="Create a sample config populated with current codes")
    ns = ap.parse_args()

    if not ns.db.exists():
        print(f"[ERR] DB not found: {ns.db}")
        return 2
    conn = sqlite3.connect(ns.db)
    try:
        if ns.init_sample and not ns.config.exists():
            dump_sample(conn, ns.config)
            return 0
        if not ns.config.exists():
            print(f"[ERR] Config not found: {ns.config}. Run with --init-sample to create one.")
            return 2
        mapping = json.loads(ns.config.read_text(encoding="utf-8"))
        updated = apply_labels(conn, mapping)
        print(f"[APPLIED] label updates rows={updated}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

