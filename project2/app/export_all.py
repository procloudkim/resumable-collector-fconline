"""
project2 전체 기간 CSV 내보내기 유틸리티

의도(WHY)
- `project2/db/topdailyrecord.db` 내 테이블 `top_daily_record`의 전체(또는 지정 범위) 레코드를
  하나의 CSV 파일로 통합 내보낸다. 월별 CSV 조각을 합치지 않고, DB를 신뢰 소스로 삼는다.

동작(HOW)
- SQLite 연결 후 PRAGMA로 컬럼 순서를 조회한다(생성 순서 보장).
- 주어진 날짜 범위(포함)로 WHERE 절을 구성하고, ORDER BY "date", "rank"로 정렬한다.
- 대용량도 스트리밍(fecthmany)으로 처리해 메모리 사용량을 제한한다.
- BDD 스타일 로그를 표준 출력으로 남긴다.

입력/출력
- 입력: DB 경로, 날짜 범위(from/to, YYYY-MM-DD 문자열)
- 출력: CSV 경로(부모 디렉터리 자동 생성). UTF-8, 1행 헤더 포함.

예외/에러 처리
- DB/테이블 없음, 스키마 이상 시 한국어 메시지와 함께 예외를 발생시킨다.
- 외부 비밀값 사용 없음.

복잡도
- 시간: O(N) (N=선택된 행 수), 공간: O(1) (fetchmany 배치 크기만큼)

대안
- 월별 CSV를 단순 병합하는 방법이 있으나, 누락/중복 가능성을 방지하기 위해 DB에서 추출한다.
"""
from __future__ import annotations

import csv
import os
import sqlite3
import time
from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple


DEFAULT_DB = os.path.join("project2", "db", "topdailyrecord.db")
DEFAULT_OUT = os.path.join(
    "project2",
    "out",
    "topdailyrecord_all_20200520_20250911.csv",
)
TABLE = "top_daily_record"


@dataclass
class ExportResult:
    rows: int
    columns: List[str]
    seconds: float


def _ensure_parent_dir(path: str) -> None:
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def _connect(db_path: str) -> sqlite3.Connection:
    """
    SQLite 연결을 생성한다.

    Args:
        db_path: DB 파일 경로
    Returns:
        sqlite3.Connection
    Raises:
        FileNotFoundError: DB 파일이 없을 때
    """
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"DB 파일이 없습니다: {db_path}")
    conn = sqlite3.connect(db_path)
    # 텍스트 디코딩 로스 방지(가능한 UTF-8 우선)
    conn.text_factory = lambda b: b.decode("utf-8", errors="replace") if isinstance(b, (bytes, bytearray)) else b
    return conn


def list_topdailyrecord_columns(db_path: str, table: str = TABLE) -> List[str]:
    """
    테이블 컬럼명을 생성 순서대로 반환한다.

    Args:
        db_path: DB 경로
        table: 테이블명(기본: top_daily_record)
    Returns:
        컬럼명 리스트
    Raises:
        RuntimeError: 테이블이 없거나 조회 실패 시
    """
    with _connect(db_path) as conn:
        cur = conn.execute(f"PRAGMA table_info({table})")
        rows = cur.fetchall()
        if not rows:
            raise RuntimeError(f"테이블을 찾을 수 없습니다: {table}")
        # PRAGMA table_info: cid, name, type, notnull, dflt_value, pk
        return [r[1] for r in rows]


def get_topdailyrecord_date_bounds(db_path: str, table: str = TABLE) -> Tuple[str, str]:
    """
    테이블의 최소/최대 날짜 문자열(YYYY-MM-DD)을 반환한다.

    Args:
        db_path: DB 경로
        table: 테이블명
    Returns:
        (min_date, max_date)
    """
    with _connect(db_path) as conn:
        cur = conn.execute(f"SELECT MIN(\"date\"), MAX(\"date\") FROM {table}")
        row = cur.fetchone()
        if not row or not row[0] or not row[1]:
            raise RuntimeError("date 컬럼에서 최소/최대 값을 찾지 못했습니다.")
        return str(row[0]), str(row[1])


