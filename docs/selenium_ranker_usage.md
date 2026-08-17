Selenium 옵션과 랭커 스크래퍼 사용법
===================================

데이터센터 크롤러 (daily_trade)
--------------------------------
- 기본(요청): `python -m crawler.daily_trade.cli --start-date 2020-05-20 --end-date 2025-09-11 --players pairs.json --export-csv`
- Selenium 사용: `python -m crawler.daily_trade.cli --start-date 2020-05-20 --end-date 2025-09-11 --players pairs.json --export-csv --use-selenium`

랭커 Top20 닉네임 스크래핑
---------------------------
- 실행: `python -m crawler.rankers.cli --top 20 --resolve-ouid`
- 출력: `data/processed/daily_rankers.csv` (date, nickname)
- OUID 매핑: `--resolve-ouid`를 주면 Open API로 즉시 ouid_map/ranker_sample 업데이트

설치
----
`pip install -r requirements.txt` (selenium, webdriver-manager 포함)

