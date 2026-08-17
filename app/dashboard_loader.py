"""
대시보드 로더: 로컬 파일 시스템에서 최신 CSV 경로를 탐색하고 로드

의도(WHY)
- 분석 환경에서 경로 가변성(ko/strip/clean 원본 등)을 흡수하고, 우선순위로 첫 가용 파일을 선택

함수
- find_first(paths): 존재하는 첫 경로 반환(None 가능)
- load_comments/load_topdaily/load_bestprice/load_events: DataFrame과 사용 경로를 반환
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional, Tuple

import pandas as pd


def find_first(paths: Iterable[Path]) -> Optional[Path]:
    for p in paths:
        if p and p.exists():
            return p
    return None


def load_comments() -> Tuple[pd.DataFrame, Optional[Path]]:
    cands = [
        Path("analytics/clean/comments.clean.csv"),
        Path("analytics/youtube/comments.csv"),
    ]
    p = find_first(cands)
    return (pd.read_csv(p) if p else pd.DataFrame()), p


def load_topdaily() -> Tuple[pd.DataFrame, Optional[Path]]:
    cands = [
        Path("analytics/new_analytics/top_daily_record.clean.ko.strip.fixed.csv"),
        Path("analytics/clean/top_daily_record.clean.ko.strip.csv"),
        Path("analytics/clean/top_daily_record.clean.ko.csv"),
        Path("analytics/clean/top_daily_record.clean.csv"),
        Path("analytics/game/top_daily_record.csv"),
    ]
    p = find_first(cands)
    return (pd.read_csv(p) if p else pd.DataFrame()), p


def load_bestprice() -> Tuple[pd.DataFrame, Optional[Path]]:
    cands = [
        Path("analytics/new_analytics/best_price_daily.clean.names.strip.fixed.csv"),
        Path("analytics/clean/best_price_daily.clean.names.strip.csv"),
        Path("analytics/clean/best_price_daily.clean.names.csv"),
        Path("analytics/clean/best_price_daily.clean.ko.csv"),
        Path("analytics/clean/best_price_daily.clean.csv"),
        Path("analytics/game/best_price_daily.csv"),
    ]
    p = find_first(cands)
    return (pd.read_csv(p) if p else pd.DataFrame()), p


def load_events() -> Tuple[pd.DataFrame, Optional[Path]]:
    cands = [Path("config/events.csv")]
    p = find_first(cands)
    return (pd.read_csv(p) if p else pd.DataFrame()), p


__all__ = [
    "load_comments",
    "load_topdaily",
    "load_bestprice",
    "load_events",
    "load_player_map",
    "find_first",
]


def load_player_map() -> Tuple[pd.DataFrame, Optional[Path]]:
    """
    선수명↔spid 매핑 로드 시도. 인코딩이 다른 경우를 대비해 utf-8→cp949 순으로 시도.
    예상 스키마: [spid, name] 또는 [spid, name_kor]
    """
    cands = [Path("config/player_map.csv"), Path("config/player_overrides.csv")]
    p = find_first(cands)
    if not p:
        return pd.DataFrame(), None
    for enc in ("utf-8", "cp949", "euc-kr"):
        try:
            df = pd.read_csv(p, encoding=enc)
            break
        except Exception:
            df = pd.DataFrame()
            continue
    if df.empty:
        return pd.DataFrame(), p
    # 표준화
    cols = {c.lower(): c for c in df.columns}
    name_col = cols.get("name") or cols.get("name_kor") or list(df.columns)[1]
    out = df.rename(columns={name_col: "name", cols.get("spid", "spid"): "spid"})
    return out[["spid", "name"]], p
