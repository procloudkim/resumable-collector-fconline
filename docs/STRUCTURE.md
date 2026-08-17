Repository Structure (Generated 2025-09-13T00:00:00Z)
====================================================

Note
- Heavy folders (e.g., images) are summarized with counts.
- Paths are workspace-relative; click to open files in your editor.

Top Level
---------
- .github/
  - .github/PULL_REQUEST_TEMPLATE.md
- .gitignore
- AGENTS.md
- README.md
- project2/  (FC 데이터센터 ‘출전 랭킹’ 크롤러 패키지)
- RPD.md
- STATUS.md
- requirements.txt
- requirements.youtube.txt
- pairs.json, pairs_50.json, pairs_clean.json, pairs_small.json

app/
----
- app/__init__.py
- app/dashboard.py
- app/sentiment_dashboard.py
- app/core/
  - app/core/__init__.py
  - app/core/cache.py
  - app/core/rate_limit.py
  - app/core/utils.py
- app/services/
  - app/services/__init__.py
  - app/services/images.py
  - app/services/meta.py

crawler/
--------
- crawler/selenium_utils.py
- crawler/daily_trade/
  - crawler/daily_trade/__init__.py
  - crawler/daily_trade/README.md
  - crawler/daily_trade/cli.py
  - crawler/daily_trade/cli_new_ver.py
  - crawler/daily_trade/fetcher.py
  - crawler/daily_trade/fetcher_new_ver.py
  - crawler/daily_trade/guard_new_ver.py
  - crawler/daily_trade/parser.py
  - crawler/daily_trade/parser_new_ver.py
  - crawler/daily_trade/writer.py
  - crawler/daily_trade/writer_new_ver.py
- crawler/rankers/
  - crawler/rankers/__init__.py
  - crawler/rankers/cli.py
  - crawler/rankers/cli_new_ver.py
  - crawler/rankers/scraper.py

scripts/
--------
- scripts/__init__.py
- scripts/aggregate_picks.py
- scripts/backfill_images.py
- scripts/build_pairs_from_raw.py
- scripts/crawl_check_new.py
- scripts/eda_daily_trade.py
- scripts/fetch_fc.py
- scripts/fetch_incremental.py
- scripts/fetch_matches.py
- scripts/fetch_ranker_stats.py
- scripts/player_cards.py
- scripts/preprocess_top10.py
- scripts/run_daily_pipeline.ps1
- scripts/run_daily_pipeline_new_ver.ps1
- scripts/schedule_fetch.py
- scripts/schedule_fetch_new_ver.py
- scripts/seed_ouids.py
- scripts/sync_players.py
- scripts/tmp_check_missing.py
- scripts/tmp_elapsed.py
- scripts/tmp_elapsed_kst.py
- scripts/tmp_hours.py
- scripts/tmp_scan_db.py
- scripts/visualize_wc.py
- scripts/run_with_log.ps1  (PowerShell run wrapper with UTC/KST timestamps)

docs/
-----
- docs/PRD.md
- docs/ERD.md
- docs/FCOnline_OpenAPI_full.md
- docs/youtube_comments.md
- docs/LOGGING.md  (Logging policy: UTC store, KST display)
- docs/DEV_ENV.md  (Dev environment snapshot and run cheatsheet)
- docs/STRUCTURE.md (this file)
 - docs/LOCAL_GUIDE_KR.md (로컬 실행/데이터 안내)

project2/
---------
- project2/app/cli.py  (출전 랭킹 크롤러 CLI: --from/--to/--resume/--fast/--headful/--hourly-log/--target-end)
- project2/app/runner.py  (수집→파싱→CSV·SQLite 저장, 진행률/ETA/재개 상태 관리)
- project2/app/fetcher.py (Selenium headless Chrome, 빠른 모드 이미지 차단/eager 로드)
- project2/app/parser/ (BeautifulSoup 파서 + CSS 셀렉터)
- project2/app/writer.py (월별 CSV append, SQLite PK=(date,rank) UPSERT)
- project2/state/ (resume_state.txt, progress.json, failures_YYYY-MM-DD.txt, nodata_YYYY-MM-DD.txt, raw_html/*.html)
- project2/out/ (topdailyrecord_YYYY-MM.csv)
- project2/db/topdailyrecord.db (table: top_daily_record)

data/
-----
- data/data.db  (SQLite; last updated 2025-09-13)
- data/new-data.db  (test/demo DB)
- data/raw/
  - data/raw/html/ (historical HTML snapshots, e.g., 20201124.html ...)
- data/processed/
  - data/processed/daily_trade.csv
  - data/processed/top10_trend.csv
  - data/processed/daily_rankers.csv (if produced by rankers CLI)
  - data/processed/comments_with_sentiment.csv
- data/reports/
  - data/reports/daily_trade_eda.md
- data/meta/
  - data/meta/spid.json
  - data/meta/spposition.json
- data/images/  (~4,650 files; large, not expanded)
- data/images_new/  (~71 files; not expanded)
- data/test/
  - data/test/images_new/*  (sample images)
  - data/test/new-data-test.db
  - data/test/processed/daily_trade_new_test.csv

tests/
-----
- tests/test_cache.py
- tests/test_fetch_ouid_400.py
- tests/test_images.py
- tests/test_images_fetcher.py
- tests/test_meta_search.py
- tests/test_parser_dailytrade.py
- tests/test_rate_limit.py
- tests/test_utils.py
- tests/test_utils_pricefmt.py
- tests/test_writer_sqlite.py
- tests/test_youtube_comments.py

docs/check/
-----------
- docs/check/check-2020.html .. docs/check/check-2025.html  (layout snapshots)
- docs/check/DOM_REPORT.md  (DOM version report and selectors)
- docs/check/new-sample.csv
- docs/check/version_selectors.yaml

config/
-------
- config/events.sample.csv
- config/rankers.txt
- config/rankers.sample.txt
- config/pairs.json  (preferred location for {id,po} pairs)
- config/youtube_videos.sample.txt  (example list of YouTube URLs/IDs)

sentiment/
---------
- sentiment/__init__.py
- sentiment/cli.py
- sentiment/io_utils.py
- sentiment/keywords.py
- sentiment/lexicon.py
- sentiment/mentions.py
- sentiment/plot_fonts.py
- sentiment/preprocess.py
- sentiment/stage_map.py

youtube_comments/
----------------
- youtube_comments/__init__.py
- youtube_comments/cli.py
- youtube_comments/client.py
- youtube_comments/fetcher.py
- youtube_comments/filtering.py
- youtube_comments/sampling.py
- youtube_comments/storage.py
- youtube_comments/utils.py

Other
-----
- TEMP_ranker.txt, temp_snippet.txt, tmp_*.py, tmp_*.txt (scratch/notes)

Regenerate This Doc
-------------------
- PowerShell (summary tree without expanding heavy folders):

      rg --files -n --hidden --glob !.git | sort > tmp_filelist.txt
      # Optionally post-process to collapse data/images* in your editor
