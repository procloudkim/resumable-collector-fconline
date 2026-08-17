"""
backfill_images.py — SPID 목록으로 선수 이미지 로컬 캐시 채우기

WHY: 대시보드/분석에서 이미지 로딩을 빠르게 하고, 중복 요청을 줄이기 위함.
WHAT: TXT/CSV 파일 또는 DB(players) 기준으로 SPID 집합을 만들고, CDN에서 이미지를 받아
      data/images/{spid}.png 로 저장한다. TTL(일) 내 파일은 스킵한다.
HOW: 진행률/다운로드/스킵/실패 카운트를 100개 단위로 로그한다. --from-db-missing 옵션 지원.
"""
from __future__ import annotations
import argparse
import sqlite3
import time as _t
from pathlib import Path
from typing import List

import pandas as pd

from app.core.utils import log, IMAGES
from app.services.images import ensure_player_image


def spids_from_csv(path: Path, topk: int | None) -> List[int]:
    df = pd.read_csv(path)
    cols = [c for c in df.columns if c != "date"]
    sums = df[cols].sum().sort_values(ascending=False)
    return [int(x) for x in sums.index[: topk]] if topk else [int(x) for x in sums.index]


def spids_from_txt(path: Path) -> List[int]:
    out: List[int] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        t = line.strip()
        if t.isdigit():
            out.append(int(t))
    return out


def spids_from_db_missing(db_path: Path) -> List[int]:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS players(
          spid INTEGER PRIMARY KEY,
          name_kor TEXT,
          name_eng TEXT,
          image_path TEXT,
          updated_at TEXT
        )
        """
    )
    rows = cur.execute("SELECT spid FROM players WHERE image_path IS NULL OR image_path='' ").fetchall()
    conn.close()
    return [int(r[0]) for r in rows]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["csv", "txt"], help="입력 소스 형식(csv/txt)")
    ap.add_argument("--path", help="입력 파일 경로")
    ap.add_argument("--topk", type=int)
    ap.add_argument("--sleep", type=float, default=0.15)
    ap.add_argument("--ttl-days", type=int, default=365, help="파일 TTL 일수(내에 있으면 스킵)")
    ap.add_argument("--from-db-missing", action="store_true", help="DB players에서 image_path 비어있는 SPID만 처리")
    ap.add_argument("--db", default="data/data.db", help="SQLite DB 경로")
    args = ap.parse_args()

    # 대상 SPID 집합 구성
    if args.from_db_missing:
        spids = spids_from_db_missing(Path(args.db))
    else:
        if not args.source or not args.path:
            raise SystemExit("--from-db-missing 또는 --source/--path 중 하나는 반드시 지정해야 합니다.")
        p = Path(args.path)
        raw_spids = spids_from_csv(p, args.topk) if args.source == "csv" else spids_from_txt(p)
        spids = sorted(set(int(s) for s in raw_spids))

    total = len(spids)
    log(f"대상 spid={total}")

    downloaded = skipped = failed = 0
    for i, sp in enumerate(spids, start=1):
        out = IMAGES / f"{int(sp)}.png"
        # TTL 스킵 판단(있고 TTL 내면 스킵)
        if out.exists() and args.ttl_days is not None:
            age_days = (_t.time() - out.stat().st_mtime) / 86400.0
            if age_days <= args.ttl_days:
                skipped += 1
                if i % 100 == 0:
                    log(
                        f"progress: {i}/{total} downloaded={downloaded} skipped={skipped} failed={failed}"
                    )
                _t.sleep(max(0.0, args.sleep))
                continue
        pth = ensure_player_image(int(sp), ttl_days=args.ttl_days)
        if pth:
            downloaded += 1
        else:
            failed += 1
        if i % 100 == 0:
            log(f"progress: {i}/{total} downloaded={downloaded} skipped={skipped} failed={failed}")
        _t.sleep(max(0.0, args.sleep))

    log(f"이미지 백필 완료: 총={total} 다운로드={downloaded} 스킵={skipped} 실패={failed}")


if __name__ == "__main__":
    main()
