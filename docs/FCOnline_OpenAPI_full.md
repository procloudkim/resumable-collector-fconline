
# EA SPORTS FC 온라인 Open API 정리 (NEXON)  
**최종 업데이트:** 2025-09-11 (Asia/Seoul)

> 본 문서는 **https://openapi.nexon.com/ko/game/fconline/** 포털의 구조(좌측 네비게이션: *계정 정보 조회·매치 정보 조회·랭커 정보 조회·메타데이터 정보 조회·이미지 정보 조회*)를 기준으로, 하위 API들을 **엔드포인트/파라미터/요청 예시/응답 구조** 순으로 체계화한 정리본입니다. 포털의 “Try it out” 영역은 **로그인 및 API Key** 필요, 또한 페이지는 동적 로딩 방식으로 일부 내용이 크롤링 도구에 노출되지 않습니다. 따라서 아래 정리는 **공식 페이지에 명시된 항목을 최대한 그대로 재구성**하되, 긴 원문을 그대로 복제하지 않고 요약·재서술하였습니다. 각 섹션 끝에 **공식 출처**를 병기했습니다. 포털의 최신 화면과 값(예: Example Value, Schema 세부)은 로그인 상태에서 “Try it out”으로 확인 가능합니다. citeturn14search3turn3view0

---

## 0) 공통 정보

- **Base URL (서버)**: `https://open.api.nexon.com`  citeturn6search1
- **인증(필수 헤더)**: `x-nxopen-api-key: <YOUR_API_KEY>`  citeturn6search1
- **응답 형식**: JSON (NEXON Open API 통일 규격)  citeturn6search1
- **오류 코드(발췌)**:  
  `OPENAPI00001(500)`, `OPENAPI00002(403)`, `OPENAPI00003(400)`, `OPENAPI00004(400)`, `OPENAPI00005(400)`, `OPENAPI00006(400)`, `OPENAPI00007(429)`, `OPENAPI00009(400)`, `OPENAPI00010(400)`, `OPENAPI00011(503)`  citeturn6search1
- **데이터 적재 주기(포털 표기)**: **매시 정각 기준 약 2시간 전 데이터 반영**(예: 15:05 호출 → 13:00까지 데이터)  citeturn17search4

> **주의**: 2024-03-07 이후 FC온라인 API는 `open.api.nexon.com`을 사용하며, **메타데이터**는 `open.api.nexon.com/static/fconline/meta/*.json`으로 이관되었습니다. (구 `public.api.nexon.com`/`static.api.nexon.co.kr` 경로는 종료)  citeturn16search1

---

## 1) 계정 정보 조회 (User)

### 1.1 계정 식별자(ouid) 조회
- **Method / Path**: `GET /fconline/v1/id`
- **Query Parameters**
  | 파라미터 | 타입 | 필수/비고 |
  |---|---:|---|
  | `nickname` | string | 필수. FC 온라인 닉네임 |
- **설명**: 닉네임으로 **ouid**(계정 고유 식별자)를 획득합니다. 포털 메뉴 트리 내 “계정 정보 조회”에 수록. citeturn5search1turn8search2
- **요청 예시**
  ```bash
  curl -G 'https://open.api.nexon.com/fconline/v1/id' \
    --data-urlencode 'nickname=YourNickname' \
    -H 'x-nxopen-api-key: <YOUR_API_KEY>'
  ```
- **응답 개요(요약 스키마)**:  
  ```json
  {
    "ouid": "string"
  }
  ```
  (필드명 `ouid`는 포털 내 설명에 명시. 실제 응답은 포털 “Try it out”에서 확인 권장) citeturn5search1

---

### 1.2 유저 기본 정보 조회
- **Method / Path**: `GET /fconline/v1/user/basic`
- **Query Parameters**
  | 파라미터 | 타입 | 필수/비고 |
  |---|---:|---|
  | `ouid` | string | 필수. 1.1에서 조회한 값 |
- **설명**: 유저의 기본 프로필(예: 닉네임, 레벨 등)을 제공합니다. 포털 섹션 명: “기본 정보 조회”. citeturn5search1
- **요청 예시**
  ```bash
  curl -G 'https://open.api.nexon.com/fconline/v1/user/basic' \
    --data-urlencode 'ouid=OUID_VALUE' \
    -H 'x-nxopen-api-key: <YOUR_API_KEY>'
  ```
- **응답 개요(요약 스키마)**: **유저 기본 속성 필드 집합**(닉네임, 레벨 등). 실제 필드/예시는 포털 “Try it out”에서 확인. citeturn6search1

---

### 1.3 유저 역대 최고 등급 조회
- **Method / Path**: `GET /fconline/v1/user/maxdivision`
- **Query Parameters**
  | 파라미터 | 타입 | 필수/비고 |
  |---|---:|---|
  | `ouid` | string | 필수 |
- **설명**: 유저의 **역대 최고 등급**(division) 정보를 반환합니다. citeturn10search3
- **요청 예시**
  ```bash
  curl -G 'https://open.api.nexon.com/fconline/v1/user/maxdivision' \
    --data-urlencode 'ouid=OUID_VALUE' \
    -H 'x-nxopen-api-key: <YOUR_API_KEY>'
  ```
