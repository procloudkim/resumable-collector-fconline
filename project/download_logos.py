from __future__ import annotations

"""
로고 이미지 일괄 다운로드 스크립트 (project/download_logos.py)

WHY(왜): 전수 크롤링 중 로고(국가/리그/팀) 이미지는 네트워크/렌더링 상황에 따라 누락될 수 있다.
    시각화 품질을 높이기 위해 DB의 코드(nation_code/league_code/team_code)를 기반으로
    실제 파일을 다운로드하여 캐시에 저장하고(중복 스킵), 필요 시 DB 경로 컬럼을 보완한다.

HOW(어떻게):
    - SQLite에서 각 코드의 distinct 집합을 추출
    - 알려진 CDN 경로 템플릿을 순서대로 시도해 첫 성공 응답을 저장
    - 이미 존재하고 0바이트가 아니면 스킵(캐시)
    - 실패 시 옵션에 따라 not_found.png로 채움
    - 옵션: --update-db-paths 로 DB의 *_logo_path 컬럼을 비어있는 경우 일괄 보완

사용 예(프로젝트 폴더에서 실행):
    python download_logos.py --db db/best_price_new.db --base-dir data/images/logos --threads 8 --fill-not-found --update-db-paths
"""

import argparse
import concurrent.futures as cf
from pathlib import Path
import sqlite3
from typing import Dict, Iterable, List, Set, Tuple

import requests

from app.images import ensure_not_found_image


# WHY: 실제 경로는 운영 시점/테마에 따라 달라질 수 있어 여러 템플릿을 준비한다.
LOGO_TEMPLATES: Dict[str, Tuple[str, ...]] = {
    "nation": (
        "https://fo4.dn.nexoncdn.co.kr/live/externalAssets/common/metadata/countries/smallflags/{code}.png",
        # 백업 경로 패턴이 다를 수 있으므로 추가 템플릿을 여기 확장 가능
    ),
    "league": (
        "https://fo4.dn.nexoncdn.co.kr/live/externalAssets/common/metadata/league/dark/{code}.png",
        "https://fo4.dn.nexoncdn.co.kr/live/externalAssets/common/metadata/league/light/{code}.png",
    ),
    "team": (
        "https://fo4.dn.nexoncdn.co.kr/live/externalAssets/common/metadata/crests/dark/small/{code}.png",
        "https://fo4.dn.nexoncdn.co.kr/live/externalAssets/common/metadata/crests/light/small/{code}.png",
    ),
}


def get_codes(db: Path, column: str) -> Set[str]:
    con = sqlite3.connect(str(db))
    try:
        rows = list(con.execute(f"select distinct {column} from best_price_daily where {column} is not null"))
        return {str(r[0]).upper() for r in rows if r and r[0]}
    finally:
        con.close()


def _code_variants(raw: str) -> List[str]:
    """코드 변형을 폭넓게 시도

    - 원본(raw)
    - lower/upper
    - 선행 'l' 제거/추가 조합 (파일명이 이미 l123 형태일 수 있음)
    중복은 제거한다.
    """
    base = str(raw or "")
    low = base.lower()
    up = base.upper()
    no_l = base[1:] if base.lower().startswith("l") else base
    no_l_low = no_l.lower()
    no_l_up = no_l.upper()
    variants = [
        base,
        low,
        up,
        no_l,
        no_l_low,
        no_l_up,
        ("l" + no_l),
        ("l" + no_l_low),
        ("l" + no_l_up),
    ]
    # 순서 유지한 채 중복 제거
    seen = set()
    uniq: List[str] = []
    for v in variants:
        if v not in seen:
            uniq.append(v)
            seen.add(v)
    return uniq


def resolve_logo(group: str, code: str, *, timeout: int = 10, retry: int = 2) -> bytes | None:
    templates = LOGO_TEMPLATES.get(group, ())
    variants = _code_variants(code)
    for _ in range(max(1, retry)):
        for tpl in templates:
            for c in variants:
                url = tpl.format(code=c)
                try:
                    r = requests.get(url, timeout=timeout)
                    if r.status_code == 200 and r.content:
                        return r.content
                except Exception:
                    pass
    return None


def download_group(group: str, codes: Iterable[str], base_dir: Path, *, threads: int = 8, timeout: int = 10, retry: int = 2, force: bool = False) -> Tuple[int, int]:
    """그룹( nation | league | team )에 대해 병렬 다운로드. 반환: (성공, 실패)"""
    out_dir = base_dir / group
    out_dir.mkdir(parents=True, exist_ok=True)

    def task(code: str) -> Tuple[int, int]:
        out = out_dir / f"{code}.png"
        if not force and out.exists() and out.stat().st_size > 0:
            return 1, 0
        content = resolve_logo(group, code, timeout=timeout, retry=retry)
        if content:
            out.write_bytes(content)
            return 1, 0
        return 0, 1

    ok = fail = 0
    with cf.ThreadPoolExecutor(max_workers=max(1, threads)) as ex:
        for s_ok, s_fail in ex.map(task, list(codes)):
            ok += s_ok
            fail += s_fail
    return ok, fail


