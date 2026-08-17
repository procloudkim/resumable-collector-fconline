from __future__ import annotations
import re
from typing import List

from bs4 import BeautifulSoup

from crawler.selenium_utils import (
    create_driver,
    wait_for_any_css,
    preinstall_overlay_kill_on_new_document,
    install_overlay_blocker,
    aggressive_kill_overlays,
    apply_stealth,
)
from crawler.daily_trade import setup_logger
import time


DEFAULT_RANKING_URL = "https://fconline.nexon.com/datacenter/rank"


def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()


def parse_top_nicknames(html: str, top: int = 20) -> List[str]:
    """Parse top N nicknames from a ranking-like page HTML.

    Strategy (robust-first):
    1) Direct selectors commonly used for nickname cells.
    2) Fallback: table rows, pick an anchor/text cell that looks like a nickname.
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1) Try explicit class-based selectors
    nick_elems = soup.select(
        ", ".join([
            # New target per provided DOM
            ".tbody .tr .coach_wrap .name.profile_pointer",
            ".td.rank_coach .name.profile_pointer",
            "span.name.profile_pointer",
            # Legacy/alternative structures
            "td.nickname", "span.nickname", ".ranking-list .name", ".nick", ".user-name", ".nickname",
            "li .name", "li .nickname",
        ])
    )
    nicks = [_clean_text(el.get_text(" ")) for el in nick_elems if _clean_text(el.get_text(" "))]
    if len(nicks) >= top:
        uniq: List[str] = []
        seen: set[str] = set()
        for v in nicks:
            if v not in seen:
                uniq.append(v)
                seen.add(v)
        return uniq[:top]

    # 2) Fallback: table rows
    out: List[str] = []
    seen: set[str] = set()
    hangul_or_latin = re.compile(r"[A-Za-z\uAC00-\uD7A3]")
    for tr in soup.select("table tbody tr, .table tbody tr, .tbl tbody tr, .ranking-list tr, .tbody .tr"):
        cells = tr.select("td, th")
        # Prefer explicit nickname span inside this row
        nick_in_row = tr.select_one(".coach_wrap .name.profile_pointer, .td.rank_coach .name.profile_pointer, span.name.profile_pointer")
        if nick_in_row:
            cand = _clean_text(nick_in_row.get_text(" "))
            if cand and cand not in seen:
                out.append(cand)
                seen.add(cand)
                if len(out) >= top:
                    break
            continue
        if not cells:
            # Some div-rows may not use td/th; fall back to any direct anchor/text
            a = tr.select_one("a")
            cand = _clean_text(a.get_text(" ")) if a else None
            if cand and cand not in seen:
                out.append(cand)
                seen.add(cand)
                if len(out) >= top:
                    break
            continue
        cand = None
        # Prefer anchor text
        a = tr.select_one("a")
        if a:
            cand = _clean_text(a.get_text(" "))
        if not cand:
            for td in cells:
                txt = _clean_text(td.get_text(" "))
                # Reject ranks, numbers, percents, arrows
                if not txt or re.fullmatch(r"[0-9.,%▶▲▼]+", txt):
                    continue
                # Heuristic: nicknames are short-ish and contain letters/Hangul
                if 2 <= len(txt) <= 20 and hangul_or_latin.search(txt):
                    cand = txt
                    break
        if cand and cand not in seen:
            out.append(cand)
            seen.add(cand)
        if len(out) >= top:
            break

    return out[:top]


def scrape_top_nicknames(
    url: str = DEFAULT_RANKING_URL,
    top: int = 20,
    *,
    headless: bool = True,
) -> List[str]:
    logger = setup_logger()
    driver = create_driver(headless=headless)
    try:
        logger.info("event=ranker_open url=%s", url)
        # Be polite and stealthy; also kill overlays early
        try:
            apply_stealth(driver)
        except Exception:
            pass
        try:
            preinstall_overlay_kill_on_new_document(
                driver,
                [
                    '.iconMatchFixedBanner',
                    '.iconMatchFixedBanner.sub',
                    '.iconmatchfixedbanner',
                    "[class*='iconMatchFixedBanner']",
                ],
            )
        except Exception:
            pass

        driver.get(url)
        try:
            time.sleep(0.8)
            try:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight/3)")
                time.sleep(0.4)
                driver.execute_script("window.scrollTo(0, 0)")
            except Exception:
                pass
            install_overlay_blocker(driver, ['.iconMatchFixedBanner', '.iconmatchfixedbanner'])
            aggressive_kill_overlays(
                driver,
                ['.iconMatchFixedBanner', '.iconmatchfixedbanner'],
                duration_ms=10000,
                period_ms=250,
            )
        except Exception:
            pass

        # Wait for any likely selector to appear
        try:
            wait_for_any_css(
                driver,
                [
                    ".tbody .tr .name.profile_pointer",
                    "span.name.profile_pointer",
                    "td.nickname",
                    "span.nickname",
                    ".ranking-list .name",
                    "table tbody tr",
                    ".tbl tbody tr",
                    ".table tbody tr",
                ],
                timeout=25,
            )
        except Exception:
            # Soft-fail: proceed with whatever is rendered; parser has fallbacks
            logger.warning("event=ranker_wait_failed proceeding_with_best_effort")
        html = driver.page_source
        nicks = parse_top_nicknames(html, top=top)
        logger.info("event=ranker_parsed count=%d", len(nicks))
        return nicks
    finally:
        try:
            driver.quit()
        except Exception:
            pass


__all__ = [
    "scrape_top_nicknames",
    "parse_top_nicknames",
    "DEFAULT_RANKING_URL",
]
