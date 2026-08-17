from __future__ import annotations

"""
페이지 Fetcher (정적 요청 우선 → 실패 시 Selenium)

WHY: 정적 요청(requests)이 가볍고 빠르다. 불가피할 때만 Selenium으로 승급하는 것이 안전/효율적이다.
HOW: get_page_requests()로 먼저 시도 후 빈 결과면 Selenium 경로로 승급한다.
     성능 A: WebDriver 재사용(한 번 생성해 날짜 반복 사용), pageLoadStrategy='eager'
     성능 B: CDP로 이미지/CSS/폰트 등 리소스 차단(브라우저는 가볍게, 이미지는 HTTP로 별도 다운로드)
"""

import time
from typing import Optional

import requests


BASE = "https://fconline.nexon.com/datacenter/dailytrade"


def get_page_requests(date_str: str, *, timeout: int = 15, retry: int = 3, sleep_min: float = 0.3, sleep_max: float = 1.0) -> str:
    import random

    """
    WHY: 정적 요청 경로. 429/오류 시 재시도/백오프. 요청 간 랜덤 슬립으로 차단 리스크 완화.
    HOW: /datacenter/dailytrade?strDate=YYYY-MM-DD를 GET, 200 & 본문이면 반환.
    """
    session = requests.Session()
    url = f"{BASE}?strDate={date_str}"
    headers = {"User-Agent": "bestprice-crawler/1.0 (+requests)"}
    for i in range(retry):
        try:
            r = session.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200 and r.text:
                time.sleep(random.uniform(sleep_min, sleep_max))
                return r.text
        except requests.RequestException:
            pass
        time.sleep(min(0.5 * (2 ** i), 2.0))
    return ""


def create_driver(*, headless: bool = True, optimize_b: bool = True, timeout: int = 20):
    """
    WHY: Selenium 드라이버 생성 시 재사용을 전제로 가볍고 안정적으로 구성한다.
    HOW: headless 기본, pageLoadStrategy='eager', CDP로 불필요 리소스 차단(optimize_b).
    """
    from selenium import webdriver  # type: ignore
    from selenium.webdriver.chrome.options import Options  # type: ignore
    from selenium.webdriver.chrome.service import Service  # type: ignore
    from webdriver_manager.chrome import ChromeDriverManager  # type: ignore

    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--window-size=1280,1200")
    opts.page_load_strategy = "eager"
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)
    try:
        driver.set_page_load_timeout(timeout)
    except Exception:
        pass

    # 성능 B: 이미지/CSS/폰트 등 차단 (네트워크 부하↓)
    if optimize_b:
        try:
            driver.execute_cdp_cmd("Network.enable", {})
            driver.execute_cdp_cmd(
                "Network.setBlockedURLs",
                {
                    "urls": [
                        "*.png",
                        "*.jpg",
                        "*.jpeg",
                        "*.webp",
                        "*.gif",
                        "*.svg",
                        "*.css",
                        "*.woff",
                        "*.woff2",
                        "*.ttf",
                        "*.otf",
                    ]
                },
            )
        except Exception:
            # 일부 환경에서 CDP 호출 실패해도 치명적이지 않음
            pass
    return driver


def get_page_selenium(driver, date_str: str, *, timeout: int = 20) -> str:
    """
    WHY: 정적 요청 실패 시 보조 경로로 사용. 오버레이/동적 렌더링을 피해 최소 대기만 적용한다.
    HOW: page_source 반환(이미지 등 무거운 리소스는 차단 옵션으로 최소화).
    """
    url = f"{BASE}?strDate={date_str}"
    try:
        driver.get(url)
        time.sleep(0.8)  # 경량 대기
        html = getattr(driver, "page_source", "") or ""
        return html
    except Exception:
        return ""

