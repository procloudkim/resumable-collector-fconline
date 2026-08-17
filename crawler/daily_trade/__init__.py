"""
crawler.daily_trade 패키지

왜(WHY): 넥슨 FIFA Online 4 데이터센터(https://fconline.nexon.com/datacenter)의 일별 거래
데이터를 신뢰성 있게 수집해 분석 파이프라인을 보완하기 위함이다(OpenAPI 보조 채널).

무엇(WHAT): 정적 HTML 크롤링으로 일자별 거래/픽률 데이터를 파싱하여 다음 테이블을 채운다.
- daily_trade: 일자/선수별 가격/거래량/최대 강화
- daily_top_players: 일자별 TopN 선수와 픽률
- visited_log: 요청/작업 단위 방문 키(멱등성)

어떻게(HOW): fetcher(HTTP) → parser(BeautifulSoup) → writer(SQLite/CSV) 순서로 구성한다.
setup_logger()로 파일/콘솔 동시 로그(회전)와 구조적 로그를 활성화한다.
"""
from __future__ import annotations
from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone, timedelta

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = LOG_DIR / "daily_trade.log"


class _ISO8601Formatter(logging.Formatter):
    """ISO8601 formatter with explicit timezone control.

    tz_mode: 'UTC' for Z-suffix, 'KST' for +09:00
    """
    def __init__(self, *args, tz_mode: str = "UTC", **kwargs):
        super().__init__(*args, **kwargs)
        self._tz_mode = tz_mode.upper()

    def formatTime(self, record, datefmt=None):  # noqa: N802
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        if self._tz_mode == "KST":
            dt = dt.astimezone(timezone(timedelta(hours=9)))
        if datefmt:
            return dt.strftime(datefmt)
        s = dt.isoformat(timespec="seconds")
        if self._tz_mode == "UTC":
            return s.replace("+00:00", "Z")
        return s


def setup_logger(name: str = "crawler.daily_trade", level: int = logging.INFO) -> logging.Logger:
    """크롤러 전용 로거 생성

    왜(WHY): 크롤링은 네트워크/파싱 실패가 잦으므로, 파일+콘솔에 구조적 로그를 남겨야
    운영 중 재현 및 회고가 가능하다.

    무엇(WHAT): 회전 파일 로그(5MB×3) + 콘솔 로그, 중복 핸들러 방지, 상위 전파 차단.

    어떻게(HOW): RotatingFileHandler와 StreamHandler를 등록하고, 프로세스/스레드 식별과 함께
    `ts level name pid message` 포맷으로 출력한다.
    """
    logger = logging.getLogger(name)
    if logger.handlers:  # 이미 설정됨
        logger.setLevel(level)
        return logger

    logger.setLevel(level)
    # File handler (UTC, ISO8601 Z)
    fmt_utc = _ISO8601Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s pid=%(process)d %(message)s",
        tz_mode="UTC",
    )
    fh = RotatingFileHandler(LOG_PATH, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8")
    fh.setFormatter(fmt_utc)
    # Console handler (KST display)
    fmt_kst = _ISO8601Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s pid=%(process)d %(message)s",
        tz_mode="KST",
    )
    ch = logging.StreamHandler()
    ch.setFormatter(fmt_kst)
    logger.addHandler(fh)
    logger.addHandler(ch)
    logger.propagate = False  # 상위 로거로 중복 전파 방지
    return logger


__all__ = [
    "setup_logger",
    "LOG_PATH",
]
