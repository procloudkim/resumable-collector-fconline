# 공개본 구성

이 저장소는 2025년 9월에 작성한 비공개 저장소에서 **코드와 문서만 추려 fresh history로 발행**한 것입니다.

원본 비공개 저장소는 그대로 유지되며 링크를 제공하지 않습니다. 이 저장소가 원본의 전체 이력과 같다고 주장하지 않습니다.

기준일은 2026-08-17입니다. 파일명이 `PROVENANCE.md`가 아닌 이유는 `docs/PROVENANCE.md`가 원본 문서로 이미 있기 때문입니다. 그쪽은 데이터 출처를 다루고, 이 문서는 공개본 구성을 다룹니다.

## 코드는 원본 그대로

`crawler/`, `app/`, `project/`, `project2/`, `scripts/`, `sentiment/`, `youtube_comments/`, `tests/`의 파이썬 파일은 **내용을 고치지 않았습니다.**

공개를 위해 코드를 손댈 필요가 없었습니다. 서비스 키는 처음부터 환경변수로만 읽고 있었고, 하드코딩된 자격 증명이나 개인 경로가 없었습니다.

## 뺀 것

| 대상 | 규모 | 이유 |
|---|---|---|
| `data_check/` | 25MB, 댓글 DB와 CSV | **작성자 핸들과 댓글 원문 2.4만 행.** 제3자 개인정보 |
| `analytics/` | 187MB, CSV와 parquet | 수집 결과물. 대상 서비스 이용약관 범위를 공개 재배포까지 넓히지 않음 |
| `data/` | 7.8MB | 수집 결과와 리포트 |
| `project/db/`, `project/backups/`, `project/eda_bundles/` | 117MB 중 대부분 | SQLite 데이터베이스, 이미지 묶음 |
| `project2/db/` | 22MB 중 대부분 | 수집 데이터베이스 |
| `docs/_archive/` | 29파일 | 내부 작업 문서 아카이브. **그중 한 건에 댓글 원문과 작성자 핸들이 표로 박혀 있었음** |
| `New_2025_PPT/`, `assets/` | 2.5MB | 발표 자료와 이미지 |
| `config/` 실제 설정 | 6파일 | `.sample` 만 남김 |
| 루트 임시 파일 | `tmp_*`, `TEMP_*`, `temp_*`, `docs.zip`, `pairs*.json`, `big_match_list.csv` | 작업 잔여물 |
| `LICENSE` | MIT | 아래 참조 |

원본 510MB에서 공개본 1.3MB가 됐습니다. 코드 160파일과 문서 30여 건이 남았습니다.

## `docs/_archive/`를 통째로 뺀 이유

이 판단이 이번 공개 작업에서 가장 중요합니다.

데이터 파일을 확장자 기준으로 전부 제외한 뒤에도, `docs/_archive/dfinfo/DFINFO_comments.md` 한 건에 실제 댓글 원문과 작성자 핸들이 CSV 행 형태로 들어 있었습니다. 데이터프레임 내용을 문서에 붙여 넣은 것이었습니다.

**데이터 계층만 막으면 놓칩니다.** 문서도 데이터가 될 수 있습니다.

해당 파일만 지우는 대신 `_archive/` 전체를 뺐습니다. 내부 작업 문서 아카이브는 공개 독자에게 가치가 낮고, 같은 성격의 유출이 더 있을 위험이 있습니다.

재발을 막기 위해 `scripts/check_public_tree.py`에 세 규칙을 넣었습니다.

- `youtube-author-handle` 작성자 핸들 패턴
- `youtube-comment-id` 댓글 ID 패턴
- `comment-dump-row` 댓글 CSV 행 패턴

CI가 매 커밋 실행합니다.

## 테스트 결과를 있는 그대로 적는다

데이터를 빼면 데이터를 읽는 테스트가 실패합니다. 숫자를 그대로 적습니다.

| 상태 | 통과 | 건너뜀 | 실패 |
|---|---:|---:|---:|
| 원본 저장소를 그대로 클론해 실행 | 44 | 2 | **11** |
| 공개본 (데이터 없음, 건너뛰기 적용) | 42 | 15 | 0 |

**실패 11건은 전부 제외한 데이터를 읽으려다 난 것**입니다. 코드 결함이 아닙니다.

이것을 처리하는 방법이 셋이었습니다. 해당 테스트를 삭제하거나, 데이터를 다시 넣거나, 데이터가 없으면 건너뛰게 하는 것입니다. 삭제는 원본에 데이터 검증 테스트가 있었다는 사실을 지우고, 재투입은 공개 결정을 뒤집습니다. 세 번째를 택했습니다.

루트 `conftest.py`를 새로 추가해 필요한 데이터 경로가 없으면 건너뛰게 했습니다. 원본 `tests/conftest.py`와 테스트 파일은 손대지 않았습니다.

**건너뜀이 2건 과합니다.** 모듈 단위로 건너뛰기 때문에, 데이터가 필요 없는데 같은 파일에 있다는 이유로 함께 건너뛴 테스트가 2건 있습니다. 44에서 42로 줄어든 차이가 그것입니다. 통과 수를 부풀리는 방향이 아니라 줄이는 방향이라 그대로 두었습니다.

건너뛴 15건 중 2건은 데이터와 무관합니다. `project/tests/test_parser_selectors.py`가 HTML fixture를 요구하는데 그 파일은 **원본에도 커밋된 적이 없습니다.** `fixtures/` 디렉터리에 `.gitkeep`만 있습니다. 공개 과정에서 뺀 것이 아닙니다.

