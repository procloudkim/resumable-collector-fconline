Development Environment — Snapshot (2025-09-13)
===============================================

System
------
- OS/Shell: Windows PowerShell
- Python: Python 3.13.7
- pip: pip 25.2 (python 3.13)

Python Dependencies
-------------------
- File: `requirements.txt`
- Core: streamlit, pandas, requests, python-dotenv, beautifulsoup4, pytest, selenium, webdriver-manager, matplotlib

Data Footprint (local)
----------------------
- DBs: `data/data.db` (33.9MB), `data/new-data.db` (57KB)
- CSVs: `data/processed/daily_trade.csv` (23.5MB), `data/processed/top10_trend.csv` (1.5KB), `data/reports/daily_trade_eda.md` (1.6KB)
- Meta: `data/meta/spid.json`, `data/meta/spposition.json` (downloaded)
- Images: `data/images` (≈4,650 files), `data/images_new` (71 files)

Logging Policy
--------------
- Store UTC ISO8601 in files; display KST on console. See `docs/LOGGING.md`.
- Use `scripts/run_with_log.ps1` to wrap commands and capture UTC/KST consistently.

Run Cheatsheet (PowerShell)
---------------------------
- Daily Trade: `./scripts/run_with_log.ps1 -Cmd "python -m crawler.daily_trade.cli --start-date <YYYY-MM-DD> --end-date <YYYY-MM-DD> --players pairs.json --export-csv" -LogFile "logs/daily_trade.run.log"`
- Ranker Stats: `./scripts/run_with_log.ps1 -Cmd "python scripts/fetch_ranker_stats.py --pairs pairs.json" -LogFile "logs/ranker_stats.run.log"`
- Dashboard: `streamlit run app\dashboard.py`

