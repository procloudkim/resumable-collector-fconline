import time
from app.core.rate_limit import TokenBucket, compute_daily_budget

def test_compute_daily_budget():
    assert compute_daily_budget(900, 3) == 300
    assert compute_daily_budget(0, 3) == 0
    assert compute_daily_budget(100, 0) == 0

def test_token_bucket_rate():
    tb = TokenBucket(rate=5.0, burst=1)  # 초당 5개
    start = time.time()
    for _ in range(10):
        tb.acquire()
    elapsed = time.time() - start
    # 10개를 소비하려면 최소 약 2초는 걸려야 함(버스트1 가정)
    assert elapsed >= 1.8
