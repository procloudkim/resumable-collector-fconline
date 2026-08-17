"""
best_price_daily.clean.csv 컬럼 한글화 유틸리티

의도(WHY)
- 기존 Clean CSV(영문 컬럼)를 한국어 컬럼명으로 변환한 파일을 별도로 생성하여
  가독성을 높이고, 기존 파이프라인과의 호환성도 유지한다(영문본은 그대로 보존).

동작(HOW)
- analytics/clean/best_price_daily.clean.csv 를 읽어 지정 매핑으로 컬럼명을 변경 후
  analytics/clean/best_price_daily.clean.ko.csv 로 저장한다(기본). 옵션으로 덮어쓰기 가능.

입력/출력
- 입력: analytics/clean/best_price_daily.clean.csv
- 출력(기본): analytics/clean/best_price_daily.clean.ko.csv

예외/주의
- 일부 컬럼이 존재하지 않아도 안전하게 진행(있는 컬럼만 변환).
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd


KOREAN_MAP: Dict[str, str] = {
    "date": "날짜",
    "spid": "선수 고유 ID",
    "player_name": "선수 이름",
    "season_code": "시즌 코드",
    "position": "포지션",
    "ovr": "오버롤",
    "pay": "급여",
    "enhance": "강화 단계",
    "price_value": "거래 가격",
    "price_text": "가격 텍스트",
    "nation_code": "국가 코드",
    "league_code": "리그 코드",
    "team_code": "팀 코드",
    "player_image_path": "선수 이미지 경로",
    "nation_logo_path": "국가 로고 이미지 경로",
    "league_logo_path": "리그 로고 이미지 경로",
    "team_logo_path": "팀 로고 이미지 경로",
}


def localize_best_price_daily(
    in_path: Path = Path("analytics/clean/best_price_daily.clean.csv"),
    out_path: Path | None = None,
    overwrite: bool = False,
) -> Path:
    if out_path is None:
        out_path = in_path.with_suffix("")
        out_path = out_path.with_name(out_path.name + ".ko.csv")

    if overwrite:
        out_path = in_path  # 제자리 덮어쓰기

    df = pd.read_csv(in_path)
    # 영문→한글 매핑(존재하는 컬럼만 적용)
    rename_map = {c: KOREAN_MAP.get(c, c) for c in df.columns}
    df = df.rename(columns=rename_map)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8")
    return out_path


def _parse_args():
    import argparse

    ap = argparse.ArgumentParser(description="best_price_daily.clean.csv 컬럼 한글화")
    ap.add_argument("--in", dest="inp", default="analytics/clean/best_price_daily.clean.csv", help="입력 CSV 경로")
    ap.add_argument("--out", dest="outp", default=None, help="출력 CSV 경로(기본: *.ko.csv)")
    ap.add_argument("--overwrite", action="store_true", help="원본 파일을 덮어씁니다(주의)")
    return ap.parse_args()


def main() -> int:
    args = _parse_args()
    inp = Path(args.inp)
    outp = None if args.outp is None else Path(args.outp)
    p = localize_best_price_daily(in_path=inp, out_path=outp, overwrite=bool(args.overwrite))
    print(f"[THEN] wrote localized CSV -> {p}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

