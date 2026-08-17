Data Sources Inventory
======================

Daily Trade (HTML Crawling)
---------------------------
- Base page: `https://fconline.nexon.com/datacenter/dailytrade?strDate=YYYY-MM-DD`
  - Selenium fallback also works with `YYYY.MM.DD`.
- Layout: card/slider (swiper). Version and selectors summarized in:
  - `docs/check/DOM_REPORT.md`
  - `docs/check/version_selectors.yaml`
- Snapshots on change: `data/raw/html/YYYYMMDD.html` (saved when layout gates fail)
- Etiquette: random sleep 1–3s, retries with backoff, `User-Agent: fc-online-lab/1.0`

Nexon Open API (JSON)
---------------------
- Meta (static):
  - `/static/fconline/meta/spid.json` (player IDs and names)
  - `/static/fconline/meta/spposition.json` (positions)
- Ranker stats (top 10,000, last 20 matches average):
  - `/fconline/v1/ranker-stats?players=[{"id": <spid>, "po": <position>}, ...]`
  - Client: `scripts/fetch_ranker_stats.py` (batch up to 50, retry/backoff, token bucket)
- Matches (incremental):
  - `user/match`, `match-detail` (used by `scripts/fetch_matches.py`, `scripts/fetch_incremental.py`)

YouTube Comments (API v3)
-------------------------
- Input list (recommended): `config/youtube_videos.txt` (one URL/ID per line; see `config/youtube_videos.sample.txt`)
- CLI: `python -m youtube_comments.cli --videos <URL_or_ID_...> [--include-replies] [--balanced] [--fast-balance]`
- Output: `data/processed/comments_with_sentiment.csv` (post-annotation), per `docs/youtube_comments.md`

Related Docs
------------
- Structure/paths: `docs/STRUCTURE.md`
- Logging policy (UTC store, KST display): `docs/LOGGING.md`
