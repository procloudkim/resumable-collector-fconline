"""
분석용 데이터 레지스트리(Registry)

의도(WHY)
- EDA/대시보드/스크립트가 원천 산출물 경로에 직접 의존하지 않고
  analytics(Gold) 계층의 "논리 이름"만으로 접근하도록 한다.

동작(HOW)
- analytics/manifest.json을 읽어 논리 이름→물리 경로를 해석한다.
- 포맷은 parquet 우선, 미지원 시 csv로 폴백한다.
- 최소 스키마 검증(필요 컬럼 포함 여부)을 유틸 함수로 제공한다.

한계/가정
- pyarrow/fastparquet 미설치 환경에서는 parquet 읽기가 불가하므로 csv로 생성/소비한다.
- manifest는 scripts/build_analytics.py로 갱신한다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


MANIFEST_PATH = Path("analytics/manifest.json")


@dataclass
class DatasetEntry:
    name: str
    path: str
    fmt: str
    rows: int
    columns: List[str]
    source: List[str]
    version: Optional[str] = None


def load_manifest(path: Path = MANIFEST_PATH) -> Dict[str, DatasetEntry]:
    if not path.exists():
        raise FileNotFoundError(f"manifest 파일이 없습니다: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    mapping: Dict[str, DatasetEntry] = {}
    for it in data.get("datasets", []):
        de = DatasetEntry(
            name=it["name"],
            path=it["path"],
            fmt=it["format"],
            rows=int(it.get("rows", 0) or 0),
            columns=list(it.get("columns", [])),
            source=list(it.get("source", [])),
            version=it.get("version"),
        )
        mapping[de.name] = de
    return mapping


def load_dataset(name: str, manifest_path: Path = MANIFEST_PATH) -> pd.DataFrame:
    """
    논리 이름으로 데이터프레임을 로드한다.

    Args:
        name: 논리 데이터셋 이름(예: 'youtube/comments', 'game/top_daily_record').
    Returns:
        pandas.DataFrame
    Raises:
        FileNotFoundError: manifest 또는 파일이 없을 때
        ValueError: 포맷 미지원
    """
    reg = load_manifest(manifest_path)
    if name not in reg:
        raise FileNotFoundError(f"manifest에 데이터셋이 없습니다: {name}")
    entry = reg[name]
    p = Path(entry.path)
    if not p.exists():
        raise FileNotFoundError(f"데이터 파일이 없습니다: {p}")
    fmt = entry.fmt.lower()
    if fmt == "parquet":
        try:
            return pd.read_parquet(p)
        except Exception:  # pyarrow 미설치 등
            # parquet가 안 읽히면 csv 재시도
            alt = p.with_suffix(".csv")
            if alt.exists():
                return pd.read_csv(alt)
            raise
    if fmt == "csv":
        return pd.read_csv(p)
    raise ValueError(f"미지원 포맷: {fmt}")


def require_columns(df: pd.DataFrame, cols: List[str], *, dataset_name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{dataset_name} 스키마 컬럼 누락: {missing}")


__all__ = [
    "load_manifest",
    "load_dataset",
    "require_columns",
    "DatasetEntry",
    "MANIFEST_PATH",
]

