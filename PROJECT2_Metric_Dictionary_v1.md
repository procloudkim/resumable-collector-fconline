# PROJECT2 Metric Dictionary v1 (측정 정의서)

## 공통
- **분석 기간:** 2020-05-20 ~ 2025-09-11
- **시간 그레인(집계 단위):** 일(day) / 연(year)
- **주요 소스:**
  - 출전 랭킹(일별 TopN)
  - 이적시장 BestPrice(일별 Top18)
  - 빅매치 리스트(이벤트 날짜, 주요 선수)
  - 유튜브 댓글(카타르 월드컵 KOR vs POR, 이벤트 전후 ±7일)

- **기본 파라미터:**
  - `TOPN_APPEARANCE`: 100 (실수집 범위에 맞춰 18/100 등 설정)
  - `TOPN_BESTPRICE`: 18
  - `EVENT_WINDOW_W`: 7  (±7일)
  - **유효 수집 일(Valid Day):** 해당 일자에 최소 1개 row가 존재하는 날

---

## [A] 출전 지표(Usage)
**A-001. daily_appearance**
- 정의: 일자별 선수 출전수(TopN 랭킹에서 제공)
- 단위: 건수
- 분자/분모: N/A (원시 카운트)
- 결측: 해당 일자 미수집 시 NULL
- 구현: Pandas/SQL에서 일자-선수 그룹 기준 sum

**A-002. daily_rank**
- 정의: 일자별 선수의 출전 랭킹(1=최다 출전)
- 단위: 순위
- 결측: 미등장 시 NULL
- 구현: 해당 일자 내 appearance 기준 정렬 후 순위 부여

**A-011. yearly_appearance_sum**
- 정의: 연도별 선수 출전수 합계
- 단위: 건수
- 구현: `sum(daily_appearance)` by (year, player)

**A-012. yearly_top_player**
- 정의: 연도별 최다 출전 선수
- 단위: (player, value)
- 구현: `argmax(yearly_appearance_sum)` by year

**A-013. alltime_top11_appearance**
- 정의: 5개년(전체기간) 누적 출전 상위 11명
- 단위: (player, value) Top11
- 구현: 전체기간 `sum(daily_appearance)` 기준 Top11

---

## [B] 이적시장 지표(Market)
**B-001. daily_bestprice_ranked**
- 정의: 일자별 최고가 거래 선수 Top18 리스트
- 필드: (date, rank, player, spid, season, price_value, price_str)
- 단위: price_value(정수, BP), 보조표기 price_조(조 단위)
- 구현: HTML에서 `<span class="price" alt="정수">` 우선 사용 → 정수 파싱

**B-011. yearly_max_price**
- 정의: 연도별 최고 거래가(선수/카드/일자 포함)
- 단위: 금액(BP)
- 구현: 연도별 `max(price_value)` 및 해당 row

**B-012. alltime_top11_price**
- 정의: 전체기간 최고가 Top11(중복 선수 허용/비허용은 옵션)
- 단위: (player, price_value) Top11
- 구현: 전체기간 기준 내림차순 상위 11

---

## [C] 이벤트 윈도우 지표(Event Study, W=±7)
**C-001. event_pre_post_usage**
- 정의: 이벤트 전 7일 vs 후 7일 평균 출전수 비교
- 단위: 건수(평균), Δ(차이), Δ%(증감률)
- 구현: window slice → `mean(daily_appearance)` pre/post → diff

**C-002. event_pre_post_rank**
- 정의: 이벤트 전후 평균 순위 비교(낮을수록 인기↑)
- 단위: 순위(평균), Δ(변화량)
- 구현: window slice → `mean(daily_rank)` pre/post

**C-011. event_market_presence**
- 정의: 이벤트 전후 BestPrice Top18 진입 여부/빈도
- 단위: 진입일수/비율
- 구현: window slice → count(rank ≤ 18)

- **통계검정(공통):**
  - H0: 전후 차이 없음
  - H1: 전후 차이 있음(단측/양측 선택)
  - 제안: Wilcoxon 또는 Mann-Whitney U(표본작을 때), 보조로 t-test
  - 효과크기: Δ/표준편차 등 병기

---

## [D] 댓글·감정 지표(YouTube)
**D-001. player_mentions**
- 정의: 선수별 언급 댓글 수 (키워드 매핑 기준)
- 구현: KOREA/PORTUGAL_KEYWORDS 매칭

**D-002. sentiment_ratio**
- 정의: 긍·부정 비율(±7일 범위, 일자별 또는 전체)
- 구현: KoBERT 등 모델/사전 기반 분석 후 집계

**D-003. replies_engagement**
- 정의: 대댓글 유무/개수 비율
- 구현: reply_count > 0 비율, 평균 reply 수

**D-011. player_wordcloud_tokens**
- 정의: 특정 선수 언급 댓글의 상위 토큰 목록(워드클라우드용)
- 구현: 불용어 제거 후 빈도 상위 N개

---

## [E] 품질/검증(QA)
- 일자별 row수 < 기대 TopN의 60% → 경고
- (date, rank) 중복, (date, player) 중복 → 에러/경고
- 결측일(Missing Day) 비율 보고: 전체 달력 대비 유효 수집일 비율
- 모든 지표의 분모는 '유효 수집 일수' 기준으로 명시
