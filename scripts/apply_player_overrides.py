from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path
from typing import List


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply CSV overrides for player name and image/logo paths into best_price_daily")
    ap.add_argument("--db", type=Path, default=Path("project/db/best_price_new.db"))
    ap.add_argument("--csv", type=Path, required=True, help="CSV with columns: spid, name(optional), player_image_path(optional), nation_logo_path(optional), league_logo_path(optional), team_logo_path(optional)")
    ns = ap.parse_args()

    if not ns.db.exists():
        raise SystemExit(f"DB not found: {ns.db}")
    if not ns.csv.exists():
        raise SystemExit(f"CSV not found: {ns.csv}")

    with ns.csv.open("r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        cols = set([c.strip() for c in (r.fieldnames or [])])
        required = {"spid"}
        if not required.issubset(cols):
            raise SystemExit("CSV must include at least 'spid' column")
        updatable: List[str] = []
        for c in ("name", "player_image_path", "nation_logo_path", "league_logo_path", "team_logo_path"):
            if c in cols:
                updatable.append(c)
        if not updatable:
            raise SystemExit("CSV has no updatable columns. Include one of: name, player_image_path, nation_logo_path, league_logo_path, team_logo_path")

        con = sqlite3.connect(ns.db)
        cur = con.cursor()
        updated = 0
        rows = list(r)
        for row in rows:
            try:
                spid = int(str(row.get("spid", "")).strip())
            except Exception:
                continue
            params = []
            sets = []
            if "name" in updatable and row.get("name"):
                sets.append("player_name = ?")
                params.append(str(row["name"]))
            for c in ("player_image_path", "nation_logo_path", "league_logo_path", "team_logo_path"):
                v = row.get(c)
                if (c in updatable) and v and str(v).strip():
                    sets.append(f"{c} = ?")
                    params.append(str(v).strip())
            if not sets:
                continue
            params.append(spid)
            sql = f"UPDATE best_price_daily SET {', '.join(sets)} WHERE spid = ?"
            cur.execute(sql, params)
            updated += cur.rowcount
        con.commit()
        con.close()
        print(f"[APPLIED] rows updated: {updated}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

