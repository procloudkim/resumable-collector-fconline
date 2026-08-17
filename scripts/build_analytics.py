from __future__ import annotations

"""
analytics(Gold) 계층 빌더

의도(WHY)
- 산출물이 흩어진 소스(DB/CSV)를 표준 경로(analytics/*)로 변환/집계하고
  manifest를 생성하여 EDA/대시보드 소비를 일원화한다.

동작(HOW)
- YouTube: data/processed/comments_with_sentiment.csv → analytics/youtube/comments.{parquet|csv}
- Game(best_price): project/db/best_price_new.db:best_price_daily → analytics/game/best_price_daily.{parquet|csv}
- Game(top_daily_record): project2/out/topdailyrecord_all_*.csv → analytics/game/top_daily_record.{parquet|csv}
- daily_rankers는 제외(요청 반영).
"""

import json
import os
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ANALYTICS = ROOT / "analytics"
YT_SRC = ROOT / "data" / "processed" / "comments_with_sentiment.csv"
BESTPRICE_DB = ROOT / "project" / "db" / "best_price_new.db"
TOPDAILY_DIR = ROOT / "project2" / "out"


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _write_df(
    df: pd.DataFrame,
    base_path: Path,
    preferred: str = "parquet",
    also_csv: bool = False,
) -> Tuple[str, Path, List[str], List[Path]]:
    """DataFrame 저장 유틸

    - 기본: parquet 우선 저장, 실패 시 csv로 대체
    - 옵션: also_csv=True이면 parquet 저장 성공하더라도 csv를 함께 생성하여 완전 폴백을 보장

    Returns:
        (primary_format, primary_path, all_formats, all_paths)
    """
    formats: List[str] = []
    paths: List[Path] = []
    primary_fmt = None
    primary_path = None

    # 1) parquet 시도
    parquet_path = base_path.with_suffix(".parquet")
    if preferred == "parquet":
        try:
            df.to_parquet(parquet_path, index=False)
            primary_fmt = "parquet"
            primary_path = parquet_path
            formats.append("parquet")
            paths.append(parquet_path)
        except Exception:
            # pyarrow 미설치 등으로 parquet 저장 실패
            primary_fmt = None
            primary_path = None

    # 2) csv 저장 (parquet 실패 시 대체, 또는 also_csv=True로 동시 생성)
    csv_needed = (primary_fmt is None) or also_csv
    csv_path = base_path.with_suffix(".csv")
    if csv_needed:
        df.to_csv(csv_path, index=False, encoding="utf-8")
        formats.append("csv")
        paths.append(csv_path)
        if primary_fmt is None:
            primary_fmt = "csv"
            primary_path = csv_path

    assert primary_fmt is not None and primary_path is not None
    return primary_fmt, primary_path, formats, paths


def build_youtube(also_csv: bool = False) -> Dict:
    print(f"[GIVEN] youtube source={YT_SRC}")
    if not YT_SRC.exists():
        raise FileNotFoundError(f"YouTube 원본이 없습니다: {YT_SRC}")
    df = pd.read_csv(YT_SRC)
    out_dir = ANALYTICS / "youtube"
    _ensure_dir(out_dir)
    fmt, outp, fmts, outs = _write_df(df, out_dir / "comments", also_csv=also_csv)
    print(f"[THEN] youtube rows={len(df)} fmt={fmt} out={outp}")
    return {
        "name": "youtube/comments",
        "path": str(outp.relative_to(ROOT).as_posix()),
        "format": fmt,
        "formats": fmts,
        "rows": int(len(df)),
        "columns": list(df.columns),
        "source": [str(YT_SRC.relative_to(ROOT).as_posix())],
        "version": datetime.now().strftime("%Y%m%d%H%M%S"),
    }


def build_best_price(also_csv: bool = False) -> Dict:
    print(f"[GIVEN] best_price source_db={BESTPRICE_DB}")
    if not BESTPRICE_DB.exists():
        raise FileNotFoundError(f"best_price DB가 없습니다: {BESTPRICE_DB}")
    import sqlite3

    con = sqlite3.connect(str(BESTPRICE_DB))
    try:
        df = pd.read_sql_query("SELECT * FROM best_price_daily", con)
    finally:
        con.close()
    out_dir = ANALYTICS / "game"
    _ensure_dir(out_dir)
    fmt, outp, fmts, outs = _write_df(df, out_dir / "best_price_daily", also_csv=also_csv)
    print(f"[THEN] best_price rows={len(df)} fmt={fmt} out={outp}")
    return {
        "name": "game/best_price_daily",
        "path": str(outp.relative_to(ROOT).as_posix()),
        "format": fmt,
        "formats": fmts,
        "rows": int(len(df)),
        "columns": list(df.columns),
        "source": [str(BESTPRICE_DB.relative_to(ROOT).as_posix()), "table=best_price_daily"],
        "version": datetime.now().strftime("%Y%m%d%H%M%S"),
    }


def build_top_daily_record(also_csv: bool = False) -> Dict:
    files = sorted(glob(str(TOPDAILY_DIR / "topdailyrecord_*.csv")))
    if not files:
        raise FileNotFoundError(f"topdailyrecord CSV가 없습니다: {TOPDAILY_DIR}")
    print(f"[GIVEN] top_daily_record sources={len(files)} first={Path(files[0]).name}")
    dfs = [pd.read_csv(f) for f in files]
    df = pd.concat(dfs, ignore_index=True)
    out_dir = ANALYTICS / "game"
    _ensure_dir(out_dir)
    fmt, outp, fmts, outs = _write_df(df, out_dir / "top_daily_record", also_csv=also_csv)
    print(f"[THEN] top_daily_record rows={len(df)} fmt={fmt} out={outp}")
    return {
        "name": "game/top_daily_record",
        "path": str(outp.relative_to(ROOT).as_posix()),
        "format": fmt,
        "formats": fmts,
        "rows": int(len(df)),
        "columns": list(df.columns),
        "source": [str(Path(f).relative_to(ROOT).as_posix()) for f in files],
        "version": datetime.now().strftime("%Y%m%d%H%M%S"),
    }


def write_manifest(entries: List[Dict]) -> None:
    _ensure_dir(ANALYTICS)
    manifest = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "datasets": entries,
        "note": "daily_rankers는 제외됨",
    }
    (ANALYTICS / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"[THEN] manifest=analytics/manifest.json datasets={len(entries)}")


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Build analytics (Gold) layer")
    ap.add_argument("--also-csv", action="store_true", help="parquet 저장에 더해 csv도 동시 저장 (완전 폴백 보장)")
    args = ap.parse_args()

    print("[GIVEN] targets=youtube, game(best_price, top_daily_record)")
    entries = []
    # 순차 빌드(의존성 없음)
    entries.append(build_youtube(also_csv=args.also_csv))
    entries.append(build_best_price(also_csv=args.also_csv))
    entries.append(build_top_daily_record(also_csv=args.also_csv))
    write_manifest(entries)
    print("[SUMMARY] build OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
