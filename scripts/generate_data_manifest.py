from __future__ import annotations
import csv, hashlib, json, os, sqlite3, sys, time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

"""
WHY:
 - 레포 내 데이터/DB/설정 파일을 자동 스캔해 "현재 상태"를 기계적으로 요약합니다.
 - 내가 안전한 적재·이관·중복제거(UPSERT) 계획을 설계하려면
   파일 경로/크기/스키마/행수/해시/DB 테이블 정보를 정확히 알아야 합니다.
HOW:
 - data/, docs/check/, config/ 하위 파일 메타를 수집
 - CSV: 헤더/행수/컬럼수/sha256/UTC-수정시각
 - SQLite: 테이블/컬럼/PK/행수/인덱스 요약
 - 결과를 JSON/CSV로 data/reports/에 저장
NOTE:
 - 대용량 CSV도 처리 가능(행수는 라인 카운트 방식; 수 분 내)
 - Windows 11, Python 3.13 기준
"""

BASE = Path(".").resolve()
REPORTS = BASE / "data" / "reports"
REPORTS.mkdir(parents=True, exist_ok=True)

# ---------- Utilities ----------
def utc_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S") + "Z"

def sha256_of(path: Path, chunk: int = 2**20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b: break
            h.update(b)
    return h.hexdigest()

def count_csv_rows_and_header(path: Path) -> tuple[int, List[str]]:
    # WHY: CSV 스키마 계약 검증을 위해 헤더/행수 필요
    rows = 0
    header: List[str] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return 0, []
        for _ in reader:
            rows += 1
    return rows, header

# ---------- DTOs ----------
@dataclass
class FileInfo:
    path: str
    size_bytes: int
    mtime_utc: str
    sha256: Optional[str] = None
    kind: str = "file"  # csv/json/db/etc
    rows: Optional[int] = None
    cols: Optional[int] = None
    header: Optional[List[str]] = None

@dataclass
class TableInfo:
    name: str
    rows: int
    columns: List[Dict[str, Any]]
    indexes: List[Dict[str, Any]]

@dataclass
class DBInfo:
    path: str
    tables: List[TableInfo]

# ---------- Inspectors ----------
CSV_DIRS = [BASE / "data" / "processed", BASE / "data" / "raw"]
JSON_DIRS = [BASE / "data" / "raw"]
CONF_DIRS = [BASE / "config", BASE / "data" / "meta"]
CHECK_DIR = BASE / "docs" / "check"
DB_CANDIDATES = [BASE / "data" / "data.db", BASE / "data" / "new-data.db"]

def scan_csv_files() -> List[FileInfo]:
    items: List[FileInfo] = []
    for root in CSV_DIRS:
        if not root.exists(): continue
        for p in root.rglob("*.csv"):
            stat = p.stat()
            rows, header = count_csv_rows_and_header(p)
            fi = FileInfo(
                path=str(p.relative_to(BASE)),
                size_bytes=stat.st_size,
                mtime_utc=utc_iso(stat.st_mtime),
                sha256=sha256_of(p),
                kind="csv",
                rows=rows,
                cols=len(header),
                header=header
            )
            items.append(fi)
    return items

def scan_misc_files(patterns: List[str]) -> List[FileInfo]:
    items: List[FileInfo] = []
    for pat in patterns:
        for p in BASE.rglob(pat):
            if not p.is_file():
                continue
            stat = p.stat()
            items.append(FileInfo(
                path=str(p.relative_to(BASE)),
                size_bytes=stat.st_size,
                mtime_utc=utc_iso(stat.st_mtime),
                sha256=sha256_of(p),
                kind="misc"
            ))
    return items

def scan_sqlite_db(path: Path) -> Optional[DBInfo]:
    if not path.exists(): return None
    con = sqlite3.connect(str(path))
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    tables: List[TableInfo] = []
    try:
        for (name,) in cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"):
            # row count (may be heavy; for large tables you could sample)
            (cnt,) = cur.execute(f"SELECT COUNT(*) FROM '{name}'").fetchone()
            cols: List[Dict[str, Any]] = []
            for c in cur.execute(f"PRAGMA table_info('{name}')"):
                cols.append({"cid": c[0], "name": c[1], "type": c[2], "notnull": c[3], "dflt": c[4], "pk": c[5]})
            idxs: List[Dict[str, Any]] = []
            for idx in cur.execute(f"PRAGMA index_list('{name}')"):
                idxs.append({"seq": idx[0], "name": idx[1], "unique": idx[2]})
            tables.append(TableInfo(name=name, rows=cnt, columns=cols, indexes=idxs))
    finally:
        con.close()
    return DBInfo(path=str(path.relative_to(BASE)), tables=tables)

def validate_pairs_config() -> Dict[str, Any]:
    cfg = BASE / "config" / "pairs.json"
    out: Dict[str, Any] = {"exists": cfg.exists(), "sample": []}
    if cfg.exists():
        import json as _json
        try:
            arr = _json.loads(cfg.read_text(encoding="utf-8"))
            out["sample"] = arr[:3]
            # quick validation
            out["valid"] = all(isinstance(x.get("id"), int) and isinstance(x.get("po"), int) for x in arr[:10])
        except Exception as e:
            out["valid"] = False
            out["error"] = repr(e)
    else:
        out["valid"] = False
    return out

def scan_check_snapshots() -> Dict[str, Any]:
    return {"exists": CHECK_DIR.exists(),
            "count": sum(1 for _ in CHECK_DIR.rglob("*.html")) if CHECK_DIR.exists() else 0,
            "path": str(CHECK_DIR.relative_to(BASE))}

# ---------- Main ----------
def main() -> None:
    csvs = scan_csv_files()
    miscs = scan_misc_files(["*.json","*.jsonl"])
    dbs = [scan_sqlite_db(p) for p in DB_CANDIDATES]
    dbs = [d for d in dbs if d is not None]
    pairs = validate_pairs_config()
    checks = scan_check_snapshots()

    manifest: Dict[str, Any] = {
        "generated_at": utc_iso(time.time()),
        "paths": {
            "base": str(BASE),
            "csv_dirs": [str(p.relative_to(BASE)) for p in CSV_DIRS if p.exists()],
            "json_dirs": [str(p.relative_to(BASE)) for p in JSON_DIRS if p.exists()],
            "check_dir": checks["path"],
            "reports_dir": str(REPORTS.relative_to(BASE)),
        },
        "csv_files": [asdict(fi) for fi in csvs],
        "misc_files": [asdict(fi) for fi in miscs],
        "databases": [asdict(db) for db in dbs],
        "config_pairs": pairs,
        "check_snapshots": checks,
        "notes": {
            "deprecated_db_present": any(d["path"].endswith("new-data.db") for d in [asdict(db) for db in dbs] if d),
            "suggestions": [
                "PK/UPSERT 규칙을 STATUS에 명시해 충돌 시 자동 중복제거",
                "docs/check/ 하위 스냅샷은 운영 산출물과 분리 유지",
                "대용량 CSV는 Parquet로 병행 저장 고려(후순위)"
            ]
        }
    }

    # JSON out
    json_out = REPORTS / "data_manifest.json"
    json_out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    # CSV summary for quick view
    csv_out = REPORTS / "data_manifest.csv"
    with csv_out.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["path","kind","size_bytes","mtime_utc","rows","cols","sha256"])
        for fi in csvs:
            w.writerow([fi.path, fi.kind, fi.size_bytes, fi.mtime_utc, fi.rows, fi.cols, fi.sha256])
        for fi in miscs:
            w.writerow([fi.path, fi.kind, fi.size_bytes, fi.mtime_utc, "", "", fi.sha256])
        for db in dbs:
            # one line per table
            for t in db.tables:
                w.writerow([f"{db.path}:{t.name}", "sqlite_table", "", "", t.rows, len(t.columns), ""])
    print(f"Wrote: {json_out} / {csv_out}")

if __name__ == "__main__":
    main()

