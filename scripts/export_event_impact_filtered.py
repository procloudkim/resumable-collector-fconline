from __future__ import annotations

"""
Export filtered event-impact figures by player groups and window sizes.

Generates per-group and overlay line charts of daily play totals around an
event date (e.g., 2022-12-02 대한민국 vs 포르투갈).

Outputs go to analytics/exports/ with filenames like:
  - event_impact_kor_w7_landscape.png
  - event_impact_por_w7_landscape.png
  - event_impact_kor_por_overlay_w7_landscape.png
Also for w3 and w14 if requested.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd
import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[1]
EXPORTS = ROOT / "analytics" / "exports"


def _ensure_dirs() -> None:
    EXPORTS.mkdir(parents=True, exist_ok=True)


def _setup_korean() -> None:
    plt.rcParams["axes.unicode_minus"] = False
    for f in ["Malgun Gothic", "AppleGothic", "NanumGothic", "DejaVu Sans"]:
        try:
            plt.rcParams["font.sans-serif"] = [f]
            # Smoke
            _ = plt.figure(); plt.text(0.5, 0.5, "가", ha="center", va="center"); plt.close(_)
            break
        except Exception:
            continue


def _find_csv(*cands: str) -> Optional[Path]:
    for c in cands:
        p = ROOT / c
        if p.exists():
            return p
    return None


def load_topdaily() -> pd.DataFrame:
    p = _find_csv(
        "analytics/clean/top_daily_record.clean.ko.strip.csv",
        "analytics/clean/top_daily_record.clean.ko.csv",
        "analytics/clean/top_daily_record.clean.csv",
        "analytics/game/top_daily_record.csv",
    )
    if not p:
        raise FileNotFoundError("top_daily_record csv not found")
    df = pd.read_csv(p)
    return df


def load_events() -> pd.DataFrame:
    p = _find_csv("config/events.csv")
    if not p:
        raise FileNotFoundError("config/events.csv not found")
    return pd.read_csv(p)


def detect_cols(df: pd.DataFrame) -> tuple[str, Optional[str], str]:
    """Return (date_col, name_col, value_col). name_col may be None.
    name column is first matching among ['선수', '이름', 'player'].
    value column prefers '출전_기록' then '출전'.
    """
    # date
    date_col = "날짜" if "날짜" in df.columns else ("date" if "date" in df.columns else df.columns[0])
    # value
    value_col = None
    for c in ["출전_기록", "출전", "play", "PLAY"]:
        if c in df.columns:
            value_col = c
            break
    if value_col is None:
        # Fallback to the 4th column as in raw top_daily_record.csv
        value_col = df.columns[3]
    # name
    name_col = None
    for c in df.columns:
        if any(tok in c for tok in ["선수", "이름", "player", "기본"]):
            name_col = c
            break
    return date_col, name_col, value_col  # type: ignore


def extract_leading_name(series: pd.Series) -> pd.Series:
    s = series.astype(str)
    # many rows look like "<이름>, <시즌>, <포지션>, ..."; take the head token
    return s.str.split(',').str[0].str.strip()


@dataclass
class Group:
    key: str
    players: List[str]


KOR_PLAYERS = [
    '김승규','김문환','권경원','김영권','김진수','황인범','이재성','정우영','이강인','손흥민','조규성'
]
POR_PLAYERS = [
    '디오구 코스타','디오구 달로트','안토니우 실바','페페','주앙 칸셀루','마테우스 누네스','후벵 네베스','주앙 마리우','히카르두 오르타','비티냐','크리스티아누 호날두'
]


def _event_date(df_events: pd.DataFrame) -> pd.Timestamp:
    # Prefer exact match for 2022-12-02 and Korea/Portugal keywords
    m = df_events[
        df_events['date'].astype(str).str.contains('2022-12-02') &
        df_events['name'].astype(str).str.contains('대한민국|한국|KOR', regex=True) &
        df_events['name'].astype(str).str.contains('포르투갈|POR', regex=True)
    ]
    if m.empty:
        # fallback: first row that contains Korea/Portugal
        m = df_events[df_events['name'].astype(str).str.contains('대한민국|한국|KOR')]
    row = m.iloc[0]
    return pd.to_datetime(row['date'], errors='coerce')


def series_for_group(df: pd.DataFrame, date_col: str, name_col: Optional[str], value_col: str, players: Iterable[str]) -> pd.DataFrame:
    dd = df.copy()
    dd[date_col] = pd.to_datetime(dd[date_col], errors='coerce')
    if name_col is not None and name_col in dd.columns:
        dd['_lead_name'] = extract_leading_name(dd[name_col])
        mask = False
        for p in players:
            mask = mask | dd['_lead_name'].str.contains(p, na=False)
        dd = dd.loc[mask]
    # aggregate by date
    dd[value_col] = pd.to_numeric(dd[value_col], errors='coerce')
    g = dd.groupby(dd[date_col].dt.date)[value_col].sum().reset_index()
    g.rename(columns={date_col: 'day', value_col: 'value'}, inplace=True)
    g['day'] = pd.to_datetime(g['day'])
    return g


def plot_line(g: pd.DataFrame, event_dt: pd.Timestamp, title: str, out_name: str) -> Path:
    _setup_korean()
    plt.figure(figsize=(11, 6.5))
    plt.plot(g['day'], g['value'], marker='o')
    plt.axvline(event_dt, color='red', linestyle='--', label='경기일')
    plt.title(title)
    plt.xlabel('날짜')
    plt.ylabel('출전 합계')
    plt.legend()
    # save landscape
    out_png = EXPORTS / f"{out_name}_landscape.png"
    out_pdf = EXPORTS / f"{out_name}_landscape.pdf"
    plt.gcf().set_size_inches(11, 6.5)
    plt.tight_layout()
    plt.savefig(out_png, dpi=220)
    try:
        plt.savefig(out_pdf)
    except Exception:
        pass
    plt.close()
    return out_png


def plot_overlay(g1: pd.DataFrame, g2: pd.DataFrame, event_dt: pd.Timestamp, labels: tuple[str, str], title: str, out_name: str) -> Path:
    _setup_korean()
    plt.figure(figsize=(11, 6.5))
    plt.plot(g1['day'], g1['value'], marker='o', label=labels[0])
    plt.plot(g2['day'], g2['value'], marker='o', label=labels[1])
    plt.axvline(event_dt, color='red', linestyle='--', label='경기일')
    plt.title(title)
    plt.xlabel('날짜')
    plt.ylabel('출전 합계')
    plt.legend()
    out_png = EXPORTS / f"{out_name}_landscape.png"
    out_pdf = EXPORTS / f"{out_name}_landscape.pdf"
    plt.gcf().set_size_inches(11, 6.5)
    plt.tight_layout()
    plt.savefig(out_png, dpi=220)
    try:
        plt.savefig(out_pdf)
    except Exception:
        pass
    plt.close()
    return out_png


def subset_window(g: pd.DataFrame, center: pd.Timestamp, window: int) -> pd.DataFrame:
    m = (g['day'] >= (center - pd.Timedelta(days=window))) & (g['day'] <= (center + pd.Timedelta(days=window)))
    return g.loc[m].sort_values('day')


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Filtered event impact exporter")
    ap.add_argument('--windows', type=str, default='3,7,14', help='comma list of windows (days)')
    args = ap.parse_args()

    _ensure_dirs()
    df_t = load_topdaily()
    df_e = load_events()
    date_col, name_col, value_col = detect_cols(df_t)
    e_dt = _event_date(df_e)

    groups = [Group('kor', KOR_PLAYERS), Group('por', POR_PLAYERS)]

    for w in [int(x) for x in args.windows.split(',') if str(x).strip().isdigit()]:
        series = {}
        for g in groups:
            s = series_for_group(df_t, date_col, name_col, value_col, g.players)
            s = subset_window(s, e_dt, w)
            series[g.key] = s
            plot_line(
                s,
                e_dt,
                title=f"빅매치 임팩트(±{w}일) — {g.key.upper()} 선수군",
                out_name=f"event_impact_{g.key}_w{w}"
            )
        # overlay
        plot_overlay(
            series['kor'], series['por'], e_dt,
            labels=("대한민국", "포르투갈"),
            title=f"빅매치 임팩트(±{w}일) — 대한민국 vs 포르투갈",
            out_name=f"event_impact_kor_por_overlay_w{w}"
        )

    print(f"[OK] exports in {EXPORTS}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

