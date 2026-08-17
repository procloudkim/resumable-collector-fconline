FC Datacenter Daily Trade — DOM Version Report (check/*.html)

- Scope: check-2020.html .. check-2025.html
- Goal: Identify layout version(s), selectors, and coverage to guide robust crawling with safety checks.

Summary
- All six snapshots match the card/slider layout (card_swiper_v1).
- No table-based grids were found in any snapshot.

Per-file quick stats
- check-2020.html: tables=0, thead=0, th=0, swiper-slide=20, PlayerInfo?spid=18, price_wrap=18, buildUp=18
- check-2021.html: tables=0, thead=0, th=0, swiper-slide=20, PlayerInfo?spid=18, price_wrap=18, buildUp=18
- check-2022.html: tables=0, thead=0, th=0, swiper-slide=20, PlayerInfo?spid=18, price_wrap=18, buildUp=18
- check-2023.html: tables=0, thead=0, th=0, swiper-slide=20, PlayerInfo?spid=18, price_wrap=18, buildUp=18
- check-2024.html: tables=0, thead=0, th=0, swiper-slide=20, PlayerInfo?spid=18, price_wrap=18, buildUp=18
- check-2025.html: tables=0, thead=0, th=0, swiper-slide=20, PlayerInfo?spid=18, price_wrap=18, buildUp=18

Version fingerprints
- card_swiper_v1:
  - Present: #divBestTradeArea_price, .swiper-slide (≥10), a.outlink[href*='PlayerInfo?spid='], .price_wrap .price
  - Typical name nodes: .playerCardInfoBottom .nameWrap .name span OR .player_wrap[title] OR a.outlink > span.hidden
  - Level nodes: .buildUp a (sometimes missing per slide; +N text is fallback)
- table_v1 (not observed in these files but supported):
  - Present: <table> with headers containing one or more of [선수, 거래, 강화, 평균, 최고, 최저]

Selectors (prioritized)
- spid: a.outlink[href*='PlayerInfo?spid='] (parse query.spid)
- player_name: .playerCardInfoBottom .nameWrap .name span → .player_wrap[title]@title → a.outlink > span.hidden
- avg_price, max_price: .price_wrap .price (alt|title → text fallback), both set to the same price in card layout
- min_price: absent in card layout → null (or set = avg_price as a deterministic policy)
- trade_count: absent in card layout → null (non-top players filled with 0 to complete target set)
- max_enhance_level: .buildUp a (digits) → +N pattern in slide text

Safety gates (recommended)
- card_swiper_v1 gate: distinct SPIDs ≥ 15 AND price nodes ≥ 15; else escalate to Selenium fetch.
- table_v1 gate: at least one table AND ≥ 15 data rows with player names; else fallback to card parsing.

Policies for missing fields
- min_price: set to null (preferred). If a filled value is required, set min_price = avg_price when only a single price is present.
- trade_count: set to null for card-derived rows. For target players not in top cards, set trade_count = 0.

See also: check/version_selectors.yaml (machine-readable mapping).

