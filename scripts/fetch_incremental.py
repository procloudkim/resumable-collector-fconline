"""
利앸텇 ?섏쭛: nickname?뭀UID?뭫ser/match?뭢atch-detail
- seen_match濡?以묐났 李⑤떒
- ?좏겙踰꾪궥?쇰줈 rps/?쇱씪?덉궛 以??
"""
from __future__ import annotations
import argparse, requests, time, os, json
from app.core.utils import RAW, ensure_dirs, log, get_env
from app.core.rate_limit import TokenBucket, Quota, compute_daily_budget
from app.core.cache import get_ouid, set_ouid, is_seen, mark_seen, init_schema

BASE = "https://open.api.nexon.com"

def _get(session, url, headers, params=None, timeout=20):
    return session.get(url, headers=headers, params=params, timeout=timeout)

def fetch_detail(session, api_key, match_id):
    headers = {"x-nxopen-api-key": api_key}
    url = f"{BASE}/fconline/v1/match-detail"
    for attempt in range(5):
        r = _get(session, url, headers, params={"matchid": match_id})
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(min(0.5*(2**attempt), 8.0)); continue
        r.raise_for_status(); return r.json()
    log(f"match-detail 실패: match_id={match_id}", level="WARN"); return None

def run(nicks, pages, remain, api_key):
    ensure_dirs(); init_schema()
    tb = TokenBucket(rate=Quota().per_sec*0.9)
    budget = compute_daily_budget(remain, len(nicks))
    headers = {"x-nxopen-api-key": api_key}
    saved = 0
    with requests.Session() as s:
        for nick in nicks:
            ouid = get_ouid(nick)
            if not ouid:
                r = _get(s, f"{BASE}/fconline/v1/id", headers, params={"nickname": nick})
                if r.status_code == 400: log(f"OUID ?놁쓬: {nick}", level="WARN"); continue
                r.raise_for_status(); ouid = r.json().get("ouid")
                if not ouid: log(f"OUID ?묐떟 ?댁긽: {nick}", level="WARN"); continue
                set_ouid(nick, ouid)
            per_nick = min(budget, pages*100 if pages else 100)
            fetched = 0
            for p in range(pages):
                tb.acquire()
                r = _get(s, f"{BASE}/fconline/v1/user/match", headers,
                         params={"ouid":ouid, "matchtype":50, "limit":100, "offset":p*100})
                r.raise_for_status()
                ids = r.json()
                if not ids: break
                for mid in ids:
                    if fetched >= per_nick: break
                    if is_seen(mid): continue
                    tb.acquire()
                    detail = fetch_detail(s, api_key, mid)
                    if not detail: continue
                    with (RAW/"matches_sample.jsonl").open("a", encoding="utf-8") as fo:
                        fo.write(json.dumps(detail, ensure_ascii=False)+"\n")
                    mark_seen(mid); fetched+=1; saved+=1
    log(f"利앸텇 ?섏쭛 ?꾨즺: saved={saved}"); return saved

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nick", nargs="+", required=True)
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--remain", type=int, default=1000)
    ap.add_argument("--api-key", default=get_env("NEXON_OPENAPI_API_KEY"))
    args = ap.parse_args()
    if not args.api_key: raise SystemExit("API ???꾩슂(--api-key ?먮뒗 ?섍꼍蹂??")
    run(args.nick, args.pages, args.remain, args.api_key)

if __name__ == "__main__":
    main()

