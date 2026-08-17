Data Quality (요약 리포트)
=========================

지표
----
- 수집 실패율: 요청 대비 HTTP 오류/타임아웃 비율 (logs/metrics_latest.csv)
- 중복 키: UPSERT 충돌률 (writer 로그 event=upsert_*)
- 결측 TOP N: NULL 비율 상위 컬럼 (EDA 스크립트 보조: scripts/eda_daily_trade.py)

처리 방안
--------
- 실패: 429/5xx → 지수 백오프 재시도, 일일 예산 내 분산 (rate_limit.TokenBucket)
- 결측: 가격/거래수 미노출 시 NULL 허용 · 2차 수집 시 보간/재크롤링
- 중복: PK 멱등 UPSERT, visited_log로 재진입 방지

모니터링 산출물
--------------
- logs/app.log — JSON 라인(구조화 이벤트)
- logs/metrics_latest.csv — 최근 실행 요약 (requests/success/429/failed/rows)

