FC Online Analytics — CODEMAP (역할 중심 지도)
=============================================

진입점
-----
- 수집(웹): `crawler/daily_trade/cli.py` — 날짜 범위 → HTML → 파싱 → DB/CSV
- 수집(API): `scripts/fetch_ranker_stats.py` — pairs[{id,po}] → Open API → DB
- 전처리: `scripts/preprocess_top10.py` — 원천 → `data/processed/top10_trend.csv`
- 대시보드: `app/dashboard.py` — `data/data.db`/`data/processed` 가시화

코어/서비스
----------
- `app/core/utils.py` — 경로/로거/.env, 보조 유틸
- `app/core/cache.py` — SQLite(ouid_map/seen_match/meta/players/ranker_stats)
- `app/core/rate_limit.py` — TokenBucket, 일일 예산 분배
- `app/services/meta.py` — 메타 JSON 로딩, 이름 검색, 코드 매핑
- `app/services/images.py` — 이미지 URL/캐시, 다운로드 보장

크롤러(웹)
---------
- `crawler/daily_trade/fetcher.py` — GET/렌더링(옵션: Selenium)
- `crawler/daily_trade/parser.py` — 표/카드형 레이아웃 파싱, 가격 파서
- `crawler/daily_trade/writer.py` — DB 스키마, UPSERT, CSV append

유튜브 분석
----------
- `youtube_comments/*` — 댓글 수집/필터/저장/샘플링
- `sentiment/*` — 키워드/멘션/전처리/CLI

텍스트 다이어그램(수집)
---------------------
Rankers CLI ─┬─> OUID 시드(ouid_map)
             └─> TopN 랭커 목록

DailyTrade CLI: 날짜범위 × 선수목록 → [fetcher] → HTML → [parser] → rows → [writer] → DB/CSV

Open API: pairs[{id,po}] → `fetch_ranker_stats.py` → ranker_stats(UPSERT)

전처리: DB/CSV → `preprocess_top10.py` → `data/processed/top10_trend.csv`

대시보드: `top10_trend.csv` + DB(ranker_stats) + 이미지 캐시 → 시각화

운영 배선
--------
- 원클릭: `scripts/bootstrap.ps1` → setup/demo/fetch 태스크
- 스모크: `pytest -q -m smoke`

