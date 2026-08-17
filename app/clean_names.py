"""
best_price_daily.clean.csv 선수 이름 정규화 + 공백 점검/정리 유틸리티

의도(WHY)
- 혼합 표기(예: "115 ST 23 8 크리스티아누 호날두 4,480억")에서 선수 이름만 추출해 표준화한다.
- 이름 외 컬럼의 선행/후행 공백 존재 여부를 점검하고, 사용자가 원하면 일괄 제거한다.

동작(HOW)
- 입력 CSV의 컬럼명이 영문(player_name) 또는 한글(선수 이름)인 경우 모두 지원.
- 이름 정규화 규칙:
  - 토큰 단위(공백 분리)로 검사하여 숫자/포지션코드/통화표현 토큰 제거
  - 한글 또는 영문 알파벳이 포함된 토큰만 유지
  - 남은 토큰을 공백으로 결합 후 strip()
- 공백 점검:
  - 문자열 타입 컬럼에 대해 value != value.strip() 건수 집계
  - 요약 리포트를 출력하고, --strip-whitespace 지정 시 실제로 strip 적용

입출력
- 입력: analytics/clean/best_price_daily.clean.csv (기본)
- 출력: 기본은 별도 파일 analytics/clean/best_price_daily.clean.names.csv
         --overwrite 지정 시 입력 파일을 덮어씀
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd


# 포지션 코드(일반적인 축구 포지션 약어)
POSITION_CODES = {
    "GK","CB","LB","RB","LWB","RWB","CDM","CM","CAM","LM","RM","LW","RW","CF","ST","SUB","RES"
}


def _looks_currency_token(tok: str) -> bool:
    s = tok.strip()
    if not s:
        return False
    # 숫자/콤마/억/만/원/₩ 조합이면 통화 표현으로 간주
    return bool(re.fullmatch(r"[0-9,]+(억|만|원)?", s)) or ("₩" in s)


def _keep_token(tok: str) -> bool:
    s = tok.strip()
    if not s:
        return False
    # 숫자만/포지션코드/시즌숫자(예: 23)/단일 숫자 제거
    if s.isdigit():
        return False
    if s.upper() in POSITION_CODES:
        return False
    if _looks_currency_token(s):
        return False
    # 한글 또는 알파벳 포함 토큰만 유지
    return bool(re.search(r"[A-Za-z\uAC00-\uD7A3]", s))


def normalize_player_name(raw: str) -> str:
    toks = re.split(r"\s+", str(raw or "").strip())
    kept: List[str] = [t for t in toks if _keep_token(t)]
    return " ".join(kept).strip()


@dataclass
class CleanReport:
    whitespace_issues: Dict[str, int]
    total_rows: int


def clean_best_price_names(
    df: pd.DataFrame,
    *,
    strip_whitespace: bool = False,
) -> Tuple[pd.DataFrame, CleanReport]:
    df = df.copy()
    # 이름 컬럼 탐지(영문/한글)
    name_col = None
    for c in df.columns:
        if c == "player_name" or c.strip() in ("선수 이름", "선수의이름"):
            name_col = c
            break
    if name_col is None:
        # best effort: player_name로 가정 생성
        name_col = "player_name"
        if name_col not in df.columns:
            df[name_col] = ""

    df[name_col] = df[name_col].apply(normalize_player_name)

    # 공백 점검(이름 제외)
    issues: Dict[str, int] = {}
    for c in df.columns:
        if c == name_col:
            continue
        if pd.api.types.is_object_dtype(df[c]):
            s = df[c].astype(str)
            cnt = int(((s != s.str.strip()).sum()))
            if cnt > 0:
                issues[c] = cnt
            if strip_whitespace and cnt > 0:
                df[c] = s.str.strip()

    rep = CleanReport(whitespace_issues=issues, total_rows=len(df))
    return df, rep


def _parse_args():
    import argparse

    ap = argparse.ArgumentParser(description="best_price_daily 이름 정규화 + 공백 점검/정리")
    ap.add_argument("--in", dest="inp", default="analytics/clean/best_price_daily.clean.csv", help="입력 CSV 경로")
    ap.add_argument("--out", dest="outp", default=None, help="출력 CSV 경로(기본: *.names.csv)")
    ap.add_argument("--overwrite", action="store_true", help="원본 파일을 덮어씁니다")
    ap.add_argument("--strip-whitespace", action="store_true", help="이름 외 문자열 컬럼 선행/후행 공백 제거")
    return ap.parse_args()


def main() -> int:
    args = _parse_args()
    inp = Path(args.inp)
    outp: Optional[Path]
    if args.overwrite:
        outp = inp
    else:
        outp = Path(args.outp) if args.outp else inp.with_name(inp.stem + ".names.csv")

    df = pd.read_csv(inp)
    cleaned, rep = clean_best_price_names(df, strip_whitespace=bool(args.strip_whitespace))
    outp.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(outp, index=False, encoding="utf-8")

    # 리포트 출력
    print(f"[GIVEN] rows={rep.total_rows} input={inp}")
    if rep.whitespace_issues:
        pairs = ", ".join([f"{k}:{v}" for k, v in rep.whitespace_issues.items()])
        print(f"[WHEN] whitespace_issues (trim-needed) => {pairs}")
        if not args.strip_whitespace:
            print("[THEN] 공백 제거는 수행하지 않았습니다. --strip-whitespace 옵션으로 적용 가능합니다.")
    else:
        print("[WHEN] whitespace_issues => none")
    print(f"[THEN] wrote output={outp}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
