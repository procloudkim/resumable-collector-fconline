"""
sync_players.py — SPID↔이름↔이미지 매핑 생성 및 동기화

WHY: 분석/대시보드에서 선수 라벨과 썸네일을 안정적으로 쓰기 위해
     이름 사전(spid.json)과 로컬 이미지 캐시를 한 번에 맞춰둔다.

WHAT:
  - 입력 SPID 집합(JSON/CSV/TXT) → 이름 매핑 로드 → 이미지 존재/다운로드
  - 결과를 CSV(data/processed/players.csv)로 덤프
  - 옵션으로 SQLite(data/data.db) players 테이블에 UPSERT

HOW:
  - names: app.services.meta.load_spid_map()
  - images: app.services.images.ensure_player_image()
  - DB: CREATE TABLE IF NOT EXISTS players(...), INSERT OR REPLACE
"""
from __future__ import annotations
import argparse
import csv
import json
import sqlite3
from pathlib import Path
from typing import Iterable, List, Set

from app.core.utils import IMAGES, PROC, log
from app.services.meta import load_spid_map
from app.services.images import ensure_player_image


def _load_spids(path: Path) -> List[int]:
    suf = path.suffix.lower()
    if suf == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        # allow: [ {"id": 123, ...}, ... ] or [123, ...]
        if isinstance(data, list):
            out: List[int] = []
            for it in data:
                if isinstance(it, int):
                    out.append(int(it))
                elif isinstance(it, dict):
                    v = it.get("spid") or it.get("id")
                    if v is not None:
                        out.append(int(v))
            return out
        raise SystemExit("Unsupported JSON structure for --spids")
    elif suf == ".csv":
        out: List[int] = []
        with path.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            # auto-detect spid/id column
            cand = None
            for k in reader.fieldnames or []:
                kk = (k or "").strip().lower()
                if kk in ("spid", "id"):
                    cand = k
                    break
            for row in reader:
                v = row.get(cand) if cand else None
                if v and str(v).strip().isdigit():
                    out.append(int(v))
        return out
    else:
        # treat as TXT: one spid per line
        out: List[int] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            t = line.strip()
            if t.isdigit():
                out.append(int(t))
        return out


def _ensure_players_table(conn: sqlite3.Connection) -> None:
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
    cur.execute("CREATE INDEX IF NOT EXISTS idx_players_name ON players(name_kor, name_eng)")
    conn.commit()


def _upsert_players(conn: sqlite3.Connection, rows: List[dict]) -> int:
    if not rows:
        return 0
    cur = conn.cursor()
    params = [
        (r.get("spid"), r.get("name_kor"), r.get("name_eng"), r.get("image_path"))
        for r in rows
    ]
    cur.executemany(
        """
        INSERT INTO players(spid, name_kor, name_eng, image_path, updated_at)
        VALUES(?, ?, ?, ?, datetime('now'))
        ON CONFLICT(spid) DO UPDATE SET
          name_kor=excluded.name_kor,
          name_eng=excluded.name_eng,
          image_path=excluded.image_path,
          updated_at=datetime('now')
        """,
        params,
    )
    conn.commit()
    return len(rows)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spids", help="입력 SPID 목록(JSON/CSV/TXT). 미지정시 pairs.json 자동 탐색", default=None)
    ap.add_argument("--download", action="store_true", help="이미지 미존재 시 다운로드 수행")
    ap.add_argument("--ttl-days", type=int, default=365, help="이미지 TTL 일수(내보다 최신이면 스킵)")
    ap.add_argument("--out-csv", default=str(PROC / "players.csv"))
    ap.add_argument("--db", default=str(Path("data") / "data.db"))
    ap.add_argument("--no-db", action="store_true", help="DB upsert 생략")
    args = ap.parse_args()

    # Resolve input SPIDs
    spids: List[int]
    if args.spids:
        p = Path(args.spids)
        if not p.exists():
            raise SystemExit(f"SPIDs file not found: {p}")
        spids = _load_spids(p)
    else:
        # Fallback to pairs.json if present
        p = Path("pairs.json")
        if not p.exists():
            raise SystemExit("--spids 미지정이고 pairs.json이 없습니다. 입력 파일을 지정하세요.")
        spids = _load_spids(p)

    uniq: List[int] = sorted(set(int(s) for s in spids))
    log(f"입력 SPID 수: raw={len(spids)} uniq={len(uniq)}")

    # Load name dictionary
    name_map = load_spid_map()

    # Ensure images dir
    IMAGES.mkdir(parents=True, exist_ok=True)

    rows: List[dict] = []
    downloaded = skipped = missing = 0
    for sp in uniq:
        nm = name_map.get(int(sp)) or {}
        name_kor = nm.get("name_kor") or nm.get("name")
        name_eng = nm.get("name_eng") or nm.get("name_en")
        img_path = IMAGES / f"{int(sp)}.png"
        # Download if requested and missing
        if args.download and not img_path.exists():
            pth = ensure_player_image(int(sp), ttl_days=args.ttl_days)
            if pth:
                downloaded += 1
            else:
                missing += 1
        else:
            if img_path.exists():
                skipped += 1
            else:
                missing += 1
        rows.append({
            "spid": int(sp),
            "name_kor": name_kor,
            "name_eng": name_eng,
            "image_path": str(img_path) if img_path.exists() else None,
        })

    # Write CSV
    out_csv = Path(args.out_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=["spid", "name_kor", "name_eng", "image_path"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    log(f"CSV 저장: {out_csv} rows={len(rows)}")

    # Upsert DB
    if not args.no_db:
        conn = sqlite3.connect(Path(args.db))
        _ensure_players_table(conn)
        n = _upsert_players(conn, rows)
        log(f"DB upsert: players rows={n} db={args.db}")

    log(f"이미지 상태: downloaded={downloaded} skipped_existing={skipped} missing={missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