`pytest -q -rs`로 돌리면 건너뛴 사유가 경로와 함께 출력됩니다.

## 라이선스를 빼는 이유

`DATA_LICENSE.md`는 `docs/` 아래로 옮겼습니다. 루트에 두면 GitHub이 코드 라이선스로 인식해 사이드바에 `Other`로 표시합니다. 그 문서는 데이터 출처의 이용 약관을 적은 것이지 코드 사용 권리를 준 것이 아닙니다. 내용은 원본 그대로이며 위치만 바꿨습니다.


원본에는 MIT 라이선스가 있었습니다. 공개본에서는 부여하지 않습니다.

공개 열람과 복제 및 재사용 허가는 다른 문제입니다. 포트폴리오 저장소의 목적은 전자이고, 수집 대상 서비스의 데이터를 다루는 코드라 재배포 허가까지 열 근거가 없습니다.

데이터 취급 조건은 `docs/DATA_LICENSE.md`에 그대로 남겨 두었습니다.

## 이 저장소에서 확인되는 것과 확인되지 않는 것

| 확인되는 것 | 확인 방법 |
|---|---|
| 재시작 가능한 수집 구조 | `crawler/`, `project/app/`, `project2/app/` |
| 중단 재개 테스트 | `project2/test/test_resume_state.py` |
| 복합키 UPSERT 저장 | `project2/app/writer.py`, `project/app/storage.py` |
| 정적 요청 우선, 실패 시 브라우저 승급 | `crawler/fetcher.py`, `crawler/selenium_utils.py` |
| 감성 사전과 규칙 기반 스코어러 | `sentiment/` |
| 거버넌스 문서 7종 | `docs/` |
| 대시보드 4개 탭 구성 | `app/`, `streamlit_app.py` |

| 확인되지 않는 것 | 이유 |
|---|---|
| 분석 재현 | 수집 데이터가 없다 |
| 본문에 적은 행 수 | 원본 저장소의 산출물 기준이며 이 저장소에서 재계산할 수 없다 |
| 대시보드 화면 | 데이터가 없어 빈 화면으로 뜬다 |
| 커밋 이력 | fresh history 로 발행했다 |
| 테스트 커버리지 | 원본에도 측정 설정이 없었다 |

## 문서가 가리키는데 여기 없는 파일

문서 안의 경로 인용 52건이 이 저장소에서 해소되지 않습니다. 네 가지 서로 다른 이유이므로 나눠 적습니다. **하나도 이식 누락이 아닙니다.**

### 1. 실행하면 생기는 것

코드가 만들어 내는 산출물입니다. 저장소에 담을 대상이 아닙니다.

| 인용 | 만드는 주체 |
|---|---|
| `data/processed/*.csv` (`daily_trade`, `top10_trend`, `daily_top_players`, `comments_with_sentiment` 등) | `scripts/preprocess_*.py`, 수집기 |
| `data/reports/*` (`csv_summary.txt`, `data_manifest.json`, `daily_trade_eda.md`) | `scripts/generate_data_manifest.py`, EDA 스크립트 |
| `data/meta/spid.json`, `data/meta/spposition.json` | 메타 수집기. Nexon 정적 자원의 로컬 사본 |
| `project2/state/{resume_state,failures_*,nodata_*}.txt` | 재개 상태 파일. 중단 지점을 여기에 적는다 |
| `project2/out/topdailyrecord_YYYY-MM.csv`, `project/data/csv/bestprice_YYYY-MM.csv` | 월별 수집 산출물. `YYYY-MM`은 자리표시자 |
| `analytics/clean/*.clean.csv`, `project/eda_bundles/*` | 분석 레이어 산출물 |
| `config/pairs.json` | `scripts/build_pairs_from_raw.py` 가 RAW 에서 생성 |
| `data/images/*.png` | 이미지 로컬 캐시. `app/services/images.py` 가 받아서 채운다 |

### 2. 쓰는 사람이 만드는 것

`config/` 에 `.sample.` 이 붙은 원본이 있습니다. 복사해서 이름을 바꾸면 됩니다.

| 필요한 파일 | 여기 있는 원본 |
|---|---|
| `config/youtube_videos.txt` | `config/youtube_videos.sample.txt` |
| `config/rankers.txt` | `config/rankers.sample.txt` |
| `config/events.csv` | `config/events.sample.csv` |
| `config/logo_labels_ko.json` | `config/logo_labels_ko.sample.json` |
| `.streamlit/secrets.toml` | 없음. 키는 `.env` 로 넣는 것을 권한다 |

### 3. 일부러 뺀 것

| 인용 | 뺀 이유 |
|---|---|
| `docs/_archive/dfinfo/DFINFO_comments.md` | 제3자 댓글 원문과 작성자 핸들. 위의 `docs/_archive/` 절 참조 |
| `2025-09-13-newcrawling.txt` | 작업 중 메모. 산출물이 아니다 |

### 4. 원본에도 없던 것

원본 저장소에도 존재하지 않는 인용입니다. 이 공개 작업 때문에 끊긴 것이 아니라 **처음부터 끊겨 있었습니다.** 고치지 않고 그대로 둡니다. 원본을 손대면 이 저장소가 원본 그대로라는 말이 거짓이 되기 때문입니다.

`docs/CODE_TECHNICAL_SUMMARY_KR.md`, `SUMMARY.md`, `docs/check/version_selectors.yaml`, `data/sample/top10_trend.sample.csv`

문서가 실제 트리보다 앞서 나간 흔적입니다. 문서를 먼저 쓰고 파일을 나중에 만들면 이렇게 됩니다.
