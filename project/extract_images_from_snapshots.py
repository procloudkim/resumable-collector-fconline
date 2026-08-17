from __future__ import annotations

"""
스냅샷(HTML) 기반 이미지 일괄 추출기

WHY: 코드 기반(CDN 템플릿)으로는 일부 로고/이미지(L_DATA_PLAYER_LOGO 등 자리표시 코드)가
    해석되지 않아 다운로드에 실패한다. 저장된 스냅샷의 실제 img[src]를 파싱해
    정확한 URL로 직접 내려받아 누락을 최소화한다.

HOW:
    - check 디렉터리의 HTML을 파싱
    - 선수 이미지: 각 카드 슬라이드의 .playerCardThumb 내 img[src] 수집 → SPID 정규식으로 파일명 결정
    - 로고 이미지: 각 카드 내 .playerCardInfoSort 하위 nation/league/team img[src] 수집 → 파일명 그대로 코드로 저장
    - 다운로드는 ThreadPool(기본 8), 이미 존재/0바이트 아님 → 스킵
    - 옵션: 실패분 not_found.png로 채움, DB의 *_logo_path 보완(update-db-paths)

사용 예:
    python extract_images_from_snapshots.py \
      --check-dir docs/check --check-dir check \
      --players-out data/images/players --logos-out data/images/logos \
      --threads 8 --fill-not-found --update-db-paths --db db/best_price_new.db
"""

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

import requests
from bs4 import BeautifulSoup  # type: ignore

from app.images import DownloadTask, download_many, ensure_not_found_image
from download_logos import update_db_paths  # 재사용


SPID_RE = re.compile(r"/p(\d+)(?:_\d+)?\.png", re.I)


@dataclass
class SnapshotResult:
    player_tasks: List[DownloadTask]
    logo_tasks: List[DownloadTask]
    logo_codes_by_group: Dict[str, Set[str]]


def parse_snapshot(html: str, *, players_out: Path, logos_out: Path) -> SnapshotResult:
    soup = BeautifulSoup(html, "lxml")
    player_tasks: List[DownloadTask] = []
    logo_tasks: List[DownloadTask] = []
    logo_codes_by_group: Dict[str, Set[str]] = {"nation": set(), "league": set(), "team": set()}

    # 카드 슬라이드 루프
    slides = soup.select("#bestPrice #divBestTradeArea_price .item_list, #divBestTradeArea_price .item_list, #divBestTradeArea_price .swiper-slide")
    for s in slides:
        # 선수 이미지
        img = s.select_one(".playerCardThumb .img img[src]")
        if img and img.has_attr("src"):
            src = str(img["src"]).strip()
            m = SPID_RE.search(src)
            if m:
                spid = m.group(1)
                out = players_out / f"{spid}.png"
                player_tasks.append(DownloadTask(url=src, out_path=out))

        # 로고 이미지(카드 내부 우선)
        for group, sel in (
            ("nation", ".playerCardInfoSort .nation img[src]"),
            ("league", ".playerCardInfoSort .league img[src]"),
            ("team", ".playerCardInfoSort .team img[src]"),
        ):
            node = s.select_one(sel)
            if node and node.has_attr("src"):
                src = str(node["src"]).strip()
                code = Path(src).stem  # 파일명(확장자 제외)을 코드로 저장
                out = logos_out / group / f"{code}.png"
                logo_tasks.append(DownloadTask(url=src, out_path=out))
                logo_codes_by_group.setdefault(group, set()).add(code)

    return SnapshotResult(player_tasks, logo_tasks, logo_codes_by_group)


def collect_html(check_dirs: List[Path]) -> List[Path]:
    files: List[Path] = []
    for d in check_dirs:
        if not d.exists():
            continue
        files.extend(sorted(d.glob("check-*.html")))
    return files


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract and download images from HTML snapshots")
    ap.add_argument("--check-dir", action="append", type=Path, default=[], help="HTML 스냅샷 디렉터리(여러 개 지정 가능)")
    ap.add_argument("--players-out", type=Path, default=Path("data/images/players"))
    ap.add_argument("--logos-out", type=Path, default=Path("data/images/logos"))
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--fill-not-found", action="store_true")
    ap.add_argument("--update-db-paths", action="store_true")
    ap.add_argument("--db", type=Path, default=Path("db/best_price_new.db"))
    ns = ap.parse_args(argv)

    # 기본 검색 경로 보강
    check_dirs = list(dict.fromkeys(ns.check_dir or []))  # de-dup
    if not check_dirs:
        # 합리적 기본값들 시도
        for p in (Path("docs/check"), Path("check"), Path("tests/fixtures")):
            check_dirs.append(p)

    html_files = collect_html(check_dirs)
    if not html_files:
        print(f"[WARN] no HTML snapshots found in: {[str(p) for p in check_dirs]}")
        return 0

    # 수집
    all_player_tasks: List[DownloadTask] = []
    all_logo_tasks: List[DownloadTask] = []
    all_logo_codes: Dict[str, Set[str]] = {"nation": set(), "league": set(), "team": set()}

    for f in html_files:
        html = f.read_text(encoding="utf-8", errors="ignore")
        res = parse_snapshot(html, players_out=ns.players_out, logos_out=ns.logos_out)
        all_player_tasks.extend(res.player_tasks)
        all_logo_tasks.extend(res.logo_tasks)
        for k in all_logo_codes.keys():
            all_logo_codes[k].update(res.logo_codes_by_group.get(k, set()))

    # 다운로드
    ok_p, fail_p = download_many(all_player_tasks, max_workers=ns.threads)
    ok_l, fail_l = download_many(all_logo_tasks, max_workers=ns.threads)
    print(f"[PLAYERS] ok={ok_p} fail={fail_p}")
    print(f"[LOGOS]   ok={ok_l} fail={fail_l}")

    if ns.fill_not_found and (fail_p or fail_l):
        nf = ns.logos_out / "not_found.png"
        ensure_not_found_image(nf)
        nf_bytes = nf.read_bytes()
        # 선수
        for t in all_player_tasks:
            if not t.out_path.exists() or t.out_path.stat().st_size == 0:
                t.out_path.parent.mkdir(parents=True, exist_ok=True)
                t.out_path.write_bytes(nf_bytes)
        # 로고
        for t in all_logo_tasks:
            if not t.out_path.exists() or t.out_path.stat().st_size == 0:
                t.out_path.parent.mkdir(parents=True, exist_ok=True)
                t.out_path.write_bytes(nf_bytes)
        print("[FILL] not_found applied to missing images")

    # DB 보완(로고 경로)
    if ns.update_db_paths:
        updated = update_db_paths(ns.db, ns.logos_out, groups=[g for g in ("nation","league","team")])
        print(f"[DB] logo paths updated rows={updated}")

    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

