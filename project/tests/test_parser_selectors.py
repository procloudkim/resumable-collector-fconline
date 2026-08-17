import pytest
from pathlib import Path

from app.parser import parse_bestprice_cards


def _load(year: int) -> str:
    # WHY: 사용자가 tests/fixtures 에 check-*.html을 붙여넣으면 실데이터 기반 검증이 가능
    p = Path("tests/fixtures") / f"check-{year}.html"
    if not p.exists():
        pytest.skip(f"missing fixture {p}")
    return p.read_text(encoding="utf-8", errors="ignore")


def test_parse_minimum_fields_2020():
    html = _load(2020)
    rows = parse_bestprice_cards(html, "2020-05-20")
    assert len(rows) >= 10
    r = rows[0]
    assert "spid" in r and isinstance(r["spid"], int)
    assert "price_value" in r


def test_parse_minimum_fields_2025():
    html = _load(2025)
    rows = parse_bestprice_cards(html, "2025-09-11")
    assert len(rows) >= 10
    r = rows[0]
    assert "spid" in r and isinstance(r["spid"], int)
    assert "position" in r

