from __future__ import annotations

import sys
from pathlib import Path
import pandas as pd


FILES = [
    'analytics/clean/comments.clean.csv',
    'analytics/clean/top_daily_record.clean.ko.strip.csv',
    'analytics/clean/best_price_daily.clean.names.strip.csv',
    'analytics/youtube/comments.csv',
    'analytics/game/top_daily_record.csv',
    'analytics/game/best_price_daily.csv',
]


def main() -> int:
    root = Path('.').resolve()
    for f in FILES:
        p = root / f
        if not p.exists():
            continue
        print('='*80)
        print(f'FILE: {p}')
        try:
            df = pd.read_csv(p)
        except Exception as e:
            print(f'LOAD ERROR: {e}')
            continue
        print(f'SHAPE: {df.shape}')
        # info()
        df.info()
        # null summary
        nulls = df.isna().sum()
        nz = nulls[nulls > 0]
        if not nz.empty:
            print('\n[Null Summary (>0)]')
            print(nz.to_string())
        print('\nCOLUMNS:', list(df.columns)[:20])
    print('='*80)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

