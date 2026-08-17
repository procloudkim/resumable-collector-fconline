from __future__ import annotations
import random
import time
from typing import Optional
import requests

from . import setup_logger

BASE = "https://fconline.nexon.com/datacenter/dailytrade"


def polite_sleep(min_s: float = 1.0, max_s: float = 3.0) -> None:
    """폴라이트 슬립(1~3초 랜덤)

    왜(WHY): 데이터센터는 정적 페이지지만 과도한 빈도로 접근하면 차단될 수 있다.
    무엇(WHAT): 각 요청 간 임의의 지연을 추가해 서버 부하를 완화한다.
    어떻게(HOW): [min_s, max_s] 범위에서 균등분포로 지연을 선택하고 로그로 남긴다.
    """
    delay = random.uniform(min_s, max_s)
    setup_logger().info("event=sleep_polite seconds=%.2f", delay)
    time.sleep(delay)


def get_dailytrade_page(date_str: str, *, session: Optional[requests.Session] = None, timeout: int = 10):
    """일별 거래 페이지 HTML을 가져온다.

    왜(WHY): 파서가 정적 HTML에서 표 데이터를 추출하기 위해 원문 HTML이 필요하다.
    무엇(WHAT): `strDate=YYYY-MM-DD` 쿼리 파라미터로 대상 일자의 HTML을 GET.
    어떻게(HOW): User-Agent/타임아웃을 설정하고, 3회까지 지수 백오프로 재시도한다.
    요청 간 폴라이트 슬립(1~3초)을 적용하며, 각 단계별 로그를 남긴다.
    """
    logger = setup_logger()
    owns_session = False
    if session is None:
        session = requests.Session()
        owns_session = True

    url = f"{BASE}?strDate={date_str}"
    headers = {
        "User-Agent": "fc-online-lab/1.0 (+crawler.daily_trade)"
    }

    try:
        for attempt in range(3):
            if attempt > 0:
                backoff = min(0.5 * (2 ** (attempt - 1)), 2.0)
                logger.warning("event=retry url=%s attempt=%d wait=%.2fs", url, attempt, backoff)
                time.sleep(backoff)
            logger.info("event=fetch url=%s date=%s attempt=%d", url, date_str, attempt + 1)
            try:
                t0 = time.perf_counter()
                resp = session.get(url, headers=headers, timeout=timeout)
                elapsed = (time.perf_counter() - t0) * 1000.0
                status = resp.status_code
                logger.info(
                    "event=fetch_done url=%s date=%s status=%s bytes=%d elapsed_ms=%.1f",
                    url, date_str, status, len(resp.content), elapsed,
                )
                if status == 200 and resp.text:
                    return resp.text
                if status >= 500:
                    continue
                # 4xx는 재시도 가치 낮으나, 429는 서버 정책상 잠시 대기 후 재시도
                if status == 429:
                    continue
                break
            except requests.RequestException as e:
                logger.exception("event=fetch_error url=%s date=%s", url, date_str)
                continue
            finally:
                polite_sleep()
    finally:
        if owns_session:
            session.close()

    logger.warning("event=fetch_failed url=%s date=%s", url, date_str)
    return ""


