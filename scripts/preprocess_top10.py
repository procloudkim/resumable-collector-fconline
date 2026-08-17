"""
RAW JSONL → 날짜별 Top10 출전(픽) 시계열 CSV
"""
from __future__ import annotations
from pathlib import Path
import argparse, json, pandas as pd
from app.core.utils import RAW, PROC, ensure_dirs, log

def parse_jsonl(fp: Path):
    with fp.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            try: yield json.loads(line)
            except Exception: pass

def build_timeseries() -> pd.DataFrame:
    files = sorted(RAW.glob("*.jsonl"))
    if not files: log("RAW 없음", level="WARN"); return pd.DataFrame()
    recs = []
    for fp in files:
        for obj in parse_jsonl(fp):
            d = obj.get("matchDate") or obj.get("matchInfo", [{}])[0].get("matchDate")
            if d and "T" in d: d = d.split("T")[0]
            if not d: continue
            for team in obj.get("matchInfo", []):
                for p in team.get("player", []):
                    sp = p.get("spId") or p.get("spid")
                    if not sp: continue
                    recs.append({"date": d, "spid": int(sp), "cnt": 1})
    df = pd.DataFrame(recs)
    if df.empty: return df
    df = df.groupby(["date","spid"])["cnt"].sum().reset_index()
    top = df.groupby("spid")["cnt"].sum().sort_values(ascending=False).head(10).index.tolist()
    df = df[df["spid"].isin(top)]
    pivot = df.pivot_table(index="date", columns="spid", values="cnt", aggfunc="sum").fillna(0)
    pivot.index = pd.to_datetime(pivot.index)
    return pivot.sort_index()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=PROC/"top10_trend.csv")
    args = ap.parse_args()
    ensure_dirs()
    ts = build_timeseries()
    if ts.empty: log("전처리 결과 없음", level="WARN"); return
    ts.to_csv(args.out); log(f"저장 완료 → {args.out}")

if __name__=="__main__": main()
