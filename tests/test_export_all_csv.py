"""
project2 전체 CSV 내보내기(TDD용) 테스트

- 목적: DB 스키마와 최소 범위 내보내기 동작을 검증한다.
- 전제: 실제 DB `project2/db/topdailyrecord.db`가 존재한다.
- 주의: 대용량 전체 내보내기는 이 테스트에서 실행하지 않고, 하루 범위만 샘플로 검증한다.
"""
from pathlib import Path


def test_db_exists_and_module_importable():
    # DB 존재 확인
    db = Path("project2/db/topdailyrecord.db")
    assert db.exists(), "project2/db/topdailyrecord.db 가 존재하지 않습니다. 먼저 project2 수집을 실행하세요."

    # 모듈 임포트 가능해야 함 (아직 미구현이면 이 테스트가 실패함)
    from project2.app import export_all  # noqa: F401


def test_export_minimal_range_creates_csv(tmp_path):
    from project2.app.export_all import (
        get_topdailyrecord_date_bounds,
        export_topdailyrecord_to_csv,
        list_topdailyrecord_columns,
    )

    db_path = "project2/db/topdailyrecord.db"
    # DB의 실제 최소/최대 일자를 조회하여 최소한 1일만 내보낸다.
    min_date, _ = get_topdailyrecord_date_bounds(db_path)
    out_csv = tmp_path / "topdailyrecord_test_export.csv"

    rows, cols = export_topdailyrecord_to_csv(
        db_path=db_path,
        out_csv=str(out_csv),
        date_from=min_date,
        date_to=min_date,
    )

    # 파일 생성 및 기본 검증
    assert out_csv.exists(), "내보낸 CSV 파일이 존재하지 않습니다."
    assert rows >= 0, "내보낸 행 수가 0보다 작을 수 없습니다."

    # 스키마 컬럼 검증: 반드시 date/rank 컬럼이 포함되어야 한다.
    all_cols = list_topdailyrecord_columns(db_path)
    assert "date" in all_cols, "스키마에 'date' 컬럼이 없습니다."
    assert "rank" in all_cols, "스키마에 'rank' 컬럼이 없습니다."

