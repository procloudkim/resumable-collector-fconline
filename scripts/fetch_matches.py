"""
fetch_matches.py — 유저 경기 상세 RAW 수집기

왜(WHY): 특정 시기에 특정 선수의 '사용 빈도(픽)'를 집계하려면 원천이 되는 경기 상세를
안전하게 받아와 로컬에 축적해야 한다.

무엇(WHAT): 닉네임 목록을 받아 Nexon OpenAPI로
  닉네임→OUID→/user/match(페이지네이션)→/match-detail 순으로 호출하고,
  각 상세 JSON을 JSONL 파일(data/raw/matches_sample.jsonl)에 한 줄씩 저장한다.
  중복 match_id는 DB의 seen_match로 차단한다.

어떻게(HOW): 토큰 버킷으로 RPS 제한, 429/5xx 백오프 재시도, 일일 예산 분배.
  API 키는 환경변수 NEXON_OPENAPI_API_KEY 또는 --api-key 인자에서 읽는다.
"""
from __future__ import annotations
import argparse, requests, time, json
from typing import List

from app.core.utils import RAW, ensure_dirs, log, get_env
from app.core.rate_limit import TokenBucket, Quota, compute_daily_budget
from app.core.cache import get_ouid, set_ouid, is_seen, mark_seen, init_schema

BASE = "https://open.api.nexon.com"


def _get(session, url, headers, params=None, timeout=20):
    return session.get(url, headers=headers, params=params, timeout=timeout)


def fetch_detail(session, api_key: str, match_id: str):
    """경기 상세 조회

    왜: 집계의 원천이 되는 상세 JSON을 안전하게 획득하기 위함.
    무엇: /fconline/v1/match-detail?matchid=...
    어떻게: 429/5xx는 지수 백오프로 최대 5회 재시도, 성공 시 JSON 반환.
    """
    headers = {"x-nxopen-api-key": api_key}
    url = f"{BASE}/fconline/v1/match-detail"
    for attempt in range(5):
        r = _get(session, url, headers, params={"matchid": match_id})
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(0.5 * (2**attempt), 8.0)); continue
        r.raise_for_status(); return r.json()
    log(f"match-detail 실패: match_id={match_id}", level="WARN"); return None


def run(nicks: List[str], pages: int, remain: int, api_key: str) -> int:
    """유저 닉네임 목록에 대해 경기 상세 RAW를 축적

    왜: 이후의 '일별 픽 집계'가 신뢰할 수 있도록 원천 데이터를 충분히 누적하기 위해.
    무엇: JSONL 파일 저장 + seen_match 업데이트.
    어떻게: 토큰 버킷과 일일 예산을 적용해 안정적으로 호출.
    """
    ensure_dirs(); init_schema()
    tb = TokenBucket(rate=Quota().per_sec * 0.9)
    budget = compute_daily_budget(remain, len(nicks))
    headers = {"x-nxopen-api-key": api_key}
    saved = 0
    # 닉네임 입력 정제/중복 제거로 불필요 호출 방지
    cleaned = sorted({(nick or "").strip() for nick in nicks if (nick or "").strip()})
    log(f"fetch_matches start: nick_count={len(cleaned)} pages={pages} remain={remain} daily_budget_per_nick≈{budget}")
    with requests.Session() as s:
        for nick in cleaned:
            log(f"nick_start: nickname={nick}")
            ouid = get_ouid(nick)
            cached = bool(ouid)
            if not ouid:
                r = _get(s, f"{BASE}/fconline/v1/id", headers, params={"nickname": nick})
                if r.status_code == 400: log(f"OUID 없음: {nick}", level="WARN"); continue
                r.raise_for_status(); ouid = r.json().get("ouid")
                if not ouid: log(f"OUID 응답 이상: {nick}", level="WARN"); continue
                set_ouid(nick, ouid)
                log(f"ouid_resolved: nickname={nick} ouid={ouid}")
            if cached:
                log(f"ouid_cached: nickname={nick} ouid={ouid}")
            per_nick = min(budget, pages * 100 if pages else 100)
            fetched = 0
            log(f"plan: nickname={nick} per_nick_limit={per_nick} pages={pages}")
            for p in range(pages):
                tb.acquire()
                offset = p * 100
                log(f"page_fetch: nickname={nick} page={p+1}/{pages} offset={offset}")
                r = _get(s, f"{BASE}/fconline/v1/user/match", headers,
                         params={"ouid": ouid, "matchtype": 50, "limit": 100, "offset": offset})
                r.raise_for_status()
                ids = r.json()
                # 같은 페이지 내 중복 방지(이례적이지만 보호적 처리)
                if isinstance(ids, list):
                    ids = list(dict.fromkeys(ids))
                if not ids:
                    log(f"page_empty: nickname={nick} page={p+1}")
                    break
                log(f"page_ids: nickname={nick} page={p+1} ids_count={len(ids)}")
                for mid in ids:
                    if fetched >= per_nick: break
                    if is_seen(mid): continue
                    tb.acquire()
                    detail = fetch_detail(s, api_key, mid)
                    if not detail: continue
                    with (RAW / "matches_sample.jsonl").open("a", encoding="utf-8") as fo:
                        fo.write(json.dumps(detail, ensure_ascii=False) + "\n")
                    mark_seen(mid); fetched += 1; saved += 1
                    if fetched % 10 == 0:
                        log(f"progress: nickname={nick} fetched={fetched}/{per_nick}")
    log(f"RAW 수집 완료: saved={saved}"); return saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nick", nargs="+", required=True, help="유저 닉네임(공백으로 구분)")
    ap.add_argument("--pages", type=int, default=1, help="유저별 페이지 수(한 페이지=100경기)")
    ap.add_argument("--remain", type=int, default=1000, help="일일 호출 예산")
    ap.add_argument("--api-key", default=get_env("NEXON_OPENAPI_API_KEY"))
    args = ap.parse_args()
    if not args.api_key:
        raise SystemExit("API 키 필요(--api-key 또는 환경변수 NEXON_OPENAPI_API_KEY)")
    run(args.nick, args.pages, args.remain, args.api_key)


if __name__ == "__main__":
    main()
