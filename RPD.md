# FC Online Analytics — Repository Process Document (RPD)

This document summarizes what the codebase does, how it is laid out, the data model (ERD), and how to run the main pipelines locally on Windows (PowerShell).

## 1) Objectives
- Track player usage (pick frequency) over time.
- Complement Nexon Open API with a static web crawler for the Data Center to cross‑check market/TopN info.
- Provide a local Streamlit dashboard that reads only locally stored data (no live Open API calls).

## 2) Repository Layout (key files)
- app/
  - core/
    - utils.py — paths, .env loading, simple logger; streamlit/env key helper
    - cache.py — SQLite helpers (ouid_map, seen_match, meta, players, ranker_stats, indexes)
    - rate_limit.py — TokenBucket (burst=2), daily budget util
  - services/
    - meta.py — loads and caches static meta JSON (spid, spposition, matchtype, division)
    - images.py — downloads player images from CDN candidates; local cache
  - dashboard.py — Streamlit app (reads local DB/CSV/images only)
- scripts/
  - fetch_matches.py — nickname → OUID → user/match → match-detail → raw JSONL (incremental)
  - aggregate_picks.py — aggregates raw JSONL into daily_pick (date/spid pick counts)
  - fetch_ranker_stats.py — calls ranker-stats for (spid, po) pairs with batching and pruning
  - backfill_images.py — populate local images cache from CSV/IDs (when present)
- crawler/daily_trade/
  - __init__.py — rotating file logger (logs/daily_trade.log)
  - fetcher.py — polite HTTP GET with UA, timeout, retries, random sleep
  - parser.py — parse daily trade and TopN tables, price formatter (조/억 → BIGINT), layout guard
  - writer.py — SQLite upserts (daily_trade, daily_top_players, daily_pick), visited_log, CSV append
  - cli.py — CLI for date ranges and optional CSV export/dry‑run
  - README.md — crawler module documentation
- tests/
  - test_utils_pricefmt.py — unit for price conversion
  - test_parser_dailytrade.py — parser tests with HTML fixtures
  - test_writer_sqlite.py — writer upsert & visited_log idempotency

## 3) Data Model (ERD)
Core tables in SQLite at `data/data.db`:

- ouid_map(nickname TEXT PK, ouid TEXT)
- seen_match(match_id TEXT PK) — processed match ids
- players(spid INTEGER PK, name_kor, name_eng, image_path, updated_at)
- ranker_stats(
  spid INTEGER,
  po INTEGER,
  create_date TEXT,
  dribble, dribble_try, dribble_success,
  pass_try, pass_success,
  block, tackle, assist, goal,
  match_count,
  PRIMARY KEY(spid, po, create_date)
) — indexes on create_date, spid, po
- daily_trade(
  date TEXT, spid INTEGER,
  player_name TEXT,
  avg_price BIGINT, max_price BIGINT, min_price BIGINT,
  trade_count INTEGER, max_enhance_level INTEGER,
  source TEXT DEFAULT 'web',
  PRIMARY KEY(date, spid)
)
- daily_top_players(
  date TEXT, spid INTEGER,
  rank INTEGER, pick_rate REAL,
  PRIMARY KEY(date, spid)
)
- daily_pick(
  date TEXT NOT NULL,
  spid INTEGER NOT NULL,
  matchtype INTEGER DEFAULT 0,
  pick_count INTEGER NOT NULL,
  sample_match_count INTEGER NOT NULL,
  source TEXT DEFAULT 'api',
  PRIMARY KEY(date, spid, matchtype, source)
) — daily player usage time series (from match-detail aggregation)
- visited_log(key TEXT PK, created_at TEXT) — idempotency keys for crawler/aggregators

Simple relations (logical):
- ranker_stats.spid ↔ players.spid
- daily_pick.spid ↔ players.spid

