See also: PROJECT2_ERD_KR.md (출전 랭킹 ERD)

erDiagram

  OUID_MAP {
    TEXT nickname PK
    TEXT ouid
  }

  SEEN_MATCH {
    TEXT match_id PK
  }

  META_KV {
    TEXT k PK
    TEXT v
  }

  PLAYERS {
    INTEGER spid PK
    TEXT    name_kor
    TEXT    name_eng
    TEXT    image_path
    TEXT    updated_at
  }

  RANKER_STATS {
    INTEGER spid   FK "→ PLAYERS.spid (논리 FK)"
    INTEGER po
    TEXT    create_date
    INTEGER dribble
    INTEGER dribble_try
    INTEGER dribble_success
    INTEGER pass_try
    INTEGER pass_success
    INTEGER block
    INTEGER tackle
    INTEGER assist
    INTEGER goal
    INTEGER match_count
    %% 복합 PK
    %% PK(spid, po, create_date)
  }

  %% (선택) 코드 테이블
  SP_POSITION {
    INTEGER code PK
    TEXT    name
  }

  MATCHTYPE {
    INTEGER code PK
    TEXT    name
  }

  DIVISION {
    INTEGER code PK
    TEXT    name
  }

  %% 관계(논리 FK)
  PLAYERS ||--o{ RANKER_STATS : has
  SP_POSITION ||--o{ RANKER_STATS : used_as


  <!-- 엔터티 설명

ouid_map – 게임 닉네임을 OUID로 매핑하는 캐시 테이블 (PK: nickname).

seen_match – 이미 처리된 match_id를 저장하여 증분 수집 시 중복 호출을 방지합니다 (PK: match_id).

meta_kv – 간단한 키/값 형태의 메타 정보 저장용 테이블입니다 (예: 버전, 마지막 업데이트 시간).

players – 선수 기본 정보와 이미지 경로를 저장하는 테이블 (PK: spid).

ranker_stats – 탑 랭커의 20경기 평균 스탯을 주기적으로 저장하는 테이블로 (spid, po, create_date)가 논리적 PK입니다. spid는 players 테이블의 FK입니다. 각 필드는 드리블, 패스 성공률, 골 등 주요 지표를 담습니다.

sp_position / matchtype / division – 포지션 코드, 매치 타입, 리그(디비전) 코드 등을 저장하는 정적 테이블로, 필요 시 조회 성능 향상을 위해 ERD에 포함할 수 있습니다.

이 ERD는 프로젝트의 데이터 흐름과 테이블 간 관계를 이해하는 데 도움이 될 것입니다. -->
개요

이 ERD는 FC온라인 데이터 파이프라인의 최소 스키마(캐시/차원/사실)를 정의합니다.
핵심 흐름: 닉네임→OUID 캐시, 매치 중복 방지, 메타 캐시, 선수 차원, 랭커 스탯 사실, 선택적 코드 테이블(포지션/매치/디비전).
엔티티

OUID_MAP: 닉네임↔OUID 캐시. 중복 조회 방지용.
SEEN_MATCH: 수집한 match_id 기록. 증분 수집에서 재호출 차단.
META_KV: 간단 설정/메타 버전/갱신시간 저장용 KV.
PLAYERS: 선수 차원. spid PK, 한글/영문 이름, 로컬 이미지 경로, 갱신시각.
RANKER_STATS: 랭커 20경기 평균 스탯 스냅샷(주기적). 복합 PK 제안 (spid, po, create_date). 컬럼은 드리블/패스/수비/공격 지표와 경기수.
SP_POSITION/MATCHTYPE/DIVISION: 코드 룩업(선택). 현재는 API 정적 메타를 파일 캐시로 쓰지만, 필요 시 테이블로 물리화 가능.
관계

PLAYERS 1 — N RANKER_STATS: RANKER_STATS.spid → 선수별 시계열 스냅샷 다건.
SP_POSITION 1 — N RANKER_STATS: RANKER_STATS.po → 포지션 코드 매핑.
나머지 코드 테이블은 선택적(룩업/필터링 시 조인).
코드 매핑

테이블 생성: init_schema()가 OUID_MAP/SEEN_MATCH/META_KV/PLAYERS/RANKER_STATS를 생성.
적재 경로:
증분 수집 → SEEN_MATCH/OUID_MAP 이용해 중복/조회 최적화.
ranker-stats 수집 → RANKER_STATS upsert.
메타 JSON(spid/position 등) → 현재 파일 캐시 사용, 필요 시 SP_POSITION 등으로 확장 가능.
차원 데이터(PLAYERS): 이름/이미지 캐시가 쌓이면 채워 사용(대시보드 라벨·썸네일).
설계 의도(왜)

캐시 계층(OUID_MAP/SEEN_MATCH/META_KV)로 API 한도와 중복 호출을 최소화.
사실 테이블(RANKER_STATS)은 복합 PK로 스냅샷 중복 없이 upsert 가능.
선수 차원(PLAYERS)을 별도로 유지해 라벨·이미지·조인 비용 절감.
코드 테이블은 ERD에 명시(확장성)하되, 초기에 파일 캐시로 단순 운영(복잡성 최소화).
운영/확장 메모

인덱스: 날짜 질의 빈번 → RANKER_STATS(create_date) 인덱스 권장. 이름 검색 → PLAYERS(name_kor,name_eng) 인덱스.
타입: create_date는 ISO 날짜/시각 문자열로 저장(일 단위 스냅샷이면 DATE 규격 사용 검토).
FK: SQLite에선 PRAGMA foreign_keys=ON 필요. 현재는 애플리케이션 레벨에서 참조 무결성 관리.
히스토리: 향후 MATCH/TRADE 등 사실을 도입하면 EVENT/TEAM/LEAGUE 차원도 추가 가능.
메타 물리화: SP_POSITION/MATCHTYPE/DIVISION을 SQLite에 적재해 조인형 분석/필터링 가독성 개선.
요약: ERD는 “수집 캐시(ouid/seen/meta) → 선수 차원(players) → 랭커 스탯 사실(ranker_stats)”의 최소 골격으로, PRD의 증분 수집·주간 스냅샷·대시보드 요구를 충족하며, 코드 테이블과 추가 사실/차원으로 자연스럽게 확장 가능하도록 설계되어 있습니다.
