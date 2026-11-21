"""Execute multi-seed comparison for the ecological adapter (synthetic fixtures)."""
import argparse
import json
from pathlib import Path
from biome_search import VARIANTS
from ecological_adapter import compare

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original",default="genesis/fauna01/sim.py")
    p.add_argument("--out",default="f01-ecological-comparison.json")
    p.add_argument("--ticks",type=int,default=120)
    args=p.parse_args()
    result=compare(args.original,VARIANTS,ticks=args.ticks)
    destination=Path(args.out)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    for record in result["results"]:
        print(f'{record["candidate"]}: population={record["mean_survivors"]}, extinction={record["extinction_rate"]}, cap={record["cap_hit_rate"]}')

if __name__=="__main__":main()
