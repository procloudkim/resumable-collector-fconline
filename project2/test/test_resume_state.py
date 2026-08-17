# -*- coding: utf-8 -*-
"""
test_resume_state.py: 중단 후 재개(resume) 기능에 대한 테스트.
- 중간에 중단된 상태에서 상태 파일이 올바르게 기록되는지
- resume 옵션으로 재실행 시 올바른 날짜부터 시작하는지 등을 검증합니다.
"""

import os
from datetime import datetime, timedelta

import project2.app.runner as runner
import project2.app.cli as cli


def test_incomplete_run_state(tmp_path, monkeypatch):
    """
    인위적으로 크롤링을 중단시켰을 때 상태 파일(resume_state.txt)이 올바르게 기록되는지 테스트.
    """
    state_file = runner.STATE_FILE
    # 테스트 전 상태 파일이 존재하면 제거
    if os.path.exists(state_file):
        os.remove(state_file)

    # 더미 DataFetcher: 첫 번째 호출은 정상, 두 번째 호출에서 KeyboardInterrupt 발생시켜 중단 상황을 재현
    class DummyFetcher:
        def __init__(self):
            self.calls = 0

        def start(self):
            pass

        def fetch(self, date):
            if self.calls == 0:
                self.calls += 1
                return "<html>dummy</html>"  # 첫 번째 호출은 가짜 HTML 반환
            else:
                # 두 번째 호출 시 KeyboardInterrupt 발생 (중단)
                raise KeyboardInterrupt

        def close(self):
            pass

    # 더미 parser.parse_page: 항상 한 개의 더미 기록을 반환
    def dummy_parse_page(date, html):
        return [{
            "date": date.strftime("%Y-%m-%d"),
            "rank": 1,
            "선수 기본정보": "TEST, 0, 0 0, 0",
            "출전": 0,
            "공격 포인트": "",
            "득점": "",
            "도움": "",
            "유효 슈팅": "",
            "일반 슈팅": "",
            "패스 성공률": "",
            "드리블 성공률": "",
            "공중볼 경합 성공률": "",
            "가로채기": "",
            "태클 성공률": "",
            "차단 성공률": "",
            "선방(골 차단)": "",
            "평점": "",
        }]

    # writer 모듈의 파일/DB 기록 함수를 더미로 치환 (실제 파일 쓰지 않도록)
    monkeypatch.setattr(runner, "DataFetcher", DummyFetcher)
    monkeypatch.setattr(runner.parser, "parse_page", dummy_parse_page)
    monkeypatch.setattr(runner.writer, "write_csv", lambda date, records: None)
    monkeypatch.setattr(runner.writer, "write_db", lambda records: None)

    # 2일 범위로 실행 (두 번째 날에 중단되도록)
    start_date = datetime(2020, 5, 20).date()
    end_date = datetime(2020, 5, 21).date()
    # runner.run을 실행 - DummyFetcher 설정에 따라 두 번째 fetch에서 KeyboardInterrupt 발생
    runner.run(start_date, end_date, resume=False)

    # 실행 후 상태 파일 확인
    assert os.path.exists(state_file), "상태 파일이 생성되어야 합니다."
    with open(state_file, 'r', encoding='utf-8') as sf:
        content = sf.read().strip().split()
    # end_date와 last_date 라인이 기록되어 있는지 검증
    lines = {line.split('=')[0]: line.split('=')[1] for line in content if '=' in line}
    # end_date는 2020-05-21 이어야 함 (target)
    assert lines.get("end_date") == "2020-05-21"
    # last_date는 2020-05-20 이어야 함 (첫째 날 완료 후 중단)
    assert lines.get("last_date") == "2020-05-20"


def test_resume_continues_from_state(monkeypatch):
    """
    상태 파일을 기반으로 재개 실행 시 올바른 일자부터 시작하여 모든 남은 일을 처리하는지 테스트.
    """
    state_file = runner.STATE_FILE
    # 상태 파일에 임의의 중단 상태 기록 (예: 2020-05-20까지 완료, 목표 2020-05-22)
    with open(state_file, 'w', encoding='utf-8') as sf:
        sf.write("end_date=2020-05-22\n")
        sf.write("last_date=2020-05-20\n")

    # DummyFetcher: 호출 시 항상 가짜 HTML 반환 (중단 없음)
    class DummyFetcher2:
        def __init__(self):
            pass

        def start(self):
            pass

        def fetch(self, date):
            return "<html>dummy</html>"

        def close(self):
            pass

    # dummy parser: 항상 한 개의 더미 기록 반환
    def dummy_parse_page(date, html):
        return [{
            "date": date.strftime("%Y-%m-%d"),
            "rank": 1,
            "선수 기본정보": "PLAYER",
            "출전": 1,
            "공격 포인트": "",
            "득점": "",
            "도움": "",
            "유효 슈팅": "",
            "일반 슈팅": "",
            "패스 성공률": "",
            "드리블 성공률": "",
            "공중볼 경합 성공률": "",
            "가로채기": "",
            "태클 성공률": "",
            "차단 성공률": "",
            "선방(골 차단)": "",
            "평점": "",
        }]

    # writer 모듈의 write_csv/write_db를 호출 횟수 추적용 더미로 대체
    calls = {"csv": 0, "db": 0}

    def dummy_write_csv(date, records):
        calls["csv"] += 1

    def dummy_write_db(records):
        calls["db"] += 1

    monkeypatch.setattr(runner, "DataFetcher", DummyFetcher2)
    monkeypatch.setattr(runner.parser, "parse_page", dummy_parse_page)
    monkeypatch.setattr(runner.writer, "write_csv", dummy_write_csv)
    monkeypatch.setattr(runner.writer, "write_db", dummy_write_db)

    # CLI를 통해 --resume 실행
    cli.main(['run', '--resume'])

    # resume 실행 후 상태 파일이 삭제되었는지 확인 (모든 작업 완료)
    assert not os.path.exists(state_file), "모든 날짜 처리 후 상태 파일은 삭제되어야 합니다."
    # Dummy writer 호출 횟수로 2020-05-21, 2020-05-22 두 날짜가 처리되었는지 확인
    assert calls["csv"] == 2 and calls["db"] == 2, "남은 2일의 데이터가 모두 처리되어야 합니다."

