from __future__ import annotations

"""
Offline crawler for check/*.html snapshots (new pipeline).

Parses card layout to extract key fields, downloads player images,
and writes to CSV and a separate SQLite DB with "new" in filenames.

CSV: data/processed/daily_trade_new.csv
DB:  data/new-data.db (table: daily_trade_new)
Images: data/images_new/
"""

import argparse
import csv
import re
import sqlite3
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup  # type: ignore


OUT_CSV = Path("data/processed/daily_trade_new.csv")
OUT_DB = Path("data/new-data.db")
IMG_DIR = Path("data/images_new")


def ensure_dirs(csv_path: Path, db_path: Path, img_dir: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    img_dir.mkdir(parents=True, exist_ok=True)


def _price_to_int(text: Optional[str]) -> Optional[int]:
    if text is None:
        return None
    s = (text or "").strip()
    if not s:
        return None
    s2 = s.replace(",", "")
    if re.fullmatch(r"\d+", s2):
        try:
            return int(s2)
        except Exception:
            return None
    # 억/만 support (best-effort)
    total = 0
    matched = False
    m = re.search(r"(\d+)\s*억", s)
    if m:
        total += int(m.group(1)) * 100_000_000
        matched = True
    m = re.search(r"(\d+)\s*만", s)
    if m:
        total += int(m.group(1)) * 10_000
        matched = True
    if matched:
        return total
    # Fallback: digits only
    digits = re.sub(r"[^0-9]", "", s2)
    return int(digits) if digits else None


def _slide_spid(slide) -> Optional[int]:
    a = slide.select_one("a.outlink[href*='PlayerInfo?spid=']")
    if not a:
        return None
    try:
        href = a.get("href") or ""
        q = parse_qs(urlparse(href).query)
        spid = q.get("spid", [None])[0]
        return int(spid) if spid else None
    except Exception:
        return None


def _slide_name(slide) -> Optional[str]:
    n = slide.select_one(".playerCardInfoBottom .nameWrap .name span, .player_wrap[title]")
    if n and n.get_text(" "):
        return n.get_text(" ").strip()
    if n and n.has_attr("title"):
        return str(n["title"]).strip()
    hidden = slide.select_one("a.outlink > span.hidden")
    if hidden and hidden.get_text(" "):
        return hidden.get_text(" ").strip()
    return None


def _slide_price(slide) -> Optional[int]:
    p = slide.select_one(".price_wrap .price")
    if p is not None:
        for attr in ("alt", "title"):
            v = p.get(attr)
            if v:
                v2 = re.sub(r"[^0-9]", "", str(v))
                if v2:
                    try:
                        return int(v2)
                    except Exception:
                        pass
        txt = p.get_text(" ")
        v = _price_to_int(txt)
        if v is not None:
            return v
    return _price_to_int(slide.get_text(" "))


def _slide_level(slide) -> Optional[int]:
    a = slide.select_one(".buildUp a")
    if a and re.search(r"\d+", a.get_text(" ")):
        try:
            return int(re.search(r"\d+", a.get_text(" ")).group(0))
        except Exception:
            return None
    m = re.search(r"\+(\d+)", slide.get_text(" "))
    return int(m.group(1)) if m else None


def _slide_image(slide) -> Optional[str]:
    img = slide.select_one("img[src*='players']") or slide.select_one("img[src*='playersAction']")
    if img and img.has_attr("src"):
        return str(img["src"]).strip()
    return None


def download_image(url: str, out_dir: Path) -> Optional[Path]:
    try:
        parsed = urlparse(url)
        name = Path(parsed.path).name
        if not name:
            return None
        out = out_dir / name
        if out.exists() and out.stat().st_size > 0:
            return out
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and r.content:
            out.write_bytes(r.content)
            return out
    except Exception:
        return None
    return None


def parse_file(
    path: Path,
    *,
    date: str,
    download_images: bool = True,
    img_dir: Path = IMG_DIR,
    limit_slides: Optional[int] = None,
) -> List[dict]:
    html = path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(html, "html.parser")
    slides = soup.select("#divBestTradeArea_price .swiper-slide")
    if limit_slides is not None:
        try:
            n = int(limit_slides)
            if n >= 0:
                slides = slides[:n]
        except Exception:
            pass
    rows: List[dict] = []
    for slide in slides:
        spid = _slide_spid(slide)
        if not spid:
            continue
        name = _slide_name(slide)
        price = _slide_price(slide)
        level = _slide_level(slide)
        img_url = _slide_image(slide)
        img_path: Optional[str] = None
        if download_images and img_url:
            p = download_image(img_url, img_dir)
            if p:
                img_path = str(p)
        rows.append({
            "date": date,
            "spid": spid,
            "player_name": name,
            "avg_price": price,
            "max_price": price,
            "min_price": None,
            "trade_count": None,
            "max_enhance_level": level,
            "image_url": img_url,
            "image_path": img_path,
            "source_file": path.name,
        })
    return rows


def write_csv(path: Path, rows: Iterable[dict]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "date", "spid", "player_name",
        "avg_price", "max_price", "min_price", "trade_count", "max_enhance_level",
        "image_url", "image_path", "source_file",
    ]
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if not exists:
            w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in fields})
    return len(rows)


