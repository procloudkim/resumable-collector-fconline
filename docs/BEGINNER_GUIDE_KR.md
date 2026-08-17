FC Online Lab — 입문자용 안내서 (BDD 기반)
=========================================

대상과 목표
------------
- 대상: 비전공자, 처음 개발 환경을 만지는 사용자
- 목표: 1) 수집 스크립트를 실행해 CSV/DB를 만들고, 2) 대시보드를 띄워 결과를 확인하며, 3) 로그/증빙을 남깁니다.

사전 준비(5분)
---------------
- Windows PowerShell (권장), Python 3.13 이상, pip
- 저장소 내려받기(이 폴더가 준비됨)
- API 키 준비: 환경변수 또는 .env 파일에 설정
  - NEXON_OPENAPI_API_KEY
  - YOUTUBE_API_KEY (유튜브 댓글 수집에 필요)

설치
----
1) 의존성 설치: `python -m pip install -r requirements.txt`
2) (유튜브 모듈 추가 의존) `python -m pip install -r requirements.youtube.txt`

폴더 구조 한눈에 보기
----------------------
- 전체 구조는 `docs/STRUCTURE.md` 참고 (클릭하여 세부 경로 확인 가능)

데이터 소스(무엇을 어디서 받는가)
---------------------------------
- 상세 정리는 `docs/SOURCES.md` 참고. 핵심만 요약:
  - 일일 거래(HTML): `https://fconline.nexon.com/datacenter/dailytrade?strDate=YYYY-MM-DD`
  - 오픈 API(JSON): 메타(spid/position), 랭커스탯(`/fconline/v1/ranker-stats`)
  - 유튜브 API v3: 지정한 영상들의 댓글 수집

로깅(UTC 저장 · KST 표시)
------------------------
- 정책: 파일 로그는 UTC(ISO 8601, 예: 2025-09-13T08:30:00Z), 콘솔은 KST(+09:00)
- 문서: `docs/LOGGING.md`
- 권장 실행(파워셸 래퍼): `scripts/run_with_log.ps1`
  - 예: `./scripts/run_with_log.ps1 -Cmd "python -m crawler.daily_trade.cli --start-date 2025-08-13 --end-date 2025-09-10 --players config/pairs.json --export-csv" -LogFile "logs/daily_trade.run.log"`

입력 파일(설정)
---------------
- 선수쌍(랭커스탯 등): `config/pairs.json`
  - 스키마 예: `[{"id": <spId>, "po": <positionCode>}, ...]`
- 유튜브 영상 목록: `config/youtube_videos.txt`
  - 한 줄에 하나의 URL 또는 11자리 영상 ID (샘플: `config/youtube_videos.sample.txt`)

BDD 시나리오별 실행 예
----------------------

1) 일일 거래 수집 → DB/CSV
- Given: 날짜 범위와 선수 목록, API 키(필요 없음/HTML 기반)
- When: 일일 거래 크롤러 실행
  - PowerShell 권장: `./scripts/run_with_log.ps1 -Cmd "python -m crawler.daily_trade.cli --start-date 2025-08-13 --end-date 2025-09-10 --players config/pairs.json --export-csv" -LogFile "logs/daily_trade.run.log"`
  - 직접 실행: `python -m crawler.daily_trade.cli --start-date 2025-08-13 --end-date 2025-09-10 --players config/pairs.json --export-csv`
- Then: `data/data.db`의 `daily_trade` 테이블과 `data/processed/daily_trade.csv`가 갱신됩니다.

2) Top10 출전 추이 전처리 → CSV
- Given: 기존 RAW/DB 산출물
- When: `python scripts/preprocess_top10.py`
- Then: `data/processed/top10_trend.csv` 생성

3) 랭커 평균 스탯 수집 → DB upsert
- Given: `config/pairs.json` (spId/pos), `NEXON_OPENAPI_API_KEY`
- When: `./scripts/run_with_log.ps1 -Cmd "python scripts/fetch_ranker_stats.py --pairs config/pairs.json" -LogFile "logs/ranker_stats.run.log"`
- Then: `data/data.db`의 `ranker_stats` 테이블 upsert
- 주의: API 쿼터(429/일일 한도)를 고려해 배치/재시도 로직이 들어있습니다.

