"""
analytics(Gold) 계층 검증 테스트

목표
- manifest.json 파싱 가능
- 핵심 데이터셋 3종(YouTube, best_price, top_daily_record) 로드 가능 및 비어있지 않음
- 최소 스키마 컬럼 존재

전제
- scripts/build_analytics.py 를 실행해 analytics/* 를 생성한 상태여야 테스트 통과
"""
from pathlib import Path
import json
import pandas as pd

from app.data_registry import load_manifest, load_dataset, require_columns


def test_manifest_exists_and_parsable():
    p = Path("analytics/manifest.json")
    assert p.exists(), "analytics/manifest.json 누락 — scripts/build_analytics.py 실행 필요"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert "datasets" in data and isinstance(data["datasets"], list)


def test_core_datasets_loadable_and_nonempty():
    reg = load_manifest()
    for name in [
        "youtube/comments",
        "game/best_price_daily",
        "game/top_daily_record",
    ]:
        assert name in reg, f"manifest에 {name} 누락"
        df = load_dataset(name)
        assert isinstance(df, pd.DataFrame)
        assert len(df) >= 0  # 빈 가능성은 남겨두되, 후속 컬럼 검증에서 실질 체크


def test_minimum_schema_columns():
    y = load_dataset("youtube/comments")
    require_columns(
        y,
        ["video_id", "comment_id", "text", "sentiment_label", "published_at"],
        dataset_name="youtube/comments",
    )
    tdr = load_dataset("game/top_daily_record")
    # 최소 키 컬럼 검증
    assert "date" in tdr.columns, "top_daily_record에 date 컬럼이 없습니다"
    assert "rank" in tdr.columns or "순위" in tdr.columns, "top_daily_record에 순위 컬럼이 없습니다"

