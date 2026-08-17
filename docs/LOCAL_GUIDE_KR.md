로컬 데이터/작업 가이드 (비전공자용)
=================================

목적과 한눈 요약
- 목적: 로컬 PC에서 FC 온라인 관련 데이터를 수집·가공·확인하는 전 과정을 한 문서로 안내합니다.
- 한눈 요약: raw → processed → reports/EDA 번들 순으로 누적되며, 주요 산출물은 CSV/SQLite와 요약 JSON/MD입니다. 실행은 제공된 파이썬 스크립트로 재현 가능합니다.

폴더 구조와 핵심 산출물
- `data/raw/`: 원천 데이터 저장소 (예: 경기 상세 JSONL, 수집된 HTML 스냅샷)
- `data/processed/`: 가공된 CSV (예: `daily_trade.csv`, `top10_trend.csv`, `comments_with_sentiment.csv`)
- `data/meta/`: 보조 메타데이터 (예: `spid.json`, 포지션 코드 등)
- `data/reports/`: 자동 생성 리포트와 매니페스트 (예: `csv_summary.txt`, `data_manifest.json`)
- `project/eda_bundles/EDA_YYYYMMDD-HHMM/`: 배포·공유용 번들(샘플/전체 CSV, 요약 JSON/MD, 선택: SQLite)

주요 데이터셋 개요(예시)
- `data/processed/daily_trade.csv`: 날짜×선수 거래 요약(평균/최대/최소 가격, 거래 수, 강화 레벨 등)
  - 생성: `python -m crawler.daily_trade.cli --start-date <YYYY-MM-DD> --end-date <YYYY-MM-DD> --players config/pairs.json --export-csv`
  - 근거/검증: `data/reports/csv_summary.txt`의 rows/cols, 매니페스트

- `data/processed/top10_trend.csv`: 기간 동안 출전 상위 10명 선수의 추세(카운트 기반)
  - 생성: `python scripts/preprocess_top10.py --out data/processed/top10_trend.csv`
  - 입력: RAW 경기 JSONL (`data/raw/*.jsonl`)

- `data/processed/comments_with_sentiment.csv`: 유튜브 댓글 + 간이 감성 점수
  - 입력/코드: `youtube_comments/*` (클라이언트, 페처, 필터링, 샘플링)

- EDA 번들 예시: `project/eda_bundles/EDA_20250913-1645/`
  - CSV: `bestprice_all.csv`(예: rows=34937, cols=17), `bestprice_sample.csv`(1000행 샘플)
  - DB(선택): `best_price_new.db` 내 `best_price_daily_stg`/`best_price_daily`
  - 요약: `summary.json`(기간/결측/통계), `SUMMARY.md`(사람이 읽기 쉬운 요약)
  - 컬럼 하이라이트(일부): `date`, `spid`, `player_name`, `season_code`, `position`, `ovr`, `pay`, `enhance`, `price_value`, `price_text`, 그리고 로고/이미지의 로컬/상대 경로 필드

실행 준비(로컬 환경)
- 파이썬과 가상환경: `python -m venv .venv` 후 활성화, `pip install -r requirements.txt`
- 환경변수 파일: 루트의 `.env`에 API 키를 저장합니다. 예)
  - `NEXON_OPENAPI_API_KEY=YOUR_KEY_HERE`
  - `YOUTUBE_API_KEY=YOUR_KEY_HERE`
- 보안: `.env`는 Git에 올리지 않습니다. 키는 외부 공유 금지, 문서에는 마스킹 처리.

수집·가공 워크플로(자주 쓰는 경로/명령)
- 일별 거래 가격 수집
  - 명령: `python -m crawler.daily_trade.cli --start-date <FROM> --end-date <TO> --players config/pairs.json --export-csv`
  - 동작: 페이지 GET → DOM 파싱 → 가격 파싱 → CSV/DB 기록
  - 산출: `data/processed/daily_trade.csv` 갱신(또는 DB upsert)

- 경기 RAW 수집 및 집계
  - RAW 수집: `python scripts/fetch_matches.py --nick <닉네임> --pages 2 --remain 1000 --api-key $env:NEXON_OPENAPI_API_KEY`
  - 집계: `python scripts/aggregate_picks.py --raw data/raw/matches_sample.jsonl --players config/pairs.json --emit-csv data/processed/daily_pick.csv`

- 상위 10 추세 전처리
  - 명령: `python scripts/preprocess_top10.py --out data/processed/top10_trend.csv`

- EDA 번들 생성(재현 가능)
  - 명령 예시:
    `python project/scripts/make_eda_bundle.py --csv-dir data/csv --db-path project/db/best_price_new.db --bundle-dir project/eda_bundles --include-db --include-quality --sample 1000 --from 2020-05-20 --to 2025-09-11`
  - 결과: `project/eda_bundles/EDA_YYYYMMDD-HHMM`에 CSV/샘플/요약/DB(옵션) 생성

결과 확인과 검증(비전공자용 체크리스트)
- 폴더 존재: `data/raw`, `data/processed`, `data/meta`, `data/reports`가 모두 존재해야 합니다.
- CSV 형태: `data/reports/csv_summary.txt`에서 각 CSV의 rows/cols를 확인합니다.
- 매니페스트: `data/reports/data_manifest.json`의 파일 경로/크기/미리보기와 `csv_summary.txt`가 모순 없는지 확인합니다.
- EDA 번들: `project/eda_bundles/EDA_20250913-1645/` 내 `bestprice_all.csv`, `bestprice_sample.csv`, `summary.json`, `SUMMARY.md`가 존재하는지 확인합니다.

