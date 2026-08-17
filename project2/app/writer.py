# -*- coding: utf-8 -*-
"""
writer 모듈: 크롤링한 데이터를 CSV 파일과 SQLite DB에 저장하는 기능을 담당합니다.
WHY: 데이터를 누락 없이 영구 저장하고, 향후 분석 및 조회에 활용하기 위해 두 가지 형식(CSV, SQLite)을 모두 사용합니다.
HOW: 월별 CSV 파일로 누적 기록을 저장하고, SQLite 데이터베이스에 동일한 데이터를 테이블로 저장합니다.
     SQLite에서는 기본 키(PK)를 설정하고 INSERT OR REPLACE로 중복 입력을 방지합니다.
"""

import os
import csv
import sqlite3

# 출력 디렉토리 경로 설정
BASE_DIR = os.path.dirname(os.path.dirname(__file__))  # project2/app/.. => project2/
OUT_DIR = os.path.join(BASE_DIR, "out")
DB_DIR = os.path.join(BASE_DIR, "db")
STATE_DIR = os.path.join(BASE_DIR, "state")

# DB 파일 및 테이블 명
DB_PATH = os.path.join(DB_DIR, "topdailyrecord.db")
TABLE_NAME = "top_daily_record"

# CSV 및 DB 공통 필드명 정의 (요구사항에 따라 한글 컬럼명을 사용)
FIELDNAMES = [
    "date", "rank", "선수 기본정보", "출전", "공격 포인트", 
    "득점", "도움", "유효 슈팅", "일반 슈팅", "패스 성공률", 
    "드리블 성공률", "공중볼 경합 성공률", "가로채기", "태클 성공률", 
    "차단 성공률", "선방(골 차단)", "평점"
]

# 필요 디렉토리 생성 (존재하지 않을 경우)
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(STATE_DIR, exist_ok=True)

# SQLite DB 연결 (애플리케이션 전체에서 하나만 사용)
_conn = None


def _get_connection():
    """내부용: SQLite3 연결을 생성하거나 기존 연결 반환."""
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH)
        # 테이블이 없으면 생성 (컬럼명은 한글 포함, PK 설정)
        create_sql = f'''
        CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
            date TEXT,
            rank INTEGER,
            "선수 기본정보" TEXT,
            "출전" INTEGER,
            "공격 포인트" TEXT,
            "득점" TEXT,
            "도움" TEXT,
            "유효 슈팅" TEXT,
            "일반 슈팅" TEXT,
            "패스 성공률" TEXT,
            "드리블 성공률" TEXT,
            "공중볼 경합 성공률" TEXT,
            "가로채기" TEXT,
            "태클 성공률" TEXT,
            "차단 성공률" TEXT,
            "선방(골 차단)" TEXT,
            "평점" TEXT,
            PRIMARY KEY(date, rank)
        )
        '''
        _conn.execute(create_sql)
        _conn.commit()
    return _conn


def configure_paths(out_dir: str | None = None, db_path: str | None = None, state_dir: str | None = None) -> None:
    """런타임 출력 경로 설정을 재구성합니다.

    WHY: BestPrice CLI와 유사하게 CSV/DB/STATE 경로를 명령행에서 제어할 수 있도록 합니다.
    HOW: 모듈 전역 경로 상수를 업데이트하고 필요 디렉토리를 생성합니다. DB 경로가 바뀌면 기존 연결을 닫습니다.
    """
    global OUT_DIR, DB_DIR, STATE_DIR, DB_PATH, _conn
    if out_dir:
        OUT_DIR = out_dir
        os.makedirs(OUT_DIR, exist_ok=True)
    if state_dir:
        STATE_DIR = state_dir
        os.makedirs(STATE_DIR, exist_ok=True)
    if db_path:
        # db_path가 디렉토리가 아닌 파일 전체 경로일 수 있음
        DB_PATH = db_path
        # 디렉토리 보장
        os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
        # 기존 연결이 있다면 닫고 재연결하도록 None
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None


def write_csv(date, records):
    """
    주어진 날짜의 기록 리스트(records)를 해당 월의 CSV 파일에 추가로 기록합니다.
    CSV 파일은 월별로 분할되며, 파일명이 topdailyrecord_YYYY-MM.csv 형식을 따릅니다.
    """
    if not records:
        return  # 기록이 없으면 아무 것도 안 함
    # 파일명 결정 (연도-월 기반)
    month_str = date.strftime("%Y-%m")  # e.g., "2020-05"
    csv_path = os.path.join(OUT_DIR, f"topdailyrecord_{month_str}.csv")
    file_exists = os.path.exists(csv_path)
    try:
        with open(csv_path, mode='a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=FIELDNAMES)
            # 파일이 새로 생성된 경우 헤더 작성
            if not file_exists:
                writer.writeheader()
            # CSV에 행들 추가
            for rec in records:
                writer.writerow(rec)
    except Exception as e:
        # CSV 쓰기 실패 시 (디스크 오류 등) 상위에서 처리하거나 로깅
        raise


def write_db(records):
    """
    주어진 기록 리스트(records)를 SQLite DB의 top_daily_record 테이블에 저장합니다.
    INSERT OR REPLACE 구문을 사용하여 PK 중복 시 기존 기록을 대체합니다.
    """
    if not records:
        return
    conn = _get_connection()
    try:
        # 컬럼명에 한글/공백/괄호가 포함되어 있어 SQL 식별자 인용이 필요합니다.
        quoted_columns = ", ".join([f'"{col}"' for col in FIELDNAMES])
        placeholders = ", ".join(["?"] * len(FIELDNAMES))
        sql = f"INSERT OR REPLACE INTO {TABLE_NAME} ({quoted_columns}) VALUES ({placeholders})"
        values_list = [tuple(rec.get(col) for col in FIELDNAMES) for rec in records]
        conn.executemany(sql, values_list)
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def close_db():
    """SQLite 연결을 닫습니다."""
    global _conn
    if _conn:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None
