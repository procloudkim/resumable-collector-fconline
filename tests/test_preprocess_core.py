"""
전처리 코어 함수 테스트(TDD)

목표
- analytics CSV 3종을 읽어 clean CSV를 생성한다.
- 최소 컬럼/타입 정규화가 적용된다.
"""
from pathlib import Path
import pandas as pd

from app.preprocess import (
    clean_comments,
    clean_top_daily_record,
    clean_best_price_daily,
    preprocess_all,
)


def test_clean_comments_minimum_columns():
    p = Path("analytics/youtube/comments.csv")
    assert p.exists(), "analytics/youtube/comments.csv 누락"
    df = pd.read_csv(p, nrows=100)
    out = clean_comments(df)
    for c in ["video_id", "comment_id", "text", "sentiment_label"]:
        assert c in out.columns, f"댓글 스키마 컬럼 누락: {c}"


def test_clean_top_daily_record_minimum_columns():
    p = Path("analytics/game/top_daily_record.csv")
    assert p.exists(), "analytics/game/top_daily_record.csv 누락"
    df = pd.read_csv(p, nrows=100)
    out = clean_top_daily_record(df)
    assert "date" in out.columns
    # rank는 존재 시 정수 캐스팅 검사
    if "rank" in out.columns:
        assert str(out["rank"].dtype).startswith("Int"), "rank 정수 캐스팅 실패"


def test_clean_best_price_daily_minimum_columns():
    p = Path("analytics/game/best_price_daily.csv")
    assert p.exists(), "analytics/game/best_price_daily.csv 누락"
    df = pd.read_csv(p, nrows=100)
    out = clean_best_price_daily(df)
    assert "date" in out.columns
    if "spid" in out.columns:
        assert str(out["spid"].dtype).startswith("Int")


def test_preprocess_all_outputs(tmp_path: Path):
    outs = preprocess_all(out_dir=tmp_path)
    # 최소 2개 이상(환경에 따라 youtube 원본 부재 시 2개일 수 있음)
    assert len(outs) >= 2
    for p in outs.values():
        assert Path(p).exists()