로컬 이미지/로고 경로 필드
- 번들 컬럼 중 `*_logo_path`, `player_image_path` 등은 “로컬/상대 경로”입니다.
- 의미: 번들을 다른 PC로 옮겨도 폴더 구조만 유지하면 이미지가 연결됩니다(웹이 아닌 파일 경로 참조).

HTML 체크 파일(파싱 구조 확인용)
- `project2/check_html-1.html`, `project2/check_html-2.html`은 크롤링 대상 페이지의 구조(출전/공격포인트/슈팅 등 테이블·드롭다운)를 로컬에서 미리 살펴보는 샘플입니다.
- 활용: 파서 수정 시 해당 HTML을 열어 선택자/DOM 구조를 육안으로 확인합니다.

안전·품질 유의사항
- 요청 간 대기: `project/app/utils.py`의 `polite_sleep(min_s, max_s)`를 활용해 429/차단 위험을 줄입니다.
- 안전 저장: `atomic_write(path, data)`는 임시 파일로 기록 후 교체하여 부분저장/깨짐을 방지합니다(Windows 호환).
- 재실행 안전성: 수집 중단/재시작에도 중복·누락을 줄이도록 UPSERT/visited 로그를 사용합니다.
- 실행 로그: Windows에서는 `scripts/run_with_log.ps1`로 표준 로그 파일 남기기를 권장합니다.

빠르게 시작하기(예시 시나리오)
1) `.venv` 구성 후 `pip install -r requirements.txt`
2) `.env`에 API 키 입력(NEXON/YOUTUBE)
3) 일별 거래 CSV 생성: 위 “일별 거래 가격 수집” 명령 실행
4) `data/reports/csv_summary.txt`로 행·열 확인, 문제가 없으면 EDA 번들 생성
5) 번들 폴더에서 `summary.json`/`SUMMARY.md`를 열어 기간/결측/통계를 확인

코드 변경 히스토리(쉽게 풀어쓴 요약)
- 문서·스크립트 정비: “문서/스크립트 추가” 커밋으로 재현용 스크립트와 README·RUNBOOK·FAQ가 보강되었습니다.
- 번들/매니페스트 추가: EDA 번들 생성과 이미지 추출, 데이터 매니페스트 생성 유틸이 도입되어 산출물 공유가 쉬워졌습니다.
- 수집 기능 확장: 일별 거래·랭커 수집(셀레니움 포함)과 유튜브 댓글 수집 모듈이 추가되어 데이터 폭이 넓어졌습니다.
- 리포지토리 정리: `.gitignore` 개선, 생성물/상태 파일은 추적 제외, DB/모델 바이너리는 LFS 트래킹으로 관리됩니다.
- 호환성/품질: 줄바꿈(LF) 정규화, 불필요 파일 정리, 대시보드/문서 리팩터링 등 유지보수성이 향상되었습니다.
- 작업 메모: “다시 크롤링해야함”, “다시시작” 등은 진행 중 메모성 커밋입니다(기능 변화는 제한적).

FAQ(비전공자 관점)
- Q. 데이터는 어디서 보나요?  A. `data/processed/*.csv`와 EDA 번들의 CSV/요약을 열어보세요.
- Q. 이미지가 안 보여요.  A. 번들을 통째로 이동하고 상대 경로를 유지해야 합니다. 경로가 끊기면 로고/선수 이미지가 안 보입니다.
- Q. 키가 없어서 수집이 안 돼요.  A. `.env`에 올바른 API 키를 넣고, 공유·커밋하지 마세요.
- Q. 너무 빨리 요청해서 막혀요.  A. `polite_sleep` 범위를 넉넉히 주고 재시도하세요.
- Q. 어떤 파일이 만들어졌는지 알고 싶어요.  A. `data/reports/data_manifest.json`을 먼저 확인하세요.

참고 파일(문서/예시)
- `data/reports/LOCAL_DATA_OVERVIEW_KR.txt`: 로컬 데이터 개요와 BDD 체크리스트
- `project/eda_bundles/EDA_20250913-1645/DATASET_INFO_KR.txt`: 번들 상세 설명(컬럼, 생성/검증 방법)
- `project/eda_bundles/EDA_20250913-1645/summary.json`: 기간·결측·통계 요약(JSON)
- `project/app/utils.py`: 안전 저장/대기 등 공통 유틸
- `project2/check_html-1.html`, `project2/check_html-2.html`: 파싱 대상 구조 확인용 HTML 샘플


## 출전 랭킹 수집 가이드(project2)

- 목적: FC 데이터센터의 일별 ‘출전’ 부문 랭킹을 CSV·SQLite로 수집/보관합니다.
- 결과 위치:
  - CSV: `project2/out/topdailyrecord_YYYY-MM.csv`
  - DB: `project2/db/topdailyrecord.db` (table: `top_daily_record`, PK=(date,rank))
  - 상태: `project2/state/` (progress.json, resume_state.txt, 실패/무자료 마커)
- 실행 예시:
  - 전체 기간: `python -m project2.app.cli run --from 2020-05-20 --to 2025-09-11`
  - 특정 기간: `python -m project2.app.cli run --from 2021-01-01 --to 2021-12-31`
  - 재개: `python -m project2.app.cli run --resume`
  - 빠른 모드: `--fast` (이미지 차단 + eager 로드)
  - 디버깅: `--headful` (브라우저 창 표시)
  - 진행/ETA: `--hourly-log`, `--target-end 2025-09-14T23:00`
  - 경로 재정의: `--csv-dir`, `--db-path`, `--state-dir`
- 무자료 처리: 페이지에 “검색 결과가 없습니다”가 표시되면 실패로 치지 않고 nodata 마커(`project2/state/nodata_YYYY-MM-DD.txt`)를 기록합니다.
