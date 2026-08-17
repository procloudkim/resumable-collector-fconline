# -*- coding: utf-8 -*-
"""
runner 모듈: fetcher, parser, writer를 조합하여 전체 크롤링 작업을 수행하는 로직을 구현합니다.
WHY: 모듈들을 유기적으로 연결하여 지정된 날짜 범위의 데이터를 순차적으로 수집하고 저장하기 위함입니다.
HOW: 주어진 시작~종료 날짜에 대해 매일 데이터를 수집/파싱/저장하며, 중간 중단 시 재시작할 수 있도록 상태를 파일로 기록합니다.
"""

import os
import time
from datetime import datetime, timedelta
from pathlib import Path

from project2.app import parser
from project2.app import writer
from project2.app import progress

# 테스트에서 monkeypatch로 주입 가능한 훅. 기본은 None으로 두고 실행 시 지연 로드합니다.
DataFetcher = None  # type: ignore

# 상태 파일 경로
STATE_FILE = os.path.join(writer.STATE_DIR, "resume_state.txt")


def run(start_date, end_date, resume=False, *, hourly_log: bool = False, target_end: datetime | None = None):
    """
    지정된 날짜 범위 [start_date, end_date]에 대해 출전 랭킹 데이터를 수집하여 CSV와 DB에 기록합니다.
    resume=True인 경우 이전 중단 지점부터 재개합니다.

    WHY: 실패/중단 상황에서도 재실행 시 중복 없이 이어받아 신뢰성을 확보합니다.
    HOW: 상태 파일에 목표 종료일과 마지막 처리일을 기록하고, 마지막 처리일의 다음 날부터 이어서 처리합니다.
    """
    # DataFetcher 초기화 및 브라우저 시작
    # 테스트 용이성을 위해 지연 로딩 및 주입 가능(monkeypatch)하게 설계합니다.
    FetcherCls = globals().get("DataFetcher")
    if FetcherCls is None:
        from project2.app.fetcher import DataFetcher as FetcherCls  # 실제 실행 시에만 Selenium 의존성 로드
    fetcher = FetcherCls()
    fetcher.start()
    incomplete_run = False  # 크롤링 완료 여부 추적 (중단 시 True로 설정)
    try:
        # 진행 로그/상태 초기화
        dates_total = (end_date - start_date).days + 1
        state_path = os.path.join(writer.STATE_DIR, "progress.json")
        st = progress.load_state(Path(state_path)) if resume else None
        if not st:
            st = progress.init_state(Path(state_path), start_date.isoformat(), end_date.isoformat(), dates_total)
        print(progress.fmt_scenario(start_date.isoformat(), end_date.isoformat()), flush=True)
        start_ts = time.time()
        last_hourly = start_ts
        done_days = st.done_days
        failed_days = st.failed_days
        total_rows = st.total_rows

        # 상태 파일 초기 설정
        if not resume:
            # 새로운 실행: 상태 파일에 target(종료일) 기록, last_date는 비워둠
            with open(STATE_FILE, 'w', encoding='utf-8') as sf:
                sf.write(f"end_date={end_date.strftime('%Y-%m-%d')}\n")
                sf.write("last_date=\n")
        # 날짜 반복 (start_date에서 end_date까지)
        current_date = start_date
        while current_date <= end_date:
            try:
                # 페이지 가져오기
                html = fetcher.fetch(current_date)
            except Exception as e:
                # 데이터 가져오기 실패: 해당 일자를 실패 목록에 기록하고 건너뜀
                _log_failure(current_date, f"FETCH_ERROR: {e}")
                failed_days += 1
                st.failed_days = failed_days
                progress.save_state(Path(state_path), st)
                done_days += 1
                st.done_days = done_days
                print(progress.fmt_progress(done_days, dates_total, start_ts, total_rows, failed_days), flush=True)
                if hourly_log and (time.time() - last_hourly) >= 3600:
                    print(progress.fmt_hourly(ok_days=done_days - failed_days), flush=True)
                    last_hourly = time.time()
                current_date += timedelta(days=1)
                continue

            # 페이지에 공식 '검색 결과가 없습니다' 메시지가 있는 경우: 정상(무자료)으로 처리
            try:
                if html and ("검색 결과가 없습니다" in html):
                    _log_nodata(current_date)
                    # 상태 파일의 last_date 업데이트
                    try:
                        with open(STATE_FILE, 'w', encoding='utf-8') as sf:
                            sf.write(f"end_date={end_date.strftime('%Y-%m-%d')}\n")
                            sf.write(f"last_date={current_date.strftime('%Y-%m-%d')}\n")
                    except Exception:
                        pass
                    done_days += 1
                    st.done_days = done_days
                    st.current_date = current_date.isoformat()
                    progress.save_state(Path(state_path), st)
                    print(progress.fmt_progress(done_days, dates_total, start_ts, total_rows, failed_days), flush=True)
                    if hourly_log and (time.time() - last_hourly) >= 3600:
                        print(progress.fmt_hourly(ok_days=done_days - failed_days), flush=True)
                        last_hourly = time.time()
                    current_date += timedelta(days=1)
                    continue
            except Exception:
                # 메시지 감지 중 예외는 무시하고 일반 플로우로 진행
                pass

            # 페이지 파싱
            try:
                records = parser.parse_page(current_date, html)
            except Exception as e:
                # 파싱 중 오류 발생: 실패 기록 후 다음 날짜로
                _log_failure(current_date, f"PARSE_ERROR: {e}")
                # 디버깅용 HTML 스냅샷 저장
                _save_html_snapshot(current_date, html)
                failed_days += 1
                st.failed_days = failed_days
                progress.save_state(Path(state_path), st)
                done_days += 1
                st.done_days = done_days
                print(progress.fmt_progress(done_days, dates_total, start_ts, total_rows, failed_days), flush=True)
                if hourly_log and (time.time() - last_hourly) >= 3600:
                    print(progress.fmt_hourly(ok_days=done_days - failed_days), flush=True)
                    last_hourly = time.time()
                current_date += timedelta(days=1)
                continue

            if not records or len(records) == 0:
                # 데이터가 없는 경우 (빈 페이지 등): 실패로 간주하고 기록
                _log_failure(current_date, "NO_DATA")
                _save_html_snapshot(current_date, html)
                failed_days += 1
                st.failed_days = failed_days
                progress.save_state(Path(state_path), st)
                done_days += 1
                st.done_days = done_days
                print(progress.fmt_progress(done_days, dates_total, start_ts, total_rows, failed_days), flush=True)
                if hourly_log and (time.time() - last_hourly) >= 3600:
                    print(progress.fmt_hourly(ok_days=done_days - failed_days), flush=True)
                    last_hourly = time.time()
                current_date += timedelta(days=1)
                continue

            # 데이터 저장 (CSV, DB)
            try:
                writer.write_csv(current_date, records)
                writer.write_db(records)
            except Exception as e:
                # 저장 중 오류: 실패 기록 후 다음 날짜로 (DB나 파일 쓰기 문제 발생 가능성)
                _log_failure(current_date, f"WRITE_ERROR: {e}")
                failed_days += 1
                st.failed_days = failed_days
                progress.save_state(Path(state_path), st)
                done_days += 1
                st.done_days = done_days
                print(progress.fmt_progress(done_days, dates_total, start_ts, total_rows, failed_days), flush=True)
                if hourly_log and (time.time() - last_hourly) >= 3600:
                    print(progress.fmt_hourly(ok_days=done_days - failed_days), flush=True)
                    last_hourly = time.time()
                current_date += timedelta(days=1)
                continue

            # 정상 처리된 경우 상태 파일의 last_date 업데이트
            try:
                with open(STATE_FILE, 'w', encoding='utf-8') as sf:
                    sf.write(f"end_date={end_date.strftime('%Y-%m-%d')}\n")
                    sf.write(f"last_date={current_date.strftime('%Y-%m-%d')}\n")
            except Exception:
                # 상태 파일 업데이트 실패 시, 계속 진행은 하지만 resume 기능에 영향
                pass

            # 진행 상태/누적 카운트 업데이트
            total_rows += len(records)
            st.total_rows = total_rows
            done_days += 1
            st.done_days = done_days
            st.current_date = current_date.isoformat()
            progress.save_state(Path(state_path), st)
            print(progress.fmt_progress(done_days, dates_total, start_ts, total_rows, failed_days), flush=True)
            if hourly_log and (time.time() - last_hourly) >= 3600:
                print(progress.fmt_hourly(ok_days=done_days - failed_days), flush=True)
                last_hourly = time.time()

            # 다음 날짜로 진행
            current_date += timedelta(days=1)
    except KeyboardInterrupt:
        # 사용자가 실행 중단 (Ctrl+C 등) 한 경우
        incomplete_run = True
        print("\n[INFO] 크롤링이 사용자에 의해 중단되었습니다. 진행 상태가 저장됩니다.")
    finally:
        # 리소스 정리: WebDriver 종료, DB 커밋/닫기
        fetcher.close()
        writer.close_db()
        # 만약 정상 완료되었다면 상태 파일 제거 (더 이상 resume 불필요)
        if not incomplete_run:
            try:
                if os.path.exists(STATE_FILE):
                    os.remove(STATE_FILE)
            except Exception:
                pass
        # 요약 출력
        try:
            print(
                progress.fmt_summary(
                    target_end=target_end,
                    started_at=st.started_at if 'st' in locals() and st else datetime.now().isoformat(),
                    total=(end_date - start_date).days + 1,
                    ok=(done_days - failed_days) if 'done_days' in locals() else 0,
                    fail=failed_days if 'failed_days' in locals() else 0,
                    rows=total_rows if 'total_rows' in locals() else 0,
                ),
                flush=True,
            )
        except Exception:
            pass


