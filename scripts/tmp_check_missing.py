import os, json, pandas as pd, numpy as np
from glob import glob
root = 'data/processed'
files = sorted(glob(os.path.join(root,'*.csv')))
report = {}
for fp in files:
    try:
        df = pd.read_csv(fp)
        df = df.replace(r'^\s*$', np.nan, regex=True)
        na = df.isna().sum()
        total = len(df)
        miss = {c:{'n':int(na[c]), 'pct': round(float(na[c])*100/total,2) if total else 0.0} for c in df.columns if int(na[c])>0}
        report[fp] = {'rows': total, 'missing': miss}
    except Exception as e:
        report[fp] = {'error': str(e)}
print(json.dumps(report, ensure_ascii=False, indent=2))
