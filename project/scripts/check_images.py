from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser(description="Check image/logo path completeness in DB and filesystem existence")
    ap.add_argument("--db", type=Path, default=Path("project/db/best_price_new.db"))
    ap.add_argument("--root", type=Path, default=Path("."), help="Repo root for resolving relative paths")
    ap.add_argument("--emit-missing-spids", type=Path, default=None, help="Optional path to write missing player image SPIDs list")
    ns = ap.parse_args()

    conn = sqlite3.connect(ns.db)
    cur = conn.cursor()

    def q1(sql: str) -> int:
        cur.execute(sql)
        return int(cur.fetchone()[0])

    out: dict[str, object] = {}
    out["db_path"] = str(ns.db)
    out["rows_total"] = q1("SELECT COUNT(*) FROM best_price_daily")
    out["spids_distinct"] = q1("SELECT COUNT(DISTINCT spid) FROM best_price_daily")

    def analyze_col(col: str) -> dict[str, int]:
        d: dict[str, int] = {}
        cur.execute(f"SELECT COUNT(*) FROM best_price_daily WHERE {col} IS NULL OR {col}='' ")
        d["missing_rows"] = int(cur.fetchone()[0])
        cur.execute(f"SELECT COUNT(DISTINCT spid) FROM best_price_daily WHERE {col} IS NULL OR {col}='' ")
        d["missing_spids"] = int(cur.fetchone()[0])
        cur.execute(f"SELECT DISTINCT {col} FROM best_price_daily WHERE {col} IS NOT NULL AND {col}<>'' ")
        paths = [r[0] for r in cur.fetchall()]
        d["unique_paths"] = len(paths)
        existing = 0
        for p in paths:
            try:
                pth = Path(p)
                if not pth.is_absolute():
                    pth = ns.root / pth
                if pth.exists() and pth.stat().st_size > 0:
                    existing += 1
            except Exception:
                pass
        d["existing_files"] = existing
        d["missing_files"] = d["unique_paths"] - d["existing_files"]
        return d

    cols = [
        "player_image_path",
        "nation_logo_path",
        "league_logo_path",
        "team_logo_path",
    ]
    for c in cols:
        out[c] = analyze_col(c)

    # Optional write of missing player image SPIDs
    if ns.emit_missing_spids:
        cur.execute("SELECT DISTINCT spid FROM best_price_daily WHERE player_image_path IS NULL OR player_image_path='' ORDER BY spid")
        spids = [str(r[0]) for r in cur.fetchall()]
        ns.emit_missing_spids.parent.mkdir(parents=True, exist_ok=True)
        ns.emit_missing_spids.write_text("\n".join(spids), encoding="utf-8")
        out["spids_missing_images_written"] = str(ns.emit_missing_spids)
        out["spids_missing_images_count"] = len(spids)

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

