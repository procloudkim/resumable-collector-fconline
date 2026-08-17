from __future__ import annotations

"""
Export a template CSV for player overrides.

Output: config/player_overrides.csv (UTF-8-SIG)
Columns: spid,name,player_image_path,nation_logo_path,league_logo_path,team_logo_path
"""

import csv
import sqlite3
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    db_path = root / "project" / "db" / "best_price_new.db"
    out_csv = root / "config" / "player_overrides.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    if not db_path.exists():
        print(f"[ERR] DB not found: {db_path}")
        return 2

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    cur.execute(
        "SELECT DISTINCT spid, COALESCE(player_name,'') FROM best_price_daily ORDER BY spid"
    )
    rows = cur.fetchall()
    con.close()

    with out_csv.open("w", encoding="utf-8-sig", newline="") as fo:
        w = csv.writer(fo)
        w.writerow([
            "spid",
            "name",
            "player_image_path",
            "nation_logo_path",
            "league_logo_path",
            "team_logo_path",
        ])
        for spid, name in rows:
            n = " ".join(str(name or "").split())  # collapse whitespace/newlines
            w.writerow([spid, n, "", "", "", ""])

    print(f"[OK] Wrote template -> {out_csv} (rows={len(rows)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
