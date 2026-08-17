# 로컬 아키텍처 총괄 개요(코드·데이터·문서)

본 문서는 레포지토리 전반의 구성요소, 데이터 흐름, 실행 방법, 산출물, 운영 가이드, 관련 문서 링크를 한눈에 정리합니다. 코드/DB는 변경하지 않으며, 문서 정합성을 최신으로 유지하는 데 목적이 있습니다.

## 시스템 개요
- 파이프라인 A: BestPrice(일별 거래/TopN) — `project/`, `crawler/daily_trade/`, `scripts/`
- 파이프라인 B: 출전 랭킹(일별 ‘출전’ 부문) — `project2/`
- 공용 자산: `data/`(raw/processed/meta/reports), `docs/`(PRD/ERD/정책/가이드), `logs/`

## 기술 스택
- 언어/런타임: Python 3.13, PowerShell(Windows)
- 크롤링: Selenium 4(headless Chrome, Selenium Manager), requests
- 파싱: BeautifulSoup4, lxml
- 저장: CSV(월별 파일), SQLite(UPSERT/PK)
- 품질/테스트: pytest, manual EDA bundles

## 폴더·역할 요약
- `project/`: BestPrice 1회성 크롤러(거래/TopN), ETA/진행 로그, EDA 번들 스크립트 포함
- `project2/`: 출전 랭킹 크롤러(수집→파싱→CSV/DB, 진행률/ETA/재개/빠른 모드)
- `docs/`: PRD, ERD, 정책, 실행 가이드(본 문서 포함)
- `data/`: raw HTML/JSONL, processed CSV, meta 코드맵, reports(매니페스트/요약)

## 실행(요약)
- BestPrice: `python -m app.cli run --from YYYY-MM-DD --to YYYY-MM-DD --csv-dir data/csv --db-path db/best_price_new.db --hourly-log --resume`
- 출전 랭킹: `python -m project2.app.cli run --from 2020-05-20 --to 2025-09-11 --fast --hourly-log`
  - 재개: `python -m project2.app.cli run --resume`
  - 옵션: `--fast`(이미지 차단+eager), `--headful`, `--hourly-log`, `--target-end`, `--csv-dir/--db-path/--state-dir`

## 산출물
- BestPrice:
  - CSV: `project/data/csv/bestprice_YYYY-MM.csv`
  - DB: `project/db/best_price_new.db`
  - 상태: `project/state/progress.json`
- 출전 랭킹:
  - CSV: `project2/out/topdailyrecord_YYYY-MM.csv`
  - DB: `project2/db/topdailyrecord.db` (table: `top_daily_record`)
  - 상태: `project2/state/`(progress.json, resume_state.txt, failures_*, nodata_*, raw_html/*.html)

## 데이터 모델(요약)
- BestPrice(요약): `best_price_daily` 중심, PK=(date, spid, season_code, enhance)
- 출전 랭킹:
  - `top_daily_record`(PK=(date, rank))
  - 컬럼: date, rank, 선수 기본정보, 출전, 공격 포인트, 득점, 도움, 유효 슈팅, 일반 슈팅, 패스 성공률, 드리블 성공률, 공중볼 경합 성공률, 가로채기, 태클 성공률, 차단 성공률, 선방(골 차단), 평점

## 운영(진행/재개/무자료)
- 진행/ETA: 콘솔 `[PROGRESS] ...`와 `state/progress.json`로 관리
- 재개: `--resume`(마지막 성공일 다음 날부터)
- 실패: `failures_YYYY-MM-DD.txt` 기록 + 파싱 실패 시 `raw_html/` 스냅샷 저장
- 무자료: 페이지에 “검색 결과가 없습니다” 감지 시 실패로 간주하지 않고 `nodata_YYYY-MM-DD.txt` 생성

## 문서 링크
- BestPrice: `project/README.md`, `docs/PRD.md`, `docs/ERD.md`, `docs/STRUCTURE.md`, `docs/DEV_ENV.md`, `docs/LOGGING.md`
- 출전 랭킹: `project2/README.md`, `docs/PROJECT2_RUNBOOK_KR.md`, `docs/PROJECT2_PRD_KR.md`, `docs/PROJECT2_BDD_KR.md`, `docs/PROJECT2_ERD_KR.md`

## 변경 이력(문서)
- 2025-09-14: 출전 랭킹 파이프라인 문서 일괄 반영(런북/PRD/BDD/ERD/아키텍처 총괄)