def _log_failure(date, message):
    """
    지정한 일자(date)에 대한 실패 원인(message)을 상태 디렉토리에 기록합니다.
    WHY: 누락된 날짜나 오류를 나중에 확인할 수 있도록 로그를 남깁니다.
    HOW: 파일명을 failures_YYYY-MM-DD.txt 형식으로 생성하고, 에러 메시지를 기록합니다.
    """
    fail_date_str = date.strftime("%Y-%m-%d")
    fname = f"failures_{fail_date_str}.txt"
    fpath = os.path.join(writer.STATE_DIR, fname)
    try:
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write(str(message))
    except Exception:
        pass


def _log_nodata(date):
    """데이터 없음(정상 무자료) 마커 파일을 기록합니다."""
    try:
        fpath = os.path.join(writer.STATE_DIR, f"nodata_{date.strftime('%Y-%m-%d')}.txt")
        with open(fpath, 'w', encoding='utf-8') as f:
            f.write("NO_RESULT")
    except Exception:
        pass


def _save_html_snapshot(date, html: str | None):
    """실패한 날짜의 HTML 스냅샷을 저장하여 사후 분석에 활용합니다."""
    if not html:
        return
    try:
        raw_dir = os.path.join(writer.STATE_DIR, "raw_html")
        os.makedirs(raw_dir, exist_ok=True)
        out = os.path.join(raw_dir, f"{date.strftime('%Y-%m-%d')}.html")
        with open(out, 'w', encoding='utf-8') as f:
            f.write(html)
    except Exception:
        pass
