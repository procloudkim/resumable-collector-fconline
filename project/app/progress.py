from __future__ import annotations

"""
진행률/재개/로그 포맷

WHY: 1회성 전수 크롤링이라도 중단 가능성이 있다. 재개/진행률/ETA/헬스체크를 표준화하여 운영 안정성을 높인다.
HOW: progress.json에 상태를 저장하고, BDD 스타일 로그 메시지를 포맷팅한다.
"""

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional


@dataclass
class ProgressState:
    started_at: str
    date_from: str
    date_to: str
    current_date: Optional[str]
    done_days: int
    total_days: int
    total_rows: int
    failed_days: int
    last_hourly_at: float


def init_state(path: Path, date_from: str, date_to: str, total_days: int) -> ProgressState:
    now = datetime.now().isoformat(timespec="seconds")
    st = ProgressState(
        started_at=now,
        date_from=date_from,
        date_to=date_to,
        current_date=None,
        done_days=0,
        total_days=total_days,
        total_rows=0,
        failed_days=0,
        last_hourly_at=time.time(),
    )
    save_state(path, st)
    return st


def save_state(path: Path, st: ProgressState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(st), ensure_ascii=False, indent=2), encoding="utf-8")


def load_state(path: Path) -> Optional[ProgressState]:
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return ProgressState(**data)


def fmt_scenario(date_from: str, date_to: str) -> str:
    return (
        f"[SCENARIO] 전수 크롤링 시작 ({date_from} ~ {date_to})\n"
        " GIVEN bestPrice 카드 전수 수집\n"
        " WHEN 날짜 순차 처리 + 이미지/로고 제한 병렬\n"
        " THEN CSV 누적 후 SQLite 적재 및 리포트"
    )


def fmt_progress(done: int, total: int, start_ts: float, total_rows: int, failed_days: int) -> str:
    pct = (100.0 * done / total) if total else 0.0
    elapsed = time.time() - start_ts
    # ETA 계산: 단순 선형 예측
    rate = done / elapsed if elapsed > 1 else 0.0
    rem = (total - done) / rate if rate > 0 else 0.0
    eta = datetime.now() + timedelta(seconds=rem)
    hh = int(elapsed // 3600)
    mm = int((elapsed % 3600) // 60)
    ss = int(elapsed % 60)
    return (
        f"[PROGRESS] {done}/{total}일 ({pct:.1f}%) | 경과 {hh:02d}:{mm:02d}:{ss:02d} | "
        f"ETA {eta.strftime('%Y-%m-%d %H:%M')} | 실패일 {failed_days} | 누적행 {total_rows}"
    )


def fmt_hourly(ok_days: int, missing_imgs: int, missing_ratio: float) -> str:
    return (
        f"[HOURLY CHECK] 정상작동 | 최근 1h 처리일 {ok_days} | "
        f"누락이미지 {missing_imgs} ({missing_ratio:.2%})"
    )


def fmt_summary(
    target_end: Optional[datetime],
    started_at: str,
    total: int,
    ok: int,
    fail: int,
    rows: int,
    pimgs: int,
    nlogo: int,
    llogo: int,
    tlogo: int,
) -> str:
    actual = datetime.now()
    tstr = target_end.isoformat(timespec="minutes") if target_end else "(미지정)"
    diff_min = None
    if target_end:
        diff_min = int((actual - target_end).total_seconds() / 60)
    return (
        "[SUMMARY] 완료\n"
        f" 목표 종료: {tstr} | 실제 종료: {actual.isoformat(timespec='minutes')} "
        f"({('+' if (diff_min or 0) >= 0 else '')}{diff_min}분)\n"
        f" 총일수 {total} | 성공 {ok} | 실패 {fail} | 총행 {rows} | 이미지 {pimgs} | 로고 distinct {nlogo}/{llogo}/{tlogo}"
    )

