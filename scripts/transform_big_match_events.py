from __future__ import annotations

import argparse
import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


@dataclass
class ColMap:
    date: str
    match: str
    comp: Optional[str] = None
    players: Optional[str] = None
    notes: Optional[str] = None


def guess_delimiter(sample: str) -> str:
    return "\t" if "\t" in sample else ","


def normalize_date(s: str) -> Tuple[Optional[str], bool]:
    s = (s or "").strip()
    if not s:
        return None, False
    fmts = [
        "%Y-%m-%d",
        "%Y.%m.%d",
        "%Y/%m/%d",
        "%Y-%m-%d.",
        "%Y.%m.%d.",
    ]
    for fmt in fmts:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%Y-%m-%d"), True
        except Exception:
            pass
    # Last resort: pick first date-like token
    m = re.search(r"(20\d{2})[-./](\d{1,2})[-./](\d{1,2})", s)
    if m:
        y, mo, d = m.groups()
        try:
            dt = datetime(int(y), int(mo), int(d))
            return dt.strftime("%Y-%m-%d"), True
        except Exception:
            return None, False
    return None, False


TEAM_SPLIT_RE = re.compile(
    r"\s*(?P<a>.+?)\s*(?:vs|VS|Vs|v\.?|대|:|\-|–|—)\s*(?P<b>.+?)\s*$"
)


def split_teams(match_text: str) -> Tuple[Optional[str], Optional[str]]:
    s = (match_text or "").strip()
    if not s:
        return None, None
    m = TEAM_SPLIT_RE.match(s)
    if m:
        return m.group("a").strip(), m.group("b").strip()
    return None, None


SCORE_RE = re.compile(r"(\d+)\s*[-:]\s*(\d+)")


def extract_score(texts: List[str]) -> Optional[str]:
    for t in texts:
        if not t:
            continue
        m = SCORE_RE.search(str(t))
        if m:
            return f"{m.group(1)}-{m.group(2)}"
    return None


def extract_tag(comp_text: Optional[str]) -> Optional[str]:
    if not comp_text:
        return None
    # Remove score fragments like 3-2
    t = SCORE_RE.sub("", str(comp_text)).strip()
    return t or None


def sanitize_header(h: str) -> str:
    # Keep unicode header but avoid commas/newlines
    return str(h).replace("\n", " ").replace(",", " ").strip()


def detect_columns(headers: List[str]) -> ColMap:
    # Heuristic mapping using Korean keywords; fallback to positions
    low = [h.lower() for h in headers]
    def find(*keys: str) -> Optional[str]:
        for i, h in enumerate(headers):
            hl = low[i]
            if any(k in hl for k in keys):
                return h
        return None

    date_col = find("날짜", "date") or headers[0]
    match_col = find("경기", "match") or (headers[1] if len(headers) > 1 else headers[0])
    comp_col = find("리그", "대회", "결과", "league", "cup", "tournament")
    players_col = find("주요", "선수", "players")
    notes_col = find("요약", "하이라이트", "summary", "highlight")
    return ColMap(date=date_col, match=match_col, comp=comp_col, players=players_col, notes=notes_col)


def read_rows(path: Path) -> Tuple[List[Dict[str, str]], List[str], str]:
    with path.open("r", encoding="utf-8-sig", errors="replace") as f:
        sample = f.readline()
        delim = guess_delimiter(sample)
        f.seek(0)
        reader = csv.DictReader(f, delimiter=delim)
        headers = [sanitize_header(h) for h in (reader.fieldnames or [])]
        rows = []
        for r in reader:
            # Keep original mapping
            rows.append({sanitize_header(k): (v or "").strip() for k, v in r.items()})
        return rows, headers, delim


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fo:
        w = csv.DictWriter(fo, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_path", default="big_match_list.csv")
    ap.add_argument("--out", dest="out_path", default=str(Path("config") / "events.csv"))
    ap.add_argument("--report-dir", dest="report_dir", default=str(Path("data") / "reports"))
    ns = ap.parse_args()

    src = Path(ns.in_path)
    if not src.exists():
        print(json.dumps({"error": f"missing input: {src}"}, ensure_ascii=False))
        return 1

    rows, headers, delim = read_rows(src)
    if not rows:
        print(json.dumps({"error": "no data rows", "headers": headers}, ensure_ascii=False))
        return 2

    cmap = detect_columns(headers)

    out_rows: List[Dict[str, str]] = []
    # EDA counters
    n_total = 0
    n_date_ok = 0
    n_team_ok = 0
    tags: Dict[str, int] = {}

    for r in rows:
        n_total += 1
        date_raw = r.get(cmap.date, "")
        date_norm, okd = normalize_date(date_raw)
        if okd:
            n_date_ok += 1
        name = r.get(cmap.match, "").strip()
        team_a, team_b = split_teams(name)
        if team_a and team_b:
            n_team_ok += 1
        comp_text = r.get(cmap.comp, "") if cmap.comp else ""
        score = extract_score([comp_text, name])
        tag = extract_tag(comp_text)
        if tag:
            tags[tag] = tags.get(tag, 0) + 1

        key_players = r.get(cmap.players, "") if cmap.players else ""
        notes = r.get(cmap.notes, "") if cmap.notes else ""

        # Preserve original row as JSON for no-loss guarantee
        orig_json = json.dumps(r, ensure_ascii=False)

        out: Dict[str, str] = {
            "date": date_norm or date_raw,
            "name": name,
            "team_a": team_a or "",
            "team_b": team_b or "",
            "tag": tag or (comp_text or ""),
            "score": score or "",
            "key_players": key_players,
            "notes": notes,
            "source_file": str(src),
            "orig_json": orig_json,
        }
        # Also include all original columns with prefix to avoid collision
        for h in headers:
            if h in out:
                out[f"orig__{h}"] = r.get(h, "")
            else:
                out[f"orig__{h}"] = r.get(h, "")

        out_rows.append(out)

    # Determine field order
    base_cols = [
        "date",
        "name",
        "team_a",
        "team_b",
        "tag",
        "score",
        "key_players",
        "notes",
        "source_file",
        "orig_json",
    ]
    orig_cols = [f"orig__{h}" for h in headers]
    fieldnames = base_cols + orig_cols

    out_path = Path(ns.out_path)
    write_csv(out_path, out_rows, fieldnames)

    # EDA reports
    rep_dir = Path(ns.report_dir)
    rep_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "input": str(src),
        "delimiter": "tab" if delim == "\t" else "comma",
        "rows": n_total,
        "date_parsed": n_date_ok,
        "team_parsed": n_team_ok,
        "date_parse_rate": round(n_date_ok / n_total, 3),
        "team_parse_rate": round(n_team_ok / n_total, 3),
        "tags": tags,
        "output": str(out_path),
    }
    (rep_dir / "big_match_events_eda.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    # Lightweight markdown view
    md = [
        f"# Big Match Events EDA\n",
        f"- input: `{src}`\n",
        f"- delimiter: {'tab' if delim == '\t' else 'comma'}\n",
        f"- rows: {n_total}\n",
        f"- date_parse_rate: {summary['date_parse_rate']} ({n_date_ok}/{n_total})\n",
        f"- team_parse_rate: {summary['team_parse_rate']} ({n_team_ok}/{n_total})\n",
        f"- output: `{out_path}`\n",
        f"- tags: {json.dumps(tags, ensure_ascii=False)}\n",
    ]
    (rep_dir / "big_match_events_eda.md").write_text("".join(md), encoding="utf-8")

    print(json.dumps({"ok": True, **summary}, ensure_ascii=False))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

