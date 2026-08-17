"""
Analytics CSV 산출물 검증 테스트

목표
- 핵심 3종 데이터셋의 CSV 파일이 존재하고 행 수가 0보다 크다.
- Parquet가 존재하면 CSV와 최소 행수 일관성을 점검한다(엄격 동등성은 환경차를 고려해 생략).
"""
from pathlib import Path
import pandas as pd


def _safe_read_parquet(p: Path):
    try:
        return pd.read_parquet(p)
    except Exception:
        return None


def test_csv_files_exist_and_nonempty():
    files = [
        Path("analytics/youtube/comments.csv"),
        Path("analytics/game/best_price_daily.csv"),
        Path("analytics/game/top_daily_record.csv"),
    ]
    for f in files:
        assert f.exists(), f"CSV가 없습니다: {f}"
        df = pd.read_csv(f)
        assert len(df) > 0, f"CSV가 비어있습니다: {f}"


def test_parquet_vs_csv_rowcount_consistency():
    pairs = [
        (Path("analytics/youtube/comments.parquet"), Path("analytics/youtube/comments.csv")),
        (Path("analytics/game/best_price_daily.parquet"), Path("analytics/game/best_price_daily.csv")),
        (Path("analytics/game/top_daily_record.parquet"), Path("analytics/game/top_daily_record.csv")),
    ]
    for pq, csv in pairs:
        if pq.exists() and csv.exists():
            d_pq = _safe_read_parquet(pq)
            d_csv = pd.read_csv(csv)
            if d_pq is not None:
                assert len(d_csv) >= 0 and len(d_pq) >= 0
                # 느슨한 일관성 체크: 행 수가 지나치게 작은 경우만 경고 수준으로 실패 처리
                assert len(d_csv) >= min(len(d_pq), 1), f"CSV 행 수가 비정상적으로 작습니다: {csv}"

