from datetime import datetime, timedelta
import pandas as pd

from app.analysis_utils import compute_pre_post_stats


def test_compute_pre_post_stats_basic():
    # event: 2025-01-10, pre days 7 with value=1, post days 7 with value=3
    e = datetime(2025, 1, 10)
    pre_days = [e - timedelta(days=i) for i in range(1, 8)]
    post_days = [e + timedelta(days=i) for i in range(1, 8)]
    rows = []
    rows += [{"d": d.date(), "v": 1} for d in pre_days]
    rows += [{"d": d.date(), "v": 3} for d in post_days]
    df = pd.DataFrame(rows)
    stats = compute_pre_post_stats(df, date_col="d", value_col="v", event_date=e.date(), window=7)
    assert stats.n_pre == 7 and stats.n_post == 7
    assert abs(stats.pre_mean - 1.0) < 1e-9
    assert abs(stats.post_mean - 3.0) < 1e-9
    assert abs(stats.delta - 2.0) < 1e-9
    assert abs(stats.pct_change - 2.0) < 1e-9

