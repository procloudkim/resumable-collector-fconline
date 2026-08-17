"""
seed_ouids.py — 랭커 샘플 OUID 시드 스크립트

왜(WHY): '상위 랭커 근사 코호트'를 정의해 match-detail 집계가 상위권 메타를 반영하도록 만들기 위함.
무엇(WHAT): 닉네임 파일(또는 인자)에서 닉네임을 읽어 Nexon OpenAPI /id 로 OUID를 조회 후
            로컬 DB(ouid_map)에 저장하고(멱등), 선택적으로 ranker_sample 테이블에도 기록한다.
어떻게(HOW): TokenBucket으로 초당 호출 제한을 준수하고, 429/5xx는 지수 백오프로 재시도한다.
            파일은 txt(줄당 닉네임) 또는 CSV(헤더 nickname|nick) 자동 인식.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from typing import List, Set
import time
import requests

from app.core.utils import log, get_env
from app.core.rate_limit import TokenBucket, Quota
from app.core.cache import set_ouid, get_ouid, connect as db_connect, init_schema

BASE = "https://open.api.nexon.com"


def _load_nicks(path: Path | None, inline: List[str]) -> List[str]:
    """닉네임 목록 로드

    왜: 사람이 관리하는 목록을 읽어 API 호출 대상을 결정.
    무엇: TXT(줄당 닉네임) 또는 CSV(헤더 nickname|nick) 지원, 인자 병합.
    어떻게: 공백/중복 제거 후 리스트로 반환.
    """
    nicks: Set[str] = set(x.strip() for x in inline if x and x.strip())
    if path and path.exists():
        if path.suffix.lower() == ".csv":
            import csv
            with path.open("r", encoding="utf-8", newline="") as f:
                reader = csv.DictReader(f)
                col = None
                for k in reader.fieldnames or []:
                    kk = (k or "").strip().lower()
                    if kk in ("nickname", "nick", "name"):
                        col = k; break
                for row in reader:
                    v = (row.get(col) or "").strip() if col else ""
                    if v: nicks.add(v)
        else:
            for line in path.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s: nicks.add(s)
    return sorted(nicks)


def _get(session: requests.Session, url: str, headers: dict, params: dict | None = None, timeout: int = 15):
    return session.get(url, headers=headers, params=params, timeout=timeout)


def run(nick_file: Path | None, nicks: List[str], api_key: str, save_ranker_sample: bool) -> int:
    """닉네임→OUID 시드

    왜: 추후 수집(경기/픽 집계)을 위한 기반 식별자 확보.
    무엇: /id 호출로 OUID를 얻어 ouid_map에 저장, 옵션으로 ranker_sample에도 기록.
    어떻게: 세션/버킷/백오프로 안정성 확보, 멱등 저장.
    """
    headers = {"x-nxopen-api-key": api_key}
    items = _load_nicks(nick_file, nicks)
    if not items:
        log("닉네임 입력이 없습니다.", level="WARN"); return 0
    tb = TokenBucket(rate=Quota().per_sec * 0.9)
    saved = 0
    with requests.Session() as s:
        # app.core.cache.init_schema()는 내부에서 자체 커넥션을 여는 형태이므로 인자가 필요 없습니다.
        # WHY: 스키마 존재 보장 → 이후 ranker_sample 등 추가 테이블 생성에 앞서 안정화
        init_schema()
        conn = db_connect()
        if save_ranker_sample:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ranker_sample(
                    ouid TEXT PRIMARY KEY,
                    nickname TEXT,
                    cohort_at TEXT DEFAULT (date('now'))
                )
                """
            )
            conn.commit()
        for nick in items:
            tb.acquire()
            url = f"{BASE}/fconline/v1/id"
            # 이미 DB에 있는 닉네임이면 API 호출 생략 (API 절약)
            cached = get_ouid(nick)
            if cached:
                if save_ranker_sample:
                    conn.execute(
                        "INSERT OR REPLACE INTO ranker_sample(ouid, nickname) VALUES(?,?)",
                        (cached, nick),
                    )
                    conn.commit()
                saved += 1
                continue
            for attempt in range(5):
                r = _get(s, url, headers, params={"nickname": nick})
                if r.status_code in (429,) or r.status_code >= 500:
                    time.sleep(min(0.5 * (2**attempt), 8.0)); continue
                if r.status_code == 400:
                    log(f"닉네임 없음/형식 오류: {nick}", level="WARN"); break
                r.raise_for_status()
                ouid = (r.json() or {}).get("ouid")
                if not ouid:
                    log(f"OUID 응답 누락: {nick}", level="WARN"); break
                set_ouid(nick, ouid)
                if save_ranker_sample:
                    conn.execute("INSERT OR REPLACE INTO ranker_sample(ouid, nickname) VALUES(?,?)", (ouid, nick))
                    conn.commit()
                saved += 1
                break
    log(f"시드 완료: 닉네임={len(items)}, 저장={saved}")
    return saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path, default=Path("config/rankers.txt"), help="닉네임 목록 파일(txt/csv)")
    ap.add_argument("--nick", nargs="*", default=[], help="인라인 닉네임(공백 구분)")
    ap.add_argument("--api-key", default=get_env("NEXON_OPENAPI_API_KEY"))
    ap.add_argument("--save-ranker-sample", action="store_true", help="ranker_sample 테이블에도 기록")
    args = ap.parse_args()
    if not args.api_key:
        raise SystemExit("API 키 필요(--api-key 또는 환경변수 NEXON_OPENAPI_API_KEY)")
    run(args.file, args.nick, args.api_key, args.save_ranker_sample)


if __name__ == "__main__":
    main()