4) 선수 이미지 캐시
- Given: spid 집합
- When: `python scripts/sync_players.py --spids config/pairs.json --download`
- Then: `data/images/*.png` 로컬 캐시 확보

5) 유튜브 댓글 수집 → CSV/SQLite
- Given: `YOUTUBE_API_KEY`, `config/youtube_videos.txt`
- When(PS): `python -m youtube_comments.cli --videos (Get-Content config\youtube_videos.txt) --include-replies --csv-out data/processed/comments.csv --sqlite-out data/processed/comments.db`
- Then: 댓글 CSV/DB 생성 (필요 시 추가 전처리/주석으로 `comments_with_sentiment.csv` 사용)

대시보드 열기
-------------
- 종합 대시보드: `streamlit run app\dashboard.py`
  - 탭: Top10 추이, 일자별 누적 지표, 개별 이미지(이름→spid 검색)
  - (감성 요약은 별도 앱 `app/sentiment_dashboard.py`에서 풍부하게 확인 가능)
- 감성 대시보드: `streamlit run app\sentiment_dashboard.py`

상태판(STATUS) 읽는 법
---------------------
- 문서: `STATUS.md`
- 분류: 완료, 완료(로컬), 보류
  - 예) 일일 거래: “완료(로컬 산출물 존재, 레포 반영 대기)”
  - 예) 유튜브 감성: “완료(로컬) · 대시보드 연계 보류”

증빙 자동화(무결성·크기·시각)
----------------------------
- 실행: `pwsh -File scripts/status_evidence.ps1 -OutDir data/reports`
- 산출: `data/reports/status_evidence.(csv|json)`, `data/reports/csv_summary.txt`
- 포함 정보: 파일 크기, 최종 수정시각(UTC/KST), SHA-256, CSV 행/열 요약
- 활용: STATUS “근거” 섹션에 붙여넣으면 리뷰어 설득력↑

개발 일정(권장)
---------------
- D1~D2: 증분/캐시 최적화 + 메타/이미지 준비
- D3: SQLite 스키마 정리 + 통계 스크립트 + 대시보드 초안
- D4: 대시보드 꾸미기(그래프) + 보고 자료 정리
- D5: 최종 발표/리뷰/회고

문제 해결(FAQ)
-------------
- API 키가 없다고 나와요
  - .env 또는 환경변수에 `NEXON_OPENAPI_API_KEY`(넥슨), `YOUTUBE_API_KEY`(유튜브)를 넣고 터미널을 다시 열어 실행하세요.
- 429 / Rate limit
  - 스크립트가 자동으로 재시도/간격조절 합니다. 여전히 실패하면 기간/입력 범위를 줄이세요.
- HTML 레이아웃이 바뀌었나요?
  - 파서가 실패하면 `data/raw/html/YYYYMMDD.html`로 스냅샷을 저장합니다. `docs/check/DOM_REPORT.md`와 `docs/check/version_selectors.yaml`를 참고해 셀렉터를 보강하세요.
- 파일이 어디 있죠?
  - 구조는 `docs/STRUCTURE.md`를 열어 확인하세요(클릭 가능 경로).

안전/정책
---------
- robots.txt와 서비스 약관을 준수하세요.
- 요청 간 랜덤 슬립(1~3초)과 재시도(backoff)를 지킵니다.
- 공개 저장소에 API 키/개인정보가 올라가지 않도록 주의하세요.

용어(간단 정리)
---------------
- SPID: 선수 고유 ID
- PO: 포지션 코드
- Ranker stats: 상위 유저들의 최근 20경기 평균 스탯 요약
- Daily trade: 날짜별 거래(가격/강화 등) 지표

바로 실행 체크리스트
-------------------
1) `python -m pip install -r requirements.txt`
2) .env에 `NEXON_OPENAPI_API_KEY` (필요 시 `YOUTUBE_API_KEY`) 입력
3) `./scripts/run_with_log.ps1 -Cmd "python -m crawler.daily_trade.cli --start-date 2025-08-13 --end-date 2025-09-10 --players config/pairs.json --export-csv" -LogFile "logs/daily_trade.run.log"`
4) `streamlit run app\dashboard.py`
5) `pwsh -File scripts/status_evidence.ps1 -OutDir data/reports`

