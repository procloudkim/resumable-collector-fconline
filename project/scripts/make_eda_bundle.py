from __future__ import annotations

"""
EDA 번들을 생성하는 유틸리티

WHY: 분석/공유를 위해 월별 CSV를 하나로 병합하고, 요약 리포트/진행상태/DB(옵션)를
     타임스탬프 폴더 및 ZIP으로 묶는다.
HOW: CSV 스트리밍 병합(헤더 1회), 핵심 지표 산출, 샘플 생성, 선택적으로 DB/quality report 포함.

사용 예(프로젝트 폴더에서):
  python scripts/make_eda_bundle.py \
    --csv-dir data/csv \
    --db-path db/best_price_new.db \
    --bundle-dir eda_bundles \
    --include-db --include-quality \
    --sample 1000 \
    --from 2020-05-20 --to 2025-09-11
"""

import argparse
import csv
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


REQUIRED_COLUMNS = [
    "date",
    "spid",
    "player_name",
    "season_code",
    "position",
    "ovr",
    "pay",
    "enhance",
    "price_value",
    "price_text",
    "nation_code",
    "league_code",
    "team_code",
    "nation_logo_path",
    "league_logo_path",
    "team_logo_path",
    "player_image_path",
]


def in_range(d: str, d_from: Optional[str], d_to: Optional[str]) -> bool:
    if d_from and d < d_from:
        return False
    if d_to and d > d_to:
        return False
    return True


def make_bundle(
    csv_dir: Path,
    db_path: Optional[Path],
    bundle_root: Path,
    *,
    d_from: Optional[str],
    d_to: Optional[str],
    include_db: bool,
    include_quality: bool,
    sample_n: int,
) -> Path:
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    bundle_dir = bundle_root / f"EDA_{stamp}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    merged = bundle_dir / "bestprice_all.csv"
    sample_path = bundle_dir / "bestprice_sample.csv"
    summary_md = bundle_dir / "SUMMARY.md"
    summary_json = bundle_dir / "summary.json"

    files = sorted(csv_dir.glob("bestprice_*.csv"))
    if not files:
        raise SystemExit(f"No files under {csv_dir}")

    # 지표 누적
    total_rows = 0
    date_min = None
    date_max = None
    per_date: Dict[str, int] = {}
    spids: set[int] = set()
    missing = {k: 0 for k in ["player_name", "season_code", "position", "ovr", "pay", "enhance", "price_value"]}

    # 병합 + 샘플
    sample_buf: List[Dict[str, str]] = []
    header_written = False
    with merged.open("w", encoding="utf-8", newline="") as fw:
        w = csv.DictWriter(fw, fieldnames=REQUIRED_COLUMNS)
        w.writeheader()
        header_written = True
        for f in files:
            with f.open("r", encoding="utf-8", newline="") as fr:
                r = csv.DictReader(fr)
                # 컬럼 차이가 있어도 REQUIRED_COLUMNS 기준으로 정렬하여 출력
                for row in r:
                    d = row.get("date") or ""
                    if not d or not in_range(d, d_from, d_to):
                        continue
                    # 누적 지표
                    total_rows += 1
                    date_min = d if date_min is None or d < date_min else date_min
                    date_max = d if date_max is None or d > date_max else date_max
                    per_date[d] = per_date.get(d, 0) + 1
                    try:
                        v_spid = row.get("spid")
                        if v_spid:
                            spids.add(int(v_spid))
                    except Exception:
                        pass
                    # 결측
                    for k in list(missing.keys()):
                        v = row.get(k)
                        if v is None or (str(v).strip() == ""):
                            missing[k] += 1
                    # 샘플
                    if len(sample_buf) < sample_n:
                        sample_buf.append({k: row.get(k) for k in REQUIRED_COLUMNS})
                    # 출력
                    w.writerow({k: row.get(k) for k in REQUIRED_COLUMNS})

    # 샘플 저장
    if sample_buf:
        with sample_path.open("w", encoding="utf-8", newline="") as fs:
            ws = csv.DictWriter(fs, fieldnames=REQUIRED_COLUMNS)
            ws.writeheader()
            for r in sample_buf:
                ws.writerow(r)

    # 요약 저장
    # per-date 통계
    counts = list(per_date.values())
    if counts:
        min_cards = min(counts)
        avg_cards = round(sum(counts) / len(counts), 2)
        max_cards = max(counts)
    else:
        min_cards = avg_cards = max_cards = 0

    summary = {
        "period": {"min": date_min, "max": date_max},
        "rows": total_rows,
        "distinct_spids": len(spids),
        "cards_per_day": {"min": min_cards, "avg": avg_cards, "max": max_cards},
        "missing": missing,
        "filters": {"from": d_from, "to": d_to},
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        f"# EDA Summary ({stamp})",
        f"- Period: {date_min} ~ {date_max}",
        f"- Rows: {total_rows}",
        f"- Distinct SPIDs: {len(spids)}",
        f"- Cards per day (min/avg/max): {min_cards}/{avg_cards}/{max_cards}",
        "- Missing core fields:",
        *[f"  - {k}: {v}" for k, v in missing.items()],
    ]
    summary_md.write_text("\n".join(lines), encoding="utf-8")

    # 품질 리포트 동봉(있으면)
    if include_quality:
        q = Path("data/reports/quality_report.md")
        if q.exists():
            shutil.copy2(q, bundle_dir / q.name)

    # progress.json 동봉(재현성 기록)
    p = Path("state/progress.json")
    if p.exists():
        shutil.copy2(p, bundle_dir / p.name)

    # DB 동봉(옵션)
    if include_db and db_path and db_path.exists():
        shutil.copy2(db_path, bundle_dir / db_path.name)

    # 압축(zip)
    zip_path = bundle_root / f"{bundle_dir.name}.zip"
    shutil.make_archive(str(zip_path.with_suffix("")), "zip", root_dir=bundle_root, base_dir=bundle_dir.name)
    return bundle_dir


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build an EDA bundle (merged CSV + summary + optional DB/quality report)")
    ap.add_argument("--csv-dir", type=Path, default=Path("data/csv"))
    ap.add_argument("--db-path", type=Path, default=Path("db/best_price_new.db"))
    ap.add_argument("--bundle-dir", type=Path, default=Path("eda_bundles"))
    ap.add_argument("--from", dest="date_from", type=str, default=None)
    ap.add_argument("--to", dest="date_to", type=str, default=None)
    ap.add_argument("--include-db", action="store_true")
    ap.add_argument("--include-quality", action="store_true")
    ap.add_argument("--sample", type=int, default=1000)
    ns = ap.parse_args(argv)

    dest = make_bundle(
        csv_dir=ns.csv_dir,
        db_path=ns.db_path,
        bundle_root=ns.bundle_dir,
        d_from=ns.date_from,
        d_to=ns.date_to,
        include_db=ns.include_db,
        include_quality=ns.include_quality,
        sample_n=ns.sample,
    )
    print(f"[SAVED] bundle at {dest}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

