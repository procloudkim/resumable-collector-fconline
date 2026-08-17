from pathlib import Path
import pandas as pd

from app.clean_names import normalize_player_name, clean_best_price_names


def test_normalize_player_name_examples():
    assert normalize_player_name("케빈 더브라위너") == "케빈 더브라위너"
    s = "115 ST 23 8 크리스티아누 호날두 4,480억"
    assert normalize_player_name(s) == "크리스티아누 호날두"


def test_clean_best_price_names_basic(tmp_path: Path):
    df = pd.DataFrame({
        "player_name": ["115 ST 23 8 크리스티아누 호날두 4,480억", "케빈 더브라위너"],
        "price_text": [" 4,480억 ", " 1,000억"],
    })
    out, rep = clean_best_price_names(df, strip_whitespace=False)
    assert list(out["player_name"]) == ["크리스티아누 호날두", "케빈 더브라위너"]
    assert rep.whitespace_issues.get("price_text", 0) == 2

