from __future__ import annotations

"""
CLI 엔트리포인트

WHY: 비전공 사용자도 한 줄 명령으로 전수(1회성) 크롤링을 실행할 수 있게 한다.
HOW: argparse로 옵션을 받아 runner.run()에 전달한다.
     성능 토글(옵션 A/B/C), 재개(--resume), 시간당 헬스체크(--hourly-log),
     목표 종료 시각 비교(--target-end), 드라이런(--dry-run) 등을 지원한다.
"""

import argparse
from datetime import datetime
from pathlib import Path

from .runner import run


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(prog="app.cli", description="FC bestPrice 전수(1회성) 크롤러")
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="전수 크롤링 수행")
    r.add_argument("--from", dest="date_from", required=True, help="YYYY-MM-DD")
    r.add_argument("--to", dest="date_to", required=True, help="YYYY-MM-DD")
    r.add_argument("--csv-dir", type=Path, required=True)
    r.add_argument("--db-path", type=Path, required=True)
    r.add_argument("--players-dir", type=Path, required=True)
    r.add_argument("--logos-dir", type=Path, required=True)
    r.add_argument("--target-end", type=str, default=None, help='목표 종료시간 ISO(예: "2025-09-13T18:00")')
    r.add_argument("--img-threads", type=int, default=8)
    r.add_argument("--hourly-log", action="store_true")
    r.add_argument("--resume", action="store_true")
    r.add_argument("--page-workers", type=int, default=1, help="페이지 병렬 수(안전상 1 권장)")
    r.add_argument("--retry", type=int, default=3)
    r.add_argument("--timeout", type=int, default=20)
    r.add_argument("--dry-run", action="store_true", help="네트워크 없이 파서 검증(픽스처 필요)")
    # 성능 토글 A/B/C
    r.add_argument("--opt-A", dest="opt_a", action="store_true", default=True, help="A: WebDriver 재사용 등 구조 최적화")
    r.add_argument("--no-opt-A", dest="opt_a", action="store_false")
    r.add_argument("--opt-B", dest="opt_b", action="store_true", default=True, help="B: 브라우저 리소스(이미지/CSS/폰트) 차단")
    r.add_argument("--no-opt-B", dest="opt_b", action="store_false")
    r.add_argument("--opt-C", dest="opt_c", action="store_true", default=True, help="C: 정적 요청 우선 후 Selenium 승급")
    r.add_argument("--no-opt-C", dest="opt_c", action="store_false")
    # 요청 슬립 튜닝
    r.add_argument("--sleep-min", type=float, default=0.3, help="요청 간 랜덤 슬립 최소(초)")
    r.add_argument("--sleep-max", type=float, default=1.0, help="요청 간 랜덤 슬립 최대(초)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    ns = parse_args(argv)
    if ns.cmd == "run":
        target_end = None
        if ns.target_end:
            try:
                target_end = datetime.fromisoformat(ns.target_end)
            except Exception:
                target_end = None
        return run(
            date_from=ns.date_from,
            date_to=ns.date_to,
            csv_dir=ns.csv_dir,
            db_path=ns.db_path,
            players_dir=ns.players_dir,
            logos_dir=ns.logos_dir,
            target_end=target_end,
            img_threads=ns.img_threads,
            hourly_log=ns.hourly_log,
            resume=ns.resume,
            page_workers=ns.page_workers,
            retry=ns.retry,
            timeout=ns.timeout,
            dry_run=ns.dry_run,
            opt_a=ns.opt_a,
            opt_b=ns.opt_b,
            opt_c=ns.opt_c,
            sleep_min=ns.sleep_min,
            sleep_max=ns.sleep_max,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

