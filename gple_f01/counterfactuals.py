"""F01 controlled counterfactual screen: resource regrowth, water access and reproduction.

Interventions isolate simulation mechanisms, not ecological causal claims.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from biome_search import VARIANTS, load_f01
from ecological_adapter import EcoF01

INTERVENTIONS=("baseline","no_water","no_regrowth","no_births")
def experiment(original,seeds=(11,23,37),ticks=400):
    if not seeds or len(seeds)>20 or not 1<=ticks<=10000:
        raise ValueError("invalid experimental budget")
    f01=load_f01(original)
    cases=[]
    for variant in VARIANTS:
        for seed in seeds:
            for intervention in INTERVENTIONS:
                world=EcoF01(f01,variant,seed=seed,water_access=(intervention!="no_water"))
                world.spawn(8)
                if intervention=="no_regrowth":
                    for row in world.env:
                        for cell in row:cell.regrowth=0.0
                if intervention=="no_births":
                    # Experimental counterfactual: block reproduction via nonzero cooldown every turn.
                    # Deliberately not interpreted as a natural population condition.
                    pass
                extinct_at=None
                for tick in range(1,ticks+1):
                    if intervention=="no_births":
                        for a in world.world.organisms:a.cooldown=world.world.parameters.cooldown+2
                    world.step()
                    if not world.world.organisms and extinct_at is None:extinct_at=tick
                events=world.events
                cases.append({"candidate":variant["id"],"seed":seed,"intervention":intervention,
                              "alive":len(world.world.organisms),"extinct_at":extinct_at,
                              "births":events["births"],"deaths":events["deaths"],
                              "hydration_deaths":events["hydration_deaths"],
                              "energy_deaths":events["energy_deaths"],
                              "age_deaths":events["age_deaths"],
                              "food_consumed":round(events["eaten"],4),
                              "food_regrown":round(events["grown"],4),
                              "ledger_checks":events["resource_ledger_checks"]})
    return {"schema":"osixbay.gple.f01.counterfactuals.v1",
            "status":"mechanism_diagnostics_synthetic_only",
            "ticks":ticks,"seeds":list(seeds),"interventions":list(INTERVENTIONS),
            "cases":cases,"caveats":["Death cause = immediate simulated mechanism, not an ecological root cause",
                                      "No births intervention is a controlled code manipulation",
                                      "Resource replenishment is an external model input, not a closed nutrient cycle",
                                      "Actual F01 physiology and real habitat not yet validated"]}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--original",default="genesis/fauna01/sim.py")
    parser.add_argument("--ticks",type=int,default=400)
    parser.add_argument("--out",default="f01-counterfactuals.json")
    a=parser.parse_args()
    report=experiment(a.original,ticks=a.ticks)
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    summary={}
    for row in report["cases"]:
        key=row["intervention"]
        stats=summary.setdefault(key,{"runs":0,"extinctions":0,"hydration_deaths":0,"energy_deaths":0,"age_deaths":0})
        stats["runs"]+=1;stats["extinctions"]+=row["extinct_at"] is not None
        for k in ("hydration_deaths","energy_deaths","age_deaths"):stats[k]+=row[k]
    print(json.dumps(summary,sort_keys=True))
if __name__=="__main__":main()
