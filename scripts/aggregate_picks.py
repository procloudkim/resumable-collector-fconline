"""
aggregate_picks.py — 일별 선수 '사용 빈도(픽)' 집계기

왜(WHY): 문서 목표는 '평균 스탯'이 아니라 '어떤 시기에 어떤 선수가 얼마나 사용되었는지'를
시계열로 파악하는 것이다. 이를 위해 경기 상세 RAW(JSONL)를 읽어 날짜·선수별 등장 횟수를 합산한다.

무엇(WHAT): data/raw/matches_sample.jsonl(또는 지정 파일들)을 입력으로 받아
  각 레코드의 matchDate, matchInfo[].player[].spId를 이용해
  date(YYYY-MM-DD), spid 기준으로 pick_count를 세고, 같은 날짜의 sample_match_count도 함께 저장한다.
  결과는 SQLite daily_pick 테이블에 UPSERT한다.

어떻게(HOW):
  - 선수 필터: --players JSON/CSV가 주어지면 해당 spid만 집계(없으면 전체)
  - matchtype: 기본 50로 저장. --matchtype auto이면 경기별 matchType을 사용해 유형별로 분리 저장
  - 멱등성: visited_log 키 `dailypick:{date}:{matchtype}`로 중복 집계를 건너뛴다.
  - 무결성: 잘못된 JSON/필드 누락 레코드는 건너뛰고 경고 로그
  - 확장: --emit-csv로 결과 CSV 저장, --events와 --window로 이벤트 전후 비교용 CSV도 생성 가능
"""
from __future__ import annotations
import argparse, json, re
from pathlib import Path
from typing import Dict, Set, List, Any, Optional, Iterable, Tuple

from app.core.utils import log
from crawler.daily_trade.writer import connect, init_schema, is_visited, mark_visited
from crawler.daily_trade.writer import upsert_daily_trade  # noqa: F401 (참고용)
from crawler.daily_trade.writer import DB_PATH_DEFAULT


def _load_players(path: Optional[Path]) -> Set[int]:
    """선수 목록 로드 → spid 집합 반환

    왜: 특정 선수만 집계하여 대상이 아닌 선수 노이즈를 줄인다.
    무엇: JSON(list[dict]|list[int]) 또는 CSV(spid,name_kor,name_eng)
    어떻게: spid 컬럼/키를 찾아 int로 수집.
    """
    if not path:
        return set()
    if not path.exists():
        log(f"players 파일 없음: {path}", level="WARN"); return set()
    if path.suffix.lower() == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        out: Set[int] = set()
        if isinstance(data, list):
            for it in data:
                if isinstance(it, int):
                    out.add(int(it)); continue
                if isinstance(it, dict):
                    spid = it.get("spid") or it.get("id")
                    if spid is not None:
                        out.add(int(spid))
        return out
    # CSV
    import csv
    out: Set[int] = set()
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        spid_col = None
        for k in reader.fieldnames or []:
            kk = (k or "").strip().lower()
            if kk in ("spid", "id"):
                spid_col = k
                break
        for row in reader:
            v = row.get(spid_col) if spid_col else None
            if v:
                try: out.add(int(v))
                except Exception: pass
    return out


def _iter_jsonl(files: List[Path]) -> Iterable[Dict[str, Any]]:
    for fp in files:
        for line in fp.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line: continue
            try:
                yield json.loads(line)
            except Exception:
                log(f"JSON 파싱 실패: {fp}", level="WARN")


