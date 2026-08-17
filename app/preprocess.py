"""
분석 전처리(로컬 CSV 기반)

의도(WHY)
- analytics 계층에서 생성된 CSV 3종(youtube/comments, game/top_daily_record, game/best_price_daily)을
  분석 친화적 스키마와 타입으로 정돈(정규화)하여 clean CSV로 저장한다.

동작(HOW)
- 컬럼명 정규화: 소문자, 공백→언더스코어, 좌우공백 제거
- 날짜/시간 파싱: date, *_at 계열을 ISO8601 문자열로 정규화
- 타입 캐스팅: spid/rank/가격/지표를 수치형으로 변환(가능한 범위 내에서)
- 파생 필드(필요 최소): youtube/comments에 sentiment_label 보정

입출력
- 입력: analytics/youtube/comments.csv, analytics/game/top_daily_record.csv, analytics/game/best_price_daily.csv
- 출력(기본): analytics/clean/{comments.clean.csv, top_daily_record.clean.csv, best_price_daily.clean.csv}

제한/가정
- 원본 CSV 스키마는 기존 파이프라인 산출을 따른다. 존재하지 않는 컬럼은 best-effort로 건너뛴다.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [
        (c or "").strip().lower().replace(" ", "_") for c in df.columns
    ]
    return df


def _parse_datetime_col(df: pd.DataFrame, col: str) -> None:
    if col in df.columns:
        try:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%dT%H:%M:%S%z").str.replace("\+0000", "+00:00", regex=False)
        except Exception:
            # best-effort: coerce to string
            df[col] = df[col].astype(str)


def _parse_date_col(df: pd.DataFrame, col: str) -> None:
    if col in df.columns:
        try:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date.astype(str)
        except Exception:
            df[col] = df[col].astype(str)


def clean_comments(df: pd.DataFrame) -> pd.DataFrame:
    """YouTube 댓글 데이터 정리

    Args:
        df: 원본 DataFrame(analytics/youtube/comments.csv)
    Returns:
        정리된 DataFrame
    """
    df = _normalize_columns(df)
    # sentiment alias 보정
    if "sentiment_label" not in df.columns and "sentiment" in df.columns:
        df["sentiment_label"] = df["sentiment"]
    # 필수 최소 컬럼이 없으면 생성만 해둠
    for c in ["video_id", "comment_id", "text"]:
        if c not in df.columns:
            df[c] = ""
    # 날짜/시간 파싱
    for c in ["published_at", "updated_at"]:
        _parse_datetime_col(df, c)
    return df


def clean_top_daily_record(df: pd.DataFrame) -> pd.DataFrame:
    """출전 기록 데이터 정리(Top Daily Record)

    - date: YYYY-MM-DD
    - rank: int
    """
    df = _normalize_columns(df)
    _parse_date_col(df, "date")
    if "rank" in df.columns:
        try:
            df["rank"] = pd.to_numeric(df["rank"], errors="coerce").astype("Int64")
        except Exception:
            pass
    return df


def clean_best_price_daily(df: pd.DataFrame) -> pd.DataFrame:
    """베스트프라이스 일별 데이터 정리

    - date: YYYY-MM-DD
    - spid: int
    - price_value: int
    """
    df = _normalize_columns(df)
    _parse_date_col(df, "date")
    for c in ["spid", "price_value", "ovr", "pay", "enhance"]:
        if c in df.columns:
            try:
                df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
            except Exception:
                pass
    return df


def preprocess_all(
    *,
    comments_csv: Path = Path("analytics/youtube/comments.csv"),
    top_daily_record_csv: Path = Path("analytics/game/top_daily_record.csv"),
    best_price_daily_csv: Path = Path("analytics/game/best_price_daily.csv"),
    out_dir: Path = Path("analytics/clean"),
) -> Dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: Dict[str, Path] = {}

    # comments
    if comments_csv.exists():
        dfc = pd.read_csv(comments_csv)
        dfc = clean_comments(dfc)
        p = out_dir / "comments.clean.csv"
        dfc.to_csv(p, index=False, encoding="utf-8")
        outputs["youtube/comments"] = p

    # top_daily_record
    if top_daily_record_csv.exists():
        dft = pd.read_csv(top_daily_record_csv)
        dft = clean_top_daily_record(dft)
        p = out_dir / "top_daily_record.clean.csv"
        dft.to_csv(p, index=False, encoding="utf-8")
        outputs["game/top_daily_record"] = p

    # best_price_daily
    if best_price_daily_csv.exists():
        dfb = pd.read_csv(best_price_daily_csv)
        dfb = clean_best_price_daily(dfb)
        p = out_dir / "best_price_daily.clean.csv"
        dfb.to_csv(p, index=False, encoding="utf-8")
        outputs["game/best_price_daily"] = p

    return outputs


def _parse_args():
    import argparse

    ap = argparse.ArgumentParser(description="Analytics CSV 전처리")
    ap.add_argument("--out", default="analytics/clean", help="clean CSV 출력 디렉터리")
    return ap.parse_args()


def main() -> int:
    args = _parse_args()
    print("[GIVEN] inputs=analytics/youtube/comments.csv, analytics/game/top_daily_record.csv, analytics/game/best_price_daily.csv")
    outs = preprocess_all(out_dir=Path(args.out))
    for k, v in outs.items():
        print(f"[THEN] wrote {k} -> {v}")
    if not outs:
        print("[WARN] 처리된 항목이 없습니다. 입력 CSV 경로를 확인하세요.")
        return 1
    print("[SUMMARY] preprocess OK items=", len(outs))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

