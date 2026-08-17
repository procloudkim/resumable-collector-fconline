from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from bs4 import BeautifulSoup


BESTPRICE_SEL = "#bestPrice"
CARD_SEL = ".item_list_wrap__card"


RE_PLAYER = re.compile(r"/players(?:Action)?/p(\d+)(?:_\d+)?\.png", re.I)
RE_SEASON = re.compile(r"/season/[^/]+\.png", re.I)
RE_LEAGUE = re.compile(r"/metadata/league/(?:dark|light)/([A-Za-z0-9_\-]+)\.png", re.I)
RE_TEAM = re.compile(r"/metadata/crests/(?:dark|light)/(?:small|large)/([A-Za-z0-9_\-]+)\.png", re.I)
RE_NATION = re.compile(r"/(?:countries|smallflags)/([A-Za-z0-9_\-]+)\.png", re.I)


def classify_img(src: str) -> str:
    if RE_PLAYER.search(src):
        return "player"
    if RE_SEASON.search(src):
        return "season"
    if RE_LEAGUE.search(src):
        return "league"
    if RE_TEAM.search(src):
        return "team"
    if RE_NATION.search(src):
        return "nation"
    return "other"


def find_spid(card) -> str | None:
    # 1) direct data attributes
    for k in ("data-spid", "data-playerid", "data-id", "data-no"):
        v = card.get(k)
        if v and v.isdigit():
            return v
    # 2) img src pattern p{spid}.png
    for img in card.select("img[src]"):
        m = RE_PLAYER.search(img["src"])
        if m:
            return m.group(1)
    # 3) anchor href that includes spid
    for a in card.select("a[href]"):
        m = re.search(r"spid=(\d+)", a["href"]) or re.search(r"/player/(\d+)", a["href"], re.I)
        if m:
            return m.group(1)
    return None


def summarize_file(path: Path) -> Dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    try:
        soup = BeautifulSoup(text, "lxml")
    except Exception:
        soup = BeautifulSoup(text, "html.parser")
    best = soup.select_one(BESTPRICE_SEL) or soup.find(id="bestPrice")
    cards = (best.select(CARD_SEL) if best else []) or soup.select(CARD_SEL)
    entries: List[Dict[str, object]] = []
    img_counts: Dict[str, int] = {}
    for card in cards:
        imgs = [img.get("src", "") for img in card.select("img[src]")]
        types = [classify_img(src) for src in imgs]
        for t in types:
            img_counts[t] = img_counts.get(t, 0) + 1
        spid = find_spid(card)
        # extract codes by type if present in image URLs
        nation_codes, league_codes, team_codes = set(), set(), set()
        for src in imgs:
            m = RE_NATION.search(src)
            if m:
                nation_codes.add(m.group(1))
            m = RE_LEAGUE.search(src)
            if m:
                league_codes.add(m.group(1))
            m = RE_TEAM.search(src)
            if m:
                team_codes.add(m.group(1))
        # keep up to a few sample images per card
        sample = []
        for src in imgs:
            if len(sample) >= 5:
                break
            sample.append(src)
        entries.append({
            "spid": spid,
            "images_sample": sample,
            "nation_codes": sorted(nation_codes),
            "league_codes": sorted(league_codes),
            "team_codes": sorted(team_codes),
        })
    # Compose markdown
    md: List[str] = []
    md.append(f"### {path.name}")
    md.append("")
    md.append(f"- File: `{path.as_posix()}`")
    md.append(f"- bestPrice present: {'yes' if best else 'no'}")
    md.append(f"- card elements: {len(cards)}")
    if img_counts:
        md.append("- image types:")
        for k in sorted(img_counts.keys()):
            md.append(f"  - {k}: {img_counts[k]}")
    # list first 10 cards for brevity
    show = entries[:10]
    for i, e in enumerate(show, 1):
        spid = e['spid'] or 'N/A'
        md.append(f"  - card#{i} spid={spid}")
        for src in e["images_sample"]:
            md.append(f"    - {src}")
        # codes parsed from images
        nc = e.get('nation_codes') or []
        lc = e.get('league_codes') or []
        tc = e.get('team_codes') or []
        if nc or lc or tc:
            md.append(f"    - codes: nation={list(nc)} league={list(lc)} team={list(tc)}")
        if e['spid']:
            md.append("    - derived player image URLs:")
            md.append(f"      - https://fo4.dn.nexoncdn.co.kr/live/externalAssets/common/playersAction/p{spid}.png")
            md.append(f"      - https://fo4.dn.nexoncdn.co.kr/live/externalAssets/common/players/p{spid}.png")
            md.append(f"      - https://fo4.dn.nexoncdn.co.kr/live/externalAssets/common/playersAction/p{spid}_24.png")
            md.append(f"      - https://fo4.dn.nexoncdn.co.kr/live/externalAssets/common/players/p{spid}_24.png")
    # hints to construct player image URLs if spid known (templates)
    md.append("- player image URL templates (by spId):")
    md.append("  - https://fo4.dn.nexoncdn.co.kr/live/externalAssets/common/playersAction/p{spid}.png")
    md.append("  - https://fo4.dn.nexoncdn.co.kr/live/externalAssets/common/players/p{spid}.png")
    md.append("  - https://fo4.dn.nexoncdn.co.kr/live/externalAssets/common/playersAction/p{spid}_24.png")
    md.append("  - https://fo4.dn.nexoncdn.co.kr/live/externalAssets/common/players/p{spid}_24.png")
    md.append("")
    return {"markdown": "\n".join(md), "cards": len(cards)}


def run() -> None:
    root = Path("docs/check")
    files = sorted(root.glob("*.html"))
    out = Path("docs/check/BESTPRICE_HTML_SUMMARY.md")
    parts: List[str] = []
    parts.append("# FC 데이터센터 best_price HTML 점검 요약")
    parts.append("")
    parts.append("대상 셀렉터: `#bestPrice > div > div.content.item_list_wrap > div.item_list_wrap__card` (유사 구조 포함)")
    parts.append("")
    total_cards = 0
    for f in files:
        res = summarize_file(f)
        parts.append(res["markdown"])  # type: ignore
        total_cards += int(res["cards"])  # type: ignore
    parts.append("")
    parts.append(f"총 카드 개수 합계: {total_cards}")
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"[WROTE] {out} (files={len(files)} cards={total_cards})")


if __name__ == "__main__":
    run()
