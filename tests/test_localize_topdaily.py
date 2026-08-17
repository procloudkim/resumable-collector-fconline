from pathlib import Path
import pandas as pd

from app.localize_topdaily import localize_top_daily


def test_localize_and_parse_player_info(tmp_path: Path):
    src = tmp_path / "top_daily_record.clean.csv"
    df = pd.DataFrame({
        "date": ["2025-01-01"],
        "선수_기본정보": ["엘링 홀란, 3, ST 99, 21"],
        "출전": [1],
        "태클성공률": [55],
    })
    df.to_csv(src, index=False, encoding="utf-8")

    outp = tmp_path / "top_daily_record.clean.ko.csv"
    out = localize_top_daily(in_path=src, out_path=outp)
    assert out.exists()
    got = pd.read_csv(out)
    # 컬럼명 변경 확인
    assert "날짜" in got.columns and "출전_기록" in got.columns and "태클_성공률" in got.columns
    # 파싱 확인
    assert list(got["선수명"]) == ["엘링 홀란"]
    assert list(got["강화 단계"]) == [3]
    assert list(got["포지션"]) == ["ST"]
    assert list(got["오버롤"]) == [99]
    assert list(got["급여"]) == [21]

