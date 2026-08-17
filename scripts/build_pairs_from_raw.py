"""
RAW에서 (spid, 최빈 포지션) 추정 → pairs.json 생성
- po는 메타(spposition)에 존재하는 코드만 허용
"""
from __future__ import annotations
import argparse, json, glob
from collections import Counter
from pathlib import Path
from app.core.utils import RAW, log
from app.services.meta import load_position_map

def build_pairs_from_raw(raw_glob: str, topk: int):
    combo = Counter(); count = Counter()
    pos_map = load_position_map()
    files = sorted(glob.glob(raw_glob))
    if not files: log(f"RAW 없음: {raw_glob}", level="WARN"); return []
    import json
    for fp in files:
        with open(fp,"r",encoding="utf-8") as f:
            for line in f:
                line=line.strip()
                if not line: continue
                try: obj=json.loads(line)
                except Exception: continue
                for team in obj.get("matchInfo", []):
                    for p in team.get("player", []):
                        spid=p.get("spId") or p.get("spid"); po=p.get("spPosition") or p.get("po")
                        if spid is None or po is None: continue
                        spid,po=int(spid),int(po)
                        if po not in pos_map: continue
                        combo[(spid,po)]+=1; count[spid]+=1
    top_spids=[sp for sp,_ in count.most_common(topk)]
    po_by_spid={}
    for sp in top_spids:
        cands=[(po,n) for (s,po),n in combo.items() if s==sp]
        if not cands: continue
        po_by_spid[sp]=max(cands,key=lambda x:x[1])[0]
    return [{"id":sp,"po":po} for sp,po in po_by_spid.items()]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--raw-glob",default=str(RAW/"*.jsonl"))
    ap.add_argument("--topk",type=int,default=200)
    ap.add_argument("--out",default="pairs.json")
    args=ap.parse_args()
    pairs=build_pairs_from_raw(args.raw_glob,args.topk)
    Path(args.out).write_text(json.dumps(pairs,ensure_ascii=False,indent=2),encoding="utf-8")
    log(f"생성 완료 → {args.out} (개수={len(pairs)})")

if __name__=="__main__": main()
