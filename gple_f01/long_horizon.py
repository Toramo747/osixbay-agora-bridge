"""Long-horizon F01 ecological stress screen, synthetic experiment only."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from biome_search import VARIANTS, load_f01
from ecological_adapter import EcoF01

def endurance(original, seeds=(11,23,37),ticks=1500,snapshot_every=250):
    if not 1<=ticks<=10000 or not 1<=len(seeds)<=20 or snapshot_every<1:
        raise ValueError("invalid endurance budget")
    f01=load_f01(original)
    results=[]
    for variant in VARIANTS:
        for seed in seeds:
            world=EcoF01(f01,variant,seed=seed)
            world.spawn(8)
            checkpoints=[]
            extinct_at=None
            for tick in range(1,ticks+1):
                world.step()
                if not world.world.organisms and extinct_at is None:
                    extinct_at=tick
                if tick % snapshot_every==0 or tick==ticks:
                    snap=world.snapshot()
                    restored=EcoF01.from_snapshot(f01,snap)
                    if restored.snapshot()!=snap: raise ValueError("snapshot parity")
                    checkpoints.append({"tick":tick,"alive":len(world.world.organisms),
                                        "stages":world.stage_counts(),
                                        "food":round(sum(c.food for row in world.env for c in row),5)})
            results.append({"candidate":variant["id"],"seed":seed,
                            "final_population":len(world.world.organisms),
                            "extinct_at":extinct_at,
                            "births":world.events["births"],"deaths":world.events["deaths"],
                            "consumed":round(world.events["eaten"],5),
                            "regrown":round(world.events["grown"],5),
                            "ledger_checks":world.events["resource_ledger_checks"],
                            "checkpoints":checkpoints})
    return {"schema":"osixbay.gple.f01.endurance.v1","status":"synthetic_test_not_validated_ecology",
            "ticks":ticks,"seeds":list(seeds),"scenarios":len(results),"results":results,
            "caveats":["Age thresholds experimental","Finite resource stock tracked, not full mass/energy conservation",
                       "Real terrain, weather and physiological data missing","No Kaggle run implied"]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original",default="genesis/fauna01/sim.py")
    p.add_argument("--ticks",type=int,default=1500)
    p.add_argument("--out",default="f01-endurance.json")
    a=p.parse_args()
    result=endurance(a.original,ticks=a.ticks)
    f=Path(a.out);f.parent.mkdir(parents=True,exist_ok=True)
    f.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"scenarios":result["scenarios"],"ticks":result["ticks"],
                      "extinctions":sum(x["extinct_at"] is not None for x in result["results"])}))
if __name__=="__main__": main()
