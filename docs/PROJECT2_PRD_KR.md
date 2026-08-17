# PRD: 출전 랭킹 수집(프로젝트2)

## 배경/문제
- FC Online 데이터센터의 ‘출전’ 부문 일별 랭킹을 장기간 수집해 분석/참조 가능한 구조로 보관할 필요
- 페이지는 동적 로딩이므로 완전 렌더링(브라우저) 기반 수집이 안전

## 목표/KPI
- 날짜 범위(2020-05-20 ~ 2025-09-11) 전체 수집 완료
- ETA/진행률 가시화, 중단 후 재개(멱등)
- CSV(월별) + SQLite(UPSERT, PK=(date,rank)) 동시 저장

## 범위/비범위
- 범위: 수집(Selenium), 파싱(BeautifulSoup), 저장(CSV/SQLite), 재개/상태 관리, 무자료/실패 처리
- 비범위: 대규모 분산 크롤러, 시각화 대시보드, 오디오/비디오 콘텐츠 처리

## 성공조건(AC)
- CLI 옵션: `--from/--to/--resume/--fast/--headful/--hourly-log/--target-end/--csv-dir/--db-path/--state-dir`
- 콘솔 `[PROGRESS] ...` 출력 및 `state/progress.json` 업데이트
- 무자료 페이지는 실패로 카운트하지 않고 `nodata_YYYY-MM-DD.txt` 기록
- 실패 시 `failures_YYYY-MM-DD.txt` 및 `raw_html/` 스냅샷(파싱 실패) 생성

## 리스크/대응
- DOM 변경: 셀렉터 유니온 사용(`#divPalyerStatDetail|#divPlayerStatDetail|.tbody .tr`) + 스냅샷 보관
- 차단/지연: `--fast`(이미지 차단+eager), 대기조건 강화, 재개로 이어가기
- 중복: CSV는 append이므로 날짜별 재실행은 주의(실패일만 재시도 권장), DB는 UPSERT로 멱등

