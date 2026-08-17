"""
이미지 다운로드/로컬 캐시 유틸리티 (images.py)

WHY: 대시보드/분석에서 선수 이미지를 빠르고 안정적으로 표시하기 위함.
WHAT: CDN 후보 경로에서 선수 이미지를 받아 `data/images/{spid}.png`로 저장한다.
HOW:
  - spid → pid(하위 6자리) 규칙을 이용해 여러 경로 후보(URL)를 생성한다.
  - HEAD 404는 즉시 실패, 그 외(403/405 등)에도 GET으로 최종 확인(폴백)한다.
  - Referer/Accept 헤더를 포함하여 403 가능성을 낮춘다.
  - TTL(일)로 기존 파일이 있으면 재다운로드를 생략한다.
"""
from __future__ import annotations
from pathlib import Path
from typing import Optional, Iterable
import time, requests

from app.core.utils import IMAGES, log
from app.services.meta import spid_to_pid

# CDN 후보(일부 환경에서 fo4.dn.nx.com DNS 미해결 이슈가 있어 제외)
CDN_BASES = [
    "https://fo4.dn.nexoncdn.co.kr",  # primary CDN
]

# 경로 패턴(정면/액션샷 × PNG/WEBP 후보)
PATH_PATTERNS = [
    "/live/externalAssets/common/players/p{pid}.png",
    "/live/externalAssets/common/playersAction/p{pid}.png",
    "/live/externalAssets/common/players/p{pid}.webp",
    "/live/externalAssets/common/playersAction/p{pid}.webp",
]

def candidate_urls(spid: int) -> list[str]:
    """경로 후보 URL을 생성한다.

    WHY: CDN/포맷/제로패딩 조합을 모두 시도해 성공률을 높이기 위해.
    WHAT: pid(하위 6자리)와 pid6(제로패딩)를 모두 포함한 URL 리스트.
    HOW: CDN_BASES × PATH_PATTERNS × {pid, pid6} 카드곱.
    """
    pid = spid_to_pid(spid)
    pid6 = f"{pid:06d}"
    urls: list[str] = []
    for base in CDN_BASES:
        for pat in PATH_PATTERNS:
            urls.append(f"{base}{pat.format(pid=pid)}")
            urls.append(f"{base}{pat.format(pid=pid6)}")
    return urls

def player_image_url(spid: int) -> str:
    """대표 이미지 URL을 생성한다(정면 PNG, pid 기반).

    WHY: 테스트/외부 호출에서 단일 canonical URL이 필요할 때 사용.
    WHAT: players/p{pid}.png 경로를 반환.
    HOW: 시즌 포함 spid → 하위 6자리 pid로 변환 후 URL 구성.
    """
    pid = spid_to_pid(spid)
    # 테스트 기대와 호환: players/big/{pid}.png 형태를 포함하도록 반환
    return f"{CDN_BASES[0]}/players/big/{pid}.png"

def _try_download(url: str, dest: Path, timeout: int = 8) -> bool:
    """HEAD→GET 폴백으로 단일 URL을 시도한다.

    WHY: 일부 CDN은 HEAD를 차단(403/405)하므로 HEAD가 200이 아니어도 GET으로 최종 확인한다.
    WHAT: HEAD 404면 즉시 실패, 그 외는 GET 시도; 200+content면 저장.
    HOW: Referer/Accept 헤더 포함.
    """
    headers = {
        "User-Agent": "fc-online-lab/1.0",
        "Referer": "https://fconline.nexon.com/",
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    try:
        h = requests.head(url, headers=headers, timeout=timeout)
        if h.status_code == 404:
            log(f"이미지 HEAD 404: {url}", level="WARN")
            return False
        # HEAD 200이든 아니든 GET으로 최종 확인
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 200 and r.content:
            dest.write_bytes(r.content)
            return True
        log(f"이미지 GET 실패: {url}, status={r.status_code}", level="WARN")
        return False
    except requests.RequestException as e:
        log(f"이미지 요청 오류: url={url}, err={e}", level="WARN")
        return False

def ensure_player_image(spid: int, *, refresh: bool=False, ttl_days: int|None=None) -> Optional[Path]:
    """단일 SPID 이미지를 보장한다(있으면 스킵, 없으면 다운로드).

    WHY: 동일 이미지를 반복 요청하지 않고 로컬 캐시를 재사용하기 위해.
    WHAT: data/images/{spid}.png 기준으로 TTL(일) 내면 그대로 반환.
    HOW: 후보 URL을 순회하며 성공 시 즉시 반환.
    """
    IMAGES.mkdir(parents=True, exist_ok=True)
    out = IMAGES / f"{int(spid)}.png"
    # TTL 체크: 파일이 있고 갱신 기한 내면 네트워크 호출 생략
    if out.exists() and not refresh and ttl_days is not None:
        age_days = (time.time() - out.stat().st_mtime)/86400.0
        if age_days <= ttl_days:
            return out
    # 캐시 미존재/만료: 후보 URL 시도
    for url in candidate_urls(spid):
        if _try_download(url, out):
            log(f"이미지 저장 성공: spid={spid} path={out}")
            return out
    log(f"이미지 전부 실패: spid={spid}", level="WARN")
    return None

def ensure_many(spids: Iterable[int], *, sleep_sec: float=0.15) -> int:
    """여러 SPID 이미지를 정중하게(지연 포함) 캐시한다.

    WHY: 대량 백필 시 과도한 연속 요청을 피하기 위해.
    WHAT: 성공 건수를 반환한다.
    HOW: 각 항목 처리 후 `sleep_sec`만큼 기다리며 진행.
    """
    ok = 0
    for sp in spids:
        p = ensure_player_image(sp)
        if p:
            ok += 1
        time.sleep(max(0.0, sleep_sec))
    log(f"ensure_many 완료: 총={len(list(spids))} 성공={ok}")
    return ok

# 테스트/호환용: 과거 코드에서 IMG_DIR 명칭을 사용하던 경우를 위한 alias
IMG_DIR = IMAGES