## 4) Data Sources & APIs
- Nexon Open API (base: https://open.api.nexon.com)
  - GET /fconline/v1/id?nickname=… → OUID (user identifier)
  - GET /fconline/v1/user/match?ouid=…&limit=100&offset=…&matchtype=… → match id list
  - GET /fconline/v1/match-detail?matchid=… → per‑match details (team/player stats)
  - GET /fconline/v1/ranker-stats?players=<URL-encoded JSON> → snapshot of recent 20 matches for top10k rankers (stats, not picks)
  - Static meta: /static/fconline/meta/(spid|spposition|matchtype|division).json
- Data Center (static HTML): https://fconline.nexon.com/datacenter/dailytrade?strDate=YYYY-MM-DD
  - Used by crawler to parse daily trade tables and daily TopN player table (pick_rate)

Limits & policies (implemented):
- Dev quota: ~1000/day, ~5 req/sec → TokenBucket with burst=2, daily budget split per nickname
- Retry/backoff: 429 or 5xx → exponential backoff; random polite sleep 1–3s
- Idempotency: seen_match, visited_log, composite PK upserts

## 5) Pipelines (C: Collection stage)
A. User‑centric (actual picks via match-detail)
1) scripts/fetch_matches.py
   - Input: nicknames, pages, remaining budget
   - Flow: nickname → /id → /user/match (paged) → /match-detail → append raw JSONL
   - Output: data/raw/matches_sample.jsonl; DB updates: ouid_map, seen_match
2) scripts/aggregate_picks.py
   - Input: JSONL, optional players list (JSON/CSV), matchtype (50 or auto)
   - Logic: per date (YYYY‑MM‑DD), count unique spId appearances per match (per date); record sample_match_count per date
   - Output: upsert into daily_pick(date, spid, matchtype, pick_count, sample_match_count, source='api')

B. Ranker stats snapshot (reference metric)
- scripts/fetch_ranker_stats.py
  - Input: list of {id: spid, po: position} (≤50 per request)
  - Encodes players param without spaces and fully URL‑encodes; 400 → binary split pruning; 429/5xx → backoff retry
  - Output: ranker_stats upsert (PK spid, po, create_date)

C. Crawler (daily trade & TopN)
- crawler/daily_trade/cli.py
  - Input: --start-date/--end-date, --players JSON/CSV, optional --only-topN, --dry-run, --export-csv
  - Fetch: polite GET of Data Center page per date
  - Parse: tables for trade metrics and TopN; layout guard and HTML snapshots on change
  - Write: upsert into daily_trade / daily_top_players; append CSV if requested; visited_log for idempotency

## 6) Running Locally (PowerShell)
Prereqs
- `python -m pip install -r requirements.txt`
- `setx NEXON_OPENAPI_API_KEY "<YOUR_API_KEY>"` (or `$env:NEXON_OPENAPI_API_KEY="..."` for the current session)

User‑centric pick time series
- Collect raw (2 pages per nickname, split budget 500):
  ```powershell
  python scripts/fetch_matches.py --nick NICK1 NICK2 --pages 2 --remain 500
  ```
- Aggregate picks for official matchtype 50 (filter to players JSON optional):
  ```powershell
  python scripts/aggregate_picks.py --raw data\raw\matches_sample.jsonl --players data\meta\top11.json --matchtype 50
  ```

Ranker stats snapshot
```powershell
python scripts/fetch_ranker_stats.py --pairs pairs_small.json
```

Crawler (TopN only; dry run)
```powershell
python -m crawler.daily_trade.cli --start-date 2023-08-01 --end-date 2023-08-07 --only-topN --dry-run
```

Dashboard
```powershell
streamlit run app\dashboard.py
```

## 7) Files & Outputs
- SQLite: `data/data.db` → daily_pick, daily_top_players, ranker_stats, ouid_map, seen_match, visited_log, players, …
- Raw JSONL: `data/raw/matches_sample.jsonl`
- Crawler CSV: `data/processed/daily_trade.csv`, `data/processed/daily_top_players.csv`
- Images: `data/images/{spid}.png`
- Logs: `logs/daily_trade.log` (crawler), console logs for scripts

## 8) Reliability & Idempotency
- Rate limiting: TokenBucket (burst=2), daily budget per nickname
- Retries: 429/5xx exponential backoff, per‑request timeouts
- Idempotent writes: composite PK upserts; seen_match and visited_log keys
- Layout change: crawler stores HTML snapshot under `data/raw/html/` and logs WARN

## 9) Security & Secrets
- API key is read from environment (`NEXON_OPENAPI_API_KEY`) or CLI arg; never commit secrets.
- Dashboard does not call Open API; it reads local DB/CSV/images only.

## 10) Testing
- Run: `pytest -q` (after installing pytest)
- Scope: price formatter, HTML parser, writer upsert & visited_log

## 11) Roadmap (nice‑to‑have)
- Map crawler TopN names → spid (disambiguation by season when needed)
- Add dashboard views for daily_pick time series
- Add cohort management for “top ranker” nickname lists (seed file + scheduler)
- Contract tests against official OpenAPI schema if/when available

