from __future__ import annotations

"""
선수 이미지 일괄 다운로드 스크립트 (project/download_images.py)

WHY(왜): 전수 크롤링 결과(DB)에 담긴 SPID 목록을 기반으로 선수 이미지를
    실제 파일로 내려받아 시각화/리포트에서 바로 쓸 수 있게 한다.
    크롤링 시점에 네트워크 실패/드라이런으로 비어있을 수 있으므로 별도 백필용 스크립트를 제공한다.

HOW(어떻게):
    - SQLite에서 distinct spid를 조회
    - 알려진 CDN 경로 템플릿을 순서대로 시도해 첫 성공 이미지를 저장
    - 이미 존재하고 0바이트가 아니면 스킵(캐시)
    - 실패 시 옵션에 따라 not_found.png로 채움(시각화 파이프라인 단절 방지)

사용 예(프로젝트 폴더에서 실행):
    python download_images.py --db db/best_price_new.db --out data/images/players --threads 8 --fill-not-found
"""

import argparse
import concurrent.futures as cf
from pathlib import Path
import sqlite3
from typing import Iterable, List, Tuple

import requests

from app.images import ensure_not_found_image


CDN_TEMPLATES: tuple[str, ...] = (
    # WHY: 시즌/스킨 별로 경로가 다를 수 있어 여러 템플릿을 시도한다.
    # HOW: 첫 성공 응답(HTTP 200 & 바디 존재)을 채택한다.
    "https://fo4.dn.nexoncdn.co.kr/live/externalAssets/common/playersAction/p{spid}.png",
    "https://fo4.dn.nexoncdn.co.kr/live/externalAssets/common/players/p{spid}.png",
    "https://fo4.dn.nexoncdn.co.kr/live/externalAssets/common/playersAction/p{spid}_24.png",
    "https://fo4.dn.nexoncdn.co.kr/live/externalAssets/common/players/p{spid}_24.png",
)


def get_spids(db: Path) -> List[int]:
    """DB에서 distinct spid 목록 조회"""
    con = sqlite3.connect(str(db))
    try:
        rows = list(con.execute("select distinct spid from best_price_daily"))
        return [int(r[0]) for r in rows if r and r[0] is not None]
    finally:
        con.close()


def resolve_image(spid: int, *, timeout: int = 10, retry: int = 2) -> bytes | None:
    """SPID에 대한 이미지 바이트 조회(템플릿 순차 시도 + 간단 재시도)"""
    sid = str(spid)
    for _ in range(max(1, retry)):
        for tpl in CDN_TEMPLATES:
            url = tpl.format(spid=sid)
            try:
                r = requests.get(url, timeout=timeout)
                if r.status_code == 200 and r.content:
                    return r.content
            except Exception:
                pass
    return None


def download_many(spids: Iterable[int], out_dir: Path, *, threads: int = 8, timeout: int = 10, retry: int = 2,
                  force: bool = False) -> Tuple[int, int]:
    """여러 SPID에 대해 병렬 다운로드

    반환: (성공, 실패)
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    def task(spid: int) -> Tuple[int, int]:
        out = out_dir / f"{spid}.png"
        if not force and out.exists() and out.stat().st_size > 0:
            return 1, 0
        content = resolve_image(spid, timeout=timeout, retry=retry)
        if content:
            out.write_bytes(content)
            return 1, 0
        return 0, 1

    ok = fail = 0
    with cf.ThreadPoolExecutor(max_workers=max(1, threads)) as ex:
        for s_ok, s_fail in ex.map(task, spids):
            ok += s_ok
            fail += s_fail
    return ok, fail


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Download player images by SPID from SQLite DB")
    ap.add_argument("--db", type=Path, default=Path("db/best_price_new.db"))
    ap.add_argument("--out", type=Path, default=Path("data/images/players"))
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=10)
    ap.add_argument("--retry", type=int, default=2)
    ap.add_argument("--force", action="store_true", help="기존 파일이 있어도 다시 다운로드")
    ap.add_argument("--fill-not-found", action="store_true", help="실패분을 not_found.png로 채움")
    ns = ap.parse_args(argv)

    spids = get_spids(ns.db)
    if not spids:
        print(f"[WARN] no spids found in {ns.db}")
        return 0

    ok, fail = download_many(spids, ns.out, threads=ns.threads, timeout=ns.timeout, retry=ns.retry, force=ns.force)
    print(f"[DONE] images downloaded={ok} failed={fail} dir={ns.out}")

    if ns.fill_not_found and fail:
        nf = Path("data/images/logos/not_found.png")
        ensure_not_found_image(nf)
        nf_bytes = nf.read_bytes()
        filled = 0
        for spid in spids:
            out = ns.out / f"{spid}.png"
            if not out.exists() or out.stat().st_size == 0:
                out.write_bytes(nf_bytes)
                filled += 1
        print(f"[FILL] not_found applied to {filled} files")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

