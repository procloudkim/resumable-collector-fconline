import sys, sqlite3
from pathlib import Path

def inspect(db):
    p = Path(db)
    if not p.exists():
        print(f'MISSING {p}')
        return
    con = sqlite3.connect(str(p))
    cur = con.cursor()
    cur.execute("select name from sqlite_master where type='table'")
    tables=[r[0] for r in cur.fetchall()]
    print('TABLES', tables)
    for t in tables:
        try:
            cur.execute(f'PRAGMA table_info({t})')
            cols=[r[1] for r in cur.fetchall()]
            cur.execute(f'SELECT COUNT(*) FROM {t}')
            n=cur.fetchone()[0]
            print(f'  - {t}: rows={n} cols={len(cols)}')
        except Exception as e:
            print(f'  - {t}: ERROR {e}')
    con.close()

if __name__ == '__main__':
    for arg in sys.argv[1:]:
        print('==', arg)
        inspect(arg)
