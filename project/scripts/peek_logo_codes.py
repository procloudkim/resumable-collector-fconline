from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, default=Path("project/db/best_price_new.db"))
    ap.add_argument("--limit", type=int, default=50)
    ns = ap.parse_args()

    conn = sqlite3.connect(ns.db)
    cur = conn.cursor()
    for col in ["nation_code", "league_code", "team_code"]:
        cur.execute(f"SELECT COUNT(DISTINCT {col}) FROM best_price_daily WHERE {col} IS NOT NULL AND {col}<>''")
        cnt = cur.fetchone()[0]
        print(f"{col}: distinct={cnt}")
        cur.execute(f"SELECT DISTINCT {col} FROM best_price_daily WHERE {col} IS NOT NULL AND {col}<>'' LIMIT {ns.limit}")
        rows = [r[0] for r in cur.fetchall()]
        print(f"  sample: {rows}")


if __name__ == "__main__":
    main()

