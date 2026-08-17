from __future__ import annotations

import sqlite3
import sys


def main(path: str) -> int:
    con = sqlite3.connect(path)
    cur = con.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY 1").fetchall()]
    print("tables:", tables)
    for t in tables:
        try:
            cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})").fetchall()]
        except Exception as e:
            print("PRAGMA error", t, e)
        else:
            print("cols:", t, cols)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