def get_dailytrade_page_via_selenium(date_str: str, *, driver: object, pause_on_captcha: bool = False) -> str:
    """Fetch dailytrade page HTML using a Selenium driver with light interaction.

    - Try both 'YYYY-MM-DD' and 'YYYY.MM.DD' for strDate.
    - Attempt to click '이적'/'거래'/'강화' tab if present.
    - Wait for typical table/grid selectors.
    """
    logger = setup_logger()
    try:
        from crawler.selenium_utils import (
            wait_for_any_css,
            click_first_by_text,
            detect_captcha,
            install_overlay_blocker,
            remove_elements,
            aggressive_kill_overlays,
            preinstall_overlay_kill_on_new_document,
        )  # type: ignore
    except Exception:
        wait_for_any_css = None  # type: ignore
        click_first_by_text = None  # type: ignore
        detect_captcha = None  # type: ignore
        install_overlay_blocker = None  # type: ignore
        remove_elements = None  # type: ignore
        aggressive_kill_overlays = None  # type: ignore
        preinstall_overlay_kill_on_new_document = None  # type: ignore

    for ds in (date_str, date_str.replace("-", ".")):
        url = f"{BASE}?strDate={ds}"
        try:
            logger.info("event=fetch_selenium url=%s date=%s", url, ds)
            # Preinstall overlay killer so banner never shows at T=0
            if preinstall_overlay_kill_on_new_document:
                try:
                    preinstall_overlay_kill_on_new_document(driver, [
                        '.iconMatchFixedBanner',
                        '.iconMatchFixedBanner.sub',
                        '.iconmatchfixedbanner',
                        "[class*='iconMatchFixedBanner']",
                    ])
                except Exception:
                    pass
            driver.get(url)
            # Kill sliding bottom popup persistently
            if install_overlay_blocker:
                try:
                    install_overlay_blocker(driver, [
                        '.iconMatchFixedBanner',
                        '.iconmatchfixedbanner',
                    ])
                except Exception:
                    pass
            if aggressive_kill_overlays:
                try:
                    aggressive_kill_overlays(driver, [
                        '.iconMatchFixedBanner',
                        '.iconmatchfixedbanner',
                    ], duration_ms=15000, period_ms=250)
                except Exception:
                    pass
            # Optional: click trade tab if present
            if click_first_by_text:
                try:
                    click_first_by_text(driver, ["이적", "거래", "강화"])
                except Exception:
                    pass
            # Wait for content
            time.sleep(0.8)
            if wait_for_any_css:
                try:
                    wait_for_any_css(driver, [
                        "#divBestTradeArea_price .swiper-slide",
                        "#divBestTradeArea_grade .swiper-slide",
                        "#divEnchanceArea_price .swiper-slide",
                        "#divEnchanceArea_grade .swiper-slide",
                        "table", ".tbl table", "div.table", "div.tbody .tr", "ul li"
                    ], timeout=12)
                except Exception:
                    pass
            # Best-effort scroll to trigger lazy render
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2)")
                time.sleep(0.6)
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(0.6)
                # Re-kill overlays that might have re-appeared
                if remove_elements:
                    remove_elements(driver, ['.iconMatchFixedBanner'])
            except Exception:
                pass
            html = getattr(driver, "page_source", "") or ""
            # CAPTCHA 감지 시 대처
            if detect_captcha and detect_captcha(html):
                logger.warning("event=captcha_detected date=%s", ds)
                if pause_on_captcha:
                    logger.info("event=captcha_wait msg=Solve CAPTCHA in the opened browser, then press Enter here")
                    try:
                        input("[CAPTCHA] 브라우저에서 인증을 완료한 뒤 Enter를 눌러 계속합니다...")
                        time.sleep(1.0)
                        html = getattr(driver, "page_source", "") or ""
                    except Exception:
                        pass
            if html:
                polite_sleep()
                return html
        except Exception:
            logger.exception("event=selenium_error url=%s date=%s", url, ds)
            polite_sleep()
    logger.warning("event=fetch_failed_selenium date=%s", date_str)
    return ""


def get_dailytrade_page_any(
    date_str: str,
    *,
    use_selenium: bool = False,
    driver: object | None = None,
    session: Optional[requests.Session] = None,
    timeout: int = 10,
    pause_on_captcha: bool = False,
) -> str:
    """Convenience wrapper: choose Selenium or requests path."""
    if use_selenium and driver is not None:
        return get_dailytrade_page_via_selenium(date_str, driver=driver, pause_on_captcha=pause_on_captcha)
    return get_dailytrade_page(date_str, session=session, timeout=timeout)
