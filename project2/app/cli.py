# -*- coding: utf-8 -*-
"""
cli 모듈: 명령행 인터페이스(CLI)를 제공하여 사용자가 크롤러를 실행할 수 있도록 합니다.
WHY: 스크립트를 편리하게 실행하고, 날짜 범위나 재개 여부 등의 옵션을 전달하기 위함입니다.
HOW: argparse를 이용하여 하위 명령 'run'과 옵션 (--from, --to, --resume)을 처리하며,
     입력받은 옵션에 따라 runner.run을 호출합니다.
"""

import argparse
import os
from datetime import datetime

from project2.app import runner
from project2.app import writer


def main(argv=None):
    # argparse로 명령행 인자 파싱
    parser = argparse.ArgumentParser(prog="project2", description="FC온라인 데이터센터 출전 랭킹 크롤러")
    subparsers = parser.add_subparsers(dest="command")
    # 'run' 명령의 하위 파서 설정
    run_parser = subparsers.add_parser('run', help="크롤러 실행 (데이터 수집 시작)")
    run_parser.add_argument('--from', dest='from_date', help="시작 날짜 (YYYY-MM-DD)", metavar='YYYY-MM-DD')
    run_parser.add_argument('--to', dest='to_date', help="종료 날짜 (YYYY-MM-DD)", metavar='YYYY-MM-DD')
    run_parser.add_argument('--resume', dest='resume', action='store_true', help="이전 중단 지점부터 이어서 실행")
    # 성능/디버깅 옵션
    run_parser.add_argument('--fast', dest='fast', action='store_true', help="빠른 모드(이미지 차단, eager 로드)")
    run_parser.add_argument('--headful', dest='headful', action='store_true', help="브라우저 창 표시(headful)")
    # BestPrice CLI 스타일의 경로 재정의 옵션 (선택)
    run_parser.add_argument('--csv-dir', dest='csv_dir', help="CSV 출력 디렉토리(선택)")
    run_parser.add_argument('--db-path', dest='db_path', help="SQLite DB 파일 경로(선택)")
    run_parser.add_argument('--state-dir', dest='state_dir', help="STATE 디렉토리(선택)")
    run_parser.add_argument('--hourly-log', dest='hourly_log', action='store_true', help='1시간 주기 진행 체크 출력')
    run_parser.add_argument('--target-end', dest='target_end', type=str, help='목표 종료 시각 ISO 문자열 (예: 2025-09-13T18:00)')

    args = parser.parse_args(argv)

    if args.command == 'run':
        # 경로 재정의가 들어오면 writer 경로 구성 업데이트
        if args.csv_dir or args.db_path or args.state_dir:
            writer.configure_paths(out_dir=args.csv_dir, db_path=args.db_path, state_dir=args.state_dir)
            # runner.STATE_FILE도 최신 STATE_DIR 기준으로 갱신
            runner.STATE_FILE = os.path.join(writer.STATE_DIR, "resume_state.txt")
        # 성능/표시 관련 옵션은 환경변수로 전달하여 fetcher에서 적용
        if args.fast:
            os.environ["PROJECT2_FAST"] = "1"
        if args.headful:
            os.environ["PROJECT2_HEADFUL"] = "1"
        # 날짜 범위 해석
        if args.resume:
            # resume 모드: 상태 파일에서 이전 진행 상황을 불러옴
            try:
                with open(runner.STATE_FILE, 'r', encoding='utf-8') as sf:
                    lines = sf.readlines()
                state_info = {}
                for line in lines:
                    if '=' in line:
                        key, val = line.strip().split('=', 1)
                        state_info[key] = val
            except FileNotFoundError:
                print("[ERROR] 재개할 상태 정보가 없습니다. --resume 옵션 없이 실행하십시오.")
                return
            # 상태 파일에서 마지막 처리 날짜와 목표 종료 날짜 읽기
            last_date_str = state_info.get('last_date')
            end_date_str = state_info.get('end_date')
            if not last_date_str:
                print("[ERROR] 상태 파일에 last_date 정보가 없습니다. 새로 시작하십시오.")
                return
            if not end_date_str:
                print("[ERROR] 상태 파일에 end_date 정보가 없습니다. 새로 시작하십시오.")
                return
            try:
                last_date = datetime.strptime(last_date_str, "%Y-%m-%d").date()
                end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
            except ValueError:
                print("[ERROR] 상태 파일의 날짜 형식이 올바르지 않습니다.")
                return
            # 재개 시작일은 last_date의 다음 날
            start_date = last_date + runner.timedelta(days=1)
            if start_date > end_date:
                print("[INFO] 이전 실행에서 이미 모든 날짜를 완료했습니다.")
                return
            # runner.run 호출 (resume 모드)
            # target_end 파싱
            target_end = None
            if args.target_end:
                try:
                    target_end = datetime.fromisoformat(args.target_end)
                except Exception:
                    target_end = None
            runner.run(start_date, end_date, resume=True, hourly_log=bool(args.hourly_log), target_end=target_end)
        else:
            # 일반 모드: 인자로 받은 from/to 사용, 없으면 기본 전체 범위 사용
            if args.from_date:
                try:
                    start_date = datetime.strptime(args.from_date, "%Y-%m-%d").date()
                except ValueError:
                    print("[ERROR] --from 날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형태로 입력하세요.")
                    return
            else:
                # 명시적 시작 날짜 없으면 전체 범위 시작값 (2020-05-20)
                start_date = datetime(2020, 5, 20).date()
            if args.to_date:
                try:
                    end_date = datetime.strptime(args.to_date, "%Y-%m-%d").date()
                except ValueError:
                    print("[ERROR] --to 날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형태로 입력하세요.")
                    return
            else:
                # 명시적 종료 날짜 없으면 전체 범위 종료값 (2025-09-11)
                end_date = datetime(2025, 9, 11).date()
            if start_date > end_date:
                print("[ERROR] 시작 날짜가 종료 날짜보다 늦습니다.")
                return
            # runner.run 호출 (일반 모드)
            target_end = None
            if args.target_end:
                try:
                    target_end = datetime.fromisoformat(args.target_end)
                except Exception:
                    target_end = None
            runner.run(start_date, end_date, resume=False, hourly_log=bool(args.hourly_log), target_end=target_end)
    else:
        # 명령이 지정되지 않은 경우 도움말 출력
        parser.print_help()


if __name__ == "__main__":
    main()