def update_db_paths(db: Path, base_dir: Path, *, groups: List[str]) -> int:
    """DB의 *_logo_path 컬럼을 비어있는 경우 경로로 보완(멱등). 반환: 보완 건수"""
    con = sqlite3.connect(str(db))
    cur = con.cursor()
    updated = 0
    if "nation" in groups:
        path_prefix = str((base_dir / "nation").as_posix())
        # nation_logo_path가 NULL인 행만 보완
        for (code,) in cur.execute("select distinct nation_code from best_price_daily where nation_code is not null and (nation_logo_path is null or nation_logo_path='')"):
            p = f"{path_prefix}/{str(code).upper()}.png"
            cur.execute("update best_price_daily set nation_logo_path = COALESCE(nation_logo_path, ?) where nation_code = ? and (nation_logo_path is null or nation_logo_path='')", (p, code))
            updated += cur.rowcount
    if "league" in groups:
        path_prefix = str((base_dir / "league").as_posix())
        for (code,) in cur.execute("select distinct league_code from best_price_daily where league_code is not null and (league_logo_path is null or league_logo_path='')"):
            p = f"{path_prefix}/{str(code).upper()}.png"
            cur.execute("update best_price_daily set league_logo_path = COALESCE(league_logo_path, ?) where league_code = ? and (league_logo_path is null or league_logo_path='')", (p, code))
            updated += cur.rowcount
    if "team" in groups:
        path_prefix = str((base_dir / "team").as_posix())
        for (code,) in cur.execute("select distinct team_code from best_price_daily where team_code is not null and (team_logo_path is null or team_logo_path='')"):
            p = f"{path_prefix}/{str(code).upper()}.png"
            cur.execute("update best_price_daily set team_logo_path = COALESCE(team_logo_path, ?) where team_code = ? and (team_logo_path is null or team_logo_path='')", (p, code))
            updated += cur.rowcount
    con.commit()
    con.close()
    return updated


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Download nation/league/team logos and (optionally) update DB paths")
    ap.add_argument("--db", type=Path, default=Path("db/best_price_new.db"))
    ap.add_argument("--base-dir", type=Path, default=Path("data/images/logos"))
    ap.add_argument("--groups", type=str, default="nation,league,team", help="comma-separated: nation,league,team")
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=10)
    ap.add_argument("--retry", type=int, default=2)
    ap.add_argument("--force", action="store_true", help="기존 파일이 있어도 다시 다운로드")
    ap.add_argument("--fill-not-found", action="store_true", help="실패분을 not_found.png로 채움")
    ap.add_argument("--update-db-paths", action="store_true", help="DB의 *_logo_path 컬럼을 경로로 보완")
    ap.add_argument("--debug-sample", type=int, default=0, help="실패 코드 샘플 N개를 출력")
    ns = ap.parse_args(argv)

    groups = [g.strip() for g in ns.groups.split(",") if g.strip() in ("nation", "league", "team")]
    if not groups:
        print("[WARN] no valid groups specified; use --groups nation,league,team")
        return 0

    # not_found 준비
    nf = ns.base_dir / "not_found.png"
    ensure_not_found_image(nf)

    # 코드 수집
    all_counts: Dict[str, int] = {}
    all_ok: Dict[str, int] = {}
    all_fail: Dict[str, int] = {}
    failed_samples: Dict[str, List[str]] = {}
    for g in groups:
        col = f"{g}_code"
        codes = sorted(get_codes(ns.db, col))
        all_counts[g] = len(codes)
        if not codes:
            print(f"[INFO] no codes for group={g}")
            all_ok[g] = 0
            all_fail[g] = 0
            continue
        ok, fail = download_group(g, codes, ns.base_dir, threads=ns.threads, timeout=ns.timeout, retry=ns.retry, force=ns.force)
        all_ok[g] = ok
        all_fail[g] = fail
        print(f"[DONE] group={g} codes={len(codes)} downloaded={ok} failed={fail}")

        if ns.fill_not_found and fail:
            # 실패 파일을 not_found로 채움
            nf_bytes = nf.read_bytes()
            for code in codes:
                out = ns.base_dir / g / f"{code}.png"
                if not out.exists() or out.stat().st_size == 0:
                    out.write_bytes(nf_bytes)
        # 실패 코드 샘플 수집(옵션)
        if ns.debug_sample and fail:
            sample = []
            for code in codes:
                out = ns.base_dir / g / f"{code}.png"
                if not out.exists() or out.stat().st_size == 0:
                    sample.append(code)
                    if len(sample) >= ns.debug_sample:
                        break
            failed_samples[g] = sample

    if ns.update_db_paths:
        updated = update_db_paths(ns.db, ns.base_dir, groups=groups)
        print(f"[DB] logo paths updated rows={updated}")

    # 요약 출력
    for g in groups:
        print(f"group={g} total_codes={all_counts.get(g,0)} ok={all_ok.get(g,0)} fail={all_fail.get(g,0)}")
        if ns.debug_sample and all_fail.get(g,0):
            print(f"  failed_sample[{g}]: {failed_samples.get(g,[]) }")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
