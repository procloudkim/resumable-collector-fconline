# RUNBOOK: 출전 랭킹 크롤러(project2)

## 목적
- FC 데이터센터 ‘출전’ 부문 일별 랭킹을 수집해 CSV·SQLite로 저장하고, 진행률/ETA·재개를 지원합니다.

## 사전 준비
- Windows 10/11 + Python 3.13 + PowerShell
- 의존성: `pip install -r project/requirements.txt` 또는 최소 `pip install selenium beautifulsoup4`
- Chrome 최신 설치(대부분 Selenium Manager가 드라이버를 자동 관리)

## 실행
- 전체 기간: `python -m project2.app.cli run --from 2020-05-20 --to 2025-09-11`
- 특정 기간: `python -m project2.app.cli run --from 2021-01-01 --to 2021-12-31`
- 재개: `python -m project2.app.cli run --resume`

## 옵션
- 성능: `--fast`(이미지 차단 + pageLoadStrategy=eager), `--headful`(창 표시)
- 진행: `--hourly-log`(1시간 주기 체크), `--target-end 2025-09-14T23:00`(목표 종료 시각)
- 출력 경로: `--csv-dir`, `--db-path`, `--state-dir`

## 산출물 경로
- CSV: `project2/out/topdailyrecord_YYYY-MM.csv`
- DB: `project2/db/topdailyrecord.db` (table: `top_daily_record`, PK=(date,rank))
- 상태: `project2/state/` — `progress.json`, `resume_state.txt`, `failures_*.txt`, `nodata_*.txt`, `raw_html/*.html`

## 동작 요약
1) Selenium(Headless)로 날짜별 페이지 로드 → ‘출전’ 탭 활성 확인
2) 필요한 DOM이 보일 때까지 대기(또는 “검색 결과가 없습니다” 감지)
3) BeautifulSoup으로 파싱 → 레코드 생성
4) 월별 CSV append, SQLite UPSERT(멱등)
5) 진행률/ETA 로깅, 상태 파일 갱신 → 재개 지원

## 무자료/실패 처리
- “검색 결과가 없습니다” 감지 시 실패로 치지 않고 `nodata_YYYY-MM-DD.txt` 저장
- 파싱/저장 실패 시 `failures_YYYY-MM-DD.txt` 저장 + `raw_html/YYYY-MM-DD.html` 스냅샷(파싱 실패)

## 재시도
- 단일 날짜: `python -m project2.app.cli run --from 2022-06-28 --to 2022-06-28 --fast`
- 실패일 일괄: PowerShell에서 `Get-ChildItem project2/state -Filter 'failures_*.txt' | ForEach-Object { $d = ($_.BaseName -replace '^failures_',''); python -m project2.app.cli run --from $d --to $d --fast }`

## ETA/진행 확인
- 콘솔: `[PROGRESS] 123/1941일 (6.3%) | 경과 00:12:34 | ETA 2025-09-14 21:10 | 실패일 0 | 누적행 2345`
- 파일: `project2/state/progress.json`

## 트러블슈팅
- Chrome/Driver 오류: Chrome 업데이트, `pip install --upgrade selenium`, 재부팅
- CAPTCHA/차단 의심: 기간/요청간격 늘리고 `--fast` 해제 후 재시도
- DOM 변경: `project2/state/raw_html/*.html` 열람 → 셀렉터 보강 필요 시 `project2/app/parser/selectors.py` 수정

