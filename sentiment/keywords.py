from __future__ import annotations

# Player/team mention keyword lists (case-insensitive for roman terms)

"""Keyword lists for player/team mentions.

Canonical keys are player names in Korean; term lists include variants.
Roman terms should be provided in lowercase for case-insensitive matching.
"""

# Korea players
KOREA_KEYWORDS = {
    "손흥민": ["손흥민", "흥민", "쏜"],
    "황희찬": ["황희찬", "황소"],
    "김영권": ["김영권"],
}

# Portugal players
PORTUGAL_KEYWORDS = {
    "호날두": ["호날두", "크리스티아누", "cr7", "ronaldo"],
    "호르타": ["호르타"],
    "달롯": ["달롯", "dalot"],
}

# Flattened sets for quick flags
KOREA_TERMS = {t for v in KOREA_KEYWORDS.values() for t in v}
PORTUGAL_TERMS = {t for v in PORTUGAL_KEYWORDS.values() for t in v}

# Player -> team mapping and complete player list
PLAYER_TO_TEAM = {**{k: "korea" for k in KOREA_KEYWORDS.keys()}, **{k: "portugal" for k in PORTUGAL_KEYWORDS.keys()}}
PLAYER_LIST = list(PLAYER_TO_TEAM.keys())

