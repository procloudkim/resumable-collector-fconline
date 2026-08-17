from __future__ import annotations

"""
Progress state and logging helpers used by the bestPrice crawler.
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
    # Use explicit unicode escapes for stable output across consoles
    return (
        f"[SCENARIO] \uc804\uc218 \ud06c\ub864\ub9c1 \uc2dc\uc791 ({date_from} ~ {date_to})\n"
        " GIVEN bestPrice \uce74\ub4dc \ud06c\ub864\ub9c1 \uc900\ube44\n"
        " WHEN \ub0a0\uc9dc \ubc94\uc704 \ucc98\ub9ac + \uc774\ubbf8\uc9c0/\ub85c\uace0 \uc218\uc9d1 \uc9c4\ud589\n"
        " THEN CSV \uc800\uc7a5 \ubc0f SQLite \uc800\uc7a5 \ub9ac\uc2a4\ud2b8"
    )


def fmt_progress(done: int, total: int, start_ts: float, total_rows: int, failed_days: int) -> str:
    pct = (100.0 * done / total) if total else 0.0
    elapsed = time.time() - start_ts
    # ETA \uacc4\uc0b0: \ub2e8\uc21c \ub204\uc801 \ud3c9\uade0 \uc18d\ub3c4 \uae30\ubc18
    rate = done / elapsed if elapsed > 1 else 0.0
    rem = (total - done) / rate if rate > 0 else 0.0
    eta = datetime.now() + timedelta(seconds=rem)
    hh = int(elapsed // 3600)
    mm = int((elapsed % 3600) // 60)
    ss = int(elapsed % 60)
    return (
        f"[PROGRESS] {done}/{total}\uc77c ({pct:.1f}%) | \uacbd\uacfc {hh:02d}:{mm:02d}:{ss:02d} | "
        f"ETA {eta.strftime('%Y-%m-%d %H:%M')} | \uc2e4\ud328\uc77c {failed_days} | \ub204\uc801\ud589 {total_rows}"
    )


def fmt_hourly(ok_days: int, missing_imgs: int, missing_ratio: float) -> str:
    return (
        f"[HOURLY CHECK] \uc790\ub3d9\uc810\uac80 | \ucd5c\uadfc 1h \ucc98\ub9ac\uc77c {ok_days} | "
        f"\ub204\ub77d\uc774\ubbf8\uc9c0 {missing_imgs} ({missing_ratio:.2%})"
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
    tstr = target_end.isoformat(timespec="minutes") if target_end else "(\ubbf8\uc9c0\uc815)"
    diff_min = None
    if target_end:
        diff_min = int((actual - target_end).total_seconds() / 60)
    return (
        "[SUMMARY] \uc644\ub8cc\n"
        f" \ubaa9\ud45c \uc885\ub8cc: {tstr} | \uc2e4\uc81c \uc885\ub8cc: {actual.isoformat(timespec='minutes')} "
        f"({('+' if (diff_min or 0) >= 0 else '')}{diff_min}\ubd84)\n"
        f" \uc804\uccb4\uc77c {total} | \uc131\uacf5 {ok} | \uc2e4\ud328 {fail} | \ud589\uc218 {rows} | \uc774\ubbf8\uc9c0 {pimgs} | \ub85c\uace0 distinct {nlogo}/{llogo}/{tlogo}"
    )

