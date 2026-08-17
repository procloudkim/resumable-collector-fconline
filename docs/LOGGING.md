Logging Policy and How-To
=========================

Standard
--------
- Timezone: Store in UTC, display in KST only.
- Format: ISO 8601 seconds precision.
  - UTC example: 2025-09-13T08:30:00Z
  - KST example: 2025-09-13T17:30:00+09:00
- Location: `logs/*.log` with rotation when applicable.

Python Loggers
--------------
- Crawler (`crawler.daily_trade.setup_logger`):
  - File handler: UTC ISO8601 (Z-suffix), rotating 5MB × 3.
  - Console handler: KST ISO8601 display.
- Utilities (`app/core/utils.log`): prints single-line logs with UTC ISO8601.
  - When running via wrappers below, console prefix is KST; file prefix is UTC.

Run Wrappers (Recommended)
--------------------------
- PowerShell (Windows): `scripts/run_with_log.ps1`
  - Stores each line with UTC in the log file, prints each line with KST to console.
  - Examples:
    - `./scripts/run_with_log.ps1 -Cmd "python -m crawler.daily_trade.cli --start-date 2025-08-13 --end-date 2025-09-10 --players pairs.json --export-csv" -LogFile "logs/daily_trade.run.log"`
    - `./scripts/run_with_log.ps1 -Cmd "python scripts/fetch_ranker_stats.py --pairs pairs.json" -LogFile "logs/ranker_stats.run.log"`

Shell Redirects
---------------
- For quick ad-hoc runs (UTC in file only):
  - PowerShell: `python script.py 2>&1 | ForEach-Object { $ts=([DateTimeOffset]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ssZ')); "$ts $_" } | Tee-Object -FilePath logs/script.run.log`

Operational Notes
-----------------
- Keep logs per pipeline with clear names: `daily_trade.run.log`, `ranker_stats.run.log`, etc.
- For scheduled jobs (Task Scheduler/cron), run via the wrapper so timestamps are consistent.
- Application logs (crawler) and run logs (wrapper) complement each other; don’t disable rotating file logs.
 - When sharing logs, redact API keys and PII.

Project2 (출전 랭킹) 진행/ETA 로깅
---------------------------------
- 콘솔 진행 로그 형식:
  - `[PROGRESS] 1939/1941일 (99.9%) | 경과 00:21:02 | ETA 2025-09-14 20:36 | 실패일 2 | 누적행 34866`
- 상태 파일:
  - `project2/state/progress.json` — 누적 처리량/실패일/현재 날짜 등
  - `project2/state/resume_state.txt` — 재개용 마지막 성공일/목표 종료일
- 무자료/실패 마커:
  - `project2/state/nodata_YYYY-MM-DD.txt` — “검색 결과가 없습니다” 감지 시 정상 무자료 처리
  - `project2/state/failures_YYYY-MM-DD.txt` — FETCH/PARSE/WRITE 오류 메시지 기록
  - `project2/state/raw_html/YYYY-MM-DD.html` — 파싱 실패 시 스냅샷
