# -*- coding: utf-8 -*-
"""
FC 온라인 데이터센터 '출전 랭킹' 크롤러 패키지 (project2).
이 패키지는 CLI, fetcher, parser, writer, runner 모듈로 구성되어 있으며, 
FC Online 데이터센터의 일별 선수 기록(출전 부문)을 크롤링하여 CSV 및 SQLite DB로 저장합니다.

WHY: 수집-파싱-저장 단계를 명확히 분리하여 모듈화/테스트 용이성을 극대화합니다.
HOW: Selenium으로 동적 페이지를 수집하고(collector), BeautifulSoup으로 필요한 필드를 파싱(parser),
     CSV 및 SQLite로 저장(writer)하며, runner와 CLI가 전체 파이프라인을 오케스트레이션합니다.
"""

