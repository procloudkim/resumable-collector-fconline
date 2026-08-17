**Purpose**
- Build a clean, stand-alone YouTube comments collector for multiple Gamst videos (2022 World Cup: Korea vs Portugal), with balanced sampling, spam filtering, and CSV/SQLite storage. Keeps existing 5-year crawling code untouched.

**ERD**
- **comments**: id (PK), video_id, video_title, comment_id (UNIQUE), author, text, like_count, published_at, updated_at, is_reply, parent_id, created_at

**Inputs (Video List)**
- Recommended path: `config/youtube_videos.txt`
- Format: one YouTube URL or 11-char ID per line; lines starting with `#` are ignored.
- Sample: `config/youtube_videos.sample.txt`
- How to pass this file to the CLI:
  - PowerShell: `python -m youtube_comments.cli --videos (Get-Content config\youtube_videos.txt)`
  - Bash: `python -m youtube_comments.cli --videos $(cat config/youtube_videos.txt)`

**CRUD**
- **Create**: `upsert_comments()` inserts new comments, ignores duplicates by `comment_id`.
- **Read**: query via SQLite externally; CSV readable for analysis.
- **Update**: inserting same `comment_id` is ignored (stable snapshot). Extend with `ON CONFLICT DO UPDATE` if needed.
- **Delete**: `delete_by_video(db_path, video_id)` for refresh.

**CLI Usage**
- Env: set `YOUTUBE_API_KEY` in `.env` or pass `--api-key`.
- Install deps: `pip install -r requirements.youtube.txt`
- Run:
  - `python -m youtube_comments.cli --videos <URL_or_ID_1> <URL_or_ID_2> ... --include-replies --no-filter --csv-out data/processed/gamst_comments.csv --sqlite-out data/processed/gamst_comments.db`
  - Add `--fast-balance` to fetch only a balanced target size instead of fetch-all-then-sample.
  - Add `--limit-per-video 800` to cap API calls per video.
  - Add `--progress-every 200` to log progress per video during fetch.
  - Logging: Prefer the PowerShell wrapper `scripts/run_with_log.ps1` to capture UTC file logs and KST console timestamps (see `docs/LOGGING.md`).

**Recommended Workflow**
- Step 1: Verify API access using small `--limit-per-video 100`.
- Step 2: Check counts auto-fetched; decide balanced strategy.
- Step 3: Run with `--balanced` (and optionally `--fast-balance`) for parity.
- Step 4: Use CSV/DB as inputs to later sentiment/visualization modules.

**Design Notes**
- Client: `build_youtube_client(api_key)` uses YouTube Data API v3 (`google-api-python-client`).
- Fetch: `fetch_comments()` paginates `commentThreads.list` (max 100 per page) with `order=time` and `textFormat=plainText`.
- Replies: add `--include-replies` to also fetch replies via `comments.list(parentId=...)`. CSV/DB include `is_reply`, `parent_id` to distinguish.
- Balance: Fetch all then random-sample for fairness (optional `--balanced`). For quota friendliness, use `--fast-balance` to early-stop at the balanced target size. Works across N videos.
- Filtering: Filters URLs and common KR ad terms; extendable via regex.
- Storage: CSV (UTF-8) plus SQLite with `comments` table; `comment_id` unique.
- Extensibility: Keep module MECE from downstream sentiment/visualization.

**Video Identification**
- Pass URLs or 11-char IDs; utility parses `watch?v=`, `youtu.be/ID`, `embed/ID`, `shorts/ID`.
  - Avoid stray characters (e.g., trailing `1`) in IDs; correct IDs are exactly 11 chars.

**Testing**
- Unit tests (mock-friendly) cover parsing, filtering, sampling, and SQLite I/O.

**Caveats**
- For very large threads, consider time-window or stratified sampling by `published_at`.

**Expected Issues + Mitigation**
- Quota exhaustion: YouTube Data API has a daily unit quota (commonly 10,000/day). `commentThreads.list`, `comments.list`, `videos.list` typically cost 1 unit each; heavy paging can exhaust quota. Mitigate with `--limit-per-video`, split runs across days, or reduce `--include-replies`.
- Rate limiting / transient errors: 403 rateLimitExceeded, 429, 5xx may occur. The fetcher includes basic exponential backoff/retry.
- Missing/limited comments: Deleted/held-for-review/private comments are not returned.
- Inconsistent counts: `statistics.commentCount` counts top-level only; replies inflate total fetched when `--include-replies`.
- Filtering side effects: If `--no-filter` is off, URL/광고 패턴 제거로 표본 수가 줄 수 있음.
