"""
best_price_daily.clean.csv 컬럼 한글화 테스트

목표
- 한글 매핑으로 컬럼명이 변환된 CSV가 생성되는지 검증한다.
"""
from pathlib import Path
import pandas as pd

from app.localize import localize_best_price_daily, KOREAN_MAP


def test_localize_creates_korean_header(tmp_path: Path):
    src = Path("analytics/clean/best_price_daily.clean.csv")
    assert src.exists(), "입력 CSV 누락: analytics/clean/best_price_daily.clean.csv"
    out = tmp_path / "best_price_daily.clean.ko.csv"
    p = localize_best_price_daily(in_path=src, out_path=out)
    assert p.exists()
    df = pd.read_csv(p, nrows=0)  # 헤더만 확인
    cols = list(df.columns)
    # 매핑에 있는 주요 컬럼들이 한글로 존재하는지 확인(일부만 샘플링)
    for eng, kor in list(KOREAN_MAP.items())[:5]:
        if eng in pd.read_csv(src, nrows=0).columns:
            assert kor in cols, f"한글 컬럼 누락: {kor}"

