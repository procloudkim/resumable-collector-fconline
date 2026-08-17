Provenance (출처 족보)
=====================

- ranker_stats.*: NEXON Open API `fconline/v1/ranker-stats` 응답 필드에서 직접 매핑
- daily_trade.*: 대상 사이트 HTML — `crawler/daily_trade/parser.py`의 선택자/규칙으로 추출
- daily_top_players.*: 동일 페이지의 TopN 섹션 파싱 결과
- daily_pick.*: RAW 매치(JSONL) 집계(`scripts/aggregate_picks.py`) 결과
- players.*: 메타 JSON/이름 정규화(`app/services/meta.py`) + 이미지 캐시(`app/services/images.py`)

참고 문서/스냅샷
---------------
- `docs/check/DOM_REPORT.md` — 연도별 레이아웃
- `docs/check/version_selectors.yaml` — 셀렉터 버전 관리
- `docs/FCOnline_OpenAPI_full.md` — Open API 스펙 전문