def aggregate(files: List[Path], player_filter: Set[int], matchtype_mode: str) -> Dict[tuple, Dict[str, int]]:
    """RAW JSONL로부터 (date, matchtype, spid) → {pick_count, sample_match_count}

    왜: 일별·선수별 사용 빈도를 계산해 시계열 테이블에 적재하기 위함.
    무엇: 각 경기마다 등장한 spid를 중복 없이 한 번만 세고, 날짜별 총 경기 수도 함께 세어 분모를 만든다.
    어떻게: matchtype은 기본 50 고정, auto이면 각 레코드의 matchType을 사용해 분리 저장.
    """
    out: Dict[tuple, Dict[str, int]] = {}
    for obj in _iter_jsonl(files):
        # 날짜 추출
        match_date = obj.get("matchDate") or obj.get("createDate")
        if not isinstance(match_date, str) or len(match_date) < 10:
            log("matchDate 누락", level="WARN"); continue
        date = match_date[:10]
        # matchtype
        mt = obj.get("matchType") if matchtype_mode == "auto" else 50
        try:
            mt = int(mt) if mt is not None else 0
        except Exception:
            mt = 0
        # 한 경기에서 중복 spid 제거
        spids: Set[int] = set()
        for team in obj.get("matchInfo", []) or []:
            for p in (team.get("player", []) or []):
                spid = p.get("spId") or p.get("spid")
                try:
                    spid = int(spid)
                except Exception:
                    continue
                if player_filter and spid not in player_filter:
                    continue
                spids.add(spid)
        if not spids:
            continue
        # 카운트 업데이트
        key_sample = (date, mt, None)
        rec_sample = out.setdefault(key_sample, {"pick_count": 0, "sample_match_count": 0})
        rec_sample["sample_match_count"] += 1
        for sp in spids:
            key = (date, mt, sp)
            rec = out.setdefault(key, {"pick_count": 0, "sample_match_count": 0})
            rec["pick_count"] += 1
    return out


def _write_csv(path: Path, rows: List[Dict[str, Any]], headers: List[str]) -> int:
    """CSV 쓰기(헤더 포함)

    왜: 대시보드/분석 초기 단계에서 DB 없이도 빠르게 결과를 확인하기 위함.
    무엇: 지정 헤더 순서로 행을 출력.
    어떻게: 존재하면 덮어쓴다.
    """
    import csv
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in headers})
    return len(rows)