- **응답 개요(요약 스키마)**: division 관련 식별자 목록/속성. (상세 스키마는 포털에서 확인) citeturn10search4

---

### 1.4 유저의 매치 기록 조회
- **Method / Path**: `GET /fconline/v1/user/match`
- **Query Parameters**
  | 파라미터 | 타입 | 필수/비고 |
  |---|---:|---|
  | `ouid` | string | 필수 |
  | `matchtype` | int | 옵션. 매치 종류 코드 |
  | `offset` | int | 옵션. 기본 0 |
  | `limit` | int | 옵션. 커뮤니티 사례상 최대 100 보고(공식 “Try it out”에서 확인 권장) |
- **설명**: 유저의 매치 **matchId 리스트**를 페이징으로 반환합니다. citeturn10search3
- **요청 예시**
  ```bash
  curl -G 'https://open.api.nexon.com/fconline/v1/user/match' \
    --data-urlencode 'ouid=OUID_VALUE' \
    --data-urlencode 'matchtype=50' \
    --data-urlencode 'offset=0' \
    --data-urlencode 'limit=100' \
    -H 'x-nxopen-api-key: <YOUR_API_KEY>'
  ```
- **응답 개요(요약 스키마)**:
  ```json
  [
    "matchId-1",
    "matchId-2",
    "..."
  ]
  ```
  (limit 상한 100에 대한 실사용 예시는 커뮤니티 글 기준. 공식값은 포털에서 확인) citeturn9search2

---

### 1.5 유저의 거래 기록 조회
- **Method / Path**: `GET /fconline/v1/user/trade`
- **Query Parameters**
  | 파라미터 | 타입 | 필수/비고 |
  |---|---:|---|
  | `ouid` | string | 필수 |
  | `tradetype` | string | 옵션. 예: `buy` 또는 `sell`(커뮤니티 용례). |
  | `offset` | int | 옵션 |
  | `limit` | int | 옵션 |
- **설명**: 유저의 **이적시장 거래 내역**(구매/판매)을 조회합니다. 포털 항목에 “유저의 거래 기록 조회”로 표기. citeturn10search3
- **요청 예시**
  ```bash
  curl -G 'https://open.api.nexon.com/fconline/v1/user/trade' \
    --data-urlencode 'ouid=OUID_VALUE' \
    --data-urlencode 'tradetype=buy' \
    --data-urlencode 'offset=0' \
    --data-urlencode 'limit=100' \
    -H 'x-nxopen-api-key: <YOUR_API_KEY>'
  ```
- **응답 개요(요약 스키마)**: 거래 일시, 선수 식별자(spid), 강화 단계, 가격 등 거래 항목 리스트. (정확한 필드명은 “Try it out”에서 확인) citeturn11search1

> **참고**: FC 온라인 **데이터센터**의 공지/가이드와 경제 관련 공지에서 이적시장/트레이드 동작 배경을 확인할 수 있습니다. 본 API는 그 기록을 기계적으로 조회하는 용도입니다. citeturn11search4turn11search7turn11search5

---

## 2) 매치 정보 조회 (Match)

### 2.1 매치 상세 기록 조회
- **Method / Path**: `GET /fconline/v1/match-detail`
- **Query Parameters**
  | 파라미터 | 타입 | 필수/비고 |
  |---|---:|---|
  | `matchid` | string | 필수. 1.4에서 받은 matchId |
- **설명**: 단일 경기의 상세 기록(참가자, 이벤트, 포지션/좌표 등)을 반환합니다. citeturn17search4
- **요청 예시**
  ```bash
  curl -G 'https://open.api.nexon.com/fconline/v1/match-detail' \
    --data-urlencode 'matchid=MATCH_ID' \
    -H 'x-nxopen-api-key: <YOUR_API_KEY>'
  ```
- **응답 개요(요약 스키마)**: 상위에 `matchId`, `matchDate`, `stadium`, `teams[]`, `players[]`, `events[]` 등(실제 필드는 포털에서 확인). **슈팅 좌표(`ShootDetailDTO.x`, `y`)는 0~1 범위**이며 1 초과는 경기장 밖 케이스(0 또는 1로 치환 가능)로 공지되어 있습니다. citeturn0search6

---

## 3) 랭커 정보 조회 (Ranker)

### 3.1 랭커 스탯 조회
- **Method / Path**: `GET /fconline/v1/ranker-stats`
- **설명**: **상위(Top) 랭커 집단**을 기준으로 선수/조합의 성과 지표를 제공합니다. 포털에 “랭커 정보 조회”로 표기되며, 엔드포인트 명도 확인됩니다. 자세한 파라미터·예시는 로그인 후 “Try it out”에서 확인하세요. citeturn14search0

> **힌트(메뉴 구조 기반)**: 랭커 분석에는 **매치 종류 코드**(matchtype)와 선수 식별 정보가 관여합니다. 메타데이터와 함께 사용하면 해석이 수월합니다. citeturn14search0turn15search0

---

## 4) 메타데이터 정보 조회 (MetaData)

