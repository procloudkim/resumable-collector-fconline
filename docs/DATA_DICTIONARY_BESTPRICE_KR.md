# Best Price 데이터 사전 (KR)

목적
- FC 데이터센터 ‘최고가 거래 선수’(best_price) 파싱 데이터의 필드 정의·타입·예시·제약을 한곳에 정리합니다.
- 분석·시각화(Streamlit)·품질점검의 기준 문서로 사용합니다.

출처/범위
- 출처: fconline.nexon.com 데이터센터(이적시장/강화 > 최고가 거래 선수)
- 수집 방식: HTML 파싱(크롤링) → 월별 CSV → SQLite 적재(`best_price_daily`)
- 기간: 번들/환경에 따라 다름(예: 2020-05-20 ~ 2025-09-11)

테이블
- 주 테이블: `best_price_daily`
- 대표 PK(논리): `(date, spid, season_code, enhance)`

용어
- spid: 선수 고유 ID
- season_code: 카드 시즌 코드(예: ICON, LH, LN, …)
- enhance: 강화 단계(+N)

## 컬럼 정의(원천 17개)

| 필드 | 타입 | 설명 | 예시 | 제약/비고 |
|---|---|---|---|---|
| date | TEXT(YYYY-MM-DD) | 거래/집계 기준 일자 | 2023-11-29 | NOT NULL |
| spid | INTEGER | 선수 고유 ID | 246001668 | NOT NULL |
| player_name | TEXT | 선수 이름(원문/국문) | 크리스티아누 호날두 | NULL 허용(메타로 보완 가능) |
| season_code | TEXT | 시즌 코드(카드 배지) | ICON, LH, LN | NOT NULL |
| position | TEXT | 포지션 코드 | ST, RW, CAM | NOT NULL |
| ovr | INTEGER | 종합 능력치 | 136 | >= 0 |
| pay | INTEGER | 급여 | 20 | >= 0 |
| enhance | INTEGER | 강화 단계(+N) | 3 | >= 0 |
| price_value | BIGINT | 가격(정규 수치, KRW) | 8140000000 | >= 0 |
| price_text | TEXT | 가격 문자열(표시용 원문) | "8,140,000,000" | 분석 시에는 `price_value` 사용 |
| nation_code | TEXT | 국가 코드(데이터센터 체계) | 18 | NULL 허용 |
| league_code | TEXT | 리그 코드(데이터센터 체계) | L350, L83 | NULL 허용, CDN 파일명과 1:1 아님 |
| team_code | TEXT | 팀 코드(데이터센터 체계) | L95, L219 | NULL 허용, CDN 파일명과 1:1 아님 |
| nation_logo_path | TEXT | 국가 로고 로컬 경로 | data/images/logos/nation/small/18.png | 상대경로 권장 |
| league_logo_path | TEXT | 리그 로고 로컬 경로 | data/images/logos/league/dark/l350.png | 상대경로 권장(미존재 가능) |
| team_logo_path | TEXT | 팀 로고 로컬 경로 | data/images/logos/team/dark/small/L95.png | 상대경로 권장(미존재 가능) |
| player_image_path | TEXT | 플레이어 이미지 로컬 경로 | data/images/players/base/246001668.png | 상대경로 권장 |

## 파생 필드(시각화용 권장)
- `player_name_kr`: 메타/원문 기반 한국어 이름
- `position_label_kr`: 포지션 한글 레이블(예: ST→스트라이커) – 선택
- `season_name_kr`: 시즌 한글 표시명(없으면 코드 그대로)
- `price_text_kr`: 한국식 단위 포맷(천단위/억·조)
- `player_img`: 이미지 우선순위 선택(base > action > base_24 > action_24)

## 품질 기준(점검 체크)
- 필수 결측: `player_name`, `season_code`, `position`, `ovr`, `pay`, `enhance`, `price_value` → 결측 0 보장
- 이미지 커버리지: 플레이어 ≥ 95% (내부 기준), 국가 로고 ≥ 95%, 리그/팀 로고는 미존재 허용(placeholder)
- 중복 규칙: 동일 `(date, spid, season_code, enhance)` 중복 시 `price_value` 최대값 1건 대표

## 경로/에셋 정책
- 모든 경로는 프로젝트 루트 기준 상대경로로 저장(이식성↑)
- 플레이어 이미지 디렉터리
  - `data/images/players/base/{spid}.png`
  - `data/images/players/action/{spid}.png`
  - `data/images/players/base_24/{spid}.png`
  - `data/images/players/action_24/{spid}.png`
- 로고 디렉터리
  - `data/images/logos/nation/small/{code}.png`
  - `data/images/logos/league/{dark|light}/{code}.png`
  - `data/images/logos/team/{dark|light}/{small|large}/{code}.png`

## 변환 가이드(시각화 직전)
1) 기간·필터 적용 후 DataFrame 구성
2) 한글 라벨 조인(선수/포지션/시즌 – 가능 범위)
3) 가격 한국식 포맷(`price_text_kr`)
4) 이미지 경로 선택 및 존재 검사(placeholder 폴백)
5) 대표 중복 규칙 적용(일자·카드 변형 단일화)

## 예시 쿼리
```sql
-- 최근 30일 Top-N 카드(가격 내림차순)
SELECT date, spid, player_name, season_code, position, ovr, pay, enhance,
       price_value, nation_logo_path, league_logo_path, team_logo_path, player_image_path
FROM best_price_daily
WHERE date BETWEEN :from AND :to
ORDER BY price_value DESC
LIMIT 200;
```

## 주의/제한
- `league_code`, `team_code`는 CDN 파일명과 일치하지 않을 수 있음(스냅샷 기반 보강 권장)
- `_24` 변형은 부재 비율이 높음(폴백 규칙 필수)
- `price_text`는 참고용이며, 분석/정렬은 반드시 `price_value` 사용

*** End of Document ***
