"""
TOP 10,000 랭커 20경기 평균 스탯 수집 → ranker_stats 저장
- players 파라미터는 [{id,po},...]이며, 1회 max 50명 권장
"""
from __future__ import annotations
import argparse, json, os, time, urllib.parse
from pathlib import Path
from typing import List, Dict, Any, Tuple
import requests, sqlite3

from app.core.utils import log, get_env
from app.core.rate_limit import TokenBucket, Quota
from app.core.cache import connect, init_schema
from app.services.meta import load_spid_map, load_position_map

BASE = "https://open.api.nexon.com"

def chunk(items: List[Dict[str,int]], size: int=50):
    for i in range(0,len(items),size): yield items[i:i+size]

def build_players_param(pairs: list[dict]) -> str:
    # JSON을 공백 없이(minified) 직렬화: separators=(',',':')
    # 그리고 안전하게 전체를 퍼센트 인코딩(safe='')
    s = json.dumps(pairs, ensure_ascii=False, separators=(',', ':'))
    return urllib.parse.quote(s, safe='')


def filter_valid_pairs(pairs: List[Dict[str,int]]) -> List[Dict[str,int]]:
    spids=load_spid_map(); pos=load_position_map()
    valid: List[Dict[str,int]]=[]
    seen: set[Tuple[int,int]] = set()
    for it in pairs:
        try:
            spid=int(it["id"]); po=int(it["po"])
        except Exception:
            continue
        if (spid not in spids) or (po not in pos):
            continue
        key=(spid,po)
        if key in seen:
            continue
        seen.add(key)
        valid.append({"id":spid,"po":po})
    return valid

def fetch_batch(pairs, session, api_key) -> list[dict]:
    if not pairs:
        return []
    url = f"{BASE}/fconline/v1/ranker-stats?players={build_players_param(pairs)}"
    headers = {"x-nxopen-api-key": api_key}
    r = session.get(url, headers=headers, timeout=20)

    if r.status_code == 200:
        return r.json()

    if r.status_code == 429 or r.status_code >= 500:
        for attempt in range(3):
            wait = min(0.5*(2**attempt), 8.0)
            log(f"재시도: status={r.status_code}, wait={wait}s", level="WARN")
            time.sleep(wait)
            rr = session.get(url, headers=headers, timeout=20)
            if rr.status_code == 200:
                return rr.json()
        log("최대 재시도 초과", level="WARN")
        return []

    if r.status_code == 400:
        if len(pairs) == 1:
            it = pairs[0]
            log(f"400 원인 제거: spid={it.get('id')} po={it.get('po')}", level="WARN")
            return []
        mid = len(pairs)//2
        left  = fetch_batch(pairs[:mid], session, api_key)
        right = fetch_batch(pairs[mid:], session, api_key)
        return left + right

    log(f"ranker-stats 실패: status={r.status_code}, url={url}", level="WARN")
    return []


def persist_rows(conn: sqlite3.Connection, rows: List[Dict[str,Any]]) -> int:
    cur=conn.cursor(); saved=0
    for rec in rows:
        s=rec.get("status",{})
        cur.execute("""
        INSERT OR REPLACE INTO ranker_stats
        (spid,po,create_date,dribble,dribble_try,dribble_success,pass_try,pass_success,block,tackle,assist,goal,match_count)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (rec.get("spId"), rec.get("spPosition"), rec.get("createDate"),
         s.get("dribble"), s.get("dribbleTry"), s.get("dribbleSuccess"),
         s.get("passTry"), s.get("passSuccess"),
         s.get("block"), s.get("tackle"),
         s.get("assist"), s.get("goal"),
         s.get("matchCount")))
        saved+=1
    conn.commit(); return saved

def run(pairs: List[Dict[str,int]], api_key: str) -> int:
    init_schema()
    conn=connect()
    valid=filter_valid_pairs(pairs)
    log(f"입력={len(pairs)}, 유효={len(valid)}")
    # 오늘자 스냅샷 존재 쌍 제외하여 API 절약
    import datetime as _dt
    today=_dt.date.today().isoformat()
    _cur=conn.cursor()
    _vf=[]
    for it in valid:
        _cur.execute("SELECT 1 FROM ranker_stats WHERE spid=? AND po=? AND date(substr(create_date,1,10))=? LIMIT 1",
                     (int(it['id']), int(it['po']), today))
        if _cur.fetchone():
            continue
        _vf.append(it)
    valid=_vf
    if not valid: return 0
    tb=TokenBucket(rate=Quota().per_sec*0.9)
    total=0
    with requests.Session() as s:
        for batch in chunk(valid,50):
            tb.acquire()
            rows=fetch_batch(batch,s,api_key)
            total+=persist_rows(conn,rows)
    log(f"저장 완료: total={total}")
    return total

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--pairs", required=True)
    ap.add_argument("--api-key", default=get_env("NEXON_OPENAPI_API_KEY"))
    args=ap.parse_args()
    if not args.api_key: raise SystemExit("API 키 필요(--api-key 또는 환경변수)")
    pairs=json.loads(Path(args.pairs).read_text(encoding="utf-8"))
    run(pairs, args.api_key)

if __name__=="__main__": main()
