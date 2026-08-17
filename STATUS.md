FC Online Lab — STATUS (as of 2025-09-13)
================================================

본 문서는 BDD 관점으로 현재 진행 상태를 “완료/설계/보류/실패”로 구분하고, 실행 명령과 증빙(파일 타임스탬프/크기)을 함께 기록합니다.

완료
----
- 데이터센터 일일 거래 크롤링 → DB/CSV 적재: requests 기반 파이프라인 동작 확인.
  - BDD: Given 대상 선수 목록과 날짜 범위, When `crawler.daily_trade.cli` 실행, Then `daily_trade` 테이블과 `data/processed/daily_trade.csv`가 멱등 UPSERT/append로 갱신된다.
  - 명령(예): `python -m crawler.daily_trade.cli --start-date 2025-08-13 --end-date 2025-09-10 --players pairs.json --export-csv`
  - 근거: `data/processed/daily_trade.csv` (23,486,745 bytes, 2025-09-13 09:47:59), `data/data.db` (33,894,400 bytes, 2025-09-13 01:47:44)
  - 상태: 완료(로컬 산출물 존재, 레포 반영 대기)
  - 검증: 행수/컬럼·SHA-256 해시 기록 자동화 예정(see `scripts/status_evidence.ps1`)

- Top10 출전 추이 CSV 생성: 전처리 스크립트로 집계 완료.
  - BDD: Given RAW/집계 원천, When `scripts/preprocess_top10.py` 실행, Then `data/processed/top10_trend.csv`가 생성·갱신된다.
  - 명령(예): `python scripts/preprocess_top10.py`
  - 근거: `data/processed/top10_trend.csv` (1,534 bytes, 2025-09-10 22:08:34)

- 거래 데이터 EDA 리포트 산출: 품질·커버리지 점검 산출물 존재.
  - BDD: Given 최신 `daily_trade.csv`, When EDA 스크립트 실행, Then null/중복/분포 요약 리포트가 생성된다.
  - 명령(예): `python scripts/eda_daily_trade.py`
  - 근거: `data/reports/daily_trade_eda.md` (1,663 bytes, 2025-09-13 09:56:49)

- 선수 이미지 로컬 캐시 확보: CDN 다중 경로 시도 후 저장.
  - BDD: Given SPID 집합, When `ensure_player_image/ensure_many` 실행, Then `data/images/*.png` 로컬 캐시가 채워진다.
  - 명령(예): `python scripts/sync_players.py --spids pairs.json --download`
  - 근거: `data/images` (파일 4,650개, 갱신 2025-09-11 18:58:10), `data/images_new` (파일 71개, 갱신 2025-09-12 23:02:52)

- 메타 캐시 확보(SPID/포지션 등): OpenAPI 정적 메타 다운로드/캐시.
  - BDD: Given 네트워크 접근, When `app/services/meta.py:load_meta` 호출, Then `data/meta/spid.json,spposition.json`이 TTL 내 존재한다.
  - 명령(예): 라이브러리 호출(내부), 초기 로딩 시 자동 다운로드
  - 근거: `data/meta/spid.json` (size≈5.1MB, 2025-09-10 06:34:15), `data/meta/spposition.json` (1,514 bytes, 2025-09-10 06:34:15)

- 유튜브 댓글 감성 데이터(주석/스코어) CSV: 분석 재현 가능 상태.
  - 상태: 완료(로컬) · 대시보드 연계 보류
  - BDD: Given 유튜브 API/주석 파이프라인, When 수집·전처리 실행, Then 주석된 CSV가 생성된다.
  - 명령(예): `python -m youtube_comments.cli --videos <...> --csv-out data/processed/gamst_comments.csv`; 후속 주석/감성 파이프라인 실행
  - 근거: `data/processed/comments_with_sentiment.csv` (4,445,258 bytes, 2025-09-12 19:48:58)

설계
----
- 랭커 평균 스탯 수집(rankers-stats) 파이프라인: 배치/쿼터/재시도/TokenBucket 설계 및 코드 준비.
  - BDD: Given 유효 (spid,po) pairs, When `scripts/fetch_ranker_stats.py --pairs pairs.json` 실행, Then `ranker_stats` 테이블이 복합PK로 upsert된다.
  - 명령(예): `python scripts/fetch_ranker_stats.py --pairs pairs.json`
  - 근거: 스크립트/스키마 존재(실행 여부는 본 STATUS에서 미확인)

- Streamlit 대시보드(선수/지표 차트) 기본 골격·로직 구현.
  - BDD: Given 가공 CSV/DB, When `app/dashboard.py` 구동, Then Top10 추이/일자별 지표 라인차트를 표시한다.
  - 명령(예): `streamlit run app/dashboard.py`
  - 근거: 앱 파일·모듈 일체 존재, 실행 로그는 본 STATUS에서 미수집
  - 추가: `app/sentiment_dashboard.py`는 별도 ‘설계’로 분리 표기(현 상태: 설계)

