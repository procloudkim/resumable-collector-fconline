# BDD: 출전 랭킹 수집(프로젝트2)

Feature: 출전 랭킹을 날짜 범위로 수집해 CSV·SQLite에 기록하고 재개/무자료를 지원한다

  Background:
    Given Windows + Python 3.13 환경과 Chrome이 있다
    And `pip install -r project/requirements.txt`를 완료했다

  Scenario: 전체 기간 수집(진행률/ETA 출력)
    When `python -m project2.app.cli run --from 2020-05-20 --to 2025-09-11 --fast --hourly-log`를 실행하면
    Then 콘솔에 `[PROGRESS] d/N일 ... ETA ...` 형식의 로그가 출력된다
    And `project2/state/progress.json`이 갱신된다

  Scenario: 중단 후 재개
    Given 이전 실행 중 Ctrl+C로 중단되었다
    When `python -m project2.app.cli run --resume`를 실행하면
    Then 마지막 성공일의 다음 날부터 계속 처리한다
    And 완료 시 `project2/state/resume_state.txt`가 제거된다

  Scenario: 무자료 날짜 처리
    Given 특정 날짜 페이지에 “검색 결과가 없습니다” 메시지가 표시된다
    When 해당 날짜를 실행하면
    Then 실패로 카운트하지 않고 `project2/state/nodata_YYYY-MM-DD.txt`가 생성된다

  Scenario: 실패일 재시도
    Given `project2/state/failures_YYYY-MM-DD.txt`가 존재한다
    When 실패일로 단일 날짜 실행을 수행하면
    Then CSV/DB에 중복 없이 기록된다(DB는 UPSERT, CSV는 날짜별 재실행 자제)

