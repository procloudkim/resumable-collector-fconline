# scripts/fetch_fc.py
"""
목적: Nexon FC온라인 API에서 최근 매치 상세를 수집하여 raw JSONL로 저장
- 실행 중 상황을 print 로그로 모두 보여준다.
- 요청 실패/지연에 대비해 재시도/백오프를 붙였다.
- Ctrl+C(KeyboardInterrupt) 시에도 현재까지 수집분을 안전하게 저장한다.
- TDD: 핵심 함수는 순수함수/작은 단위로 나눠서 테스트 가능하도록 분리.
"""

from pathlib import Path
import json
import time
import argparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.core.utils import API_KEY, RAW, ensure_dirs, log  # 공통 유틸

BASE = "https://open.api.nexon.com"
HDRS = {"x-nxopen-api-key": API_KEY}  # 요청 헤더

# ---------------------------
# 세션/재시도 설정
# ---------------------------
def build_session() -> requests.Session:
    """[HTTP] 재시도/백오프가 적용된 Session 생성"""
    retry = Retry(
        total=5,                      # 총 재시도 횟수
        backoff_factor=0.6,           # 0.6, 1.2, 2.4 ... (지수 백오프)
        status_forcelist=[429, 500, 502, 503, 504],  # 재시도할 HTTP 코드
        allowed_methods=["GET"],      # 재시도 허용 메소드
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s = requests.Session()
    s.headers.update(HDRS)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s

SESSION = build_session()

def _get(url: str, params: dict, *, timeout=(5, 20)) -> requests.Response:
    """[HTTP] 공통 GET 호출 with 로그"""
    log(f"GET {url} params={params}")
    r = SESSION.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r

# ---------------------------
# API 래퍼 (단위 테스트 용이)
# ---------------------------
def get_ouid(nickname: str) -> str:
    """닉네임 → OUID"""
    url = f"{BASE}/fconline/v1/id"
    r = _get(url, {"nickname": nickname})
    ouid = r.json().get("ouid")
    if not ouid:
        log(f"닉네임 '{nickname}'의 OUID를 찾지 못했습니다.", level="WARN")
    else:
        log(f"닉네임 '{nickname}' → OUID {ouid}")
    return ouid

def get_user_match_ids(ouid: str, *, matchtype: int = 50, limit: int = 100, offset: int = 0):
    """유저 매치 ID 목록 조회"""
    url = f"{BASE}/fconline/v1/user/match"
    params = {"ouid": ouid, "matchtype": matchtype, "limit": limit, "offset": offset}
    r = _get(url, params)
    ids = r.json()
    log(f"match_ids {len(ids)}개 반환 (offset={offset})")
    return ids

def get_match_detail(matchid: str) -> dict:
    """매치 상세 조회"""
    url = f"{BASE}/fconline/v1/match-detail"
    r = _get(url, {"matchid": matchid})
    return r.json()

def dump_jsonl(objs: list[dict], outpath: Path) -> Path:
    """JSONL 저장 (append 모드)"""
    with outpath.open("a", encoding="utf-8") as f:
        for obj in objs:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    return outpath

# ---------------------------
# 고수준 수집 함수 (루프/로깅/안전종료)
# ---------------------------
def fetch_sample_by_nicknames(nicknames: list[str], *, pages: int = 1, sleep_s: float = 0.2) -> Path:
    """
    랭커 일부 표본 닉네임 목록을 받아 최근 매치 상세를 raw JSONL로 저장.
    - pages=1이면 유저당 최대 100경기
    - 안전을 위해 매치 상세는 일정 간격으로 저장(append)
    """
    ensure_dirs()

    if not API_KEY:
        log("API_KEY가 비어 있습니다. .env를 확인하세요.", level="ERROR")
        raise SystemExit(1)

    out = RAW / "matches_sample.jsonl"
    temp_buffer: list[dict] = []
    success_cnt = 0
    error_cnt = 0

    log(f"수집 시작: 닉네임 {len(nicknames)}명, pages={pages}")
    log(f"저장 경로: {out}")

    try:
        for idx, nick in enumerate(nicknames, start=1):
            log(f"[{idx}/{len(nicknames)}] 닉네임 '{nick}' 처리 시작")
            ouid = get_ouid(nick)
            if not ouid:
                error_cnt += 1
                continue

            for p in range(pages):
                ids = get_user_match_ids(ouid, matchtype=50, limit=100, offset=p*100)
                if not ids:
                    log(f"닉네임 '{nick}' p={p}: 추가 match 없음 → 다음 유저로")
                    break

                for n, mid in enumerate(ids, start=1):
                    try:
                        detail = get_match_detail(mid)
                        temp_buffer.append(detail)
                        success_cnt += 1
                        # 50건마다 중간 저장 (안전성/가시성)
                        if len(temp_buffer) >= 50:
                            dump_jsonl(temp_buffer, out)
                            log(f"중간 저장(50건): 누적 저장 {success_cnt}건")
                            temp_buffer.clear()
                        # 호출 간격
                        time.sleep(sleep_s)
                        # 진행 로그 (10건마다)
                        if n % 10 == 0:
                            log(f"  진행률: {n}/{len(ids)} (p={p})")
                    except requests.HTTPError as e:
                        error_cnt += 1
                        log(f"HTTPError(matchid={mid}): {e}", level="WARN")
                    except requests.RequestException as e:
                        error_cnt += 1
                        log(f"RequestException(matchid={mid}): {e}", level="WARN")

        # 남은 버퍼 저장
        if temp_buffer:
            dump_jsonl(temp_buffer, out)
            log(f"마지막 버퍼 저장: 누적 저장 {success_cnt}건")
            temp_buffer.clear()

        log(f"수집 완료: 성공 {success_cnt}건, 에러 {error_cnt}건")
        return out

    except KeyboardInterrupt:
        # Ctrl+C 시에도 확보한 데이터는 저장
        if temp_buffer:
            dump_jsonl(temp_buffer, out)
            log(f"[중단] 마지막 버퍼 저장: 누적 저장 {success_cnt}건", level="WARN")
        log("[중단] 사용자 인터럽트로 수집 종료", level="WARN")
        return out

# ---------------------------
# CLI 엔트리포인트 (TDD: 파라미터 주입/작게 실행)
# ---------------------------
def main():
    parser = argparse.ArgumentParser(description="FC온라인 샘플 수집")
    parser.add_argument("--nick", nargs="*", default=["DNFJade", "Hoonsbox", "리바이브칠공일" , "NSTK777" , "에넬" , "DRXLight" , "KDF정성민" , "UnLMTD영환" , "NSRimGC", "Volition태산"], help="수집할 닉네임 목록")
    parser.add_argument("--pages", type=int, default=1, help="유저당 페이지 수(1페이지=최대 100경기)")
    args = parser.parse_args()

    log(f"실행 파라미터: nick={args.nick}, pages={args.pages}")
    path = fetch_sample_by_nicknames(args.nick, pages=args.pages)
    log(f"결과 파일: {path}")

if __name__ == "__main__":
    main()
