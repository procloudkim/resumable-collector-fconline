from __future__ import annotations

"""
DOM version detector and safety checks for FC Online Datacenter daily trade pages (new version).

Goals
- Detect layout version reliably (card/slider vs. table).
- Check coverage of essential fields before writing to DB.
- Provide a small CLI to audit local HTML snapshots in `docs/check/`.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re

from bs4 import BeautifulSoup  # type: ignore

from . import setup_logger


CARD_VERSION = "card_swiper_v1"
TABLE_VERSION = "table_v1"


def _normalize(s: str) -> str:
    return re.sub(r"[\s\W_]+", "", (s or "").strip().lower())


def detect_dom_version(html: str) -> str:
    """Return a short version key for the given HTML."""
    soup = BeautifulSoup(html or "", "html.parser")
    # Card/swiper layout
    if soup.select_one("#divBestTradeArea_price") and len(soup.select(".swiper-slide")) >= 10:
        if soup.select("a.outlink[href*='PlayerInfo?spid=']"):
            return CARD_VERSION
    # Table layout (thead or first row headers with known synonyms)
    for tb in soup.find_all("table"):
        thead = tb.find("thead")
        if thead:
            headers = [th.get_text(" ").strip() for th in thead.find_all("th")]
        else:
            tr = tb.find("tr")
            if not tr:
                continue
            headers = [th.get_text(" ").strip() for th in tr.find_all(["th", "td"])]
        norm = ",".join(_normalize(x) for x in headers)
        if any(k in norm for k in ("선수", "플레이어", "player", "거래", "강화", "평균", "최고", "최저")):
            return TABLE_VERSION
    return "unknown"


@dataclass
class Coverage:
    version: str
    spids: int
    prices: int
    names: int
    levels: int
    tables: int

    def ok(self) -> bool:
        if self.version == CARD_VERSION:
            return self.spids >= 15 and self.prices >= 15
        if self.version == TABLE_VERSION:
            return self.tables >= 1 and self.names >= 15
        return False


def summarize_coverage(html: str) -> Coverage:
    soup = BeautifulSoup(html or "", "html.parser")
    version = detect_dom_version(html)
    if version == CARD_VERSION:
        # Count distinct SPIDs from outlink hrefs
        spids = set()
        for a in soup.select("#divBestTradeArea_price .swiper-slide a.outlink[href*='PlayerInfo?spid=']"):
            href = a.get("href") or ""
            m = re.search(r"[?&]spid=(\d+)", href)
            if m:
                spids.add(int(m.group(1)))
        price_nodes = soup.select("#divBestTradeArea_price .swiper-slide .price_wrap .price")
        # Player name coverage via three strategies
        name_nodes = soup.select("#divBestTradeArea_price .swiper-slide .playerCardInfoBottom .nameWrap .name span")
        if not name_nodes:
            name_nodes = soup.select("#divBestTradeArea_price .swiper-slide .player_wrap[title]")
        if not name_nodes:
            name_nodes = soup.select("#divBestTradeArea_price .swiper-slide a.outlink > span.hidden")
        # Level coverage
        level_nodes = soup.select("#divBestTradeArea_price .swiper-slide .buildUp a")
        if not level_nodes:
            # Count +N patterns inside slides
            level_nodes = [n for n in soup.select("#divBestTradeArea_price .swiper-slide") if re.search(r"\+(\d+)", n.get_text(" "))]
        return Coverage(version, len(spids), len(price_nodes), len(name_nodes), len(level_nodes), tables=0)
    # Table version (rough counts)
    tables = len(soup.find_all("table"))
    # Names are approximated by counting rows with text in the first data column
    names = 0
    for tb in soup.find_all("table"):
        for tr in tb.find_all("tr"):
            if tr.find("th"):
                continue
            tds = tr.find_all(["td", "th"])
            if not tds:
                continue
            if (tds[0].get_text(" ") or "").strip():
                names += 1
    return Coverage(version, spids=0, prices=0, names=names, levels=0, tables=tables)


def quality_gate(html: str) -> Tuple[bool, Dict[str, int | str]]:
    """Return (ok, details)."""
    cov = summarize_coverage(html)
    details: Dict[str, int | str] = {
        "version": cov.version,
        "spids": cov.spids,
        "prices": cov.prices,
        "names": cov.names,
        "levels": cov.levels,
        "tables": cov.tables,
    }
    return cov.ok(), details


def _cli(paths: List[Path]) -> int:
    logger = setup_logger()
    rows: List[str] = []
    header = "file,version,spids,prices,names,levels,tables,ok"
    rows.append(header)
    for p in paths:
        html = p.read_text(encoding="utf-8", errors="ignore")
        ok, det = quality_gate(html)
        line = f"{p.name},{det['version']},{det['spids']},{det['prices']},{det['names']},{det['levels']},{det['tables']},{str(ok).lower()}"
        rows.append(line)
        logger.info("event=dom_guard file=%s version=%s ok=%s", p.name, det.get("version"), ok)
    out = "\n".join(rows)
    print(out)
    return 0


if __name__ == "__main__":  # pragma: no cover
    import argparse
    ap = argparse.ArgumentParser(description="Audit DOM version and coverage for dailytrade HTML snapshots")
    ap.add_argument("paths", nargs="*", type=Path, default=list((Path("check")).glob("check-*.html")))
    args = ap.parse_args()
    raise SystemExit(_cli(list(args.paths)))