def init_db(db: Path) -> sqlite3.Connection:
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS daily_trade_new(
            date TEXT NOT NULL,
            spid INTEGER NOT NULL,
            player_name TEXT,
            avg_price BIGINT,
            max_price BIGINT,
            min_price BIGINT,
            trade_count INTEGER,
            max_enhance_level INTEGER,
            image_url TEXT,
            image_path TEXT,
            source_file TEXT,
            PRIMARY KEY (date, spid)
        )
        """
    )
    conn.commit()
    return conn


def upsert_db(conn: sqlite3.Connection, rows: Iterable[dict]) -> int:
    rows = list(rows)
    if not rows:
        return 0
    cur = conn.cursor()
    params = [(
        r.get("date"), r.get("spid"), r.get("player_name"), r.get("avg_price"), r.get("max_price"),
        r.get("min_price"), r.get("trade_count"), r.get("max_enhance_level"), r.get("image_url"), r.get("image_path"), r.get("source_file"),
    ) for r in rows]
    cur.executemany(
        """
        INSERT OR REPLACE INTO daily_trade_new
        (date, spid, player_name, avg_price, max_price, min_price, trade_count, max_enhance_level, image_url, image_path, source_file)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        params,
    )
    conn.commit()
    return len(rows)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Offline crawl docs/check/*.html to new CSV/DB")
    ap.add_argument("--check-dir", default="docs/check")
    ap.add_argument("--download-images", action="store_true")
    ap.add_argument("--csv", default=str(OUT_CSV))
    ap.add_argument("--db", default=str(OUT_DB))
    ap.add_argument("--test", action="store_true", help="Use test outputs under data/test and disable images unless explicitly enabled")
    ap.add_argument("--limit-files", type=int, default=None, help="Process only first N html files")
    ap.add_argument("--limit-slides", type=int, default=None, help="Parse only first N slides per file")
    ap.add_argument("--dry-run", action="store_true", help="Do not write CSV/DB/images; print sample rows")
    ap.add_argument("--print-sample", type=int, default=3, help="Print first N rows from first processed file")
    args = ap.parse_args(argv)

    # Resolve output paths and image dir
    if args.test:
        csv_path = Path("data/test/processed/daily_trade_new_test.csv")
        db_path = Path("data/test/new-data-test.db")
        img_dir = Path("data/test/images_new")
    else:
        csv_path = Path(args.csv)
        db_path = Path(args.db)
        img_dir = IMG_DIR

    # Ensure directories unless dry-run
    if not args.dry_run:
        ensure_dirs(csv_path, db_path, img_dir)
        conn = init_db(db_path)
    else:
        conn = None  # type: ignore

    check_dir = Path(args.check_dir)
    files = sorted(check_dir.glob("check-*.html"))
    if args.limit_files is not None:
        try:
            k = int(args.limit_files)
            if k >= 0:
                files = files[:k]
        except Exception:
            pass
    total_rows = 0
    printed_sample = False
    for f in files:
        m = re.search(r"(20\d{2})", f.name)
        year = m.group(1) if m else "2020"
        date = f"{year}-01-01"
        rows = parse_file(
            f,
            date=date,
            download_images=(args.download_images and not args.dry_run),
            img_dir=img_dir,
            limit_slides=args.limit_slides,
        )
        if args.dry_run:
            upserted = 0
            written = 0
        else:
            upserted = upsert_db(conn, rows)
            written = write_csv(csv_path, rows)
        print(f"[OK] {f.name}: parsed={len(rows)} upserted={upserted} csv_appended={written}")
        if args.print_sample and not printed_sample and rows:
            n = max(0, int(args.print_sample))
            print("[SAMPLE] first rows:")
            for r in rows[:n]:
                print(json.dumps(r, ensure_ascii=False))
            printed_sample = True
        total_rows += len(rows)

    print(f"[DONE] offline crawl rows={total_rows} csv={csv_path} db={db_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
