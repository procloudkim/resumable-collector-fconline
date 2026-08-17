from datetime import datetime

from app.progress import fmt_scenario, fmt_progress, fmt_summary


def test_fmt_scenario():
    s = fmt_scenario("2020-05-20", "2025-09-11")
    assert "전수 크롤링 시작" in s


def test_fmt_progress():
    s = fmt_progress(done=10, total=100, start_ts=0.0, total_rows=180, failed_days=1)
    assert "10/100일" in s


def test_fmt_summary():
    s = fmt_summary(datetime.now(), "2025-09-13T08:00:00", 100, 95, 5, 2000, 0, 0, 0, 0)
    assert "[SUMMARY] 완료" in s

