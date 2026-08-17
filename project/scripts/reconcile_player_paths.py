from __future__ import annotations

import argparse
import shutil
import sqlite3
from pathlib import Path


PRIORITY = [
    ("base", "players/base/{spid}.png"),
    ("action", "players/action/{spid}.png"),
    ("base_24", "players/base_24/{spid}.png"),
    ("action_24", "players/action_24/{spid}.png"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Choose best available player image variant and update DB paths. Optionally migrate legacy flat files to base variant.")
    ap.add_argument("--db", type=Path, default=Path("project/db/best_price_new.db"))
    ap.add_argument("--images-root", type=Path, default=Path("data/images"))
    ap.add_argument("--migrate-legacy", action="store_true", help="Copy legacy data/images/players/{spid}.png to players/base/{spid}.png if base missing")
    ns = ap.parse_args()

    root = ns.images_root
    legacy_dir = root / "players"
    base_dir = root / "players" / "base"
    base_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(ns.db)
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT spid FROM best_price_daily")
    spids = [str(r[0]) for r in cur.fetchall()]

    updated = 0
    migrated = 0
    chosen_missing = 0

    for spid in spids:
        chosen_path: str | None = None
        # ensure migrate from legacy flat dir if requested
        leg = legacy_dir / f"{spid}.png"
        base = base_dir / f"{spid}.png"
        if ns.migrate_legacy and leg.exists() and leg.stat().st_size > 0 and not base.exists():
            try:
                shutil.copy2(leg, base)
                migrated += 1
            except Exception:
                pass

        # select best existing variant
        for _, rel in PRIORITY:
            relp = rel.format(spid=spid)
            p = root / relp
            if p.exists() and p.stat().st_size > 0:
                chosen_path = str(p.as_posix())
                break
        # fallback: legacy flat file
        if chosen_path is None and leg.exists() and leg.stat().st_size > 0:
            chosen_path = str(leg.as_posix())
        if chosen_path is None:
            chosen_missing += 1
            continue

        # update DB only when empty or different
        cur.execute(
            "UPDATE best_price_daily SET player_image_path = ? WHERE (player_image_path IS NULL OR player_image_path='' OR player_image_path<>?) AND spid = ?",
            (chosen_path, chosen_path, int(spid)),
        )
        updated += cur.rowcount

    conn.commit()
    conn.close()
    print(f"[DONE] reconciled spids={len(spids)} updated_rows={updated} migrated_flat={migrated} still_missing={chosen_missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