> **이 카테고리는 인증 없이 접근 가능한 정적 JSON 목록**을 제공합니다. (신규 체계: `/static/fconline/meta/*.json`)  citeturn16search1

- **매치 종류**: `GET /static/fconline/meta/matchtype.json` — 매치 타입 코드 테이블. citeturn6search0
- **선수 식별자(spid)**: `GET /static/fconline/meta/spid.json` — 선수 식별자 목록. citeturn6search0
- **시즌 아이디(seasonId)**: `GET /static/fconline/meta/seasonid.json` — 시즌 코드 테이블. citeturn16search0
- **선수 포지션(spposition)**: `GET /static/fconline/meta/spposition.json` — 포지션 코드 테이블. citeturn15search0
- **등급 식별자(division)**: `GET /static/fconline/meta/division.json` — 랭크/등급 코드 테이블. citeturn15search0

**응답 개요(공통)**: 위 JSON들은 **코드/이름**(예: `id`, `name`)으로 구성된 배열 형태가 일반적입니다. 실제 스키마/샘플은 각 JSON을 직접 열어 확인하세요. citeturn16search1

---

## 5) 이미지 정보 조회 (Image)

> **선수 이미지(액션샷)를 식별자 기준으로 제공**합니다. 경로 패턴은 포털에 다음과 같이 안내됩니다. citeturn17search0

- **spid 기준**: *선수 고유 식별자(spid)로 액션샷 이미지 조회*
- **pid 기준**: `GET /live/externalAssets/common/playersAction/p{pid}.png` — 선수 식별자(pid) 기반 PNG

> 실제 요청 시에는 `https://open.api.nexon.com` 호스트와 식별자 값을 결합해 접근합니다. 예시:  
> `https://open.api.nexon.com/live/externalAssets/common/playersAction/p12345.png` (식별자/가용성은 시점·라이선스에 따라 다를 수 있음)  citeturn17search0

---

## 부록 A) 요청/응답 공통 규칙 요약

- **헤더**: 모든 API 호출에 `x-nxopen-api-key` 포함. 응답이 오류일 경우 코드/사유는 표의 에러코드를 참고. citeturn6search1
- **호출 제한**: 과다 호출 시 `429 Too Many Requests`가 반환될 수 있습니다. citeturn6search1
- **데이터 시차**: FC 온라인 데이터는 포털 공지 기준으로 **두 시간 전 시점까지 반영**됩니다. 백필·정기점검 공지 확인 권장. citeturn17search4turn0search4

---

## 부록 B) 빠른 시작(cURL 스니펫)

1) **OUID 얻기 → 유저 매치목록 → 매치 상세** 순서
```bash
# 1) 닉네임으로 OUID
curl -G 'https://open.api.nexon.com/fconline/v1/id' \
  --data-urlencode 'nickname=YourNickname' \
  -H 'x-nxopen-api-key: <YOUR_API_KEY>'

# 2) 유저 매치 목록
curl -G 'https://open.api.nexon.com/fconline/v1/user/match' \
  --data-urlencode 'ouid=OUID_VALUE' \
  --data-urlencode 'matchtype=50' \
  --data-urlencode 'offset=0' \
  --data-urlencode 'limit=50' \
  -H 'x-nxopen-api-key: <YOUR_API_KEY>'

# 3) 매치 상세
curl -G 'https://open.api.nexon.com/fconline/v1/match-detail' \
  --data-urlencode 'matchid=MATCH_ID' \
  -H 'x-nxopen-api-key: <YOUR_API_KEY>'
```
(파라미터와 응답의 세부는 포털 “Try it out”에서 최신 확인) citeturn6search1

---

## 부록 C) 포털 탐색 팁

- 게임 메뉴: **EA SPORTS FC 온라인** → 좌측 카테고리(계정/매치/랭커/메타데이터/이미지)에서 API 목록 확인 → 각 항목 “Try it out”. citeturn14search3
- 메타데이터는 공개 JSON이라 스키마 파악이 쉽습니다. (경로 전환 공지 확인) citeturn16search1
- 좌표/필드 해석은 **공지**도 도움됩니다(예: 슈팅 x,y 좌표 0~1 범위). citeturn0search6

---

## 출처(Official)

- EA SPORTS FC 온라인 – NEXON Open API 메인/섹션 인덱스(계정/매치/랭커/메타/이미지) citeturn14search3turn3view0
- 계정/매치/랭커/메타데이터/이미지 섹션 페이지(동적) citeturn17search4turn14search0turn15search0turn16search0turn17search0
- Using the API(헤더·오류코드·테스트 절차) citeturn6search1
- 서비스/도메인 전환 공지(FC온라인 API·메타데이터 경로) citeturn16search1
- 매치 상세 좌표 공지(슈팅 x,y의 범위 정의) citeturn0search6

> 본 문서는 포털의 **원문 표현을 길게 복제하지 않고**, 동일한 구조·항목을 유지한 **정확한 요약/정리본**입니다. 예시 값과 전체 스키마는 계정으로 로그인 후 포털의 “Try it out”에서 그대로 확인/복사할 수 있습니다. citeturn6search1
