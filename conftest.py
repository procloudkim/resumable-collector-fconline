"""공개본 전용 pytest 설정.

이 파일은 공개본에서 새로 추가한 것이다. `tests/conftest.py` 와 원본 테스트
파일은 손대지 않았다. PROVENANCE_PUBLIC.md 의 "코드는 원본 그대로" 를 지키기
위해서다.

## 왜 필요한가

원본 저장소에는 수집 결과가 함께 있었고, 테스트 일부가 그 데이터를 읽어
검증한다. 공개본은 제3자 개인정보와 이용약관 문제로 데이터를 전부 제외했으므로
그 테스트들이 실패한다.

선택지가 셋이었다.

1. 해당 테스트를 삭제한다
2. 데이터를 다시 넣는다
3. 데이터가 없으면 건너뛰고, 건너뛴 이유를 출력한다

1번은 원본에 데이터 검증 테스트가 있었다는 사실을 지운다. 2번은 공개 결정을
뒤집는다. 3번을 택했다.

`pytest -q` 를 돌리면 건너뛴 개수와 이유가 그대로 보인다. 통과 개수를 부풀리지
않으면서 원본 구성도 보존된다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent

SKIP_REASON = (
    "수집 데이터가 공개본에 없어 건너뜁니다. "
    "제외 사유는 PROVENANCE_PUBLIC.md 를 보십시오."
)

# 테스트 모듈별로 필요한 데이터 경로.
# 하나라도 없으면 그 모듈의 테스트를 건너뛴다.
DATA_DEPENDENT: dict[str, tuple[str, ...]] = {
    "test_analytics_csv_files": ("analytics/game",),
    "test_analytics_layer": ("analytics/manifest.json",),
    "test_export_all_csv": ("project2/db/topdailyrecord.db",),
    "test_localize_best_price_daily": ("analytics/clean",),
    "test_localize_topdaily": ("analytics/clean",),
    "test_preprocess_core": ("analytics/game", "analytics/youtube"),
}


def _missing(paths: tuple[str, ...]) -> list[str]:
    return [p for p in paths if not (ROOT / p).exists()]


def pytest_collection_modifyitems(config, items):
    for item in items:
        required = DATA_DEPENDENT.get(item.module.__name__.rsplit(".", 1)[-1])
        if not required:
            continue
        missing = _missing(required)
        if missing:
            item.add_marker(
                pytest.mark.skip(reason=f"{SKIP_REASON} (없는 경로: {', '.join(missing)})")
            )


def pytest_report_header(config):
    absent = sorted(
        {p for paths in DATA_DEPENDENT.values() for p in paths if not (ROOT / p).exists()}
    )
    if not absent:
        return None
    return (
        f"공개본: 수집 데이터 {len(absent)}개 경로가 없어 관련 테스트를 건너뜁니다. "
        "PROVENANCE_PUBLIC.md 참조."
    )
