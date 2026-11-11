"""Deterministic synthetic biome proposal search for the ORIGINAL F01 simulator.

Never interpret these outputs as canonical Genesis biomes or discovered biology.
Inputs are hypotheses, not world measurements. No network calls, no LLM per tick.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import statistics
from dataclasses import asdict, replace

HABITATS = ("alien_forest", "wet_shore", "mineral_outcrop")
VARIANTS = (
    {"id":"forest_biofilm", "label":"Bosco umido con biofilm",
     "biome_mix":[0.65,0.25,0.10], "food_capacity":4.0, "regrowth":0.16, "hazard":0.08},
    {"id":"shore_nursery", "label":"Riva umida con zone di crescita",
     "biome_mix":[0.25,0.60,0.15], "food_capacity":4.5, "regrowth":0.22, "hazard":0.12},
    {"id":"rock_shelter", "label":"Rocce con rifugi e nicchie biologiche",
     "biome_mix":[0.35,0.20,0.45], "food_capacity":3.0, "regrowth":0.11, "hazard":0.06},
    {"id":"scarcity", "label":"Ambiente povero di risorse",
     "biome_mix":[0.35,0.35,0.30], "food_capacity":2.0, "regrowth":0.03, "hazard":0.18},
    {"id":"mixed_mosaic", "label":"Mosaico ecologico equilibrato",
     "biome_mix":[0.40,0.35,0.25], "food_capacity":4.0, "regrowth":0.17, "hazard":0.10},
    {"id":"stress_wetland", "label":"Zone umide instabili",
     "biome_mix":[0.20,0.65,0.15], "food_capacity":4.0, "regrowth":0.14, "hazard":0.33},
)
def load_f01(path):
    path=Path(path)
    spec=importlib.util.spec_from_file_location("f01_original_reference",path)
    if spec is None or spec.loader is None: raise ValueError("original F01 file not found")
    import sys
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module

def synthetic_map(seed, variant, width=12):
    """Irregular fixture with hypothetical labels only: not an exported Godot mask."""
    if width<6 or width>128: raise ValueError("invalid synthetic width")
    grid=[]; labels=[]
    shares=variant["biome_mix"]
    for y in range(width):
        row=[]; br=[]
        for x in range(width):
            # A deterministic irregular shape with holes and a non-rectangular boundary.
            playable=(2 <= x < width-1 and 1 <= y < width-1
                      and (x+y+seed)%11!=0 and not (x<4 and y>width-4))
            row.append(playable)
            z=((x*37+y*17+seed*7)%100)/100
            idx=0 if z<shares[0] else (1 if z<shares[0]+shares[1] else 2)
            br.append(HABITATS[idx])
        grid.append(row);labels.append(br)
    return grid,labels

def run_trial(f01,variant,seed,ticks):
    mask,labels=synthetic_map(seed,variant)
    # The original engine only supports one global regrowth rate and capacity.
    # This is a coarse proxy, NOT a valid 3-biome biophysical simulation.
    p=replace(f01.Parameters(),capacity=variant["food_capacity"],
              regrowth=variant["regrowth"])
    world=f01.World(mask,seed=seed,parameters=p)
    spots=[(x,y) for y,row in enumerate(mask) for x,ok in enumerate(row) if ok]
    for x,y in spots[:min(8,len(spots))]:
        world.add_organism(x,y)
    # Synthetic resource and environmental hazard distribution.
    for y,row in enumerate(world.cells):
        for x,c in enumerate(row):
            if not c.suitable:continue
            biome=labels[y][x]
            multiplier={"alien_forest":0.85,"wet_shore":1.0,"mineral_outcrop":0.55}[biome]
            c.food=min(p.capacity,p.capacity*multiplier)
            c.danger=min(1.0,variant["hazard"]+(0.4 if (x+y+seed)%17==0 else 0))
    born=died=0
    maximum=len(world.organisms)
    initial_food=sum(c.food for row in world.cells for c in row)
    for _ in range(ticks):
        event=world.step()
        born+=event["born"];died+=event["died"]
        maximum=max(maximum,event["alive"])
    final_food=sum(c.food for row in world.cells for c in row)
    return {"seed":seed,"survivors":len(world.organisms),"born":born,"died":died,
            "population_peak":maximum,"population_cap":p.max_population,
            "final_food":round(final_food,4),"initial_food":round(initial_food,4)}

def rank_candidate(trials):
    survivors=[v["survivors"] for v in trials]
    extinct=sum(n==0 for n in survivors)/len(survivors)
    capped=sum(v["population_peak"]>=v["population_cap"] for v in trials)/len(trials)
    # Conservative screening heuristic, not ecological fitness or evidence of evolution.
    score=round((1-extinct)*50 + min(statistics.mean(survivors),25)
                - capped*25 - statistics.pstdev(survivors)*0.25,4)
    return score,extinct,capped

def experiment(original_sim, seeds=(11,23,37,53,71),ticks=150):
    if not seeds or len(seeds)>100 or ticks<1 or ticks>10000:
        raise ValueError("simulation budget exceeded")
    if any(not isinstance(s,int) or isinstance(s,bool) for s in seeds):
        raise ValueError("invalid seed")
    f01=load_f01(original_sim)
    proposals=[]
    for v in VARIANTS:
        trials=[run_trial(f01,v,seed,ticks) for seed in seeds]
        score,extinct,capped=rank_candidate(trials)
        proposals.append({"candidate":v,"score_screening_only":score,
                          "extinction_rate":extinct,"cap_hit_rate":capped,
                          "mean_final_population":round(statistics.mean(t["survivors"] for t in trials),3),
                          "trials":trials})
    proposals.sort(key=lambda r:(-r["score_screening_only"],r["candidate"]["id"]))
    raw=json.dumps(proposals,sort_keys=True,separators=(",",":")).encode()
    return {"schema":"osixbay.gple.f01.biome-candidates.v1",
            "status":"synthetic_hypotheses_not_validated_habitats",
            "original_sim_reference":str(original_sim),
            "seeds":list(seeds),"ticks":ticks,
            "source_world_mask_imported":False,
            "caveats":["Single global resource regrowth: proxy only",
                       "No water/humidity/temperature physiology in original F01",
                       "No ecological evolutionary proof; fitness is a screening heuristic",
                       "No Godot or Cloudflare integration"],
            "replay_digest_sha256":hashlib.sha256(raw).hexdigest(),
            "proposals":proposals}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--original",default="genesis/fauna01/sim.py")
    p.add_argument("--ticks",type=int,default=150)
    p.add_argument("--out",default="f01-biome-proposals.json")
    a=p.parse_args()
    result=experiment(a.original,ticks=a.ticks)
    Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    Path(a.out).write_text(json.dumps(result,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"proposals":len(result["proposals"]),
                      "best":result["proposals"][0]["candidate"]["id"],
                      "digest":result["replay_digest_sha256"]}))

if __name__=="__main__":main()
