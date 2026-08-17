from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def main() -> int:
    db_path = Path("project/db/best_price_new.db")
    if not db_path.exists():
        print(json.dumps({"error": f"missing db: {db_path}"}, ensure_ascii=False))
        return 1
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    def q_one(sql: str) -> int:
        row = cur.execute(sql).fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    res: dict[str, int] = {}
    res["rows_total"] = q_one("SELECT COUNT(*) FROM best_price_daily")
    for col in [
        "player_image_path",
        "nation_logo_path",
        "league_logo_path",
        "team_logo_path",
    ]:
        res[f"{col}_filled"] = q_one(
            f"SELECT COUNT(*) FROM best_price_daily WHERE {col} IS NOT NULL AND {col}<>''"
        )
    # player_name coverage
    res["player_name_filled"] = q_one(
        "SELECT COUNT(*) FROM best_price_daily WHERE player_name IS NOT NULL AND player_name<>''"
    )
    res["spids_distinct"] = q_one("SELECT COUNT(DISTINCT spid) FROM best_price_daily")
    # How many rows have at least one of the paths missing
    res["paths_missing_rows"] = q_one(
        "SELECT COUNT(*) FROM best_price_daily WHERE "
        "(player_image_path IS NULL OR player_image_path='') "
        "OR (nation_logo_path IS NULL OR nation_logo_path='') "
        "OR (league_logo_path IS NULL OR league_logo_path='') "
        "OR (team_logo_path IS NULL OR team_logo_path='')"
    )

    # Existence check for distinct paths
    def count_exists(col: str) -> tuple[int, int]:
        paths = [
            r[0]
            for r in cur.execute(
                f"SELECT DISTINCT {col} FROM best_price_daily WHERE {col} IS NOT NULL AND {col}<>''"
            ).fetchall()
            if r and r[0]
        ]
        total = len(paths)
        ok = sum(1 for p in paths if Path(p).exists() and Path(p).stat().st_size > 0)
        return ok, total

    exists: dict[str, dict[str, int]] = {}
    for col in [
        "player_image_path",
        "nation_logo_path",
        "league_logo_path",
        "team_logo_path",
    ]:
        ok, total = count_exists(col)
        exists[col] = {"existing": ok, "distinct": total}

    out = {**res, "exists": exists}
    print(json.dumps(out, ensure_ascii=False))
    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
