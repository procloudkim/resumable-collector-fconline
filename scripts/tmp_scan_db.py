import os, sqlite3, json

def scan_db(path):
    out = {'path': path, 'tables': []}
    conn = sqlite3.connect(path)
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    for t in tables:
        info = {'table': t, 'rows': 0, 'columns': [], 'issues': []}
        try:
            cols = [r[1] for r in cur.execute(f"PRAGMA table_info({t})").fetchall()]
            info['columns'] = cols
            cnt = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            info['rows'] = cnt
            for c in cols:
                nulls = cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {c} IS NULL").fetchone()[0]
                try:
                    blanks = cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {c} = ''").fetchone()[0]
                except Exception:
                    blanks = 0
                if nulls>0 or blanks>0:
                    info['issues'].append({'column': c, 'nulls': nulls, 'blanks': blanks})
        except Exception as e:
            info['error'] = str(e)
        out['tables'].append(info)
    conn.close()
    return out

paths = [
    r'data/data.db',
    r'data/processed/gamst_comments.db',
    r'data/processed/gamst_comments_all.db',
    r'data/processed/gamst_comments_scored.db',
]
report = []
for p in paths:
    if os.path.isfile(p):
        report.append(scan_db(p))
    else:
        report.append({'path': p, 'error': 'not found'})
print(json.dumps(report, ensure_ascii=False, indent=2))
