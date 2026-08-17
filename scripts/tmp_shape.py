import sys, csv, sqlite3
from pathlib import Path


def csv_shape(path: Path):
    rows = 0
    cols = 0
    with path.open('r', encoding='utf-8', newline='') as f:
        r = csv.reader(f)
        for i, row in enumerate(r):
            if i == 0:
                cols = len(row)
            else:
                rows += 1
    return rows, cols


def sqlite_summary(path: Path):
    out = []
    conn = sqlite3.connect(str(path))
    try:
        cur = conn.cursor()
        for (tname,) in cur.execute("SELECT name FROM sqlite_master WHERE type='table'"):
            try:
                cur2 = conn.execute(f"SELECT COUNT(*) FROM {tname}")
                n = cur2.fetchone()[0]
            except Exception:
                n = None
            out.append((tname, n))
    finally:
        conn.close()
    return out


def main(argv):
    for arg in argv:
        p = Path(arg)
        if not p.exists():
            print(f"MISSING: {p}")
            continue
        if p.suffix.lower() == '.csv':
            r, c = csv_shape(p)
            print(f"CSV {p} rows={r} cols={c}")
        elif p.suffix.lower() == '.db':
            tables = sqlite_summary(p)
            print(f"DB  {p}")
            for t, n in tables:
                print(f"  - {t}: rows={n}")
        else:
            print(f"SKIP {p}")

if __name__ == '__main__':
    main(sys.argv[1:])
