Data Dictionary (핵심 테이블/CSV)
===============================

players (SQLite)
----------------
- spid: INTEGER, PK — 선수 식별자
- name_kor: TEXT — 한글 이름
- name_eng: TEXT — 영문 이름
- image_path: TEXT — 로컬 캐시 경로
- updated_at: TEXT — ISO8601

ranker_stats (SQLite)
---------------------
- spid: INTEGER — 선수 ID
- po: INTEGER — 포지션 코드
- create_date: TEXT — ISO8601(UTC), PK 구성
- dribble/pass/block/...: INTEGER — 누적/일자 단위 통계
- match_count: INTEGER — 표본 경기 수

daily_trade (SQLite)
--------------------
- date: TEXT — YYYY-MM-DD, PK 구성
- spid: INTEGER — 선수 ID, PK 구성
- player_name: TEXT — 페이지 표기명(보조)
- avg_price/max_price/min_price: BIGINT — 가격(원, 정규화)
- trade_count: INTEGER — 거래 수(없을 수 있음)
- max_enhance_level: INTEGER — 강화 +레벨
- source: TEXT — 'web'

daily_top_players (SQLite)
-------------------------
- date: TEXT — YYYY-MM-DD, PK 구성
- spid: INTEGER — 선수 ID, PK 구성
- rank: INTEGER — 순위(TopN 내)
- pick_rate: REAL — 출전 비율

daily_pick (SQLite)
-------------------
- date: TEXT — YYYY-MM-DD, PK 구성
- spid: INTEGER — 선수 ID, PK 구성
- matchtype: INTEGER — 경기 타입(미명시=0)
- pick_count: INTEGER — 출전 회수
- sample_match_count: INTEGER — 당일 샘플 경기 수
- source: TEXT — 'api'

top10_trend.csv (CSV)
---------------------
- date: YYYY-MM-DD
- <spid>: INTEGER 열 여러 개 — 해당 선수의 지표(예: 출전 빈도/정규화된 비율)

타입/결측 규약
--------------
- 날짜/시각: TEXT(ISO8601); 보관은 UTC, UI는 로컬 표시
- 결측: 가격·거래수·랭크 등 불명확 시 NULL/빈칸 허용
- 키: 명시된 PRIMARY KEY로 멱등 UPSERT 보장