def _quote_ident(name: str) -> str:
    """식별자 이스케이프(더블쿼트). 내부 쿼트는 2번 반복.

    SQLite의 식별자 인용 규칙을 따르며, 공백/괄호 등 특수문자 포함 컬럼명을 안전하게 사용.
    """
    return '"' + name.replace('"', '""') + '"'


def export_topdailyrecord_to_csv(
    *,
    db_path: str = DEFAULT_DB,
    out_csv: str = DEFAULT_OUT,
    date_from: str = "2020-05-20",
    date_to: str = "2025-09-11",
    fetch_size: int = 10_000,
) -> Tuple[int, List[str]]:
    """
    지정된 날짜 범위의 전체 레코드를 하나의 CSV로 내보낸다.

    Args:
        db_path: SQLite DB 경로
        out_csv: 출력 CSV 경로(부모 디렉터리 자동 생성)
        date_from: 시작일(YYYY-MM-DD)
        date_to: 종료일(YYYY-MM-DD)
        fetch_size: 배치 페치 크기(메모리 사용 최적화)
    Returns:
        (내보낸 행 수, 컬럼 리스트)
    Raises:
        FileNotFoundError: DB 없음
        RuntimeError: 테이블/스키마 문제
        sqlite3.Error: SQL 에러
    """
    t0 = time.time()
    print(
        f"[GIVEN] source_db={db_path} table={TABLE} range={date_from}..{date_to}\n"
        f"[WHEN] query=SELECT * WHERE date BETWEEN ... ORDER BY date, rank"
    )

    cols = list_topdailyrecord_columns(db_path, TABLE)
    qcols = ", ".join(_quote_ident(c) for c in cols)

    _ensure_parent_dir(out_csv)
    written = 0
    with _connect(db_path) as conn, open(out_csv, "w", encoding="utf-8", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(cols)

        # 총 건수(진행 로그용)
        try:
            total = conn.execute(
                f"SELECT COUNT(1) FROM {TABLE} WHERE \"date\" BETWEEN ? AND ?",
                (date_from, date_to),
            ).fetchone()[0]
        except Exception:
            total = None
        if total is not None:
            print(f"[WHEN] total_rows_estimate={total}")

        sql = (
            f"SELECT {qcols} FROM {TABLE} "
            f"WHERE \"date\" BETWEEN ? AND ? "
            f"ORDER BY \"date\" ASC, \"rank\" ASC"
        )
        cur = conn.execute(sql, (date_from, date_to))
        while True:
            rows = cur.fetchmany(fetch_size)
            if not rows:
                break
            w.writerows(rows)
            written += len(rows)

    dt = time.time() - t0
    print(
        f"[THEN] wrote_rows={written} seconds={dt:.2f} out={out_csv}\n"
        f"[THEN] next=검증: 헤더/행 수/표본 몇 줄 확인"
    )
    return written, cols


def _parse_args(argv: Sequence[str] | None = None):
    import argparse

    p = argparse.ArgumentParser(description="project2: topdailyrecord 전체 CSV 내보내기")
    p.add_argument("--db", default=DEFAULT_DB, help="SQLite DB 경로")
    p.add_argument("--out", default=DEFAULT_OUT, help="출력 CSV 경로")
    p.add_argument("--from", dest="date_from", default="2020-05-20", help="시작일 YYYY-MM-DD")
    p.add_argument("--to", dest="date_to", default="2025-09-11", help="종료일 YYYY-MM-DD")
    p.add_argument("--fetch-size", dest="fetch_size", type=int, default=10000, help="배치 페치 크기")
    return p.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        export_topdailyrecord_to_csv(
            db_path=args.db,
            out_csv=args.out,
            date_from=args.date_from,
            date_to=args.date_to,
            fetch_size=args.fetch_size,
        )
        return 0
    except FileNotFoundError as e:
        print(f"[ERROR] {e}")
        return 2
    except sqlite3.Error as e:
        print(f"[ERROR] SQLite 에러: {e}")
        return 2
    except Exception as e:
        print(f"[ERROR] 알 수 없는 에러: {e}")
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