- “최고가 거래 선수” 카드 레이아웃 파서 고도화 설계 및 TDD 초안.
  - BDD: Given 카드형 DOM(스와이퍼), When 신규 파서 실행, Then 이름/시즌/포지션/OVR/강화/가격/SPID/이미지 등을 구조화한다.
  - 명령(예): `python fo4_best_price_parser.py <bestPrice.html>`(설계 문서에 포함)
  - 근거: `2025-09-13-newcrawling.txt`의 파서 설계·샘플 테스트 코드

- 파이프라인 실행 스크립트 및 스케줄러 골격.
  - BDD: Given 설정/시크릿, When PowerShell/스케줄 스크립트 실행, Then 일일 파이프라인이 순차 수행된다.
  - 명령(예): `powershell -File scripts\run_daily_pipeline.ps1`
  - 근거: 스크립트 존재(실제 스케줄 구동 여부는 미확인)

보류
----
- 랭커 평균 스탯 “주간 스냅샷” 자동화 및 운영 배치.
  - BDD: Given pairs와 API키, When 일일/주간 작업 스케줄, Then 특정일자의 `ranker_stats`가 누락 없이 축적된다.
  - 차기 액션: `scripts/schedule_fetch.py`/`*_new_ver.py`와 연계한 예약 실행 검증

- TopN(일별 선호 선수) CSV 직접 산출물 운영화.
  - BDD: Given HTML 스냅샷, When `--only-topN --export-csv` 실행, Then `data/processed/daily_top_players.csv`가 생성된다.
  - 현황: 해당 CSV 미존재(보류), DB upsert 경로만 사용 중으로 보임

- OUID 초기 시딩 로그/샘플 CSV 레포 반영.
  - BDD: Given 닉네임 목록, When `scripts/seed_ouids.py` 실행, Then `ouid_map` 갱신 및 샘플 CSV 남김.
  - 현황: 실행 로그/산출물 미수집(보류)

- OUID 초기 시딩/검증 로그 정리.
  - BDD: Given 닉네임 목록, When `scripts/seed_ouids.py` 실행, Then `ouid_map`이 채워지고 샘플 CSV가 남는다.
  - 현황: 실행 로그/산출물 미수집(보류)

실패
----
- 현재 문서화된 실패 항목 없음(레이아웃 변화 시 파서가 `data/raw/html/*.html` 스냅샷을 남기도록 방어 설계되어 있음).

데이터 현황(증빙)
-----------------
- CSV: `data/processed/daily_trade.csv`(최근 갱신 2025-09-13 09:47:59), `data/processed/top10_trend.csv`(2025-09-10 22:08:34)
- DB: `data/data.db`(운영, 33.9MB, 2025-09-13 01:47:44), `data/new-data.db`(Deprecated — 통합/삭제 예정, 57KB, 2025-09-13 09:46:15)
- 메타: `data/meta/spid.json`, `data/meta/spposition.json`(2025-09-10 06:34:15)
- 이미지: `data/images` 4,650개, `data/images_new` 71개
- 체크 스냅샷: `docs/check/check-2020.html`..`docs/check/check-2025.html` 존재(카드형 DOM 지문)

실행 명령 모음(터미널)
----------------------
- 거래 크롤러: `python -m crawler.daily_trade.cli --start-date <YYYY-MM-DD> --end-date <YYYY-MM-DD> --players config/pairs.json --export-csv`
- 랭커 스탯: `python scripts/fetch_ranker_stats.py --pairs pairs.json`
- 매치/RAW 수집: `python scripts/fetch_matches.py --nick <닉1> <닉2> --pages 2 --remain 500`
- 이미지 동기화: `python scripts/sync_players.py --spids pairs.json --download`
- Top10 전처리: `python scripts/preprocess_top10.py`
- 대시보드: `streamlit run app/dashboard.py`
- 감성 대시보드: `streamlit run app/sentiment_dashboard.py`

비고
----
- 상기 “근거”의 시각은 로컬 파일의 최종 수정시각으로, 실제 실행 로그의 타임스탬프와 수 초~분 단위 차이가 있을 수 있습니다.
- 실패/에러 로그를 정식 보관하려면 `logs/` 디렉터리 로테이션 로그를 활성화하고, 주요 스크립트 실행을 PowerShell/cron에서 표준 로그로 리다이렉션해 보관하는 것을 권장합니다.
- 로그 정책(UTC 저장·KST 표시, ISO 8601)은 `docs/LOGGING.md`를 따릅니다. PowerShell 실행 시 `scripts/run_with_log.ps1`로 감싸면 파일은 UTC, 콘솔은 KST로 일관 기록됩니다.
 - STATUS 내 파일 시각 표기는 기본 UTC, 괄호로 KST 병기(예: 2025-09-13 00:00:00Z / KST+9)합니다.
 - 대용량 CSV(≥50MB)는 Git LFS 권장. 현재 `daily_trade.csv`(≈23MB)는 일반 커밋 가능.
 - `--players` 입력 스키마: `config/pairs.json` 예) `[{"id": <spId>, "po": <posCode>}]`
