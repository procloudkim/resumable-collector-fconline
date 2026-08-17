# -*- coding: utf-8 -*-
"""
project2 진행/ETA 출력 유틸.

WHY: 장시간 실행 시 진행률, ETA, 요약 정보를 일관된 포맷으로 제공해 가시성을 높입니다.
HOW: state/progress.json에 누적 상태를 저장하고, 콘솔에는 BDD 스타일 메시지로 시나리오/진행/요약을 출력합니다.
"""

from __future__ import annotations

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
        f"[SCENARIO] 출전 랭킹 수집 시작 ({date_from} ~ {date_to})\n"
        " GIVEN FC Online 데이터센터 일별 출전 랭킹\n"
        " WHEN 날짜별 HTML 수집→파싱→CSV/SQLite 저장\n"
        " THEN 진행/ETA 출력 및 재개 가능 상태 기록"
    )


def fmt_progress(done: int, total: int, start_ts: float, total_rows: int, failed_days: int) -> str:
    pct = (100.0 * done / total) if total else 0.0
    elapsed = time.time() - start_ts
    # 간단한 선형 추정 ETA
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


def fmt_hourly(ok_days: int) -> str:
    return f"[HOURLY CHECK] 최근 1h 처리일수 {ok_days}"


def fmt_summary(
    *,
    target_end: Optional[datetime],
    started_at: str,
    total: int,
    ok: int,
    fail: int,
    rows: int,
) -> str:
    actual = datetime.now()
    tstr = target_end.isoformat(timespec="minutes") if target_end else "(미지정)"
    diff_min = None
    if target_end:
        diff_min = int((actual - target_end).total_seconds() / 60)
    diff_str = f"({('+' if (diff_min or 0) >= 0 else '')}{diff_min}분)" if target_end else ""
    return (
        "[SUMMARY] 완료\n"
        f" 목표 종료: {tstr} | 실제 종료: {actual.isoformat(timespec='minutes')} {diff_str}\n"
        f" 총일수 {total} | 성공 {ok} | 실패 {fail} | 총행 {rows}"
    )

