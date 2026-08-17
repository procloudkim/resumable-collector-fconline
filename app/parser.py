from __future__ import annotations

"""
Parse DOM (bestPrice cards)

Extracts SPID, name, season, position, OVR, pay, enhance, price, image URL, and logo codes.
"""

import re
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse, parse_qs

from .price_parser import korean_money_to_int
from . import selectors as S


def _text(node) -> str:
    return (node.get_text(" ") if node else "").strip()


def _maybe_int(node) -> Optional[int]:
    s = _text(node)
    m = re.search(r"\d+", s)
    return int(m.group(0)) if m else None


def _spid_from_href(node) -> Optional[int]:
    if not node:
        return None
    href = node.get("href") or ""
    try:
        q = parse_qs(urlparse(href).query)
        v = q.get("spid", [None])[0]
        return int(v) if v else None
    except Exception:
        return None


def _spid_from_img_src(img_src: str) -> Optional[int]:
    # playersAction/p<ID>.png or players/p<ID>.png
    m = re.search(r"/p(\d+)\.png", img_src)
    return int(m.group(1)) if m else None


def _season_code_from_src(src: str) -> Optional[str]:
    # .../season/<CODE>.png or filename where code appears
    m = re.search(r"/season/([A-Za-z0-9_\-]+)\.png", src)
    return (m.group(1).upper() if m else None)


def _season_code_from_class(c) -> Optional[str]:
    # class name like _ICON carries code (fallback)
    classes = c.get("class", []) if c else []
    for cl in classes:
        if cl.startswith("_"):
            return cl[1:].upper()
    return None


def _logo_code_from_src(src: str) -> Optional[str]:
    # countries/smallflags/{code}.png, league/.../l{code}.png etc
    m = re.search(r"/([A-Za-z0-9_\-]+)\.png", src)
    return (m.group(1).upper() if m else None)


def parse_bestprice_cards(html: str, date_str: str) -> List[Dict[str, Any]]:
    """Parse cards and return list of rows with selected fields.
    Missing fields become None where appropriate.
    """
    # Lazy import to avoid hard dependency during collection
    from bs4 import BeautifulSoup  # type: ignore

    soup = BeautifulSoup(html or "", "lxml")
    cards = soup.select(S.CARDS)
    out: List[Dict[str, Any]] = []
    for c in cards:
        # SPID
        a = c.select_one(S.SPID_LINK)
        spid = _spid_from_href(a)

        # image URL / SPID fallback via src
        img_node = c.select_one(S.PLAYER_IMG)
        img_url = img_node.get("src") if img_node and img_node.has_attr("src") else None
        if not spid and img_url:
            spid = _spid_from_img_src(img_url)
        if not spid:
            continue

        # name
        name_node = c.select_one(S.NAME)
        name = _text(name_node)
        if not name:
            name_hidden = c.select_one(S.NAME_HIDDEN)
            name = _text(name_hidden)

        # season code
        season_img = c.select_one(S.SEASON_IMG)
        season_code = _season_code_from_src(season_img.get("src")) if season_img else None
        if not season_code:
            wrap = c.select_one(".playerCardWrap")
            season_code = _season_code_from_class(wrap)

        # position/OVR/pay
        position = _text(c.select_one(S.POSITION)).upper() or None
        ovr = _maybe_int(c.select_one(S.OVR))
        pay = _maybe_int(c.select_one(S.PAY))

        enh_node = c.select_one(S.ENHANCE)
        enhance = _maybe_int(enh_node)
        if enhance is None and a is not None:
            href = a.get("href") or ""
            try:
                q = parse_qs(urlparse(href).query)
                v = q.get("n1Strong", [None])[0]
                enhance = int(v) if v else None
            except Exception:
                pass

        # price (text + parsed value)
        price_node = c.select_one(S.PRICE)
        price_text = None
        price_value = None
        if price_node is not None:
            for attr in ("alt", "title"):
                v = price_node.get(attr)
                if v:
                    price_text = str(v).strip()
                    price_value = korean_money_to_int(price_text)
                    break
            if price_value is None:
                price_text = _text(price_node)
                price_value = korean_money_to_int(price_text)
        # sanitize price <= 0
        if isinstance(price_value, int) and price_value <= 0:
            price_value = None

        # logo codes (nation/league/team)
        nation_img = soup.select_one(".playerCardInfoSort .nation img[src]")
        league_img = soup.select_one(".playerCardInfoSort .league img[src]")
        team_img = soup.select_one(".playerCardInfoSort .team img[src]")
        nation_code = _logo_code_from_src(nation_img.get("src")) if nation_img else None
        league_code = _logo_code_from_src(league_img.get("src")) if league_img else None
        team_code = _logo_code_from_src(team_img.get("src")) if team_img else None

        out.append(
            {
                "date": date_str,
                "spid": spid,
                "player_name": name or None,
                "season_code": season_code,
                "position": position,
                "ovr": ovr,
                "pay": pay,
                "enhance": enhance,
                "price_value": price_value,
                "price_text": price_text,
                "player_image_url": img_url,
                "nation_code": nation_code,
                "league_code": league_code,
                "team_code": team_code,
            }
        )
    return out

