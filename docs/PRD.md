# PRD: FC Online 데이터 수집·시각화 자동화

> 목적: 일일/주간 단위로 데이터를 안정적으로 수집하고, 로컬 캐시(SQLite) 및 CSV 스냅샷으로 분석/시각화 기반을 제공합니다.
>
> 산출물: Streamlit 대시보드, GitHub 코드/문서, 분석 리포트/EDA 번들

## 1. 배경 & 문제 정의
- 현재: 닉네임별 경기 목록에서 날짜·매치타입·출전 빈도(TopN) 정도는 가능하나, 종합 지표(수비/공격/가격 등) 주간 스냅샷과 이미지 매칭이 미흡
- 해결 과제:
  1) 선수 이름 매칭(SPID 기준)과 이미지 로컬 캐시 정교화
  2) ranker-stats API 기반 최근 20경기 평균 지표의 주간 스냅샷 축적
  3) (선택) 외부 신호(YouTube/커뮤니티)와 결합하여 추세 해석 보조

## 2. 목표(KPI) & 가설
- KPI(정보카드): 득점/도움/유효슈팅/드리블·패스 성공률/수비지표(블락·태클)/매치 수 등
- 가설: 메타 변화(패치/이벤트) ±7일 구간에서 채용률·성능 지표가 유의하게 변동한다

## 3. 범위 / 비범위
- 범위: Open API 증분 수집(429/쿼터 관리), 이름·이미지 매칭, SQLite 적재, 주간 스냅샷, 문서화/Runbook
- 비범위: 대규모 분산 배치, 커스텀 감성모델 학습, 대용량 데이터 웨어하우스

## 4. 데이터 소스 & API
- 메타: `/static/fconline/meta/spid.json`, `/static/fconline/meta/spposition.json`
- 랭커 지표: `/fconline/v1/ranker-stats` (TOP 10,000, 최근 20경기 평균, players 파라미터 배치 단위 권장)
- 매치 수집: `user/match`, `match-detail` (seen 캐시로 중복 제거)
- 보조(HTML): 데이터센터 거래/TopN, robots 정책 준수

## 5. 소프트웨어 아키텍처 & 모듈 설계

### 5.1 폴더/모듈 개요
```
app/
  core/ (utils, cache, rate_limit)
  services/ (meta, images)
crawler/daily_trade/ (cli, fetcher, parser, writer)
scripts/ (seed_ouids, fetch_matches, fetch_incremental, fetch_fc, preprocess_top10, fetch_ranker_stats, sync_players ...)
data/ (raw, processed, meta, images)
docs/ (PRD, ERD, LOGGING, STRUCTURE ...)
```

### 5.2 데이터 모델(SQLite)
```sql
CREATE TABLE IF NOT EXISTS players(
  spid INTEGER PRIMARY KEY,
  name_kor TEXT, name_eng TEXT,
  image_path TEXT, updated_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_players_name ON players(name_kor, name_eng);

CREATE TABLE IF NOT EXISTS ranker_stats(
  spid INTEGER, po INTEGER, create_date TEXT,
  dribble INTEGER, dribble_try INTEGER, dribble_success INTEGER,
  pass_try INTEGER, pass_success INTEGER,
  block INTEGER, tackle INTEGER,
  assist INTEGER, goal INTEGER,
  match_count INTEGER,
  PRIMARY KEY(spid, po, create_date)
);
```

### 5.3 핵심 로직
- 증분 수집: seen 캐시로 중복 방지, 429/5xx 백오프, 배치 단위 요청
- 이름/이미지 매칭: spid.json 기반 매핑, `ensure_player_image(spid)` 로컬 캐시
- 랭커 지표: players(spid, po) 목록을 배치로 호출 후 upsert

## 6. UI 요구(대시보드)
- 검색/필터: 이름 자동완성(spid 매핑), 날짜 범위, 매치 타입
- KPI 카드: 득점/도움/유효슈팅 등
- 차트: 채용률/성능 추세, 분포
- 캐시: `st.cache_data` 활용, 버튼으로 최신화
- 출처 고지: “Data based on NEXON Open API” 등

## 7. TDD·클린코드·Git
- TDD: 실패하는 테스트→구현→리팩터링, 커버리지 80% 목표(가능 범위)
- 네이밍/주석: 핵심 로직에 WHY/HOW, snake_case, 명확한 책임 분리
- 커밋 규칙: feat/fix/chore/docs/refactor, 간결한 제목

## 8. 일정(권장)
- D1~D2: API 최적화(증분·캐시) + 메타/이미지 정비
- D3: SQLite 스키마 확정 + 통계 스크립트 + 대시보드 초안
- D4: 대시보드 고도화(필터/차트) + 보고/발표 자료
- D5: 최종 리뷰/회고

## 9. 리스크 & 완화
- 429/쿼터: 토큰버킷·배치 쪼개기·지수 백오프
- 명명 불일치: 시즌/포지션/매치타입 코드 정합성 체크, 보조 테이블
- 차단: robots 준수, 요청 헤더/간격 조절, 실패 시 분할 재시도

## 10. 소스 인벤토리(요약)
- 데이터센터(HTML): `https://fconline.nexon.com/datacenter/dailytrade?strDate=YYYY-MM-DD`
  - 레이아웃/셀렉터: `docs/check/DOM_REPORT.md`, `docs/check/version_selectors.yaml`
  - 스냅샷: `data/raw/html/YYYYMMDD.html`
- 오픈 API(Nexon): 메타/랭커 지표/매치 상세

