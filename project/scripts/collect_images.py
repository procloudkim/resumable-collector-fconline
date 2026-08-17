from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import json
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple, DefaultDict

import requests
from urllib.parse import urlparse
from threading import Semaphore, local


# -------- Helpers --------


def read_snapshots(dir_path: Path) -> Dict[str, object]:
    """Parse docs/check/*.html to collect hints and direct URLs.

    Returns dict with keys:
      - spid/nation/league/team/hosts: Set[str]
      - player_urls/nation_urls/league_urls/team_urls: Dict[str, List[str]]
    """
    from bs4 import BeautifulSoup  # lazy import

    res_sets: Dict[str, Set[str]] = {k: set() for k in ["spid", "nation", "league", "team", "hosts"]}
    res_maps: Dict[str, Dict[str, List[str]]] = {
        "player_urls": {},
        "nation_urls": {},
        "league_urls": {},
        "team_urls": {},
    }

    re_sp = re.compile(r"/players(?:Action)?/p(\d+)(?:_\d+)?\.png", re.I)
    re_nat = re.compile(r"/(?:countries|smallflags)/(\w+)\.png", re.I)
    re_lea = re.compile(r"/league/(?:dark|light)/[^/]+/(\w+)\.png", re.I)
    re_team = re.compile(r"/crests/(?:dark|light)/(?:small|large)/(\w+)\.png", re.I)
    re_host = re.compile(r"^https?://([^/]+)/")

    for f in sorted((dir_path or Path("docs/check")).glob("*.html")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        soup = BeautifulSoup(text, "html.parser")
        for img in soup.select("img[src]"):
            src: str = img.get("src", "")
            m = re_host.match(src)
            if m:
                res_sets["hosts"].add(m.group(1).lower())
            for rgx, key in ((re_sp, "spid"), (re_nat, "nation"), (re_lea, "league"), (re_team, "team")):
                m = rgx.search(src)
                if m:
                    code = m.group(1)
                    res_sets[key].add(code)
                    # store direct url
                    if key == "spid":
                        res_maps["player_urls"].setdefault(code, []).append(src)
                    elif key == "nation":
                        res_maps["nation_urls"].setdefault(code, []).append(src)
                    elif key == "league":
                        res_maps["league_urls"].setdefault(code, []).append(src)
                    elif key == "team":
                        res_maps["team_urls"].setdefault(code, []).append(src)
    res: Dict[str, object] = {}
    res.update(res_sets)
    res.update(res_maps)
    return res


def query_distinct(conn: sqlite3.Connection, col: str) -> Set[str]:
    cur = conn.cursor()
    cur.execute(f"SELECT DISTINCT {col} FROM best_price_daily WHERE {col} IS NOT NULL AND {col}<>''")
    return {str(r[0]) for r in cur.fetchall() if r and r[0] is not None}


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


@dataclass
class Task:
    key: str  # spid or code
    group: str  # players|nation|league|team
    variant: str  # base|base_24|action|action_24|small|dark|light|dark/small|...
    out: Path
    urls: Sequence[str]


_tls = local()


def _get_session(ua: str) -> requests.Session:
    s = getattr(_tls, "session", None)
    if s is None:
        s = requests.Session()
        s.headers.update({
            "User-Agent": ua,
            "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Referer": "https://fconline.nexon.com/",
        })
        adapter = requests.adapters.HTTPAdapter(pool_connections=8, pool_maxsize=16, max_retries=0)
        s.mount("http://", adapter)
        s.mount("https://", adapter)
        _tls.session = s
    return s


def attempt(urls: Sequence[str], out: Path, timeout: int, retry: int, ua: str, host_limits: Dict[str, Semaphore] | None = None) -> Tuple[bool, Optional[str], Optional[int]]:
    if out.exists() and out.stat().st_size > 0:
        return True, None, None  # skip
    ensure_dir(out.parent)
    sess = _get_session(ua)
    last_err: Optional[str] = None
    last_code: Optional[int] = None
    for _ in range(max(1, retry)):
        for url in urls:
            try:
                host = urlparse(url).hostname or ""
                sem = host_limits.get(host) if host_limits else None
                if sem:
                    sem.acquire()
                try:
                    r = sess.get(url, timeout=timeout)
                finally:
                    if sem:
                        sem.release()
                last_code = r.status_code
                if r.status_code == 200 and r.content:
                    out.write_bytes(r.content)
                    return True, None, last_code
            except Exception as e:  # noqa: BLE001
                last_err = type(e).__name__
        time.sleep(0.7)
    return False, last_err, last_code


def player_urls(spid: str, hosts: Sequence[str]) -> Dict[str, List[str]]:
    spid = str(spid)
    # 플레이어는 fo4/fco 우선, 스냅샷 호스트는 후순위
    pref = ["fo4.dn.nexoncdn.co.kr", "fco.dn.nexoncdn.co.kr"]
    host_candidates = list(dict.fromkeys(pref + [h for h in hosts if h]))
    def build(paths: Sequence[str]) -> List[str]:
        urls: List[str] = []
        for h in host_candidates:
            for p in paths:
                urls.append(f"https://{h}{p}")
        return urls

    return {
        "base": build([f"/live/externalAssets/common/players/p{spid}.png"]),
        "base_24": build([f"/live/externalAssets/common/players/p{spid}_24.png"]),
        "action": build([f"/live/externalAssets/common/playersAction/p{spid}.png"]),
        "action_24": build([f"/live/externalAssets/common/playersAction/p{spid}_24.png"]),
    }


def nation_urls(code: str, hosts: Sequence[str]) -> Dict[str, List[str]]:
    code_u = str(code).upper()
    code_l = str(code).lower()
    # 국기는 fco 우선
    pref = ["fco.dn.nexoncdn.co.kr", "fo4.dn.nexoncdn.co.kr"]
    host_candidates = list(dict.fromkeys(pref + [h for h in hosts if h]))
    def build(paths: Sequence[str]) -> List[str]:
        urls: List[str] = []
        for h in host_candidates:
            for p in paths:
                urls.append(f"https://{h}{p}")
        return urls

    return {
        "small": build([f"/live/externalAssets/common/countries/smallflags/{code_u}.png",
                         f"/live/externalAssets/common/metadata/countries/smallflags/{code_u}.png",
                         f"/live/externalAssets/common/countries/smallflags/{code_l}.png"]),
    }


def league_urls(code: str, hosts: Sequence[str]) -> Dict[str, List[str]]:
    code_u = str(code).upper(); code_l = str(code).lower()
    # 리그는 fo4 우선
    host_candidates = list(dict.fromkeys(["fo4.dn.nexoncdn.co.kr"] + [h for h in hosts if h]))
    def build(paths: Sequence[str]) -> List[str]:
        return [f"https://{h}{p}" for h in host_candidates for p in paths]
    return {
        "dark": build([f"/live/externalAssets/common/league/dark/ca/{code_l}.png",
                        f"/live/externalAssets/common/metadata/league/dark/{code_u}.png"]),
        "light": build([f"/live/externalAssets/common/league/light/ca/{code_l}.png",
                         f"/live/externalAssets/common/metadata/league/light/{code_u}.png"]),
    }


def team_urls(code: str, hosts: Sequence[str]) -> Dict[str, List[str]]:
    code_u = str(code).upper(); code_l = str(code).lower()
    # 팀 문장은 fo4 우선
    host_candidates = list(dict.fromkeys(["fo4.dn.nexoncdn.co.kr"] + [h for h in hosts if h]))
    def build(paths: Sequence[str]) -> List[str]:
        return [f"https://{h}{p}" for h in host_candidates for p in paths]
    return {
        "dark/small": build([f"/live/externalAssets/common/metadata/crests/dark/small/{code_u}.png",
                              f"/live/externalAssets/common/metadata/crests/dark/small/{code_l}.png"]),
        "dark/large": build([f"/live/externalAssets/common/metadata/crests/dark/large/{code_u}.png",
                              f"/live/externalAssets/common/metadata/crests/dark/large/{code_l}.png"]),
        "light/small": build([f"/live/externalAssets/common/metadata/crests/light/small/{code_u}.png",
                               f"/live/externalAssets/common/metadata/crests/light/small/{code_l}.png"]),
        "light/large": build([f"/live/externalAssets/common/metadata/crests/light/large/{code_u}.png",
                               f"/live/externalAssets/common/metadata/crests/light/large/{code_l}.png"]),
    }


def make_tasks(spids: Iterable[str], nations: Iterable[str], leagues: Iterable[str], teams: Iterable[str],
               hosts: Sequence[str], out_base: Path, only_variants: Optional[Set[str]] = None,
               snap_direct: Optional[Dict[str, Dict[str, List[str]]]] = None) -> List[Task]:
    tasks: List[Task] = []
    ov = {v.lower() for v in (only_variants or set())}
    # players
    for sp in spids:
        variants = player_urls(sp, hosts)
        # prepend snapshot direct links by variant if available
        if snap_direct and snap_direct.get("player_urls"):
            direct_urls = snap_direct["player_urls"].get(str(sp), [])
            if direct_urls:
                def classify_player(src: str) -> str:
                    s = src.lower()
                    if "/playersaction/" in s and "_24.png" in s:
                        return "action_24"
                    if "/playersaction/" in s:
                        return "action"
                    if "/players/" in s and "_24.png" in s:
                        return "base_24"
                    return "base"
                byv: DefaultDict[str, List[str]] = DefaultDict(list)
                for u in direct_urls:
                    byv[classify_player(u)].append(u)
                for vkey, urls in byv.items():
                    # put snapshot direct URLs first
                    variants[vkey] = list(dict.fromkeys(urls + variants.get(vkey, [])))
        for var, urls in variants.items():
            if ov and var.lower() not in ov:
                continue
            out = out_base / "players" / ("base" if var == "base" else var) / f"{sp}.png"
            tasks.append(Task(key=str(sp), group="players", variant=var, out=out, urls=urls))
    # nations
    for code in nations:
        variants = nation_urls(code, hosts)
        if snap_direct and snap_direct.get("nation_urls"):
            direct = snap_direct["nation_urls"].get(str(code), [])
            if direct:
                variants["small"] = list(dict.fromkeys(direct + variants.get("small", [])))
        for var, urls in variants.items():
            if ov and var.lower() not in ov:
                continue
            out = out_base / "logos" / "nation" / var / f"{str(code).upper()}.png"
            tasks.append(Task(key=str(code), group="nation", variant=var, out=out, urls=urls))
    # leagues
    for code in leagues:
        variants = league_urls(code, hosts)
        if snap_direct and snap_direct.get("league_urls"):
            direct = snap_direct["league_urls"].get(str(code), [])
            if direct:
                # 분류: dark/light
                darks = [u for u in direct if "/dark/" in u.lower()]
                lights = [u for u in direct if "/light/" in u.lower()]
                if darks:
                    variants["dark"] = list(dict.fromkeys(darks + variants.get("dark", [])))
                if lights:
                    variants["light"] = list(dict.fromkeys(lights + variants.get("light", [])))
        for var, urls in variants.items():
            if ov and var.lower() not in ov:
                continue
            out = out_base / "logos" / "league" / var / f"{str(code).upper()}.png"
            tasks.append(Task(key=str(code), group="league", variant=var, out=out, urls=urls))
    # teams
    for code in teams:
        variants = team_urls(code, hosts)
        if snap_direct and snap_direct.get("team_urls"):
            direct = snap_direct["team_urls"].get(str(code), [])
            if direct:
                def _team_variant(u: str) -> str:
                    s = u.lower()
                    a = "dark" if "/dark/" in s else "light"
                    b = "large" if "/large/" in s else "small"
                    return f"{a}/{b}"
                byv: DefaultDict[str, List[str]] = DefaultDict(list)
                for u in direct:
                    byv[_team_variant(u)].append(u)
                for vkey, urls0 in byv.items():
                    variants[vkey] = list(dict.fromkeys(urls0 + variants.get(vkey, [])))
        for var, urls in variants.items():
            if ov and var.lower() not in ov:
                continue
            parts = var.split("/")
            out = out_base / "logos" / "team" / Path(*parts) / f"{str(code).upper()}.png"
            tasks.append(Task(key=str(code), group="team", variant=var, out=out, urls=urls))
    return tasks


def update_db_paths(conn: sqlite3.Connection, base: Path) -> int:
    """Update *_logo_path and player_image_path with new standardized relative paths.
    Only fills when NULL or empty.
    """
    cur = conn.cursor()
    # player: prefer base variant
    # We store a representative variant path: players/base/{spid}.png
    base_players = str((base / 'players' / 'base').as_posix().rstrip('/'))
    cur.execute(
        "UPDATE best_price_daily SET player_image_path = CASE\n"
        "  WHEN player_image_path IS NULL OR player_image_path='' THEN ? || '/' || spid || '.png'\n"
        "  ELSE player_image_path END",
        (base_players,),
    )
    # For logos we cannot fill per-row without code in SQL expression easily; we do per-code updates
    updated = cur.rowcount
    for col, rel in (
        ("nation_logo_path", "logos/nation/small"),
        ("league_logo_path", "logos/league/dark"),
        ("team_logo_path", "logos/team/dark/small"),
    ):
        # Update using || concatenation with the code column
        code_col = col.replace("_logo_path", "_code")
        base_prefix = str((base / rel).as_posix().rstrip('/'))
        cur.execute(
            f"""
            UPDATE best_price_daily
               SET {col} = CASE
                 WHEN {col} IS NULL OR {col} = '' THEN ? || '/' || UPPER({code_col}) || '.png'
                 ELSE {col}
               END
            """,
            (base_prefix,),
        )
        updated += cur.rowcount
    conn.commit()
    return updated


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect player and logo images for best_price spIds and related codes")
    ap.add_argument("--db", type=Path, default=Path("project/db/best_price_new.db"))
    ap.add_argument("--snapshots", type=Path, default=Path("docs/check"))
    ap.add_argument("--out", type=Path, default=Path("data/images"))
    ap.add_argument("--threads", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=10)
    ap.add_argument("--retry", type=int, default=3)
    ap.add_argument("--status-every", type=int, default=10, help="seconds between progress prints (0 to disable)")
    ap.add_argument("--per-host", type=int, default=2, help="maximum concurrent connections per host")
    ap.add_argument("--preset", type=str, choices=["quiet","balanced","fast"], default="balanced", help="리소스 사용 프리셋")
    ap.add_argument("--shuffle", action="store_true", help="작업 순서를 무작위로 섞어 조기 성공률 향상")
    ap.add_argument("--only-variants", type=str, default="", help="comma list to restrict variants (e.g., base,action,small,dark)")
    ap.add_argument("--codes-source", type=str, default="auto", choices=["auto","snapshot","db","union"],
                    help="코드 소스 선택: snapshot(스냅샷 코드만), db(DB 코드만), union(합집합), auto(로고=스냅샷, 플레이어=DB)")
    ap.add_argument("--update-db-paths", action="store_true")
    ap.add_argument("--missing-csv", type=Path, default=Path("data/reports/missing_images.csv"))
    ap.add_argument("--log-jsonl", type=Path, default=Path("logs/images_fetch.jsonl"))
    ap.add_argument("--dry-run", action="store_true")
    ns = ap.parse_args()

    ensure_dir(ns.out)
    ensure_dir(ns.missing_csv.parent)
    ensure_dir(ns.log_jsonl.parent)

    conn = sqlite3.connect(ns.db)
    spids_db = sorted(query_distinct(conn, "spid"))
    nations_db = sorted(query_distinct(conn, "nation_code"))
    leagues_db = sorted(query_distinct(conn, "league_code"))
    teams_db = sorted(query_distinct(conn, "team_code"))

    hints = read_snapshots(ns.snapshots) if ns.snapshots.exists() else {k: set() for k in ["spid","nation","league","team","hosts"]}
    hosts = sorted(hints.get("hosts", set()))

    # 코드 소스 결정
    def choose(src: str, db_vals: Sequence[str], snap_vals: Sequence[str]) -> List[str]:
        if src == "db":
            return list(db_vals)
        if src == "snapshot":
            return list(snap_vals)
        if src == "union":
            return sorted(set(db_vals) | set(snap_vals))
        return list(db_vals)  # fallback

    # auto 모드: 플레이어=DB, 로고=스냅샷
    codes_src = ns.codes_source
    spids = spids_db
    nations = choose("snapshot" if codes_src == "auto" else codes_src, nations_db, sorted(hints.get("nation", set())))
    leagues = choose("snapshot" if codes_src == "auto" else codes_src, leagues_db, sorted(hints.get("league", set())))
    teams = choose("snapshot" if codes_src == "auto" else codes_src, teams_db, sorted(hints.get("team", set())))

    only_variants = {v.strip().lower() for v in ns.only_variants.split(',') if v.strip()}
    snap_map = {
        "player_urls": hints.get("player_urls", {}) if isinstance(hints.get("player_urls", {}), dict) else {},
        "nation_urls": hints.get("nation_urls", {}) if isinstance(hints.get("nation_urls", {}), dict) else {},
        "league_urls": hints.get("league_urls", {}) if isinstance(hints.get("league_urls", {}), dict) else {},
        "team_urls": hints.get("team_urls", {}) if isinstance(hints.get("team_urls", {}), dict) else {},
    }
    tasks = make_tasks(spids, nations, leagues, teams, hosts, ns.out, only_variants if only_variants else None, snap_map)
    if ns.shuffle:
        import random
        random.shuffle(tasks)
    total = len(tasks)

    # Execute
    ok = fail = skip = done = 0
    missing: List[Tuple[str, str, str, str, str, Optional[int]]] = []  # group,key,variant,out,err,code
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) fc-online-lab/1.1"

    # 호스트별 동시성 제한
    host_limits: Dict[str, Semaphore] = {}
    for h in (hosts + ["fo4.dn.nexoncdn.co.kr", "fco.dn.nexoncdn.co.kr"]):
        if h and h not in host_limits:
            host_limits[h] = Semaphore(max(1, ns.per_host))

    # 프리셋 적용(사용자가 명시값을 주지 않은 경우만 완만하게 조정)
    if ns.preset == "fast":
        if ns.per_host == 2:
            for h in host_limits:
                host_limits[h] = Semaphore(3)
        if ns.timeout == 10:
            ns.timeout = 8
        if ns.retry == 3:
            ns.retry = 1
    elif ns.preset == "quiet":
        if ns.per_host == 2:
            for h in host_limits:
                host_limits[h] = Semaphore(1)
        if ns.timeout == 10:
            ns.timeout = 12

    if ns.dry_run:
        print(f"[드라이런] 작업={len(tasks)} spids={len(spids)} 국가코드={len(nations)} 리그코드={len(leagues)} 팀코드={len(teams)} 호스트={hosts}")
        return 0

    with ns.log_jsonl.open("a", encoding="utf-8") as logf:
        start_ts = time.time()
        from threading import Event, Lock, Thread
        lock = Lock()
        stop_evt = Event()

        def reporter() -> None:
            if ns.status_every <= 0:
                return
            while not stop_evt.wait(ns.status_every):
                with lock:
                    elapsed = max(0.001, time.time() - start_ts)
                    rate = done / elapsed
                    remain = max(0, total - done)
                    eta = (remain / rate) if rate > 0 else 0
                    pct = (done / total * 100.0) if total else 100.0
                    print(f"[진행] 완료={done}/{total}({pct:.1f}%) 성공={ok} 실패={fail} 건너뜀={skip} 처리속도={rate:.1f}/초 남은시간≈{int(eta)}초")
        log_lock = Lock()

        def run_one(t: Task) -> Tuple[int, int, int]:
            nonlocal ok, fail, skip, done
            if t.out.exists() and t.out.stat().st_size > 0:
                with lock:
                    skip += 1
                    done += 1
                return 0, 0, 1
            success, err, code = attempt(t.urls, t.out, ns.timeout, ns.retry, ua, host_limits)
            rec = {
                "ts": time.time(),
                "group": t.group,
                "key": t.key,
                "variant": t.variant,
                "out": str(t.out.as_posix()),
                "urls": list(t.urls),
                "ok": success,
                "status": code,
                "error": err,
            }
            with log_lock:
                logf.write(json.dumps(rec, ensure_ascii=False) + "\n")
                logf.flush()
            if success:
                with lock:
                    ok += 1
                    done += 1
                return 1, 0, 0
            else:
                with lock:
                    fail += 1
                    done += 1
                missing.append((t.group, t.key, t.variant, t.out.as_posix(), err or "http_error", code))
                return 0, 1, 0

        rep_thr: Optional[Thread] = None
        if ns.status_every > 0:
            rep_thr = Thread(target=reporter, daemon=True)
            rep_thr.start()
        try:
            with cf.ThreadPoolExecutor(max_workers=max(1, ns.threads)) as ex:
                list(ex.map(run_one, tasks))
        except KeyboardInterrupt:
            print("\n[중단] 사용자 인터럽트 감지. 현재까지 진행분을 저장합니다...")
            stop_evt.set()
            if rep_thr:
                rep_thr.join(timeout=2)
        finally:
            stop_evt.set()
            if rep_thr:
                rep_thr.join(timeout=2)

    # Write missing report
    with ns.missing_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group", "key", "variant", "out_path", "error", "http_status"])  # header
        for row in missing:
            w.writerow(row)

    elapsed = max(0.001, time.time() - start_ts)
    # 오류 상위 원인 집계
    from collections import Counter
    reasons = Counter((r[4] or "http_error") for r in missing)
    top = ", ".join([f"{k}:{v}" for k, v in reasons.most_common(3)]) if reasons else "-"
    print(f"[완료] 전체작업={total} 성공={ok} 실패={fail} 건너뜀={skip} 소요={elapsed:.1f}초 누락리포트={ns.missing_csv}")
    print(f"[요약] 오류 Top: {top}")

    if ns.update_db_paths:
        updated = update_db_paths(conn, ns.out)
        print(f"[DB] paths updated rows={updated}")

    conn.close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
