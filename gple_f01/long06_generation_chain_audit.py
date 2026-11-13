"""ECO-LONG-06: controlled generation-chain perturbations, no respawn.
Uses only parent-paid initial seedbank; rate changes are experimental knobs.
All scenarios start with equal biomass and water (separate conserved ledgers).
"""
from __future__ import annotations
import contextlib
import csv
import json
import math
import pathlib

import propagules_p0 as P
import plant_lifecycle_p0 as L
from f01_feeding_bridge_p0 import F01Feeding
from stress_ecosystem_dm089 import NORMAL, _metrics
from long05_detritus_seedbank_audit import seedbank_from_live_parents, apply_extra_mineralization, stock_totals
from multi_patch_p0 import NODES

SEEDS=(11,23,37)
TICKS=1200
YEAR_TICKS=12
# All runs use the same moderate additional mineralization and starting parent-paid seedbank.
# Only one life-cycle parameter differs at a time; 'combined' is non-causal screening.
SCENARIOS=(
    ("reference", 65, 3, .45, .45, 120),
    ("longer_seed_viability", 180, 3, .45, .45, 120),
    ("earlier_germination", 65, 1, .45, .45, 120),
    ("wetter_threshold_relaxed", 65, 3, .25, .45, 120),
    ("higher_dispersal", 65, 3, .45, .85, 120),
    ("longer_plant_life", 65, 3, .45, .45, 240),
    ("combined_screen", 180, 1, .25, .85, 240),
)
@contextlib.contextmanager
def parameters(lifetime,germ_age,moisture,dispersal,plant_age):
    original=(P.SEED_LIFETIME,P.GERMINATION_AGE,P.MIN_MOISTURE,
              P.DISPERSAL_PROBABILITY,L.MAX_AGE)
    assert 1<=germ_age<=lifetime and 0<=moisture<=1 and 0<=dispersal<=1
    try:
        P.SEED_LIFETIME=lifetime
        P.GERMINATION_AGE=germ_age
        P.MIN_MOISTURE=moisture
        P.DISPERSAL_PROBABILITY=dispersal
        L.MAX_AGE=plant_age
        yield
    finally:
        (P.SEED_LIFETIME,P.GERMINATION_AGE,P.MIN_MOISTURE,
         P.DISPERSAL_PROBABILITY,L.MAX_AGE)=original

def state(sim):
    m=_metrics(sim)
    life=sim.eco.world.genetic.life
    w=sim.eco.world
    s=stock_totals(sim)
    return dict(tick=m["tick"],plants=m["plants_alive"],
                dormant=m["propagules_dormant"],
                births=life.counts["births"],
                deaths=life.counts["deaths"],
                seeds_created=w.created,seeds_germinated=w.germinated,
                seeds_expired=w.expired,seeds_dispersed=w.dispersed,
                f01=m["f01_alive"],microfauna=m["microfauna_alive"],
                biomass=m["biomass"],water=m["water"],detritus=s["detritus"],
                nutrients=s["nutrients"],
                producer_mass=s["producer_a"]+s["producer_b"])

def run_case(seed, scenario):
    name,lifetime,germ_age,moisture,dispersal,plant_age=scenario
    with parameters(lifetime,germ_age,moisture,dispersal,plant_age):
        sim=F01Feeding(seed=seed)
        deposits=seedbank_from_live_parents(sim)
        initial=state(sim)
        mb=sim.eco.world.total_biomass()
        water=sim.eco.world.genetic.life.hydro.total_water()
        rows=[]
        last_generation_tick=None
        first_empty_tick=None
        maximum_plants=initial["plants"]
        check_ticks={}
        for tick in range(1,TICKS+1):
            sim.tick(**NORMAL)
            apply_extra_mineralization(sim)
            now=state(sim)
            if first_empty_tick is not None and (now["plants"] or now["dormant"]):
                raise AssertionError("spontaneous resurrection after global extinction")
            if now["plants"]==0 and now["dormant"]==0 and first_empty_tick is None:
                first_empty_tick=tick
            if now["births"] or now["seeds_germinated"]:
                last_generation_tick=tick
            maximum_plants=max(maximum_plants,now["plants"])
            if not math.isclose(mb,sim.eco.world.total_biomass(),rel_tol=1e-10,abs_tol=1e-6):
                raise AssertionError("material ledger")
            if not math.isclose(water,sim.eco.world.genetic.life.hydro.total_water(),rel_tol=1e-10,abs_tol=1e-6):
                raise AssertionError("water ledger")
            if tick % YEAR_TICKS == 0:
                rows.append(dict(seed=seed,scenario=name,year=tick//YEAR_TICKS,**now))
            if tick in (12,120,600,1200):
                check_ticks[str(tick)]=now
        final=state(sim)
        result=dict(seed=seed,scenario=name,parameters={
            "seed_lifetime":lifetime,"germination_age":germ_age,
            "moisture_threshold":moisture,"dispersal_probability":dispersal,
            "plant_max_age":plant_age},
            initial=initial,final=final,
            first_irreversible_extinction_tick=first_empty_tick,
            last_generation_tick=last_generation_tick,
            max_live_plants=maximum_plants,
            initial_paid_propagules=len(deposits),
            initial_escrow_mass=sum(x["escrowed_mass"] for x in deposits),
            checkpoints=check_ticks,conserved=True,no_respawn=True)
        print("verified",seed,name,"plants",final["plants"],
              "germinated",final["seeds_germinated"],
              "extinction_tick",first_empty_tick,flush=True)
        return result,rows

def main():
    folder=pathlib.Path("long06_results");folder.mkdir(exist_ok=True)
    summaries=[];annual=[]
    for seed in SEEDS:
        for scenario in SCENARIOS:
            case,rows=run_case(seed,scenario)
            summaries.append(case);annual.extend(rows)
    with (folder/"annual_100_years.csv").open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(annual[0]));w.writeheader();w.writerows(annual)
    out=dict(schema="osixbay.genesis.eco.long06.v1",
        status="counterfactual_not_canonical",
        time_basis="12 abstract ticks per symbolic year; not a planet calendar",
        source="GPLE ECO-LONG-05 candidate branch",
        scenarios=[list(x) for x in SCENARIOS],
        runs=len(summaries),ticks_each=TICKS,annual_rows=len(annual),
        cases=summaries,limitations=[
            "Parameters uncalibrated and temporarily overridden only within test",
            "All scenarios use initial parent-paid seedbank and extra mineralization",
            "No original PR88 F01 physiology integration; three fixed proxy animals",
            "Cannot recolonize after local and global extinction without living parents/seeds",
            "No actual climate, mesh, Godot or production"])
    (folder/"summary.json").write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    print("AUDIT PASS",len(summaries),"cases",len(annual),"annual rows",flush=True)

if __name__=="__main__":main()
