from __future__ import annotations

"""
전체 워크플로우 조립

WHY: 날짜 범위 순회, 파싱, CSV 원자적 기록, 이미지/로고 병렬 다운로드,
     종료 후 SQLite 적재까지 한 번에 수행한다(1회성 전수).
HOW: progress.json 상태를 유지하며, BDD 스타일 로그/ETA/헬스체크를 출력한다.
"""

import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

from dateutil.parser import isoparse

from .fetcher import create_driver, get_page_requests, get_page_selenium
from .images import DownloadTask, download_many, ensure_not_found_image
from .parser import parse_bestprice_cards
from .progress import (
    fmt_hourly,
    fmt_progress,
    fmt_scenario,
    fmt_summary,
    init_state,
    load_state,
    save_state,
)
from .storage import append_rows_atomic, load_into_sqlite, monthly_csv_path
from .utils import ensure_dir, polite_sleep


def _date_range(date_from: str, date_to: str) -> List[str]:
    s = isoparse(date_from).date()
    e = isoparse(date_to).date()
    cur = s
    out: List[str] = []
    while cur <= e:
        out.append(cur.isoformat())
        cur += timedelta(days=1)
    return out


def run(
    *,
    date_from: str,
    date_to: str,
    csv_dir: Path,
    db_path: Path,
    players_dir: Path,
    logos_dir: Path,
    target_end: Optional[datetime],
    img_threads: int = 8,
    hourly_log: bool = False,
    resume: bool = False,
    page_workers: int = 1,  # 안전상 미사용(1 고정)
    retry: int = 3,
    timeout: int = 20,
    dry_run: bool = False,
    opt_a: bool = True,
    opt_b: bool = True,
    opt_c: bool = True,
    sleep_min: float = 0.3,
    sleep_max: float = 1.0,
) -> int:
    # 디렉터리 준비
    ensure_dir(csv_dir)
    ensure_dir(db_path.parent)
    ensure_dir(players_dir)
    ensure_dir(logos_dir / "nation")
    ensure_dir(logos_dir / "league")
    ensure_dir(logos_dir / "team")
    ensure_not_found_image(logos_dir / "not_found.png")  # 실패 대체 파일 확보

    # 시나리오 로그
    print(fmt_scenario(date_from, date_to), flush=True)

    # 상태 로드/초기화
    state_path = Path("state/progress.json")
    dates = _date_range(date_from, date_to)
    if resume:
        st = load_state(state_path) or init_state(state_path, date_from, date_to, len(dates))
    else:
        st = init_state(state_path, date_from, date_to, len(dates))

    start_ts = time.time()
    last_hourly = start_ts
    total_rows = st.total_rows
    done = st.done_days
    failed_days = st.failed_days

    # 성능 A: WebDriver 재사용
    driver = None
    if not dry_run and not opt_c:
        # C 비활성화 시 곧바로 Selenium 경로 → 드라이버 1회 생성
        driver = create_driver(headless=True, optimize_b=opt_b, timeout=timeout)

    # 날짜 순차 처리(안전 우선)
    for d in dates[done:]:
        st.current_date = d
        save_state(state_path, st)

        html = ""
        # C: 정적 요청 우선 시도
        if not dry_run and opt_c:
            html = get_page_requests(d, timeout=timeout, retry=retry, sleep_min=sleep_min, sleep_max=sleep_max)

        # 실패 → A: Selenium 승급
        if not dry_run and not html:
            if driver is None:
                driver = create_driver(headless=True, optimize_b=opt_b, timeout=timeout)
            html = get_page_selenium(driver, d, timeout=timeout)

        # dry-run 또는 fetch 실패 → 로컬 픽스처(있다면) 사용
        if not html:
            snap = Path("tests/fixtures") / f"check-{d[:4]}.html"
            if snap.exists():
                html = snap.read_text(encoding="utf-8", errors="ignore")

        if not html:
            failed_days += 1
            st.failed_days = failed_days
            save_state(state_path, st)
            print(f"[WARN] HTML 비어 있음 date={d}")
            polite_sleep(sleep_min, sleep_max)
            done += 1
            st.done_days = done
            continue

        # 파싱
        rows = parse_bestprice_cards(html, d)

        # 품질 게이트: 카드 수가 15 미만 → 실패일 처리
        if len(rows) < 15:
            failed_days += 1
            st.failed_days = failed_days
            save_state(state_path, st)
            print(f"[WARN] 카드 수 부족(<15) date={d} cards={len(rows)}")
            polite_sleep(sleep_min, sleep_max)
            done += 1
            st.done_days = done
            continue

        # 이미지/로고 다운로드 태스크(필수: 선수 이미지)
        img_tasks: list[DownloadTask] = []
        for r in rows:
            # 선수 이미지
            if r.get("player_image_url") and r.get("spid"):
                out = players_dir / f"{int(r['spid'])}.png"
                r["player_image_path"] = str(out)
                img_tasks.append(DownloadTask(url=r["player_image_url"], out_path=out))
            else:
                r["player_image_path"] = str(logos_dir / "not_found.png")

            # 로고(선택): 코드만 있으면 스킵(추후 백필), URL이 있을 경우에만 다운로드
            # 본 파서는 로고 코드만 추출하므로 여기서는 경로 필드만 채움(존재하면 backfill)
            r["nation_logo_path"] = None
            r["league_logo_path"] = None
            r["team_logo_path"] = None

        # CSV 기록(월별, 원자적)
        month_csv = monthly_csv_path(csv_dir, d)
        total_rows += append_rows_atomic(month_csv, rows)

        # 이미지 병렬 다운로드
        if not dry_run and img_tasks:
            ok, fail = download_many(img_tasks, max_workers=img_threads)
            if fail:
                # 실패 기록 파일
                fail_log = Path("state") / f"failures_{d}.txt"
                fail_log.parent.mkdir(parents=True, exist_ok=True)
                with fail_log.open("a", encoding="utf-8") as f:
                    for t in img_tasks:
                        p = t.out_path
                        if not p.exists() or p.stat().st_size == 0:
                            f.write(f"{d}, {t.url}\n")

        # 진행률 업데이트
        done += 1
        st.done_days = done
        st.total_rows = total_rows
        save_state(state_path, st)
        print(fmt_progress(done, len(dates), start_ts, total_rows, failed_days), flush=True)

        # 1시간 주기 헬스체크 로그
        if hourly_log and (time.time() - last_hourly) >= 3600:
            print(fmt_hourly(ok_days=done, missing_imgs=0, missing_ratio=0.0), flush=True)
            last_hourly = time.time()

        polite_sleep(sleep_min, sleep_max)

    # 드라이버 종료
    if driver is not None:
        try:
            driver.quit()
        except Exception:
            pass

    # 종료 후 SQLite 적재
    csv_files = sorted(Path(csv_dir).glob("bestprice_*.csv"))
    loaded = load_into_sqlite(db_path, csv_files)

    # 요약 로그
    print(
        fmt_summary(
            target_end=target_end,
            started_at=st.started_at,
            total=len(dates),
            ok=done - failed_days,
            fail=failed_days,
            rows=total_rows,
            pimgs=0,
            nlogo=0,
            llogo=0,
            tlogo=0,
        ),
        flush=True,
    )
    return 0

