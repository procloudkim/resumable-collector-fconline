# -*- coding: utf-8 -*-
"""
fetcher 모듈: Selenium WebDriver를 사용하여 웹 페이지를 가져옵니다.
WHY: 대상 페이지가 동적으로 로드되므로, Selenium을 통해 완전히 렌더링된 HTML을 얻기 위함입니다.
HOW: Chrome WebDriver를 Headless 모드로 실행하여 지정된 날짜의 페이지를 열고, 
     '출전' 탭의 데이터가 로드될 때까지 기다린 후 page_source를 반환합니다.
"""

import os
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from datetime import datetime
from project2.app.parser import selectors


class DataFetcher:
    def __init__(self):
        """Chrome WebDriver 초기화 (아직 브라우저를 열지 않음)."""
        self.driver = None

    def start(self):
        """Chrome WebDriver를 시작하고 설정을 적용합니다."""
        # 환경 변수로 전달된 성능/표시 옵션
        fast = os.environ.get("PROJECT2_FAST", "0") in ("1", "true", "True")
        headful = os.environ.get("PROJECT2_HEADFUL", "0") in ("1", "true", "True")

        chrome_options = Options()
        # WHY: 기본적으로 창을 띄우지 않고 빠르게 수집하기 위해 headless 모드 사용
        if not headful:
            chrome_options.add_argument("--headless=new")
        # 공통 최적화 옵션
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-notifications")
        # fast 모드: 페이지 로드 전략과 이미지 차단으로 속도 향상
        try:
            chrome_options.page_load_strategy = "eager" if fast else "normal"
        except Exception:
            # 일부 버전에서는 속성 설정이 지원되지 않을 수 있음 → 무시
            pass
        if fast:
            prefs = {
                "profile.managed_default_content_settings.images": 2,
                "profile.default_content_setting_values.images": 2,
            }
            try:
                chrome_options.add_experimental_option("prefs", prefs)
                chrome_options.add_argument("--blink-settings=imagesEnabled=false")
            except Exception:
                pass

        # Chrome WebDriver 실행 (Selenium Manager가 적절한 드라이버를 자동 관리)
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
        except Exception:
            raise

    def fetch(self, date):
        """
        주어진 date(datetime.date)의 페이지를 열어 HTML 콘텐츠를 반환합니다.
        date 형식은 2020-05-20 등의 datetime.date 객체로 가정합니다.
        """
        if self.driver is None:
            raise RuntimeError("WebDriver is not started. Call start() before fetch().")
        # URL 구성 (YYYY.MM.DD 형식으로 날짜 삽입)
        date_str = date.strftime("%Y.%m.%d")  # 예: "2020.05.20"
        url = f"https://fconline.nexon.com/datacenter/dailyrecord?strDate={date_str}"
        try:
            # 페이지 열기
            self.driver.get(url)
        except Exception:
            # 페이지 로드 자체가 실패한 경우 예외를 상위에서 처리하도록 그대로 발생시킴
            raise

        # 페이지 로드 후 '출전' 탭의 데이터가 활성화되었는지 확인
        try:
            # 현재 활성화된 통계 카테고리를 확인 (출전이 기본 활성화가 아닐 수도 있으므로)
            active_elem = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "div.th.active"))
            )
            active_data_no = active_elem.get_attribute("data-no")
            # '출전'이 활성화되어 있지 않은 경우 (data-no가 MATCHCOUNT가 아니면) -> '출전' 탭 클릭
            if active_data_no != "MATCHCOUNT":
                # 드롭다운 버튼 클릭하여 목록 표시
                try:
                    cat_button = self.driver.find_element(By.CSS_SELECTOR, selectors.CATEGORY_BUTTON)
                    cat_button.click()
                except Exception:
                    # 버튼을 찾지 못해도 바로 항목을 찾는 시도로 진행
                    pass
                try:
                    matchcount_item = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selectors.CATEGORY_ITEM_MATCHCOUNT))
                    )
                    matchcount_item.click()
                except Exception:
                    # '출전' 카테고리 선택 실패
                    raise

            # '출전' 데이터가 로드될 때까지 기다림: 선수 이름 OR '검색 결과가 없습니다' 메시지 중 하나가 나타날 때까지
            deadline = time.time() + 10
            found = False
            while time.time() < deadline:
                try:
                    if self.driver.find_elements(By.CSS_SELECTOR, "#divPalyerStatDetail .name, #divPlayerStatDetail .name"):
                        found = True
                        break
                except Exception:
                    pass
                try:
                    if self.driver.find_elements(By.XPATH, "//*[contains(normalize-space(),'검색 결과가 없습니다')]"):
                        found = True
                        break
                except Exception:
                    pass
                time.sleep(0.25)
            if not found:
                raise TimeoutError("Timed out waiting for player rows or '검색 결과가 없습니다' message")
        except Exception:
            # 페이지 구조 문제 등으로 인해 '출전' 데이터 로드 확인에 실패
            raise

        # page_source 가져오기 (모든 동적 콘텐츠가 로드되었다고 간주)
        html = self.driver.page_source
        return html

    def close(self):
        """WebDriver 리소스를 해제하고 브라우저를 종료합니다."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