def _load_events(path: Optional[Path]) -> List[Tuple[str, str]]:
    """이벤트 CSV 로드(date,name)

    왜: 빅매치 전후 비교를 자동화하기 위함.
    무엇: CSV 헤더에서 date,name(또는 event) 컬럼 읽기.
    어떻게: 형식이 다르면 빈 리스트 반환.
    """
    if not path or not path.exists():
        return []
    import csv
    out: List[Tuple[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        date_col, name_col = None, None
        for k in reader.fieldnames or []:
            kk = (k or "").strip().lower()
            if kk in ("date",):
                date_col = k
            if kk in ("name", "event"):
                name_col = k
        for row in reader:
            d = (row.get(date_col) or "").strip() if date_col else ""
            n = (row.get(name_col) or "").strip() if name_col else ""
            if d: out.append((d, n))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", nargs="+", default=["data/raw/matches_sample.jsonl"], help="입력 JSONL 파일 경로(복수 가능)")
    ap.add_argument("--players", help="대상 선수 목록(JSON/CSV)")
    ap.add_argument("--matchtype", default="50", help="집계 matchtype (정수) 또는 'auto'")
    ap.add_argument("--db", default=str(DB_PATH_DEFAULT))
    ap.add_argument("--force", action="store_true", help="visited_log를 무시하고 덮어쓰기")
    ap.add_argument("--emit-csv", type=str, help="집계 결과를 CSV로도 저장할 경로")
    ap.add_argument("--events", type=str, help="이벤트 CSV(date,name) 파일 경로")
    ap.add_argument("--window", type=int, default=7, help="이벤트 전후 비교 윈도우 일수")
    args = ap.parse_args()

    files = [Path(p) for p in args.raw]
    files = [p for p in files if p.exists()]
    if not files:
        raise SystemExit("입력 RAW 파일이 없습니다.")

    players_path = Path(args.players) if args.players else None
    player_filter = _load_players(players_path)
    matchtype_mode = "auto" if str(args.matchtype).lower() == "auto" else "fixed"

    agg = aggregate(files, player_filter, matchtype_mode)
    if not agg:
        log("집계 결과가 없습니다.", level="WARN"); return

    conn = connect(Path(args.db))
    init_schema(conn)

    # 날짜/매치타입별로 분할하여 UPSERT (visited 멱등)
    total = 0
    for (date, mt, spid), rec in agg.items():
        if spid is None:
            # 분모용 키(샘플 경기 수) — 저장은 각 선수 row에 반영
            continue
        key = f"dailypick:{date}:{int(mt)}"
        if not args.force and is_visited(conn, key):
            continue
        # 같은 date,mt의 sample_match_count를 찾아서 함께 저장
        sample = agg.get((date, mt, None), {}).get("sample_match_count", 0)
        # 단건 upsert를 위해 INSERT OR REPLACE 수행
        conn.execute(
            """
            INSERT OR REPLACE INTO daily_pick
            (date, spid, matchtype, pick_count, sample_match_count, source)
            VALUES(?,?,?,?,?, 'api')
            """,
            (date, int(spid), int(mt), int(rec["pick_count"]), int(sample)),
        )
        total += 1
        mark_visited(conn, key)
    conn.commit()
    log(f"daily_pick 업서트 완료: rows={total}")

    # (선택) CSV 출력: date, spid, matchtype, pick_count, sample_match_count, pick_rate
    if args.emit_csv:
        rows: List[Dict[str, Any]] = []
        for (date, mt, spid), rec in agg.items():
            if spid is None: continue
            sample = agg.get((date, mt, None), {}).get("sample_match_count", 0)
            pr = (rec["pick_count"]/sample) if sample else None
            rows.append({
                "date": date,
                "spid": spid,
                "matchtype": mt,
                "pick_count": rec["pick_count"],
                "sample_match_count": sample,
                "pick_rate": pr,
            })
        _write_csv(Path(args.emit_csv), rows, ["date","spid","matchtype","pick_count","sample_match_count","pick_rate"])

    # (선택) 이벤트 전후 비교 CSV: date,event,spid,pre_rate,post_rate,delta
    evs = _load_events(Path(args.events) if args.events else None)
    if evs:
        # 인메모리 agg로부터 pre/post 계산
        # 날짜 문자열 비교 간단화를 위해 그대로 사용(입력이 YYYY-MM-DD 형식임을 가정)
        from datetime import datetime, timedelta
        def d(s: str) -> datetime.date:
            return datetime.strptime(s, "%Y-%m-%d").date()
        # 그룹: (event_date, name, spid) → pre/post/delta
        out: List[Dict[str, Any]] = []
        # 사전: (date, mt, spid) → (pick_count, sample)
        # 여기서는 matchtype 무시(단일 50 사용 가정), 필요 시 확장 가능
        by_date_spid: Dict[Tuple[str,int], Tuple[int,int]] = {}
        for (date, mt, spid), rec in agg.items():
            if spid is None: continue
            sample = agg.get((date, mt, None), {}).get("sample_match_count", 0)
            by_date_spid[(date, spid)] = (rec["pick_count"], sample)
        for edate, ename in evs:
            try:
                e = d(edate)
            except Exception:
                continue
            pre_dates = {(e - timedelta(days=i)).isoformat() for i in range(1, args.window+1)}
            post_dates = {(e + timedelta(days=i)).isoformat() for i in range(0, args.window+1)}
            spids: Set[int] = {s for (_, s) in by_date_spid.keys()}
            for sp in sorted(spids):
                pre_pick = pre_samp = post_pick = post_samp = 0
                for dd in pre_dates:
                    pc, sm = by_date_spid.get((dd, sp), (0,0))
                    pre_pick += pc; pre_samp += sm
                for dd in post_dates:
                    pc, sm = by_date_spid.get((dd, sp), (0,0))
                    post_pick += pc; post_samp += sm
                pre_rate = (pre_pick/pre_samp) if pre_samp else None
                post_rate = (post_pick/post_samp) if post_samp else None
                delta = (post_rate - pre_rate) if (pre_rate is not None and post_rate is not None) else None
                out.append({
                    "event_date": edate,
                    "event_name": ename,
                    "spid": sp,
                    "pre_rate": pre_rate,
                    "post_rate": post_rate,
                    "delta_rate": delta,
                    "pre_matches": pre_samp,
                    "post_matches": post_samp,
                })
        # 저장 경로 기본값
        ev_path = Path("data/processed/daily_pick_event_compare.csv")
        _write_csv(ev_path, out, ["event_date","event_name","spid","pre_rate","post_rate","delta_rate","pre_matches","post_matches"])


if __name__ == "__main__":
    main()
