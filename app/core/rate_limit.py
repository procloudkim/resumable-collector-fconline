"""
rate_limit.py — 호출속도/예산 제어
"""
from __future__ import annotations
import threading, time
from dataclasses import dataclass

@dataclass
class Quota:
    per_sec: float = 5.0       # dev: 초당 5
    per_day: int = 1000        # dev: 일 1000
    safety_ratio: float = 0.9  # 여유 10%

class TokenBucket:
    def __init__(self, rate: float, burst: int = 2):
        self.rate = rate
        self.capacity = burst
        self.tokens = burst
        self.ts = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self):
        with self.lock:
            while True:
                now = time.monotonic()
                delta = now - self.ts
                self.ts = now
                self.tokens = min(self.capacity, self.tokens + delta * self.rate)
                if self.tokens >= 1.0:
                    self.tokens -= 1.0
                    return
                wait = (1.0 - self.tokens) / self.rate
                time.sleep(max(wait, 0.01))

def compute_daily_budget(remaining: int, nick_count: int) -> int:
    if nick_count <= 0: return 0
    return max(0, remaining // nick_count)
