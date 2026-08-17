from __future__ import annotations

import csv
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from bs4 import BeautifulSoup  # type: ignore


ROOT = Path(__file__).resolve().parents[1]
CHECK_DIR = ROOT / "docs" / "check"
OUT_OVERRIDES = ROOT / "config" / "player_overrides_from_check.csv"
OUT_MAP = ROOT / "config" / "player_map.csv"


SPID_Q_RE = re.compile(r"[?&]spid=(\d+)")


def extract_spid_from_href(href: str | None) -> int | None:
    if not href:
        return None
    try:
        qs = parse_qs(urlparse(href).query)
        v = qs.get("spid", [None])[0]
        if v and str(v).isdigit():
            return int(v)
    except Exception:
        pass
    m = SPID_Q_RE.search(href)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None
    return None


def collapse_text(s: str | None) -> str:
    if not s:
        return ""
    return " ".join(str(s).split())


def parse_names_from_check() -> dict[int, str]:
    names: dict[int, str] = {}
    if not CHECK_DIR.exists():
        return names
    for f in sorted(CHECK_DIR.glob("*.html")):
        html = ""
        for enc in ("utf-8", "cp949", "euc-kr", "latin1"):
            try:
                html = f.read_text(encoding=enc)
                break
            except Exception:
                html = ""
        if not html:
            try:
                html = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.select("a[href*='spid=']"):
            spid = extract_spid_from_href(a.get("href"))
            if not spid:
                continue
            txt = collapse_text(a.get_text(strip=True))
            if not txt:
                txt = collapse_text(a.get("title") or a.get("aria-label"))
            if not txt:
                continue
            prev = names.get(spid, "")
            if len(txt) > len(prev):
                names[spid] = txt
    return names


def write_overrides(names: dict[int, str]) -> None:
    OUT_OVERRIDES.parent.mkdir(parents=True, exist_ok=True)
    with OUT_OVERRIDES.open("w", encoding="utf-8-sig", newline="") as fo:
        w = csv.writer(fo)
        w.writerow([
            "spid",
            "name",
            "player_image_path",
            "nation_logo_path",
            "league_logo_path",
            "team_logo_path",
        ])
        for spid, name in sorted(names.items()):
            img = f"data/images/players/base/{spid}.png"
            w.writerow([spid, name, img, "", "", ""])


def write_map(names: dict[int, str]) -> None:
    OUT_MAP.parent.mkdir(parents=True, exist_ok=True)
    with OUT_MAP.open("w", encoding="utf-8-sig", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["spid", "name"])
        for spid, name in sorted(names.items()):
            w.writerow([spid, name])


def main() -> int:
    names = parse_names_from_check()
    if not names:
        print(f"[WARN] No names found under {CHECK_DIR}")
        return 1
    write_overrides(names)
    write_map(names)
    print(f"[OK] Wrote overrides: {OUT_OVERRIDES} and map: {OUT_MAP} (count={len(names)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
